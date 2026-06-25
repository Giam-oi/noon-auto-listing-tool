from __future__ import annotations

from pathlib import Path
from typing import Any

from .categories import ElectronicsClassifier
from .collectors import Ali1688Collector
from .config import runs_root
from .content import OpenAICompatibleGenerator
from .content_submit import build_payloads_for_run
from .excel_input import read_products_from_excel
from .exporters import export_all
from .images import prepare_image_suite
from .image_publish import publish_images_if_configured
from .io_utils import make_run_dir, write_json
from .models import ProductDraft, SourceProduct
from .normalizer import enrich_source_product
from .pricing import calculate_price
from .seller_lab import write_automation_plan
from .sku import make_sku
from .validation import validate_draft


class ListingPipeline:
    def __init__(self, cfg: dict[str, Any], run_dir: Path | None = None):
        self.cfg = cfg
        self.run_dir = run_dir or make_run_dir(runs_root(), "listing")
        template_dir = Path(cfg.get("noon", {}).get("template_dir", "templates"))
        if not template_dir.is_absolute():
            template_dir = Path(__file__).resolve().parents[2] / template_dir
        self.classifier = ElectronicsClassifier(template_dir)
        self.generator = OpenAICompatibleGenerator(cfg.get("ai", {}))

    def collect_1688(self, url: str) -> SourceProduct:
        collector = Ali1688Collector(self.cfg.get("collector", {}))
        return collector.collect(url, self.run_dir / "collection")

    def collect_1688_html(self, html_path: Path, source_url: str = "") -> SourceProduct:
        collector = Ali1688Collector(self.cfg.get("collector", {}))
        return collector.collect_html(html_path, source_url, self.run_dir / "collection")

    def build_from_1688_url(self, url: str) -> dict[str, Any]:
        product = self.collect_1688(url)
        return self.build_from_sources([product])

    def build_from_1688_html(self, html_path: Path, source_url: str = "") -> dict[str, Any]:
        product = self.collect_1688_html(html_path, source_url)
        return self.build_from_sources([product])

    def build_from_excel(self, path: Path, max_rows: int | None = None) -> dict[str, Any]:
        products = read_products_from_excel(path, max_rows=max_rows)
        return self.build_from_sources(products)

    def build_from_sources(self, products: list[SourceProduct]) -> dict[str, Any]:
        drafts: list[ProductDraft] = []
        sku_cfg = self.cfg.get("sku", {})
        sequence = int(sku_cfg.get("sequence_start", 1))
        for product in products:
            enrich_source_product(product)
            category = self.classifier.classify(product)
            category_code = self.classifier.category_code(category.category_key)
            sku = make_sku(sku_cfg.get("prefix", "NW"), category_code, sequence, 1)
            parent_sku = sku.rsplit("V", 1)[0]
            sequence += 1
            listing = self.generator.generate(product, category)
            draft = ProductDraft(
                sku=sku,
                parent_sku=parent_sku,
                source_product=product,
                category=category,
                listing=listing,
            )
            self._apply_prices_and_stock(draft)
            image_dir = self.run_dir / "images" / draft.sku
            prepare_image_suite(draft, image_dir, self.cfg.get("images", {}))
            publish_images_if_configured(draft, self.cfg.get("images", {}))
            validate_draft(draft, self.cfg, self.classifier)
            drafts.append(draft)

        standard = [draft.to_dict() for draft in drafts]
        write_json(self.run_dir / "standard_products.json", standard)
        write_json(
            self.run_dir / "validation_report.json",
            {
                "total": len(drafts),
                "submit_ready": sum(1 for draft in drafts if draft.submit_ready),
                "drafts": [
                    {
                        "sku": draft.sku,
                        "category": draft.category.to_dict(),
                        "submit_ready": draft.submit_ready,
                        "submit_score": draft.submit_score,
                        "issues": [issue.to_dict() for issue in draft.validation_issues],
                    }
                    for draft in drafts
                ],
            },
        )
        exports = export_all(drafts, self.run_dir / "exports", self.cfg)
        content_api = build_payloads_for_run(self.run_dir, self.cfg)
        seller_plan = write_automation_plan(self.run_dir / "seller_lab_plan.json", self.cfg)
        summary = {
            "run_dir": str(self.run_dir),
            "total_products": len(drafts),
            "submit_ready": sum(1 for draft in drafts if draft.submit_ready),
            "exports": exports,
            "content_api": {
                "payload_dir": content_api["payload_dir"],
                "submit_blocked": content_api["submit_blocked"],
            },
            "seller_lab_plan": seller_plan,
        }
        write_json(self.run_dir / "summary.json", summary)
        return summary

    def _apply_prices_and_stock(self, draft: ProductDraft) -> None:
        cost = draft.source_product.price_cny or 0.0
        for market, market_cfg in self.cfg.get("marketplaces", {}).items():
            draft.prices[market] = calculate_price(cost, market, market_cfg)
            draft.stock[market] = int(market_cfg.get("default_stock", 1000))


def sample_source(workspace: Path) -> SourceProduct:
    product = SourceProduct(
        source="sample",
        source_url="",
        title_cn="Smart watch black fitness tracker bluetooth call",
        description_cn="1.8 inch smart watch, bluetooth call, sports modes, long battery life",
        price_cny=22.3,
        attributes={
            "color": "Black",
            "model_number": "SW-SAMPLE",
            "screen_size": "1.8 inch",
            "connectivity": "Bluetooth",
            "battery_life": "",
        },
    )
    for path in (workspace / "lovart_Auto" / "output").rglob("image_1.*"):
        if path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            product.local_images.append(str(path))
            break
    return product
