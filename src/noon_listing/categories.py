from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CategoryMatch, SourceProduct


BASE_REQUIRED = [
    "brand",
    "model_number",
    "model_name",
    "color",
    "product_weight",
    "product_dimensions",
    "country_of_origin",
    "warranty",
]

STOP_CATEGORY_TERMS = {
    "black", "white", "blue", "red", "green", "pink", "grey", "gray", "gold", "silver",
    "and", "with", "for", "set", "sets", "accessories", "accessory", "replacement",
    "other", "general", "new", "old", "small", "large", "medium", "multi", "portable",
}

CHINESE_CATEGORY_HINTS = {
    "智能手表": "electronic_accessories-wearables-smartwatch",
    "手环": "electronic_accessories-wearables-fitness_tracker",
    "蓝牙耳机": "electronic_accessories-headphones-truewireless_headphones",
    "耳机": "electronic_accessories-headphones-wireless_headphones",
    "充电宝": "electronic_accessories-phone_accessories-power_banks",
    "移动电源": "electronic_accessories-phone_accessories-power_banks",
    "充电器": "electronic_accessories-phone_accessories-mobile_phone_wall_charger",
    "快充": "electronic_accessories-phone_accessories-mobile_phone_wall_charger",
    "数据线": "electronic_accessories-phone_accessories-cables_and_connectors",
    "转接头": "electronic_accessories-phone_accessories-headphone_adapter",
    "音箱": "electronic_accessories-speakers_accessories-portable_bluetooth_speakers",
    "风扇": "home_appliances-small_appliances-handheld_and_portable_fan",
    "制冷风扇": "home_appliances-small_appliances-handheld_and_portable_fan",
    "手持风扇": "home_appliances-small_appliances-handheld_and_portable_fan",
    "洁牙器": "hair_personal_care-personal_care-oral_hygiene_dental_floss_flossers",
    "冲牙器": "hair_personal_care-personal_care-oral_hygiene_dental_floss_flossers",
    "水牙线": "hair_personal_care-personal_care-oral_hygiene_dental_floss_flossers",
}

INTERNAL_TO_API_CATEGORY = {
    "mobile_charger": "electronic_accessories-phone_accessories-mobile_phone_wall_charger",
    "cable_adapter": "electronic_accessories-phone_accessories-cables_and_connectors",
    "power_bank": "electronic_accessories-phone_accessories-power_banks",
    "earbuds": "electronic_accessories-headphones-truewireless_headphones",
    "headphones": "electronic_accessories-headphones-wireless_headphones",
    "smart_watch": "electronic_accessories-wearables-smartwatch",
    "speaker": "electronic_accessories-speakers_accessories-portable_bluetooth_speakers",
    "fan": "home_appliances-small_appliances-handheld_and_portable_fan",
    "led_lighting": "home_decor-lighting-led_strips",
    "gaming_accessory": "video_games-accessories-gaming_controller",
    "soldering_tool": "home_improvement-power_tools-soldering_and_desoldering_equipment",
}


