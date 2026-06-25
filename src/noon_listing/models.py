from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SourceProduct:
    source: str
    source_url: str = ""
    supplier_name: str = ""
    title_cn: str = ""
    description_cn: str = ""
    price_cny: float | None = None
    moq: int | None = None
    variations: list[dict[str, Any]] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    image_urls: list[str] = field(default_factory=list)
    local_images: list[str] = field(default_factory=list)
    raw_path: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CategoryMatch:
    category_key: str
    noon_path: str
    confidence: float
    matched_terms: list[str] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ListingContent:
    title_en: str = ""
    title_ar: str = ""
    bullets_en: list[str] = field(default_factory=list)
    bullets_ar: list[str] = field(default_factory=list)
    description_en: str = ""
    description_ar: str = ""
    search_keywords: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    content_score: float = 0.0
    generator: str = "rule"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PriceResult:
    marketplace: str
    currency: str
    cost_cny: float
    list_price: float
    landed_cost_local: float
    estimated_fee_local: float
    estimated_vat_local: float
    estimated_profit_local: float
    margin_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    field: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductDraft:
    sku: str
    parent_sku: str
    source_product: SourceProduct
    category: CategoryMatch
    listing: ListingContent
    prices: dict[str, PriceResult] = field(default_factory=dict)
    stock: dict[str, int] = field(default_factory=dict)
    images: list[str] = field(default_factory=list)
    image_roles: dict[str, str] = field(default_factory=dict)
    validation_issues: list[ValidationIssue] = field(default_factory=list)
    submit_ready: bool = False
    submit_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


def ensure_path(value: str | Path) -> Path:
    return value if isinstance(value, Path) else Path(value)
