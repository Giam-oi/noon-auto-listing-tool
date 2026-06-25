from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from lxml import html

from ..io_utils import safe_filename, write_json, write_text
from ..models import SourceProduct


IMAGE_RE = re.compile(r"https?:?//[^\"'<>\\\s]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\"'<>\\\s]*)?", re.I)
PRICE_RE = re.compile(r"(?<!\d)(\d{1,5}(?:\.\d{1,2})?)\s*(?:yuan|rmb|cny|元)?", re.I)


def normalize_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    return url


class Ali1688Collector:
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg

    def collect_html(self, html_path: Path, source_url: str, out_dir: Path) -> SourceProduct:
        out_dir.mkdir(parents=True, exist_ok=True)
        product = SourceProduct(source="1688", source_url=source_url)
        try:
            body = html_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            product.warnings.append(f"HTML read failed: {type(exc).__name__}: {exc}")
            write_json(out_dir / "source_product.json", product.to_dict())
            return product

        raw_path = out_dir / "source.html"
        write_text(raw_path, body)
        product.raw_path = str(raw_path)
        if self._looks_like_login_page(body):
            product.warnings.append("Saved 1688 HTML still looks like an anti-bot/login verification page.")
            write_json(out_dir / "source_product.json", product.to_dict())
            return product
        self._parse_html(body, product)
        self._parse_embedded_json(body, product)
        self._dedupe_images(product)
        self._download_images(product, out_dir / "images")
        write_json(out_dir / "source_product.json", product.to_dict())
        return product

    def collect(self, url: str, out_dir: Path) -> SourceProduct:
        out_dir.mkdir(parents=True, exist_ok=True)
        product = SourceProduct(source="1688", source_url=url)
        try:
            body = self._fetch(url)
        except urllib.error.HTTPError as exc:
            product.warnings.append(f"HTTP error while collecting 1688 page: {exc.code}")
            write_json(out_dir / "source_product.json", product.to_dict())
            return product
        except Exception as exc:
            product.warnings.append(f"Collection failed: {type(exc).__name__}: {exc}")
            write_json(out_dir / "source_product.json", product.to_dict())
            return product

        write_text(out_dir / "source.html", body)
        product.raw_path = str(out_dir / "source.html")
        if self._looks_like_login_page(body):
            product.warnings.append("1688 returned an anti-bot/login verification page; set ALI1688_COOKIE or use a logged-in browser collector.")
            write_json(out_dir / "source_product.json", product.to_dict())
            return product
        self._parse_html(body, product)
        self._parse_embedded_json(body, product)
        self._dedupe_images(product)
        self._download_images(product, out_dir / "images")
        write_json(out_dir / "source_product.json", product.to_dict())
        return product

    def _fetch(self, url: str) -> str:
        headers = {"User-Agent": self.cfg.get("user_agent", "Mozilla/5.0")}
        cookie = os.environ.get(self.cfg.get("cookie_env", "ALI1688_COOKIE"), "")
        if cookie:
            headers["Cookie"] = cookie
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=int(self.cfg.get("timeout_seconds", 30))) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    def _parse_html(self, body: str, product: SourceProduct) -> None:
        doc = html.fromstring(body)
        title_candidates = [
            *doc.xpath("//meta[@property='og:title']/@content"),
            *doc.xpath("//meta[@name='title']/@content"),
            *doc.xpath("//title/text()"),
            *doc.xpath("//h1/text()"),
        ]
        desc_candidates = [
            *doc.xpath("//meta[@name='description']/@content"),
            *doc.xpath("//meta[@property='og:description']/@content"),
        ]
        if title_candidates:
            product.title_cn = self._clean_text(title_candidates[0])
        if desc_candidates:
            product.description_cn = self._clean_text(desc_candidates[0])
        supplier = doc.xpath("//*[contains(@class,'company') or contains(@class,'supplier')]/text()")
        if supplier:
            product.supplier_name = self._clean_text(supplier[0])
        og_images = [normalize_url(v) for v in doc.xpath("//meta[@property='og:image']/@content")]
        product.image_urls.extend(og_images)
        product.image_urls.extend(normalize_url(v) for v in IMAGE_RE.findall(body))
        text = self._clean_text(doc.text_content())
        price = self._extract_price(text)
        if price:
            product.price_cny = price

    def _parse_embedded_json(self, body: str, product: SourceProduct) -> None:
        for script in re.findall(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", body, flags=re.I | re.S):
            try:
                data = json.loads(script.strip())
            except json.JSONDecodeError:
                continue
            self._apply_json_blob(data, product)

        for marker in ["__INIT_DATA", "__INITIAL_STATE__", "window.__DATA__"]:
            idx = body.find(marker)
            if idx < 0:
                continue
            snippet = body[idx : idx + 250000]
            for value in re.findall(r"https?:?//[^\"']+\.(?:jpg|jpeg|png|webp)[^\"']*", snippet, flags=re.I):
                product.image_urls.append(normalize_url(value))
            if not product.price_cny:
                price = self._extract_price(snippet)
                if price:
                    product.price_cny = price

        for key, pattern in {
            "color": r"(?:颜色|color)[:：\s]+([^,，;\n<]{1,40})",
            "model_number": r"(?:型号|model)[:：\s]+([^,，;\n<]{1,40})",
            "material": r"(?:材质|material)[:：\s]+([^,，;\n<]{1,40})",
            "weight": r"(?:重量|weight)[:：\s]+([^,，;\n<]{1,40})",
            "dimensions": r"(?:尺寸|size|dimension)[:：\s]+([^,，;\n<]{1,60})",
            "wattage": r"(\d{1,4}\s*[wW])",
            "capacity": r"(\d{3,6}\s*(?:mAh|mah|MAH))",
        }.items():
            match = re.search(pattern, body)
            if match and key not in product.attributes:
                product.attributes[key] = self._clean_text(match.group(1))

    def _apply_json_blob(self, data: Any, product: SourceProduct) -> None:
        if isinstance(data, list):
            for item in data:
                self._apply_json_blob(item, product)
            return
        if not isinstance(data, dict):
            return
        if not product.title_cn:
            product.title_cn = self._clean_text(str(data.get("name") or ""))
        if not product.description_cn:
            product.description_cn = self._clean_text(str(data.get("description") or ""))
        image = data.get("image")
        if isinstance(image, str):
            product.image_urls.append(normalize_url(image))
        elif isinstance(image, list):
            product.image_urls.extend(normalize_url(str(v)) for v in image if v)
        offers = data.get("offers")
        if isinstance(offers, dict) and not product.price_cny:
            price = offers.get("price") or offers.get("lowPrice")
            try:
                product.price_cny = float(price)
            except (TypeError, ValueError):
                pass

    def _dedupe_images(self, product: SourceProduct) -> None:
        seen = set()
        result = []
        for raw in product.image_urls:
            url = normalize_url(raw)
            url = url.replace("\\/", "/")
            if url.startswith("http") and url not in seen:
                seen.add(url)
                result.append(url)
            if len(result) >= int(self.cfg.get("max_images", 12)):
                break
        product.image_urls = result

    def _download_images(self, product: SourceProduct, image_dir: Path) -> None:
        image_dir.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": self.cfg.get("user_agent", "Mozilla/5.0")}
        for idx, url in enumerate(product.image_urls, start=1):
            suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
            if suffix not in [".jpg", ".jpeg", ".png", ".webp"]:
                suffix = ".jpg"
            path = image_dir / f"source_{idx:02d}{suffix}"
            try:
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=int(self.cfg.get("timeout_seconds", 30))) as response:
                    path.write_bytes(response.read())
                product.local_images.append(str(path))
            except Exception as exc:
                product.warnings.append(f"Image download failed: {url} ({type(exc).__name__})")

    def _extract_price(self, text: str) -> float | None:
        candidates = []
        for match in PRICE_RE.findall(text[:30000]):
            try:
                value = float(match)
            except ValueError:
                continue
            if 0.1 <= value <= 99999:
                candidates.append(value)
        if not candidates:
            return None
        candidates.sort()
        return candidates[0]

    def _looks_like_login_page(self, body: str) -> bool:
        lowered = body.lower()
        return any(token in lowered for token in ["login.1688.com", "passport", "verify", "captcha", "punish", "x5secdata", "验证码", "登录"])

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()
