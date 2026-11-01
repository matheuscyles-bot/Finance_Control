import unittest

from backend import config
from frontend.theme import PALETTES, SPACING


class ThemeTests(unittest.TestCase):
    def test_premium_dark_palette(self):
        dark = PALETTES["dark"]
        self.assertEqual(dark["bg"], "#15120F")       # quase preto quente
        self.assertEqual(dark["glow"], "#27303A")     # brilho azul-acinzentado
        self.assertEqual(dark["surface"], "#211E1B")  # vidro dos cards
        self.assertEqual(dark["primary"], "#B6F23A")  # verde-limão (destaque único)
        self.assertEqual(dark["coral"], "#F08670")
        self.assertEqual(dark["blue"], "#7FB6E6")

    def test_palettes_share_the_same_tokens(self):
        self.assertEqual(set(PALETTES["dark"]), set(PALETTES["light"]))

    def test_default_and_spacing_tokens(self):
        self.assertEqual(config.DEFAULT_THEME, "dark")
        self.assertEqual(SPACING["page"], 32)
        self.assertLess(SPACING["md"], SPACING["xl"])


if __name__ == "__main__":
    unittest.main()
