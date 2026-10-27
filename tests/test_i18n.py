import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.base import ROOT  # noqa: F401
from backend.utils import i18n
from backend.utils.formatters import format_date, parse_date
from backend.utils.money import format_money


class I18nTests(unittest.TestCase):
    def setUp(self):
        self.locale = i18n.get_locale()
        self.preference_path = i18n._preference_path

    def tearDown(self):
        i18n._preference_path = self.preference_path
        i18n.set_locale(self.locale, persist=False)

    def test_locale_catalogs_match_reference(self):
        root = Path(__file__).resolve().parents[1]
        reference = json.loads((root / "locales" / "pt-BR.json").read_text(encoding="utf-8"))
        for code in i18n.SUPPORTED_LOCALES:
            with self.subTest(locale=code):
                catalog = json.loads(
                    (root / "locales" / f"{code}.json").read_text(encoding="utf-8")
                )
                self.assertEqual(catalog.keys(), reference.keys())
                self.assertTrue(all(catalog.values()))

    def test_language_preference_is_saved_and_loaded_outside_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary) / "data"
            data_dir.mkdir()
            locale = i18n.configure(data_dir, Path(temporary) / "repository")
            self.assertIn(locale, i18n.SUPPORTED_LOCALES)
            i18n.set_locale("ja")
            self.assertEqual(i18n._preference_path, data_dir / "language.json")
            saved = json.loads(i18n._preference_path.read_text(encoding="utf-8"))
            self.assertEqual(saved, {"language": "ja"})
            self.assertEqual(i18n.configure(data_dir, Path(temporary) / "repository"), "ja")

    def test_missing_translation_falls_back_to_portuguese(self):
        i18n.set_locale("en", persist=False)
        with mock.patch.object(
            i18n, "_translations",
            side_effect=lambda code: {"sample.key": "Texto em português"} if code == "pt-BR" else {},
        ):
            self.assertEqual(i18n.t("sample.key"), "Texto em português")

    def test_date_display_and_input_follow_each_locale(self):
        for code in i18n.SUPPORTED_LOCALES:
            with self.subTest(locale=code):
                i18n.set_locale(code, persist=False)
                self.assertEqual(format_date("2026-10-11"), i18n.t("format.date_pattern")
                                 .replace("yyyy", "2026").replace("mm", "10").replace("dd", "11"))
                pattern = i18n.t("format.date_pattern")
                values = {"yyyy": "2026", "mm": "10", "dd": "11"}
                localized = pattern
                for token, value in values.items():
                    localized = localized.replace(token, value)
                self.assertEqual(parse_date(localized), "2026-10-11")

    def test_category_translation_does_not_change_custom_names(self):
        i18n.set_locale("en", persist=False)
        self.assertEqual(i18n.category_label("Alimentação"), "Food")
        self.assertEqual(i18n.category_label("Minha categoria"), "Minha categoria")

    def test_money_uses_locale_separators_without_changing_minor_units(self):
        i18n.set_locale("de", persist=False)
        self.assertEqual(format_money(123456, "€"), "1.234,56\u00a0€")
        i18n.set_locale("pt-BR", persist=False)
        self.assertEqual(format_money(123456, "R$"), "R$ 1.234,56")


if __name__ == "__main__":
    unittest.main()
