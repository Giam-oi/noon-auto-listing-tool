from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", ""):
        return Path(sys._MEIPASS)
    return project_root()


DEFAULT_CONFIG_PATH = resource_root() / "config.example.json"


def load_json(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config = load_json(DEFAULT_CONFIG_PATH)
    if path:
        config = deep_merge(config, load_json(path))
    return config


def workspace_root() -> Path:
    return project_root().parent


def runs_root() -> Path:
    return project_root() / "runs"
