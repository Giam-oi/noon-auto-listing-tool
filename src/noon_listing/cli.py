from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .config import load_config, project_root, workspace_root
from .content_submit import get_content_status, submit_run_payloads
from .io_utils import write_json
from .noon_api import NoonApiProbe, NoonContentClient
from .pipeline import ListingPipeline, sample_source
from .seller_lab import write_automation_plan
from .stock_adjustments import apply_stock_to_run


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Noon auto listing MVP tool")
    parser.add_argument("--config", help="Optional local config JSON path")
    sub = parser.add_subparsers(dest="command", required=True)

    sample = sub.add_parser("sample", help="Run a local sample product through the pipeline")
    sample.add_argument("--run-dir", help="Optional output run directory")

    url = sub.add_parser("build-url", help="Build listing files from one 1688 URL")
    url.add_argument("url")
    url.add_argument("--run-dir", help="Optional output run directory")

    html = sub.add_parser("build-html", help="Build listing files from a saved 1688 HTML file")
    html.add_argument("path")
    html.add_argument("--source-url", default="", help="Original 1688 product URL")
    html.add_argument("--run-dir", help="Optional output run directory")

    excel = sub.add_parser("build-excel", help="Build listing files from Excel")
    excel.add_argument("path")
    excel.add_argument("--max-rows", type=int, default=None)
    excel.add_argument("--run-dir", help="Optional output run directory")

    probe = sub.add_parser("probe-api", help="Probe Noon API credential signing and configured endpoints")
    probe.add_argument("--credentials", help="Path to api.json")
    probe.add_argument("--out", help="Optional JSON output path")

    cats = sub.add_parser("sync-content-categories", help="Download Noon Content API categories and optional attributes")
    cats.add_argument("--credentials", help="Path to api.json")
    cats.add_argument("--out-dir", default=str(project_root() / "templates" / "content_api"), help="Output directory")
    cats.add_argument("--filter", default="", help="Comma separated category-code keyword filter; omit for all categories")
    cats.add_argument("--attributes", action="store_true", help="Also download attributes for filtered categories")
    cats.add_argument("--limit", type=int, default=0, help="Limit number of attribute calls for testing")
    cats.add_argument("--refresh", action="store_true", help="Re-download attribute JSON even if it already exists")
    cats.add_argument("--workers", type=int, default=1, help="Concurrent attribute download workers")

    seller = sub.add_parser("seller-plan", help="Write Seller Lab automation plan")
    seller.add_argument("--out", help="Output JSON path")

    stock = sub.add_parser("apply-stock", help="Apply edited stock_adjustments.xlsx to an existing run exports")
    stock.add_argument("run_dir")
    stock.add_argument("stock_workbook")

    submit = sub.add_parser("submit-content", help="Build and optionally submit Noon Content API UpsertProduct payloads for a run")
    submit.add_argument("run_dir")
    submit.add_argument("--credentials", help="Path to api.json")
    submit.add_argument("--live", action="store_true", help="Actually call UpsertProduct. Omit for dry-run payload generation.")
    submit.add_argument("--force", action="store_true", help="Submit even when local validation found blocking issues")

    status = sub.add_parser("get-content", help="Call Noon Content API GetContent for a sku_parent")
    status.add_argument("sku_parent")
    status.add_argument("--credentials", help="Path to api.json")
    status.add_argument("--out", help="Optional JSON output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)

    if args.command == "probe-api":
        credentials = Path(args.credentials).resolve() if args.credentials else None
        result = NoonApiProbe(cfg).probe(credentials)
        if args.out:
            write_json(Path(args.out), result)
        _print_json(result)
        return 0

    if args.command == "sync-content-categories":
        credentials = Path(args.credentials).resolve() if args.credentials else None
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        client = NoonContentClient(cfg, credentials)
        categories = client.list_categories()
        filters = [v.strip().lower() for v in args.filter.split(",") if v.strip()]
        if filters:
            filtered = [c for c in categories if any(f in c.lower() for f in filters)]
        else:
            filtered = list(categories)
        write_json(out_dir / "categories_all.json", {"categories": categories, "count": len(categories)})
        write_json(out_dir / "categories_filtered.json", {"categories": filtered, "count": len(filtered), "filters": filters})
        attr_count = 0
        if args.attributes:
            attr_dir = out_dir / "attributes"
            attr_dir.mkdir(parents=True, exist_ok=True)
            pending = []
            for category_code in filtered:
                safe = category_code.replace("/", "_").replace("\\", "_")
                attr_path = attr_dir / f"{safe}.json"
                if attr_path.exists() and not args.refresh:
                    continue
                pending.append((category_code, attr_path))
                if args.limit and len(pending) >= args.limit:
                    break

            if int(args.workers) <= 1:
                for category_code, attr_path in pending:
                    data = client.list_category_attributes(category_code)
                    write_json(attr_path, data)
                    attr_count += 1
                    if attr_count % 100 == 0:
                        print(f"downloaded_attributes={attr_count}")
            else:
                def fetch_one(item):
                    category_code, attr_path = item
                    local_client = NoonContentClient(cfg, credentials)
                    data = local_client.list_category_attributes(category_code)
                    write_json(attr_path, data)
                    return category_code

                with ThreadPoolExecutor(max_workers=int(args.workers)) as pool:
                    futures = [pool.submit(fetch_one, item) for item in pending]
                    for future in as_completed(futures):
                        future.result()
                        attr_count += 1
                        if attr_count % 100 == 0:
                            print(f"downloaded_attributes={attr_count}")
        _print_json({"out_dir": str(out_dir), "all_count": len(categories), "filtered_count": len(filtered), "attributes_downloaded": attr_count})
        return 0

    if args.command == "seller-plan":
        out = Path(args.out) if args.out else project_root() / "runs" / "seller_lab_plan.json"
        result = write_automation_plan(out, cfg)
        _print_json({"path": str(out), "plan": result})
        return 0

    if args.command == "apply-stock":
        result = apply_stock_to_run(Path(args.run_dir), Path(args.stock_workbook))
        _print_json(result)
        return 0

    if args.command == "submit-content":
        credentials = Path(args.credentials).resolve() if args.credentials else None
        result = submit_run_payloads(Path(args.run_dir), cfg, credentials, live=args.live, force=args.force)
        _print_json(result)
        return 0

    if args.command == "get-content":
        credentials = Path(args.credentials).resolve() if args.credentials else None
        out = Path(args.out) if args.out else None
        result = get_content_status(cfg, args.sku_parent, credentials, out)
        _print_json(result)
        return 0

    run_dir = Path(getattr(args, "run_dir", "")).resolve() if getattr(args, "run_dir", None) else None
    pipeline = ListingPipeline(cfg, run_dir)

    if args.command == "sample":
        summary = pipeline.build_from_sources([sample_source(workspace_root())])
        _print_json(summary)
        return 0

    if args.command == "build-url":
        summary = pipeline.build_from_1688_url(args.url)
        _print_json(summary)
        return 0

    if args.command == "build-html":
        summary = pipeline.build_from_1688_html(Path(args.path), source_url=args.source_url)
        _print_json(summary)
        return 0

    if args.command == "build-excel":
        summary = pipeline.build_from_excel(Path(args.path), max_rows=args.max_rows)
        _print_json(summary)
        return 0

    return 1
