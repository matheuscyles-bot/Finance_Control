"""Translation loading, locale selection, and user-level language preference."""

import json
import locale
import os
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

SUPPORTED_LOCALES = (
    "pt-BR",
    "en",
    "es",
    "fr",
    "it",
    "de",
    "ru",
    "zh-CN",
    "ja",
)

LANGUAGE_NAMES = {
    "pt-BR": "Português (Brasil)",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "de": "Deutsch",
    "ru": "Русский",
    "zh-CN": "中文",
    "ja": "日本語",
}

_FALLBACK_LOCALE = "pt-BR"
_locale = _FALLBACK_LOCALE
_preference_path = None


class LocaleConfigError(RuntimeError):
    """The saved language preference could not be read or written."""


def _normalize_locale(value):
    if not value:
        return None
    normalized = str(value).replace("-", "_").split(".", 1)[0].split("@", 1)[0]
    parts = normalized.split("_")
    language = parts[0].lower()
    region = parts[1].upper() if len(parts) > 1 else ""
    if language == "pt" and (not region or region == "BR"):
        return "pt-BR"
    if language == "zh" and (not region or region in {"CN", "SG", "HANS"}):
        return "zh-CN"
    return language if language in SUPPORTED_LOCALES else None


def system_locale():
    candidates = []
    try:
        candidates.append(locale.getlocale()[0])
    except (ValueError, TypeError):
        pass
    candidates.extend(
        os.environ.get(key)
        for key in ("LC_ALL", "LC_MESSAGES", "LANG")
        if os.environ.get(key)
    )
    for candidate in candidates:
        result = _normalize_locale(candidate)
        if result:
            return result
    return _FALLBACK_LOCALE


def _user_config_dir():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Finance Control"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home())) / "Finance Control"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "finance-control"


def _is_relative_to(path, parent):
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def configure(data_dir, repository_root):
    """Load the saved preference without touching the SQLite database."""
    global _preference_path, _locale
    data_dir = Path(data_dir).expanduser()
    repository_root = Path(repository_root).expanduser()
    if _is_relative_to(data_dir, repository_root):
        _preference_path = _user_config_dir() / "language.json"
    else:
        _preference_path = data_dir / "language.json"

    _locale = system_locale()
    try:
        raw = json.loads(_preference_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _translations.cache_clear()
        return _locale
    except (OSError, json.JSONDecodeError) as exc:
        raise LocaleConfigError(
            f"Could not read the language preference at {_preference_path}"
        ) from exc

    saved = _normalize_locale(raw.get("language")) if isinstance(raw, dict) else None
    _locale = saved or _locale
    _translations.cache_clear()
    return _locale


def get_locale():
    return _locale


def set_locale(code, persist=True):
    global _locale
    normalized = _normalize_locale(code)
    if normalized not in SUPPORTED_LOCALES:
        raise ValueError(f"Unsupported language: {code}")
    if persist:
        if _preference_path is None:
            raise LocaleConfigError("Language preference storage is not configured.")
        _preference_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=_preference_path.parent,
                prefix=".language-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                json.dump({"language": normalized}, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            temporary.replace(_preference_path)
        except OSError as exc:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
            raise LocaleConfigError(
                f"Could not save the language preference at {_preference_path}"
            ) from exc
    _locale = normalized
    _translations.cache_clear()


@lru_cache(maxsize=None)
def _translations(code):
    path = Path(__file__).resolve().parents[2] / "locales" / f"{code}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load locale catalog: {path}") from exc


def t(key, **values):
    """Translate a stable key, falling back to pt-BR for missing entries."""
    text = _translations(_locale).get(key)
    if text is None and _locale != _FALLBACK_LOCALE:
        text = _translations(_FALLBACK_LOCALE).get(key)
    if text is None:
        raise KeyError(f"Missing translation key: {key}")
    try:
        return text.format(**values)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Invalid translation template for {key}") from exc


def language_options():
    return [(code, LANGUAGE_NAMES[code]) for code in SUPPORTED_LOCALES]


_DEFAULT_CATEGORY_KEYS = {
    "Salário": "category.default.salary",
    "Freelance": "category.default.freelance",
    "Investimentos": "category.default.investments",
    "Outras receitas": "category.default.other_income",
    "Moradia": "category.default.housing",
    "Alimentação": "category.default.food",
    "Transporte": "category.default.transport",
    "Contas e serviços": "category.default.bills",
    "Saúde": "category.default.health",
    "Educação": "category.default.education",
    "Lazer": "category.default.leisure",
    "Compras": "category.default.shopping",
    "Outras despesas": "category.default.other_expense",
}


def category_label(name):
    """Localize known default categories without changing stored names."""
    key = _DEFAULT_CATEGORY_KEYS.get(name)
    return t(key) if key else name