ELECTRONICS_CATEGORIES: dict[str, dict[str, Any]] = {
    "mobile_charger": {
        "code": "CH",
        "noon_path": "Electronics > Mobiles & Accessories > Chargers",
        "keywords": ["charger", "charging", "adapter", "fast charge", "usb charger", "pd", "gan", "充电器", "快充", "适配器"],
        "required": BASE_REQUIRED + ["input_voltage", "output_voltage", "wattage", "plug_type", "compatible_devices"],
        "optional": ["cable_included", "ports", "number_of_pieces"],
    },
    "cable_adapter": {
        "code": "CA",
        "noon_path": "Electronics > Mobiles & Accessories > Cables & Adapters",
        "keywords": ["cable", "adapter", "converter", "type-c", "usb-c", "lightning", "hdmi", "数据线", "转接头", "转换器"],
        "required": BASE_REQUIRED + ["connector_type", "cable_length", "compatible_devices"],
        "optional": ["wattage", "data_transfer_rate"],
    },
    "power_bank": {
        "code": "PB",
        "noon_path": "Electronics > Mobiles & Accessories > Power Banks",
        "keywords": ["power bank", "portable charger", "mAh", "mah", "充电宝", "移动电源"],
        "required": BASE_REQUIRED + ["capacity", "battery_type", "input_voltage", "output_voltage", "wattage"],
        "optional": ["ports", "fast_charging", "cable_included"],
        "manual_flags": ["battery"],
    },
    "earbuds": {
        "code": "EB",
        "noon_path": "Electronics > Audio > Earbuds",
        "keywords": ["earbud", "earbuds", "tws", "bluetooth earphone", "wireless earphone", "耳机", "蓝牙耳机"],
        "required": BASE_REQUIRED + ["connectivity", "battery_life", "bluetooth_version", "compatible_devices"],
        "optional": ["noise_cancellation", "water_resistance"],
        "manual_flags": ["battery", "wireless"],
    },
    "headphones": {
        "code": "HP",
        "noon_path": "Electronics > Audio > Headphones",
        "keywords": ["headphone", "headset", "gaming headset", "头戴耳机", "耳麦"],
        "required": BASE_REQUIRED + ["connectivity", "compatible_devices"],
        "optional": ["microphone", "noise_cancellation", "battery_life"],
        "manual_flags": ["battery", "wireless"],
    },
    "smart_watch": {
        "code": "SW",
        "noon_path": "Electronics > Wearable Technology > Smart Watches",
        "keywords": ["smart watch", "smartwatch", "fitness tracker", "wearable", "智能手表", "运动手环", "手环"],
        "required": BASE_REQUIRED + ["screen_size", "connectivity", "battery_life", "compatible_devices"],
        "optional": ["water_resistance", "sensor_type", "strap_material"],
        "manual_flags": ["battery", "wireless"],
    },
    "speaker": {
        "code": "SP",
        "noon_path": "Electronics > Audio > Speakers",
        "keywords": ["speaker", "bluetooth speaker", "soundbar", "音箱", "音响", "喇叭"],
        "required": BASE_REQUIRED + ["connectivity", "wattage", "battery_life"],
        "optional": ["water_resistance", "number_of_speakers"],
        "manual_flags": ["battery", "wireless"],
    },
    "fan": {
        "code": "FN",
        "noon_path": "Electronics > Home Appliances > Fans",
        "keywords": ["fan", "cooling fan", "desk fan", "portable fan", "制冷风扇", "风扇", "小风扇"],
        "required": BASE_REQUIRED + ["wattage", "power_source", "number_of_speeds"],
        "optional": ["battery_type", "battery_life", "noise_level"],
        "manual_flags": ["battery"],
    },
    "led_lighting": {
        "code": "LD",
        "noon_path": "Electronics > Lighting > LED Lighting",
        "keywords": ["led", "light", "lamp", "strip light", "夜灯", "台灯", "灯带", "照明"],
        "required": BASE_REQUIRED + ["wattage", "voltage", "power_source", "light_color"],
        "optional": ["remote_control", "dimmable", "length"],
    },
    "gaming_accessory": {
        "code": "GM",
        "noon_path": "Electronics > Video Games > Accessories",
        "keywords": ["gamepad", "controller", "gaming", "keyboard", "mouse", "手柄", "游戏", "键盘", "鼠标"],
        "required": BASE_REQUIRED + ["compatible_devices", "connectivity"],
        "optional": ["battery_type", "cable_length"],
        "manual_flags": ["battery", "wireless"],
    },
    "soldering_tool": {
        "code": "ST",
        "noon_path": "Home Improvement > Power Tools > Soldering & Desoldering Equipment",
        "keywords": [
            "soldering iron",
            "soldering",
            "desoldering",
            "solder",
            "welding",
            "electric soldering iron",
            "电烙铁",
            "烙铁",
            "焊接",
            "焊锡",
            "调温烙铁",
        ],
        "required": BASE_REQUIRED + ["wattage", "voltage", "plug_type", "material"],
        "optional": ["number_of_pieces", "power_source"],
    },
    "electronics_general": {
        "code": "EL",
        "noon_path": "Electronics > Electronics Accessories",
        "keywords": [],
        "required": BASE_REQUIRED,
        "optional": ["material", "number_of_pieces", "compatible_devices"],
    },
}


def load_downloaded_templates(template_dir: Path) -> dict[str, dict[str, Any]]:
    registry = {}
    if not template_dir.exists():
        return registry
    for path in template_dir.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            continue
        key = data.get("category_key") or path.stem
        registry[key] = data
    return registry


