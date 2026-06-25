from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


LANG_EN = "LANGUAGE_EN"
LANG_AR = "LANGUAGE_AR"


ATTRIBUTE_ALIASES = {
    "color": ["colour_name", "colour_family"],
    "colour": ["colour_name", "colour_family"],
    "product_dimensions": ["product_length", "product_width_depth", "product_height"],
    "dimensions": ["product_length", "product_width_depth", "product_height"],
    "weight": ["product_weight"],
    "capacity": ["battery_size", "capacity"],
    "connectivity": ["connection_type"],
    "material": ["material"],
    "country_of_origin": ["country_of_origin"],
    "model_number": ["model_number", "mpn"],
    "model_name": ["model_name"],
    "warranty": ["warranty"],
}


SELECT_NORMALIZATION = {
    "black": "Black",
    "white": "White",
    "blue": "Blue",
    "red": "Red",
    "green": "Green",
    "pink": "Pink",
    "grey": "Grey",
    "gray": "Grey",
    "silver": "Silver",
    "gold": "Gold",
    "china": "China",
    "bluetooth": "Bluetooth",
    "usb": "USB",
}


def load_attribute_metadata(template_root: Path, category_code: str) -> dict[str, dict[str, Any]]:
    path = template_root / "content_api" / "attributes" / f"{category_code}.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {item.get("attribute_code"): item for item in data.get("attributes", []) if item.get("attribute_code")}


