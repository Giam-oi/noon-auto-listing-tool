from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import project_root
from .content_payload import build_upsert_payload_from_draft_dict
from .io_utils import write_json
from .noon_api import NoonContentClient


def template_root_from_config(cfg: dict[str, Any]) -> Path:
    template_dir = Path(cfg.get("noon", {}).get("template_dir", "templates"))
    if not template_dir.is_absolute():
        template_dir = project_root() / template_dir
    return template_dir


def load_run_drafts(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "standard_products.json"
    with open(path, "r", encoding="utf-8") as handle:
        return list(json.load(handle))


def build_payloads_for_run(run_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    template_root = template_root_from_config(cfg)
    payload_dir = run_dir / "content_api_payloads"
    payload_dir.mkdir(parents=True, exist_ok=True)
    drafts = load_run_drafts(run_dir)
    report_items = []
    for draft in drafts:
        payload, issues = build_upsert_payload_from_draft_dict(draft, template_root)
        sku = payload.get("skus", [{}])[0].get("partner_sku") or draft.get("sku") or f"draft_{len(report_items)+1}"
        payload_path = payload_dir / f"{sku}.json"
        write_json(payload_path, payload)
        report_items.append(
            {
                "sku": sku,
                "category": payload.get("category"),
                "payload_path": str(payload_path),
                "issue_count": len(issues),
                "error_count": sum(1 for issue in issues if issue.get("severity") == "error"),
                "issues": issues,
            }
        )
    report = {
        "run_dir": str(run_dir),
        "payload_dir": str(payload_dir),
        "total": len(report_items),
        "submit_blocked": sum(1 for item in report_items if item["error_count"] > 0),
        "items": report_items,
    }
    write_json(run_dir / "content_api_payloads_report.json", report)
    return report


def submit_run_payloads(
    run_dir: Path,
    cfg: dict[str, Any],
    credentials_path: Path | None = None,
    live: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    report = build_payloads_for_run(run_dir, cfg)
    submit_report: dict[str, Any] = {
        "run_dir": str(run_dir),
        "live": live,
        "force": force,
        "results": [],
    }
    client = NoonContentClient(cfg, credentials_path) if live else None
    for item in report["items"]:
        payload_path = Path(item["payload_path"])
        with open(payload_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        blocked = item["error_count"] > 0
        if blocked and not force:
            submit_report["results"].append(
                {
                    "sku": item["sku"],
                    "submitted": False,
                    "blocked": True,
                    "payload_path": str(payload_path),
                    "issues": item["issues"],
                }
            )
            continue
        if not live:
            submit_report["results"].append(
                {
                    "sku": item["sku"],
                    "submitted": False,
                    "dry_run": True,
                    "payload_path": str(payload_path),
                    "issues": item["issues"],
                }
            )
            continue
        try:
            assert client is not None
            response = client.upsert_product(payload)
            submit_report["results"].append(
                {
                    "sku": item["sku"],
                    "submitted": True,
                    "payload_path": str(payload_path),
                    "response": response,
                }
            )
        except Exception as exc:
            submit_report["results"].append(
                {
                    "sku": item["sku"],
                    "submitted": False,
                    "payload_path": str(payload_path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    write_json(run_dir / "content_api_submit_report.json", submit_report)
    return submit_report


def get_content_status(cfg: dict[str, Any], sku_parent: str, credentials_path: Path | None = None, out: Path | None = None) -> dict[str, Any]:
    client = NoonContentClient(cfg, credentials_path)
    result = client.get_content(sku_parent)
    if out:
        write_json(out, result)
    return result
