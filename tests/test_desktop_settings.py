from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from noon_listing.desktop_settings import (
    DesktopSettings,
    apply_settings_to_environment,
    load_desktop_settings,
    save_desktop_settings,
    settings_to_config_override,
)


class DesktopSettingsTest(unittest.TestCase):
    def test_saves_and_loads_local_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "desktop.local.json"
            settings = DesktopSettings(
                gemini_api_key="secret-key",
                noon_credentials_path="D:/secure/api.json",
                ali1688_cookie="cookie-value",
                default_stock=500,
                auto_submit=True,
            )

            save_desktop_settings(settings, path)
            loaded = load_desktop_settings(path)

            self.assertEqual(loaded.gemini_api_key, "secret-key")
            self.assertEqual(loaded.noon_credentials_path, "D:/secure/api.json")
            self.assertEqual(loaded.ali1688_cookie, "cookie-value")
            self.assertEqual(loaded.default_stock, 500)
            self.assertTrue(loaded.auto_submit)

    def test_applies_sensitive_values_to_process_environment(self) -> None:
        old_gemini = os.environ.get("GEMINI_API_KEY")
        old_cookie = os.environ.get("ALI1688_COOKIE")
        try:
            settings = DesktopSettings(gemini_api_key="gemini", ali1688_cookie="cookie")
            apply_settings_to_environment(settings)

            self.assertEqual(os.environ["GEMINI_API_KEY"], "gemini")
            self.assertEqual(os.environ["ALI1688_COOKIE"], "cookie")
        finally:
            if old_gemini is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = old_gemini
            if old_cookie is None:
                os.environ.pop("ALI1688_COOKIE", None)
            else:
                os.environ["ALI1688_COOKIE"] = old_cookie

    def test_builds_gemini_config_override_without_embedding_key(self) -> None:
        settings = DesktopSettings(gemini_api_key="secret-key", default_stock=321)

        override = settings_to_config_override(settings)

        self.assertEqual(override["ai"]["provider"], "gemini_native")
        self.assertEqual(override["ai"]["api_key_env"], "GEMINI_API_KEY")
        self.assertEqual(override["ai"]["model"], "gemini-3-flash-preview")
        self.assertNotIn("secret-key", repr(override))
        self.assertEqual(override["marketplaces"]["UAE"]["default_stock"], 321)
        self.assertEqual(override["marketplaces"]["KSA"]["default_stock"], 321)


if __name__ == "__main__":
    unittest.main()