class ElectronicsClassifier:
    def __init__(self, template_dir: Path | None = None):
        self.categories = dict(ELECTRONICS_CATEGORIES)
        self.api_categories: list[str] = []
        if template_dir:
            for key, data in load_downloaded_templates(template_dir).items():
                self.categories.setdefault(key, {}).update(data)
            content_categories = template_dir / "content_api" / "categories_filtered.json"
            if content_categories.exists():
                try:
                    with open(content_categories, "r", encoding="utf-8") as handle:
                        self.api_categories = list(json.load(handle).get("categories") or [])
                except (OSError, json.JSONDecodeError):
                    self.api_categories = []

    def classify(self, product: SourceProduct) -> CategoryMatch:
        text = " ".join(
            [
                product.title_cn or "",
                product.description_cn or "",
                " ".join(str(v) for v in product.attributes.values()),
            ]
        ).lower()
        for hint, category_code in CHINESE_CATEGORY_HINTS.items():
            if hint in text and (not self.api_categories or category_code in self.api_categories):
                required_fields = self._api_required_fields(category_code) or BASE_REQUIRED
                return CategoryMatch(
                    category_key=category_code,
                    noon_path=category_code,
                    confidence=0.93,
                    matched_terms=[hint],
                    required_fields=required_fields,
                    optional_fields=[],
                )
        best_key = "electronics_general"
        best_score = 0
        best_terms: list[str] = []
        for key, meta in self.categories.items():
            terms = [term.lower() for term in meta.get("keywords", [])]
            matched = [term for term in terms if term and term in text]
            score = sum(max(1, len(term.split())) for term in matched)
            if score > best_score:
                best_key = key
                best_score = score
                best_terms = matched
        meta = self.categories[best_key]
        api_category = INTERNAL_TO_API_CATEGORY.get(best_key)
        if api_category and (not self.api_categories or api_category in self.api_categories):
            return CategoryMatch(
                category_key=api_category,
                noon_path=api_category,
                confidence=min(0.96, 0.55 + best_score * 0.08) if best_score else 0.84,
                matched_terms=best_terms,
                required_fields=self._api_required_fields(api_category) or list(meta.get("required", BASE_REQUIRED)),
                optional_fields=list(meta.get("optional", [])),
            )
        confidence = min(0.96, 0.55 + best_score * 0.08) if best_score else 0.42
        api_match = self._match_api_category(text)
        if api_match and api_match[1] >= max(best_score, 2):
            best_key = api_match[0]
            best_score = api_match[1]
            best_terms = api_match[2]
            required_fields = self._api_required_fields(best_key) or list(meta.get("required", BASE_REQUIRED))
            return CategoryMatch(
                category_key=best_key,
                noon_path=best_key,
                confidence=min(0.97, 0.58 + best_score * 0.08),
                matched_terms=best_terms,
                required_fields=required_fields,
                optional_fields=[],
            )

        return CategoryMatch(
            category_key=best_key,
            noon_path=meta.get("noon_path", "Electronics"),
            confidence=confidence,
            matched_terms=best_terms,
            required_fields=list(meta.get("required", BASE_REQUIRED)),
            optional_fields=list(meta.get("optional", [])),
        )

    def category_code(self, category_key: str) -> str:
        if "-" in category_key:
            return category_key.split("-", 1)[0][:2].upper()
        return self.categories.get(category_key, {}).get("code", "EL")

    def manual_flags(self, category_key: str) -> list[str]:
        return list(self.categories.get(category_key, {}).get("manual_flags", []))

    def _match_api_category(self, text: str) -> tuple[str, int, list[str]] | None:
        best: tuple[str, int, list[str]] | None = None
        normalized_text = text.replace("_", " ").replace("-", " ")
        for category_code in self.api_categories:
            parts = category_code.replace("_", " ").replace("-", " ").split()
            terms = [p for p in parts if len(p) >= 4 and not p.isdigit() and p not in STOP_CATEGORY_TERMS]
            matched = sorted({p for p in terms if p in normalized_text})
            score = len(matched)
            if score and (best is None or score > best[1]):
                best = (category_code, score, matched)
        return best

    def _api_required_fields(self, category_code: str) -> list[str]:
        attr_path = Path(__file__).resolve().parents[2] / "templates" / "content_api" / "attributes" / f"{category_code}.json"
        if not attr_path.exists():
            return []
        try:
            with open(attr_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []
        return [a.get("attribute_code") for a in data.get("attributes", []) if a.get("is_mandatory") and a.get("attribute_code")]
