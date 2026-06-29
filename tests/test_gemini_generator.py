from __future__ import annotations

import json
import os
import unittest
from typing import Any

from noon_listing.content import GeminiNativeGenerator, make_content_generator
from noon_listing.models import CategoryMatch, SourceProduct


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class GeminiNativeGeneratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_key = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        if self.old_key is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = self.old_key

    def test_request_uses_native_generate_content_format(self) -> None:
        captured: dict[str, Any] = {}

        def fake_urlopen(request: Any, timeout: int) -> _FakeResponse:
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "title_en": "USB C Cable",
                                                "bullets_en": ["Fast charging cable"],
                                                "description_en": "Durable charging cable.",
                                                "search_keywords": ["usb cable"],
                                                "attributes": {"brand": "Generic"},
                                                "content_score": 0.91,
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            )

        generator = GeminiNativeGenerator(
            {
                "enabled": True,
                "api_key_env": "GEMINI_API_KEY",
                "model": "gemini-3-flash-preview",
                "timeout_seconds": 12,
            },
            urlopen=fake_urlopen,
        )

        product = SourceProduct(source="test", title_cn="USB C Cable")
        category = CategoryMatch(category_key="cables", noon_path="Electronics/Cables", confidence=0.8)
        content = generator.generate(product, category)

        self.assertEqual(
            captured["url"],
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent",
        )
        self.assertEqual(captured["headers"]["X-goog-api-key"], "test-key")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")
        self.assertIn("contents", captured["body"])
        self.assertIn("parts", captured["body"]["contents"][0])
        self.assertIn("USB C Cable", captured["body"]["contents"][0]["parts"][0]["text"])
        self.assertEqual(captured["timeout"], 12)
        self.assertEqual(content.title_en, "USB C Cable")
        self.assertEqual(content.generator, "gemini_native")

    def test_factory_selects_gemini_native_provider(self) -> None:
        generator = make_content_generator({"provider": "gemini_native", "enabled": True})

        self.assertIsInstance(generator, GeminiNativeGenerator)


if __name__ == "__main__":
    unittest.main()
