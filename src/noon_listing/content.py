from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from .models import CategoryMatch, ListingContent, SourceProduct


def _extract_capacity(text: str) -> str:
    match = re.search(r"(\d{3,6})\s*(mah|mAh|MAH)", text)
    return match.group(0) if match else ""


def _extract_wattage(text: str) -> str:
    match = re.search(r"(\d{1,4})\s*w\b", text, flags=re.IGNORECASE)
    return match.group(0).upper() if match else ""


def _clean_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value[:180]


class RuleContentGenerator:
    def generate(self, product: SourceProduct, category: CategoryMatch) -> ListingContent:
        source_title = product.title_cn or "Electronic Accessory"
        capacity = _extract_capacity(source_title + " " + product.description_cn)
        wattage = _extract_wattage(source_title + " " + product.description_cn)
        feature_bits = [term for term in [capacity, wattage] if term]
        simple_name = source_title
        title_en = _clean_title(" ".join([simple_name, *feature_bits, "for UAE KSA"]))
        bullets = [
            "Designed for everyday use with a practical and portable build.",
            "Suitable for home, office, travel, and daily electronic accessory needs.",
            "Made for easy setup, simple operation, and stable performance.",
            "Packed for online retail handling with clear SKU tracking.",
        ]
        if capacity:
            bullets.insert(0, f"Capacity/specification reference: {capacity}.")
        if wattage:
            bullets.insert(0, f"Power/specification reference: {wattage}.")
        attrs = dict(product.attributes)
        attrs.update({
            "brand": product.attributes.get("brand", "Generic"),
            "model_number": product.attributes.get("model_number", product.attributes.get("model", "")),
            "model_name": product.attributes.get("model_name", simple_name[:60]),
            "color": product.attributes.get("color", ""),
            "country_of_origin": product.attributes.get("country_of_origin", "China"),
            "warranty": product.attributes.get("warranty", "No Warranty"),
        })
        if capacity:
            attrs["capacity"] = capacity
        if wattage:
            attrs["wattage"] = wattage
        return ListingContent(
            title_en=title_en,
            title_ar="",
            bullets_en=bullets[:5],
            bullets_ar=[],
            description_en=" ".join(bullets[:4]),
            description_ar="",
            search_keywords=[category.category_key.replace("_", " "), "electronics accessory"],
            attributes=attrs,
            content_score=0.58,
            generator="rule",
        )


class OpenAICompatibleGenerator:
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.fallback = RuleContentGenerator()

    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled")) and bool(os.environ.get(self.cfg.get("api_key_env", "OPENAI_API_KEY")))

    def generate(self, product: SourceProduct, category: CategoryMatch) -> ListingContent:
        if not self.enabled():
            return self.fallback.generate(product, category)
        prompt = self._build_prompt(product, category)
        try:
            payload = self._request(prompt)
            return self._parse(payload, product, category)
        except Exception as exc:
            content = self.fallback.generate(product, category)
            content.generator = f"rule_after_ai_error:{type(exc).__name__}"
            return content

    def _build_prompt(self, product: SourceProduct, category: CategoryMatch) -> str:
        return json.dumps(
            {
                "task": "Create Noon marketplace ZSKU listing content for UAE and KSA electronics.",
                "rules": [
                    "Return strict JSON only.",
                    "Do not invent technical values. If a value is missing, leave it empty.",
                    "Avoid brand claims unless source explicitly contains the brand.",
                    "Create English and Arabic titles, bullets, and descriptions.",
                    "Keep title concise and marketplace friendly.",
                ],
                "output_schema": {
                    "title_en": "string",
                    "title_ar": "string",
                    "bullets_en": ["string"],
                    "bullets_ar": ["string"],
                    "description_en": "string",
                    "description_ar": "string",
                    "search_keywords": ["string"],
                    "attributes": {},
                    "content_score": "float between 0 and 1",
                },
                "category": category.to_dict(),
                "product": product.to_dict(),
            },
            ensure_ascii=False,
        )

    def _request(self, prompt: str) -> dict[str, Any]:
        base_url = str(self.cfg.get("base_url", "https://api.openai.com/v1")).rstrip("/")
        url = f"{base_url}/chat/completions"
        api_key = os.environ[self.cfg.get("api_key_env", "OPENAI_API_KEY")]
        body = {
            "model": self.cfg.get("model", "gpt-4.1-mini"),
            "messages": [
                {"role": "system", "content": "You are an ecommerce listing data generator. Output JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=int(self.cfg.get("timeout_seconds", 90))) as response:
            return json.loads(response.read().decode("utf-8"))

    def _parse(self, payload: dict[str, Any], product: SourceProduct, category: CategoryMatch) -> ListingContent:
        text = payload["choices"][0]["message"]["content"]
        data = json.loads(text)
        fallback = self.fallback.generate(product, category)
        return ListingContent(
            title_en=data.get("title_en") or fallback.title_en,
            title_ar=data.get("title_ar") or "",
            bullets_en=list(data.get("bullets_en") or fallback.bullets_en)[:5],
            bullets_ar=list(data.get("bullets_ar") or [])[:5],
            description_en=data.get("description_en") or fallback.description_en,
            description_ar=data.get("description_ar") or "",
            search_keywords=list(data.get("search_keywords") or fallback.search_keywords)[:20],
            attributes=dict(fallback.attributes | dict(data.get("attributes") or {})),
            content_score=float(data.get("content_score") or 0.75),
            generator="ai",
        )
