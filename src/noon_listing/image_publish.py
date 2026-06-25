from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .io_utils import safe_filename
from .models import ProductDraft


def publish_images_if_configured(draft: ProductDraft, cfg: dict[str, Any]) -> ProductDraft:
    publish_dir = str(cfg.get("publish_dir") or "").strip()
    public_base_url = str(cfg.get("public_base_url") or "").strip().rstrip("/")
    if not publish_dir or not public_base_url:
        return draft
    root = Path(publish_dir)
    sku_dir = root / safe_filename(draft.sku)
    sku_dir.mkdir(parents=True, exist_ok=True)
    published_urls: list[str] = []
    role_urls: dict[str, str] = {}
    for idx, image_path in enumerate(draft.images, start=1):
        path = Path(image_path)
        if not path.exists():
            continue
        target = sku_dir / f"{idx:02d}_{safe_filename(path.stem)}{path.suffix.lower() or '.jpg'}"
        shutil.copy2(path, target)
        url = f"{public_base_url}/{safe_filename(draft.sku)}/{target.name}"
        published_urls.append(url)
        for role, role_path in draft.image_roles.items():
            if Path(role_path) == path:
                role_urls[role] = url
    if published_urls:
        draft.source_product.image_urls = published_urls
        draft.image_roles.update(role_urls)
    return draft
