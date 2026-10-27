import unittest
from datetime import date

from frontend.widgets import _wheel_date


class WheelDateTests(unittest.TestCase):
    def test_day_wheel_wraps_within_valid_month(self):
        selected, preferred = _wheel_date(date(2024, 2, 29), "day", 1, 29)
        self.assertEqual(selected, date(2024, 2, 1))
        self.assertEqual(preferred, 1)

    def test_month_wheel_clamps_and_restores_preferred_day(self):
        january, preferred = _wheel_date(date(2024, 1, 31), "month", 1, 31)
        self.assertEqual(january, date(2024, 2, 29))
        self.assertEqual(preferred, 31)

        march, preferred = _wheel_date(january, "month", 1, preferred)
        self.assertEqual(march, date(2024, 3, 31))
        self.assertEqual(preferred, 31)

    def test_year_wheel_handles_leap_day(self):
        following_year, preferred = _wheel_date(date(2024, 2, 29), "year", 1, 29)
        self.assertEqual(following_year, date(2025, 2, 28))
        prior_year, _ = _wheel_date(following_year, "year", -1, preferred)
        self.assertEqual(prior_year, date(2024, 2, 29))

    def test_month_and_year_stay_within_supported_bounds(self):
        oldest, _ = _wheel_date(date(1, 1, 1), "month", -1, 1)
        newest, _ = _wheel_date(date(9999, 12, 31), "month", 1, 31)
        self.assertEqual(oldest, date(1, 1, 1))
        self.assertEqual(newest, date(9999, 12, 31))

    def test_unknown_component_is_rejected(self):
        with self.assertRaises(ValueError):
            _wheel_date(date(2026, 10, 25), "weekday", 1, 25)


if __name__ == "__main__":
    unittest.main()
