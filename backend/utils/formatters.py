"""Locale-aware display formatting while retaining ISO dates and minor units."""

import calendar
import re
from datetime import date, datetime

from backend.config import DEFAULT_CURRENCY
from backend.utils.money import (  # noqa: F401  (reexportados para o restante do app)
    format_money,
    format_money_compact,
    parse_amount,
)
from backend.utils.i18n import get_locale, t

_currency_symbol = DEFAULT_CURRENCY


def set_currency_symbol(symbol):
    global _currency_symbol
    _currency_symbol = symbol or DEFAULT_CURRENCY


def get_currency_symbol():
    return _currency_symbol


def money(minor, signed=False):
    """Formata um valor em centavos usando a moeda configurada."""
    return format_money(minor, _currency_symbol, signed=signed)


def money_compact(minor):
    return format_money_compact(minor, _currency_symbol)


# ----------------------------------------------------------------------
# Datas
# ----------------------------------------------------------------------

def today_iso():
    return date.today().isoformat()


def today():
    """Compatibilidade com a versão 1.0: data de hoje em ISO."""
    return today_iso()


def current_month():
    return date.today().strftime("%Y-%m")


def parse_date(text):
    """Parse the active locale's date order plus ISO dates; return ISO."""
    message = t("validation.date_invalid")
    if isinstance(text, date):
        return text.isoformat()
    value = str(text or "").strip()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", value):
        order = ("y", "m", "d")
    else:
        pattern = t("format.date_pattern")
        order = tuple(re.split(r"[/.-]", pattern))
    pieces = re.split(r"[/.-]", value)
    if len(pieces) != 3 or len(order) != 3:
        raise ValueError(message)
    parts = dict(zip(order, pieces))
    if not all(part.isdigit() for part in pieces):
        raise ValueError(message)
    year = int(parts["yyyy"] if "yyyy" in parts else parts["yy"] if "yy" in parts else parts["y"])
    if year < 100:
        year += 2000
    try:
        return date(year, int(parts["mm"] if "mm" in parts else parts["m"]),
                    int(parts["dd"] if "dd" in parts else parts["d"])).isoformat()
    except (ValueError, KeyError) as exc:
        raise ValueError(message) from exc


def parse_month(text):
    value = str(text or "").strip()
    if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", value):
        return value
    raise ValueError(t("validation.month_invalid"))


def format_date(iso):
    """Format an ISO date in the active locale."""
    try:
        value = datetime.strptime(iso, "%Y-%m-%d")
        pattern = t("format.date_pattern")
        return (pattern.replace("yyyy", f"{value.year:04d}")
                .replace("dd", f"{value.day:02d}")
                .replace("mm", f"{value.month:02d}"))
    except (TypeError, ValueError):
        return iso or ""


def format_date_short(iso):
    """Format a short date for compact tables."""
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return t("format.short_date_pattern", day=d.day,
                 month=t(f"format.months_abbr.{d.month}"))
    except (TypeError, ValueError):
        return iso or ""


def month_label(yyyy_mm, short=False):
    """Format a month label for the active locale."""
    year, month = (int(p) for p in yyyy_mm.split("-"))
    name = t(f"format.months_abbr.{month}" if short else f"format.months.{month}")
    if short:
        return t("format.short_month_year_pattern", month=name, year=str(year)[2:])
    return t("format.month_year_pattern", month=name, year=year)


def shift_month(yyyy_mm, delta):
    year, month = (int(p) for p in yyyy_mm.split("-"))
    index = year * 12 + (month - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_range(yyyy_mm):
    """Primeiro e último dia do mês em ISO."""
    year, month = (int(p) for p in yyyy_mm.split("-"))
    last = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}"


def add_months(start, months, anchor_day=None):
    """Soma meses mantendo o dia âncora (31/jan + 1 mês = 28/fev)."""
    anchor = anchor_day or start.day
    index = start.year * 12 + (start.month - 1) + months
    year, month = index // 12, index % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor, last))
