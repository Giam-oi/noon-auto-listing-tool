from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .models import ProductDraft, SourceProduct


CARD_LABELS = [
    ("main_white", "Main Image"),
    ("scene", "Use Scene"),
    ("features", "Key Features"),
    ("specs", "Specs"),
    ("package", "In The Box"),
]


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _open_first_image(product: SourceProduct) -> Image.Image | None:
    for value in product.local_images:
        try:
            return Image.open(value).convert("RGBA")
        except OSError:
            continue
    return None


def _trim_uniform_border(img: Image.Image) -> Image.Image:
    bg = Image.new(img.mode, img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
        return img.crop(bbox)
    return img


def _place_product(canvas: Image.Image, product_img: Image.Image, max_ratio: float = 0.72) -> None:
    size = int(canvas.size[0] * max_ratio)
    image = _trim_uniform_border(product_img)
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    x = (canvas.size[0] - image.size[0]) // 2
    y = (canvas.size[1] - image.size[1]) // 2 + 40
    canvas.alpha_composite(image, (x, y))


def _draw_card_text(canvas: Image.Image, label: str, title: str, detail: str) -> None:
    draw = ImageDraw.Draw(canvas)
    title_font = _load_font(54)
    label_font = _load_font(34)
    detail_font = _load_font(28)
    draw.text((64, 56), label, fill=(38, 64, 82, 255), font=label_font)
    draw.text((64, 106), title[:42], fill=(16, 24, 32, 255), font=title_font)
    if detail:
        draw.text((64, 1030), detail[:82], fill=(64, 75, 85, 255), font=detail_font)


def prepare_image_suite(draft: ProductDraft, out_dir: Path, cfg: dict[str, Any]) -> ProductDraft:
    out_dir.mkdir(parents=True, exist_ok=True)
    size = int(cfg.get("canvas_size", 1200))
    product_img = _open_first_image(draft.source_product)
    created: list[str] = []
    roles: dict[str, str] = {}
    title = draft.listing.title_en or draft.source_product.title_cn or draft.sku
    detail = "Noon UAE/KSA listing asset"
    palette = {
        "main_white": (255, 255, 255, 255),
        "scene": (238, 246, 244, 255),
        "features": (245, 241, 232, 255),
        "specs": (236, 241, 247, 255),
        "package": (247, 239, 239, 255),
    }
    for idx, (role, label) in enumerate(CARD_LABELS, start=1):
        canvas = Image.new("RGBA", (size, size), palette.get(role, (255, 255, 255, 255)))
        if product_img:
            _place_product(canvas, product_img, 0.76 if role == "main_white" else 0.58)
        else:
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((320, 330, 880, 880), outline=(180, 180, 180, 255), width=4)
            draw.text((420, 590), "Image Missing", fill=(90, 90, 90, 255), font=_load_font(40))
        if role != "main_white":
            _draw_card_text(canvas, label, title, detail)
        path = out_dir / f"{idx:02d}_{role}.jpg"
        canvas.convert("RGB").save(path, "JPEG", quality=92)
        created.append(str(path))
        roles[role] = str(path)
    draft.images = created
    draft.image_roles = roles
    return draft
