import unittest

from backend import config
from frontend.theme import PALETTES, SPACING


class ThemeTests(unittest.TestCase):
    def test_premium_dark_palette(self):
        dark = PALETTES["dark"]
        self.assertEqual(dark["bg"], "#0B0F14")
        self.assertEqual(dark["sidebar"], "#101720")
        self.assertEqual(dark["surface"], "#151D28")
        self.assertEqual(dark["surface_alt"], "#1B2634")
        self.assertEqual(dark["border"], "#2A3545")
        self.assertEqual(dark["text"], "#F3F6FA")
        self.assertEqual(dark["muted"], "#9AA8B8")
        self.assertEqual(dark["primary"], "#5B8DEF")

    def test_default_and_spacing_tokens(self):
        self.assertEqual(config.DEFAULT_THEME, "dark")
        self.assertEqual(SPACING["page"], 32)
        self.assertLess(SPACING["md"], SPACING["xl"])


if __name__ == "__main__":
    unittest.main()
