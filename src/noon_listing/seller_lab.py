from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def automation_plan(cfg: dict[str, Any]) -> dict[str, Any]:
    noon_cfg = cfg.get("noon", {})
    template_dir = Path(noon_cfg.get("template_dir", "templates"))
    if not template_dir.is_absolute():
        template_dir = Path(__file__).resolve().parents[2] / template_dir
    return {
        "seller_lab_url": noon_cfg.get("seller_lab_url", "https://catalog.noon.partners"),
        "template_dir": str(template_dir),
        "steps": [
            "Open Seller Lab with a persistent logged-in browser profile.",
            "Navigate to product creation / bulk creation.",
            "Download each Electronics category template for UAE and KSA.",
            "Save templates as noon_uae_electronics_template.xlsx and noon_ksa_electronics_template.xlsx, or category-specific JSON templates.",
            "Upload generated Noon bulk files.",
            "Download upload error reports and feed them back into validation.",
        ],
        "manual_login_required_until_profile_exists": True,
        "playwright_available_required_for_full_automation": True,
    }


def write_automation_plan(path: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    data = automation_plan(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    return data
