from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def safe_filename(value: str, default: str = "item") -> str:
    value = re.sub(r"[^\w\-.]+", "_", value, flags=re.UNICODE).strip("._")
    return value[:120] or default


def make_run_dir(root: Path, prefix: str = "run") -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = root / f"{prefix}_{stamp}"
    counter = 1
    while path.exists():
        path = root / f"{prefix}_{stamp}_{counter}"
        counter += 1
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(data)
