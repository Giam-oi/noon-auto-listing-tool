from __future__ import annotations

from typing import Any

from .categories import ElectronicsClassifier
from .models import ProductDraft, ValidationIssue


def validate_draft(draft: ProductDraft, cfg: dict[str, Any], classifier: ElectronicsClassifier) -> ProductDraft:
    issues: list[ValidationIssue] = []
    product = draft.source_product
    listing = draft.listing
    validation_cfg = cfg.get("validation", {})
    blocked_terms = [term.lower() for term in validation_cfg.get("blocked_terms", [])]
    text_blob = " ".join(
        [
            product.title_cn or "",
            product.description_cn or "",
            listing.title_en or "",
            listing.description_en or "",
            " ".join(listing.bullets_en),
        ]
    ).lower()

    for term in blocked_terms:
        if term and term in text_blob:
            issues.append(ValidationIssue("error", "blocked_term", f"Blocked or risky term found: {term}", "content"))

    if not listing.title_en:
        issues.append(ValidationIssue("error", "missing_title_en", "English title is missing.", "title_en"))
    if not listing.title_ar:
        issues.append(ValidationIssue("warning", "missing_title_ar", "Arabic title is missing; enable AI or fill manually.", "title_ar"))
    if len(listing.bullets_en) < 3:
        issues.append(ValidationIssue("warning", "few_bullets", "Less than 3 English bullets.", "bullets_en"))
    if not product.local_images and not product.image_urls:
        issues.append(ValidationIssue("error", "missing_images", "No images found.", "images"))
    if product.price_cny is None:
        issues.append(ValidationIssue("error", "missing_cost", "CNY cost price is missing.", "price_cny"))

    required = set(draft.category.required_fields)
    attrs = {k: v for k, v in listing.attributes.items() if v not in ("", None, [])}
    content_backed_fields = {
        "product_title": bool(listing.title_en or listing.title_ar),
        "long_description": bool(listing.description_en or listing.description_ar),
        "feature_bullet": bool(listing.bullets_en or listing.bullets_ar),
    }
    for field in sorted(required):
        if content_backed_fields.get(field):
            continue
        if field not in attrs:
            issues.append(ValidationIssue("warning", "missing_required_attribute", f"Required category attribute may be missing: {field}", field))

    flags = classifier.manual_flags(draft.category.category_key)
    if validation_cfg.get("require_manual_for_battery", True) and "battery" in flags:
        issues.append(ValidationIssue("warning", "battery_manual_check", "Battery-related electronics should be checked before auto-submit.", "category"))
    if validation_cfg.get("require_manual_for_wireless", True) and "wireless" in flags:
        issues.append(ValidationIssue("warning", "wireless_manual_check", "Wireless products may require certification or extra review.", "category"))

    for market, price in draft.prices.items():
        min_margin = float(cfg.get("marketplaces", {}).get(market, {}).get("minimum_margin_rate", 0.0))
        if price.margin_rate < min_margin:
            issues.append(ValidationIssue("error", "low_margin", f"{market} margin {price.margin_rate:.1%} is below minimum {min_margin:.1%}.", "price"))

    draft.validation_issues = issues
    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    score = 1.0
    score -= error_count * 0.25
    score -= warning_count * 0.04
    score += min(0.1, max(0.0, draft.category.confidence - 0.5) * 0.1)
    score += min(0.1, max(0.0, listing.content_score - 0.5) * 0.15)
    draft.submit_score = max(0.0, min(1.0, score))
    draft.submit_ready = error_count == 0 and draft.submit_score >= float(validation_cfg.get("auto_submit_min_score", 0.86))
    return draft
