import unittest

from tests.base import ROOT  # noqa: F401
from backend.utils.money import format_money, parse_amount, split_installments
from backend.utils.formatters import parse_date, add_months
from backend.utils.i18n import set_locale
from datetime import date


class MoneyTests(unittest.TestCase):
    def test_parse_valid(self):
        cases = {"25,50": 2550, "25.50": 2550, "1.234,56": 123456,
                 "1,234.56": 123456, "1,000": 100000, "R$ 10": 1000,
                 "£0.01": 1, "19.99": 1999, "0,10": 10}
        for text, expected in cases.items():
            self.assertEqual(parse_amount(text), expected, text)

    def test_no_float_truncation(self):
        # 19.99 * 100 em float vira 1998.9999...; aqui tem que ser exato
        for cents in range(1, 3000):
            text = f"{cents // 100}.{cents % 100:02d}"
            self.assertEqual(parse_amount(text), cents)

    def test_parse_invalid(self):
        for bad in ["", "abc", "-5", "0", "0,00", "1,234,56x", "1.2345", None,
                    "99999999999999"]:
            with self.assertRaises(ValueError, msg=str(bad)):
                parse_amount(bad)

    def test_format(self):
        set_locale("en", persist=False)
        self.assertEqual(format_money(123456, "£"), "£1,234.56")
        set_locale("pt-BR", persist=False)
        self.assertEqual(format_money(123456, "R$"), "R$ 1.234,56")
        set_locale("en", persist=False)
        self.assertEqual(format_money(-500, "£"), "-£5.00")
        set_locale("pt-BR", persist=False)

    def test_installments_sum_exact(self):
        for total in (1, 100, 1000, 9999, 10001):
            for n in (1, 2, 3, 7, 12):
                if n > total:
                    continue
                parts = split_installments(total, n)
                self.assertEqual(sum(parts), total)
                self.assertEqual(len(parts), n)
                self.assertLessEqual(max(parts) - min(parts), 1)

    def test_dates(self):
        self.assertEqual(parse_date("11/10/2026"), "2026-10-11")
        self.assertEqual(parse_date("2026-10-11"), "2026-10-11")
        with self.assertRaises(ValueError):
            parse_date("31/02/2026")
        self.assertEqual(add_months(date(2026, 1, 31), 1, 31), date(2026, 2, 28))
        self.assertEqual(add_months(date(2026, 1, 31), 2, 31), date(2026, 3, 31))


if __name__ == "__main__":
    unittest.main()


class MoneyGroupingRegression(unittest.TestCase):
    def test_four_digit_group_with_three_decimals_is_rejected(self):
        from backend.utils.money import parse_amount
        for bad in ("1234,567", "1234.567"):
            with self.assertRaises(ValueError):
                parse_amount(bad)
        self.assertEqual(parse_amount("1.234"), 123400)
