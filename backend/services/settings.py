"""Configurações do usuário guardadas no banco (tabela settings)."""

from backend.config import CURRENCY_OPTIONS, DEFAULT_CURRENCY, DEFAULT_THEME, THEMES
from database import fetch_one, get_connection


def get_setting(key, default=None):
    row = fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key, value):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )


def get_currency_symbol():
    value = get_setting("currency_symbol", DEFAULT_CURRENCY)
    return value if value in CURRENCY_OPTIONS else DEFAULT_CURRENCY


def get_theme():
    value = get_setting("theme", DEFAULT_THEME)
    return value if value in THEMES else DEFAULT_THEME