def build_upsert_payload_from_draft_dict(draft: dict[str, Any], template_root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    category_code = draft.get("category", {}).get("category_key") or draft.get("category", {}).get("noon_path")
    valid_categories = _load_valid_categories(template_root)
    attr_meta = load_attribute_metadata(template_root, category_code)
    source = draft.get("source_product", {})
    listing = draft.get("listing", {})
    listing_attrs = dict(listing.get("attributes") or {})
    brand = _clean_scalar(listing_attrs.get("brand") or "Generic")
    sku = draft.get("sku") or listing_attrs.get("source_sku")

    payload: dict[str, Any] = {
        "skus": [{"partner_sku": sku}],
        "brand": brand,
        "category": category_code,
        "images": _build_images(source, draft, issues),
        "attributes": {},
    }

    _set_localized(payload["attributes"], "product_title", listing.get("title_en"), listing.get("title_ar"), attr_meta)
    _set_localized(payload["attributes"], "long_description", listing.get("description_en"), listing.get("description_ar"), attr_meta)
    _set_multivalue_localized(payload["attributes"], "feature_bullet", listing.get("bullets_en") or [], listing.get("bullets_ar") or [], attr_meta)
    _set_localized(payload["attributes"], "whats_in_the_box", "1 x product", "", attr_meta)

    _map_listing_attributes(payload["attributes"], listing_attrs, attr_meta, issues)
    _set_market_defaults(payload["attributes"], draft, attr_meta)

    for code, meta in attr_meta.items():
        if meta.get("is_mandatory") and code not in payload["attributes"]:
            issues.append({"severity": "warning", "code": "missing_api_mandatory_attribute", "field": code, "message": f"Missing mandatory API attribute: {code}"})

    if not payload["images"]:
        issues.append({"severity": "error", "code": "missing_public_image_urls", "field": "images", "message": "Content API requires public image URLs. Local generated image paths cannot be submitted directly."})
    if not category_code:
        issues.append({"severity": "error", "code": "missing_category", "field": "category", "message": "No Noon category code found."})
    elif valid_categories and category_code not in valid_categories:
        issues.append({"severity": "error", "code": "invalid_or_unsynced_category", "field": "category", "message": f"Category '{category_code}' is not in synced Noon category list."})
    if not sku:
        issues.append({"severity": "error", "code": "missing_partner_sku", "field": "skus", "message": "No partner SKU found."})

    return payload, issues


def _build_images(source: dict[str, Any], draft: dict[str, Any], issues: list[dict[str, str]]) -> list[dict[str, Any]]:
    urls = []
    for value in source.get("image_urls") or []:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            urls.append(value)
    for value in draft.get("images") or []:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            urls.append(value)
    result = []
    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        result.append({"url": url, "sort": len(result) + 1})
        if len(result) >= 12:
            break
    if draft.get("images") and not result:
        issues.append({"severity": "warning", "code": "local_images_not_submittable", "field": "images", "message": "Generated images are local files. Upload them to public hosting before live API submit."})
    return result


def _load_valid_categories(template_root: Path) -> set[str]:
    path = template_root / "content_api" / "categories_all.json"
    if not path.exists():
        path = template_root / "content_api" / "categories_filtered.json"
    if not path.exists():
        return set()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return set(json.load(handle).get("categories") or [])
    except (OSError, json.JSONDecodeError):
        return set()


def _set_localized(attributes: dict[str, Any], code: str, en: Any, ar: Any, attr_meta: dict[str, dict[str, Any]]) -> None:
    meta = attr_meta.get(code)
    if attr_meta and not meta:
        return
    values = []
    if en not in (None, ""):
        values.append({"value": str(en), "language": LANG_EN})
    if ar not in (None, ""):
        values.append({"value": str(ar), "language": LANG_AR})
    if values:
        attributes[code] = {"values": values}


def _set_multivalue_localized(attributes: dict[str, Any], code: str, en_values: list[Any], ar_values: list[Any], attr_meta: dict[str, dict[str, Any]]) -> None:
    meta = attr_meta.get(code)
    if attr_meta and not meta:
        return
    values = []
    for idx, value in enumerate([v for v in en_values if v], start=1):
        values.append({"value": str(value), "language": LANG_EN, "sort": idx})
    for idx, value in enumerate([v for v in ar_values if v], start=1):
        values.append({"value": str(value), "language": LANG_AR, "sort": idx})
    if values:
        attributes[code] = {"values": values}


def _map_listing_attributes(attributes: dict[str, Any], listing_attrs: dict[str, Any], attr_meta: dict[str, dict[str, Any]], issues: list[dict[str, str]]) -> None:
    for source_key, value in listing_attrs.items():
        if value in (None, "", []):
            continue
        candidate_codes = [source_key] + ATTRIBUTE_ALIASES.get(source_key, [])
        for code in candidate_codes:
            if code not in attr_meta or code in attributes:
                continue
            attr_value = _coerce_attribute_value(code, value, attr_meta[code], issues)
            if attr_value is None:
                continue
            value_entry = {"value": attr_value}
            if attr_meta[code].get("is_localizable"):
                value_entry["language"] = LANG_EN
            attributes[code] = {"values": [value_entry]}
            unit = _metric_unit_for_value(value, attr_meta[code])
            if unit and f"{code}_unit" not in attributes:
                attributes[f"{code}_unit"] = {"values": [{"value": unit}]}
            break


def _set_market_defaults(attributes: dict[str, Any], draft: dict[str, Any], attr_meta: dict[str, dict[str, Any]]) -> None:
    prices = draft.get("prices") or {}
    if "msrp_ae" in attr_meta and "UAE" in prices:
        attributes.setdefault("msrp_ae", {"values": [{"value": prices["UAE"].get("list_price")}]})
    if "msrp_sa" in attr_meta and "KSA" in prices:
        attributes.setdefault("msrp_sa", {"values": [{"value": prices["KSA"].get("list_price")}]})
    if "vat_rate_ae" in attr_meta:
        _set_select(attributes, "vat_rate_ae", "Std", attr_meta)
    if "vat_rate_sa" in attr_meta:
        _set_select(attributes, "vat_rate_sa", "Std", attr_meta)
    if "item_condition" in attr_meta:
        _set_select(attributes, "item_condition", "New", attr_meta)


def _set_select(attributes: dict[str, Any], code: str, value: str, attr_meta: dict[str, dict[str, Any]]) -> None:
    meta = attr_meta.get(code)
    if not meta:
        return
    options = meta.get("attribute_options") or []
    selected = _match_select(value, options)
    if selected:
        value_entry = {"value": selected}
        if meta.get("is_localizable"):
            value_entry["language"] = LANG_EN
        attributes.setdefault(code, {"values": [value_entry]})


def _coerce_attribute_value(code: str, value: Any, meta: dict[str, Any], issues: list[dict[str, str]]) -> Any:
    attr_type = meta.get("attribute_type")
    if attr_type == "ATTRIBUTE_TYPE_NUMERIC":
        return _parse_number(value)
    if attr_type == "ATTRIBUTE_TYPE_METRIC":
        return _parse_number(value)
    if attr_type == "ATTRIBUTE_TYPE_BOOL":
        if isinstance(value, bool):
            return value
        lowered = str(value).strip().lower()
        if lowered in ("true", "yes", "1", "是"):
            return True
        if lowered in ("false", "no", "0", "否"):
            return False
        return None
    if attr_type == "ATTRIBUTE_TYPE_SELECT":
        selected = _match_select(value, meta.get("attribute_options") or [])
        if selected is None:
            issues.append({"severity": "warning", "code": "select_option_not_matched", "field": code, "message": f"Value '{value}' does not match allowed options for {code}."})
        return selected
    return _clean_scalar(value)


def _match_select(value: Any, options: list[Any]) -> Any:
    raw = str(value).strip()
    normalized = SELECT_NORMALIZATION.get(raw.lower(), raw)
    for option in options:
        if str(option) == normalized:
            return option
    for option in options:
        if str(option).lower() == normalized.lower():
            return option
    return None


def _metric_unit_for_value(value: Any, meta: dict[str, Any]) -> str | None:
    units = list(meta.get("attribute_metric_units") or [])
    if not units:
        return None
    text = str(value).lower()
    preferred = None
    if re.search(r"\bkw\b|kilowatt", text):
        preferred = "kilowatt"
    elif re.search(r"\bmw\b|milliwatt", text):
        preferred = "milliwatt"
    elif re.search(r"\bw\b|watt", text):
        preferred = "watt"
    elif "kg" in text:
        preferred = "kilogram"
    elif re.search(r"\bg\b|gram", text):
        preferred = "gram"
    elif "cm" in text:
        preferred = "centimeter"
    elif "mm" in text:
        preferred = "millimeter"
    if preferred:
        for unit in units:
            if str(unit).lower() == preferred:
                return str(unit)
    return str(units[0])


def _parse_number(value: Any) -> float | int | None:
    if isinstance(value, (int, float)):
        return value
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    number = float(match.group(0))
    return int(number) if number.is_integer() else number


def _clean_scalar(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()
