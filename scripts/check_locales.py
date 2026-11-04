#!/usr/bin/env python3
"""Compare locale JSON keys against the pt-BR reference catalog."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE_DIR = ROOT / "locales"
REFERENCE = "pt-BR"
LOCALES = ("en", "es", "fr", "it", "de", "ru", "zh-CN", "ja")


def load_catalog(code):
    path = LOCALE_DIR / f"{code}.json"
    with path.open(encoding="utf-8") as handle:
        catalog = json.load(handle)
    if not isinstance(catalog, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in catalog.items()
    ):
        raise ValueError(f"{path} must contain a JSON object of string values")
    return catalog


def main():
    reference = load_catalog(REFERENCE)
    failed = False
    for code in LOCALES:
        catalog = load_catalog(code)
        missing = sorted(reference.keys() - catalog.keys())
        extra = sorted(catalog.keys() - reference.keys())
        empty = sorted(key for key, value in catalog.items() if value == "")
        if missing or extra or empty:
            failed = True
        print(f"{code}:")
        print(f"  missing: {', '.join(missing) if missing else 'none'}")
        print(f"  extra: {', '.join(extra) if extra else 'none'}")
        print(f"  empty: {', '.join(empty) if empty else 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
