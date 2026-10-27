"""Formatação de moeda, datas e meses (interface em português do Brasil)."""

import calendar
import re
from datetime import date, datetime

from backend.config import DEFAULT_CURRENCY
from backend.utils.money import (  # noqa: F401  (reexportados para o restante do app)
    format_money,
    format_money_compact,
    parse_amount,
)

MONTH_NAMES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
MONTH_ABBR = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]
WEEKDAY_ABBR = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

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


_DATE_PATTERNS = (
    (re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"), ("y", "m", "d")),
    (re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$"), ("d", "m", "y")),
    (re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})$"), ("d", "m", "y2")),
)


def parse_date(text):
    """Aceita DD/MM/AAAA, DD-MM-AAAA, DD/MM/AA e AAAA-MM-DD. Devolve ISO."""
    message = "Data inválida. Use DD/MM/AAAA, por exemplo 11/10/2026."
    if isinstance(text, date):
        return text.isoformat()
    value = str(text or "").strip()

    for pattern, order in _DATE_PATTERNS:
        match = pattern.match(value)
        if not match:
            continue
        parts = dict(zip(order, match.groups()))
        year = parts.get("y") or parts.get("y2")
        year = int(year) + (2000 if "y2" in parts else 0)
        try:
            return date(year, int(parts["m"]), int(parts["d"])).isoformat()
        except ValueError as exc:
            raise ValueError(message) from exc
    raise ValueError(message)


def parse_month(text):
    value = str(text or "").strip()
    if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", value):
        return value
    raise ValueError("Mês inválido. Use AAAA-MM, por exemplo 2026-10.")


def format_date(iso):
    """2026-10-11 -> 11/10/2026."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso or ""


def format_date_short(iso):
    """2026-10-11 -> 11 out."""
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return f"{d.day:02d} {MONTH_ABBR[d.month - 1]}"
    except (TypeError, ValueError):
        return iso or ""


def month_label(yyyy_mm, short=False):
    """2026-10 -> Outubro 2026 (ou out/26)."""
    year, month = (int(p) for p in yyyy_mm.split("-"))
    if short:
        return f"{MONTH_ABBR[month - 1]}/{str(year)[2:]}"
    return f"{MONTH_NAMES[month - 1].capitalize()} {year}"


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
