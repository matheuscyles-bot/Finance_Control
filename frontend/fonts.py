"""Fontes empacotadas: Manrope (texto) e Lucide (ícones).

No macOS os arquivos são registrados só para este processo (CoreText), antes
de o Tk criar a janela; nada é instalado no sistema. Em outros sistemas o app
usa a fonte do sistema e ícones desenhados (veja ``widgets.draw_icon``).

Licenças: Manrope (SIL OFL 1.1) e Lucide (ISC), em ``assets/fonts``.
"""

import ctypes
import ctypes.util
import logging
import sys
from pathlib import Path

log = logging.getLogger("finance_control.fonts")

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT_FILES = ("Manrope-Variable.ttf", "lucide.ttf")
ICON_FAMILY = "lucide"

# Código de cada ícone na fonte Lucide (lucide-static 1.66.0).
ICONS = {
    "archive": 0xe041, "archive-restore": 0xe2cd, "arrow-down-left": 0xe043, "arrow-down-to-line": 0xe455,
    "arrow-left-right": 0xe24a, "arrow-up-from-line": 0xe45a, "arrow-up-right": 0xe04d,
    "banknote": 0xe052, "bell": 0xe059, "calendar": 0xe063, "calendar-check": 0xe2b7, "calendar-clock": 0xe304,
    "calendar-days": 0xe2b9, "car": 0xe1d5, "chart-bar": 0xe2a2, "chart-column": 0xe2a3,
    "chart-pie": 0xe06b, "check": 0xe06c, "chevron-down": 0xe06d, "chevron-left": 0xe06e,
    "chevron-right": 0xe06f, "circle-alert": 0xe077, "circle-check": 0xe226, "circle-dollar-sign": 0xe47d,
    "clock": 0xe087, "coins": 0xe097, "columns-3": 0xe099, "copy": 0xe09e, "credit-card": 0xe0aa,
    "database": 0xe0ad, "download": 0xe0b2, "ellipsis": 0xe0b6, "eye": 0xe0ba, "file-down": 0xe318,
    "file-up": 0xe32a, "filter": 0xe0dc, "flower-2": 0xe2d4, "folder-kanban": 0xe4c6, "gamepad-2": 0xe0df,
    "graduation-cap": 0xe234, "grid-2x2": 0xe4ff, "hand-coins": 0xe5b8, "hard-drive-download": 0xe4e5,
    "heart-pulse": 0xe36e, "house": 0xe0f5, "import": 0xe22f, "info": 0xe0f9, "kanban": 0xe4dc,
    "landmark": 0xe23a, "languages": 0xe0fe, "layout-dashboard": 0xe1c1, "layout-grid": 0xe0ff,
    "layout-list": 0xe1d9, "leaf": 0xe2de, "list": 0xe106, "log-out": 0xe10e, "mail": 0xe10f,
    "minus": 0xe11c, "moon": 0xe11e, "pencil": 0xe1f9, "piggy-bank": 0xe13a, "plus": 0xe13d,
    "power": 0xe140, "receipt": 0xe3d3, "repeat": 0xe146, "rotate-ccw": 0xe148, "rows-3": 0xe58a,
    "save": 0xe14d, "search": 0xe151, "send": 0xe152, "settings": 0xe154, "share-2": 0xe156,
    "shopping-cart": 0xe15c, "sparkles": 0xe412, "sprout": 0xe1eb, "star": 0xe176, "sun": 0xe178,
    "tag": 0xe17f, "target": 0xe180, "trash-2": 0xe18e, "trending-down": 0xe190, "trending-up": 0xe191,
    "upload": 0xe19e, "user": 0xe19f, "utensils": 0xe2f6, "wallet": 0xe204, "wand-sparkles": 0xe357,
    "x": 0xe1b2, "zap": 0xe1b4,
}

# Nomes usados pelos ícones desenhados antigos → ícone Lucide equivalente.
ALIASES = {
    "dashboard": "layout-dashboard", "chart": "chart-column", "gear": "settings",
    "transfer": "arrow-left-right", "edit": "pencil", "delete": "trash-2",
    "more": "ellipsis", "expand": "arrow-up-right", "close": "x",
}

_state = {"registered": False, "icons": False}


def _register_macos(paths):
    cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
    ct = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreText"))
    cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
    ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    done = []
    for path in paths:
        raw = str(path).encode("utf-8")
        url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
        if not url:
            continue
        try:
            # 1 = kCTFontManagerScopeProcess: só este processo enxerga a fonte.
            # Devolve False se já estava registrada, o que também serve.
            ct.CTFontManagerRegisterFontsForURL(url, 1, None)
            done.append(path.name)
        finally:
            cf.CFRelease(url)
    return done


def register():
    """Registra as fontes do app. Seguro para chamar várias vezes."""
    if _state["registered"]:
        return
    _state["registered"] = True
    paths = [FONT_DIR / name for name in FONT_FILES if (FONT_DIR / name).exists()]
    if sys.platform != "darwin" or not paths:
        return
    try:
        done = _register_macos(paths)
        _state["icons"] = "lucide.ttf" in done
    except (OSError, AttributeError) as exc:
        log.warning("Fontes do app não registradas: %s", type(exc).__name__)


def icons_available():
    return _state["icons"]


def glyph(name):
    """Caractere do ícone (string vazia se o nome não existir)."""
    code = ICONS.get(ALIASES.get(name, name))
    return chr(code) if code else ""
