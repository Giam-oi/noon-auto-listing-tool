from __future__ import annotations

import unittest

import noon_listing.desktop_gui as desktop_gui


class DesktopGuiTest(unittest.TestCase):
    def test_exposes_app_class_and_main_entrypoint(self) -> None:
        self.assertTrue(hasattr(desktop_gui, "NoonListingWindow"))
        self.assertTrue(callable(desktop_gui.main))


if __name__ == "__main__":
    unittest.main()
