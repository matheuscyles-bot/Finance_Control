"""Utilitários de texto."""

import unicodedata


def normalize_text(value):
    """Minúsculas e sem acentos: 'Água' -> 'agua'. Usado em buscas."""
    if value is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    return decomposed.encode("ascii", "ignore").decode("ascii").lower()


def escape_like(value):
    """Escapa %, _ e \\ para uso em LIKE ... ESCAPE '\\'."""
    return (
        value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
