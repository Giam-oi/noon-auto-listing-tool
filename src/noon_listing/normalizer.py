from __future__ import annotations

import re

from .models import SourceProduct


COLOR_MAP = {
    "黑": "Black",
    "黑色": "Black",
    "曜石黑": "Black",
    "白": "White",
    "白色": "White",
    "流光白": "White",
    "蓝": "Blue",
    "蓝色": "Blue",
    "红": "Red",
    "红色": "Red",
    "绿": "Green",
    "绿色": "Green",
    "粉": "Pink",
    "粉色": "Pink",
    "灰": "Grey",
    "灰色": "Grey",
    "银": "Silver",
    "银色": "Silver",
    "金": "Gold",
    "金色": "Gold",
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
}


def enrich_source_product(product: SourceProduct) -> SourceProduct:
    text = " ".join([product.title_cn or "", product.description_cn or ""]).lower()
    if not product.attributes.get("color"):
        for raw, normalized in COLOR_MAP.items():
            if raw.lower() in text:
                product.attributes["color"] = normalized
                break
    if not product.attributes.get("model_number"):
        sku = product.attributes.get("source_sku")
        if sku:
            product.attributes["model_number"] = sku
    if not product.attributes.get("product_weight"):
        match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g)\b", text, re.I)
        if match:
            product.attributes["product_weight"] = match.group(0)
    if not product.attributes.get("product_dimensions"):
        match = re.search(r"(\d+(?:\.\d+)?\s*[x*]\s*\d+(?:\.\d+)?(?:\s*[x*]\s*\d+(?:\.\d+)?)?\s*(?:cm|mm))", text, re.I)
        if match:
            product.attributes["product_dimensions"] = match.group(1)
    return product
