"""Validações centralizadas de entradas do usuário."""

from datetime import datetime

from backend.utils.formatters import parse_date, parse_month
from backend.utils.money import parse_amount

MAX_DESCRIPTION = 120
MAX_NAME = 60
MAX_NOTES = 500


def valid_date(value):
    try:
        parse_date(value)
        return True
    except ValueError:
        return False


def valid_month(value):
    try:
        parse_month(value)
        return True
    except ValueError:
        return False


def _clean_text(value, label, limit, required=True):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{label} inválido(a).")
    value = " ".join(value.split())
    if required and not value:
        raise ValueError(f"Informe {label.lower()}.")
    if len(value) > limit:
        raise ValueError(f"{label} deve ter no máximo {limit} caracteres.")
    return value


def validate_description(value):
    return _clean_text(value, "A descrição", MAX_DESCRIPTION)


def validate_name(value, label="O nome"):
    return _clean_text(value, label, MAX_NAME)


def validate_notes(value):
    if value is None:
        return ""
    value = str(value).strip()
    if len(value) > MAX_NOTES:
        raise ValueError(f"As observações devem ter no máximo {MAX_NOTES} caracteres.")
    return value


def validate_amount(value):
    """Devolve o valor em centavos (inteiro, maior que zero)."""
    return parse_amount(value)


def validate_optional_amount(value):
    """Valor que pode ser zero (ex.: saldo inicial). Aceita negativo."""
    text = "" if value is None else str(value).strip()
    if not text:
        return 0
    negative = text.startswith("-")
    if negative:
        text = text[1:].strip()
    if text in ("0", "0,00", "0.00"):
        return 0
    minor = parse_amount(text)
    return -minor if negative else minor


def validate_date(value):
    """Devolve a data no formato ISO (AAAA-MM-DD)."""
    return parse_date(value)


def validate_month(value):
    return parse_month(value)


def validate_kind(kind):
    if kind not in ("income", "expense"):
        raise ValueError("Tipo de movimentação inválido.")
    return kind


def validate_date_range(start, end):
    start = validate_date(start)
    end = validate_date(end)
    if start > end:
        raise ValueError("A data inicial não pode ser posterior à final.")
    return start, end


def iso_to_datetime(value):
    return datetime.strptime(value, "%Y-%m-%d")
