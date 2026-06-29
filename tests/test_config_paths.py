from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from noon_listing.config import resource_root


class ConfigPathTest(unittest.TestCase):
    def test_resource_root_uses_pyinstaller_meipass_when_frozen(self) -> None:
        old_frozen = getattr(sys, "frozen", None)
        old_meipass = getattr(sys, "_MEIPASS", None)
        with tempfile.TemporaryDirectory() as temp:
            try:
                sys.frozen = True
                sys._MEIPASS = temp

                self.assertEqual(resource_root(), Path(temp))
            finally:
                if old_frozen is None:
                    delattr(sys, "frozen")
                else:
                    sys.frozen = old_frozen
                if old_meipass is None:
                    delattr(sys, "_MEIPASS")
                else:
                    sys._MEIPASS = old_meipass


if __name__ == "__main__":
    unittest.main()
