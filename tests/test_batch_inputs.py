from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from noon_listing.batch import parse_1688_urls, read_urls_from_excel


class BatchInputTest(unittest.TestCase):
    def test_parse_1688_urls_filters_and_deduplicates(self) -> None:
        text = """
        https://detail.1688.com/offer/695867996979.html
        https://example.com/not-valid
        https://detail.1688.com/offer/695867996979.html?spm=a26352
        https://detail.1688.com/offer/123.html
        """

        urls = parse_1688_urls(text)

        self.assertEqual(
            urls,
            [
                "https://detail.1688.com/offer/695867996979.html",
                "https://detail.1688.com/offer/123.html",
            ],
        )

    def test_read_urls_from_excel_detects_url_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "urls.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.append(["name", "1688 URL", "note"])
            ws.append(["A", "https://detail.1688.com/offer/111.html", "ok"])
            ws.append(["B", "not a url", "skip"])
            ws.append(["C", "https://detail.1688.com/offer/222.html?spm=abc", "ok"])
            wb.save(path)

            urls = read_urls_from_excel(path)

            self.assertEqual(
                urls,
                [
                    "https://detail.1688.com/offer/111.html",
                    "https://detail.1688.com/offer/222.html",
                ],
            )


if __name__ == "__main__":
    unittest.main()
