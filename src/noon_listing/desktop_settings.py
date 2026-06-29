from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class DesktopSettings:
    gemini_api_key: str = ""
    noon_credentials_path: str = ""
    ali1688_cookie: str = ""
    default_stock: int = 1000
    auto_submit: bool = False
    gemini_model: str = "gemini-3-flash-preview"


def default_desktop_settings_path() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "NoonListingTool" / "desktop.local.json"
    return Path.home() / ".noon_listing_tool" / "desktop.local.json"


def load_desktop_settings(path: str | Path) -> DesktopSettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return DesktopSettings()
    with settings_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    allowed = {field.name for field in DesktopSettings.__dataclass_fields__.values()}
    return DesktopSettings(**{key: value for key, value in data.items() if key in allowed})


def save_desktop_settings(settings: DesktopSettings, path: str | Path) -> None:
    settings_path = Path(path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with settings_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(settings), handle, ensure_ascii=False, indent=2)


def apply_settings_to_environment(settings: DesktopSettings) -> None:
    if settings.gemini_api_key.strip():
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key.strip()
    if settings.ali1688_cookie.strip():
        os.environ["ALI1688_COOKIE"] = settings.ali1688_cookie.strip()


def settings_to_config_override(settings: DesktopSettings) -> dict[str, Any]:
    default_stock = max(int(settings.default_stock or 1000), 0)
    return {
        "ai": {
            "enabled": bool(settings.gemini_api_key.strip()),
            "provider": "gemini_native",
            "api_key_env": "GEMINI_API_KEY",
            "model": settings.gemini_model.strip() or "gemini-3-flash-preview",
            "timeout_seconds": 90,
        },
        "marketplaces": {
            "UAE": {"default_stock": default_stock},
            "KSA": {"default_stock": default_stock},
        },
        "desktop": {
            "auto_submit": bool(settings.auto_submit),
            "noon_credentials_path": settings.noon_credentials_path.strip(),
        },
    }
