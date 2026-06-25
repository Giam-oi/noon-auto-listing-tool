from __future__ import annotations

from datetime import datetime


def make_sku(prefix: str, category_code: str, sequence: int, variant: int = 1) -> str:
    date_code = datetime.now().strftime("%y%m%d")
    return f"{prefix}{date_code}{category_code.upper()}{sequence:04d}V{variant}"
