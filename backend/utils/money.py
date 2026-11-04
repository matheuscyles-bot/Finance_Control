"""Dinheiro: leitura, formatação e divisão de valores.

Todo valor é guardado como inteiro na menor unidade (centavos/pence).
Nunca usamos float para cálculos financeiros.
"""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from backend.utils.i18n import get_locale, t

MAX_MINOR = 99_999_999_999  # 999.999.999,99

_SYMBOLS = ("R$", "£", "€", "$")
_ONLY_NUMBER = re.compile(r"^[\d.,]+$")

def parse_amount(value):
    """Converte texto em valor inteiro (centavos). Sempre maior que zero.

    Aceita 25.50, 25,50, 1.234,56, 1,234.56, 1000, "£ 12,90", "R$ 5".
    """
    if value is None:
        raise ValueError(t("validation.amount_required"))

    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        number = Decimal(str(value))
        text = None
    else:
        text = str(value).strip()
        number = None

    if text is not None:
        if not text:
            raise ValueError(t("validation.amount_required"))
        for symbol in _SYMBOLS:
            text = text.replace(symbol, "")
        text = re.sub(r"[\s ]", "", text)

        if text.startswith("-") or text.startswith("("):
            raise ValueError(
                t("validation.amount_negative")
            )
        if not _ONLY_NUMBER.match(text):
            raise ValueError(t("validation.amount_help"))
        number = _decimal_from_text(text)

    try:
        number = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(t("validation.amount_help")) from exc

    if number <= 0:
        raise ValueError(t("validation.amount_positive"))

    minor = int(number * 100)
    if minor > MAX_MINOR:
        raise ValueError(t("validation.amount_too_high"))
    return minor


def _decimal_from_text(text):
    last_dot = text.rfind(".")
    last_comma = text.rfind(",")

    if last_dot != -1 and last_comma != -1:
        decimal_sep = "." if last_dot > last_comma else ","
        thousands_sep = "," if decimal_sep == "." else "."
        left, _, right = text.rpartition(decimal_sep)
        if decimal_sep in left:
            raise ValueError(t("validation.amount_help"))
        groups = left.split(thousands_sep)
        if any(not g.isdigit() for g in groups) or any(
            len(g) != 3 for g in groups[1:]
        ) or len(groups[0]) > 3:
            raise ValueError(t("validation.amount_help"))
        if not right.isdigit():
            raise ValueError(t("validation.amount_help"))
        if len(right) > 2:
            raise ValueError(t("validation.decimal_places"))
        normalized = "".join(groups) + "." + right
    elif last_dot != -1 or last_comma != -1:
        sep = "." if last_dot != -1 else ","
        parts = text.split(sep)
        if len(parts) > 2:
            # Vários separadores iguais: só pode ser separador de milhar.
            if any(len(p) != 3 or not p.isdigit() for p in parts[1:]) or not (
                parts[0].isdigit() and len(parts[0]) <= 3
            ):
                raise ValueError(t("validation.amount_help"))
            normalized = "".join(parts)
        else:
            left, right = parts
            if (left and not left.isdigit()) or (right and not right.isdigit()):
                raise ValueError(t("validation.amount_help"))
            if len(right) == 3 and left not in ("", "0"):
                if len(left) > 3:
                    raise ValueError(t("validation.decimal_places"))
                normalized = left + right  # 1,000 ou 1.000 -> mil
            elif len(right) > 2:
                raise ValueError(t("validation.decimal_places"))
            else:
                normalized = (left or "0") + "." + (right or "0")
    else:
        normalized = text

    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(t("validation.amount_help")) from exc


def format_money(minor, symbol="£", signed=False):
    """Format minor currency units with the active locale's separators."""
    minor = int(minor or 0)
    if minor < 0:
        sign = "-"
    elif signed and minor > 0:
        sign = "+"
    else:
        sign = ""

    whole, frac = divmod(abs(minor), 100)
    body = _grouped_number(whole, frac)
    return sign + _place_currency(body, symbol)


def format_money_compact(minor, symbol="£"):
    """Compact amount for chart axes."""
    value = abs(int(minor or 0)) / 100
    sign = "-" if (minor or 0) < 0 else ""
    if value >= 1_000_000:
        text = f"{value / 1_000_000:.1f}{t('format.compact_million')}"
    elif value >= 10_000:
        text = f"{value / 1_000:.0f} {t('format.compact_thousand')}"
    elif value >= 1_000:
        text = f"{value / 1_000:.1f} {t('format.compact_thousand')}"
    else:
        text = f"{value:.0f}"
    decimal = t("format.decimal_separator")
    if decimal != ".":
        text = text.replace(".", decimal)
    return sign + _place_currency(text, symbol)


def _grouped_number(whole, frac):
    group = t("format.group_separator")
    decimal = t("format.decimal_separator")
    return f"{whole:,}".replace(",", group) + decimal + f"{frac:02d}"


def _place_currency(amount, symbol):
    position = t("format.currency_position")
    if position == "before":
        spacer = " " if symbol == "R$" or get_locale() == "pt-BR" else ""
        return f"{symbol}{spacer}{amount}"
    return f"{amount}\u00a0{symbol}"


def split_installments(total_minor, count):
    """Divide um total em parcelas cuja soma é exatamente o total.

    Os centavos que sobram vão para as primeiras parcelas.
    """
    if count < 1:
        raise ValueError(t("validation.installments_invalid"))
    base, remainder = divmod(int(total_minor), count)
    return [base + (1 if i < remainder else 0) for i in range(count)]


def minor_to_text(minor):
    """Valor em centavos como texto editável (ex.: 1999 -> '19.99')."""
    whole, frac = divmod(abs(int(minor or 0)), 100)
    return f"{'-' if minor and minor < 0 else ''}{whole}.{frac:02d}"
