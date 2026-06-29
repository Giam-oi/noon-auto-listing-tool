from __future__ import annotations

import unittest
from typing import Any

from noon_listing.batch import BatchRunner


class _FakePipeline:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def build_from_1688_url(self, url: str) -> dict[str, Any]:
        self.urls.append(url)
        if "fail" in url:
            raise RuntimeError("collector blocked")
        return {"run_dir": f"runs/{len(self.urls)}", "total_products": 1, "submit_ready": 1}


class _NeedsReviewPipeline:
    def build_from_1688_url(self, url: str) -> dict[str, Any]:
        return {"run_dir": "runs/review", "total_products": 1, "submit_ready": 0}


class BatchRunnerTest(unittest.TestCase):
    def test_runner_keeps_processing_after_single_url_failure(self) -> None:
        pipeline = _FakePipeline()
        events: list[tuple[str, str]] = []
        runner = BatchRunner(pipeline)

        result = runner.run_urls(
            [
                "https://detail.1688.com/offer/111.html",
                "https://detail.1688.com/offer/fail.html",
                "https://detail.1688.com/offer/222.html",
            ],
            progress_callback=lambda item: events.append((item.source, item.status)),
        )

        self.assertEqual(result.total, 3)
        self.assertEqual(result.succeeded, 2)
        self.assertEqual(result.failed, 1)
        self.assertEqual([item.status for item in result.items], ["succeeded", "failed", "succeeded"])
        self.assertEqual(result.items[1].error, "collector blocked")
        self.assertEqual(result.items[0].run_dir, "runs/1")
        self.assertIn(("https://detail.1688.com/offer/222.html", "succeeded"), events)

    def test_runner_can_create_fresh_pipeline_per_url(self) -> None:
        pipelines: list[_FakePipeline] = []

        def factory() -> _FakePipeline:
            pipeline = _FakePipeline()
            pipelines.append(pipeline)
            return pipeline

        runner = BatchRunner(factory)

        result = runner.run_urls(
            [
                "https://detail.1688.com/offer/111.html",
                "https://detail.1688.com/offer/222.html",
            ]
        )

        self.assertEqual(result.succeeded, 2)
        self.assertEqual(len(pipelines), 2)
        self.assertEqual(result.items[0].run_dir, "runs/1")
        self.assertEqual(result.items[1].run_dir, "runs/1")

    def test_runner_marks_completed_but_not_submit_ready_as_needs_review(self) -> None:
        runner = BatchRunner(_NeedsReviewPipeline())

        result = runner.run_urls(["https://detail.1688.com/offer/111.html"])

        self.assertEqual(result.succeeded, 0)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.needs_review, 1)
        self.assertEqual(result.items[0].status, "needs_review")


if __name__ == "__main__":
    unittest.main()
