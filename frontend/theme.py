"""Tokens visuais (cores, tipografia, raios, espaços, movimento) e estilos ttk.

É a única fonte de verdade do visual: telas e componentes pedem cores com
``c("nome")`` e fontes com ``font(tamanho, peso)``. Equivale ao arquivo de
variáveis CSS de um projeto web.
"""

import sys
import tkinter.font as tkfont
from tkinter import ttk

from frontend import fonts

# ---------------------------------------------------------------- espaços e raios
SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32, "page": 32}
RADIUS = {"card": 24, "inner": 18, "chip": 999, "frame": 28}
DURATION = {"page": 0.42, "count": 0.8, "chart": 0.9, "hover": 0.16, "pill_fast": 0.36, "pill_slow": 0.55}

# ---------------------------------------------------------------- cores
# "surface" e afins são o vidro dos cards já misturado ao fundo (Tk não tem
# transparência por widget): branco ~5% sobre o fundo quente quase preto.
PALETTES = {
    "dark": {
        "bg": "#15120F", "bg_deep": "#100D0B", "glow": "#27303A",
        "surface": "#211E1B", "surface_alt": "#2A2724", "surface_hi": "#34302C",
        "border": "#2F2B28", "border_hi": "#4B4641",
        "text": "#F5F2ED", "muted": "#A29B93", "faint": "#6F6962",
        "primary": "#B6F23A", "primary_hover": "#C8F86E", "primary_text": "#15120F",
        "primary_soft": "#2F3A1B", "accent_text": "#B6F23A",
        "coral": "#F08670", "blue": "#7FB6E6", "steel": "#6F8091", "olive": "#3F4D22",
        "wine": "#5A2F2B", "mint": "#8FD9B6", "amber": "#F1C982",
        "tint_steel": "#2C3640", "tint_olive": "#353F1F", "tint_wine": "#432723",
        "tint_gray": "#2B2825",
        "income": "#8FD9B6", "expense": "#F08670", "warning": "#F1C982",
        "danger": "#F08670", "danger_hover": "#F49C8A",
        "income_soft": "#22352C", "expense_soft": "#3F2622", "warning_soft": "#3B3222",
        "select": "#3A3531", "stripe": "#1D1A17", "toast": "#2C2926", "toast_text": "#F5F2ED",
        # nomes antigos mantidos para componentes que ainda os pedem
        "sidebar": "#1C1916", "sidebar_hover": "#2A2724", "sidebar_active": "#34302C",
        "sidebar_text": "#A29B93", "sidebar_text_active": "#F5F2ED",
        "chart": ["#B6F23A", "#F08670", "#7FB6E6", "#8FD9B6", "#A7B4C2",
                  "#F1C982", "#D59BB8", "#7D766F"],
        "avatar": ["#D9F59C", "#F7C2B5", "#C4DDF3", "#C9EEDB", "#EBDDB6", "#E3C9DA"],
    },
    "light": {
        "bg": "#F2EFE9", "bg_deep": "#E8E3DB", "glow": "#D5DFE9",
        "surface": "#FBFAF7", "surface_alt": "#F1EDE6", "surface_hi": "#E7E2D9",
        "border": "#E2DCD2", "border_hi": "#C9C0B2",
        "text": "#1C1916", "muted": "#685F56", "faint": "#9A938A",
        "primary": "#B6F23A", "primary_hover": "#A4E024", "primary_text": "#1C1916",
        "primary_soft": "#E8F6C8", "accent_text": "#4C6810",
        "coral": "#D9674F", "blue": "#3F7FBD", "steel": "#7F90A1", "olive": "#E3EBC9",
        "wine": "#F2DAD4", "mint": "#3E9E74", "amber": "#B5862C",
        "tint_steel": "#E2E8EF", "tint_olive": "#E7EED0", "tint_wine": "#F4E1DC",
        "tint_gray": "#ECE8E1",
        "income": "#2E8B5E", "expense": "#CF5F49", "warning": "#A87B22",
        "danger": "#C9533F", "danger_hover": "#B0442F",
        "income_soft": "#DDF0E5", "expense_soft": "#F8E1DA", "warning_soft": "#F5EAD3",
        "select": "#E6EDD3", "stripe": "#F6F3EE", "toast": "#2A2622", "toast_text": "#FBFAF7",
        "sidebar": "#F7F5F1", "sidebar_hover": "#EDE9E2", "sidebar_active": "#E4DFD6",
        "sidebar_text": "#685F56", "sidebar_text_active": "#1C1916",
        "chart": ["#8CC21C", "#D9674F", "#3F7FBD", "#3E9E74", "#7F90A1",
                  "#B5862C", "#B0628A", "#8E867D"],
        "avatar": ["#DDF3A8", "#F6CDBF", "#CFE1F2", "#CDEBDC", "#EEE1BD", "#E8D0E0"],
    },
}

# Tons dos estágios do quadro de vencimentos (cor do ponto, cor do card).
STAGES = {
    "to_pay": ("blue", "tint_steel"),
    "due_soon": ("amber", "tint_olive"),
    "paid": ("coral", "tint_wine"),
    "received": ("text", "tint_gray"),
}

_state = {"name": "dark", "colors": PALETTES["dark"], "font": "TkDefaultFont", "brand": False}
MOD = "Command" if sys.platform == "darwin" else "Control"
MOD_LABEL = "⌘" if sys.platform == "darwin" else "Ctrl+"


def colors():
    return _state["colors"]


def c(name):
    return _state["colors"][name]


def theme_name():
    return _state["name"]


def font_family():
    return _state["font"]


def mix(color_a, color_b, amount):
    """Mistura duas cores #RRGGBB (amount=0 → a, 1 → b)."""
    a = [int(color_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(color_b[i:i + 2], 16) for i in (1, 3, 5)]
    amount = max(0.0, min(1.0, amount))
    return "#" + "".join(f"{round(x + (y - x) * amount):02X}" for x, y in zip(a, b))


# Pesos da Manrope: o Tk só conhece normal/negrito, mas aceita o nome
# PostScript da variação ("Manrope-Medium") como família.
_WEIGHTS = {
    "normal": ("Manrope", "normal"),
    "medium": ("Manrope-Medium", "normal"),
    "semibold": ("Manrope-SemiBold", "normal"),
    "bold": ("Manrope", "bold"),
}


def font(size=11, weight="normal"):
    if _state["brand"]:
        family, tk_weight = _WEIGHTS.get(weight, _WEIGHTS["normal"])
        return (family, size, tk_weight)
    return (_state["font"], size, "bold" if weight in ("semibold", "bold") else "normal")


def icon_font(size=16):
    return (fonts.ICON_FAMILY, size)


def icon(name):
    return fonts.glyph(name)


def has_icons():
    return fonts.icons_available()


def _pick_family(root):
    available = set(tkfont.families(root))
    if "Manrope" in available:
        return "Manrope"
    for name in (
        "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans",
        "Arial Unicode MS", "Yu Gothic", "Hiragino Sans",
        "Microsoft YaHei", "SF Pro Text", ".AppleSystemUIFont",
        "Helvetica Neue", "Segoe UI", "Inter", "DejaVu Sans", "Helvetica",
    ):
        if name in available:
            return name
    return tkfont.nametofont("TkDefaultFont").actual("family")


def apply(root, name):
    """Aplica a paleta (claro/escuro) e configura os estilos ttk."""
    _state["name"] = name if name in PALETTES else "dark"
    _state["colors"] = PALETTES[_state["name"]]
    _state["font"] = _pick_family(root)
    _state["brand"] = _state["font"] == "Manrope"
    p = _state["colors"]
    f = _state["font"]

    for fname in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(fname).configure(family=f, size=11)

    root.configure(bg=p["bg"])
    root.option_add("*TCombobox*Listbox.background", p["surface_alt"])
    root.option_add("*TCombobox*Listbox.foreground", p["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["select"])
    root.option_add("*TCombobox*Listbox.selectForeground", p["text"])
    root.option_add("*TCombobox*Listbox.font", (f, 11))

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=p["bg"], foreground=p["text"], font=(f, 11),
                    bordercolor=p["border"], lightcolor=p["border"],
                    darkcolor=p["border"], troughcolor=p["surface_alt"])
    style.configure("TFrame", background=p["bg"])
    style.configure("Card.TFrame", background=p["surface"])

    style.configure("Treeview", background=p["surface"], fieldbackground=p["surface"],
                    foreground=p["text"], rowheight=42, borderwidth=0,
                    font=font(11), relief="flat", padding=(4, 2))
    style.configure("Treeview.Heading", background=p["surface"],
                    foreground=p["muted"], font=font(10, "semibold"), relief="flat",
                    borderwidth=0, padding=(14, 12))
    style.map("Treeview.Heading", background=[("active", p["surface"])],
              foreground=[("active", p["text"])])
    style.map("Treeview", background=[("selected", p["select"])],
              foreground=[("selected", p["text"])])
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure("TCombobox", fieldbackground=p["surface_alt"], background=p["surface_alt"],
                    foreground=p["text"], arrowcolor=p["muted"], padding=8,
                    bordercolor=p["border"], selectbackground=p["surface_alt"],
                    selectforeground=p["text"])
    style.map("TCombobox", fieldbackground=[("readonly", p["surface_alt"])],
              foreground=[("readonly", p["text"])],
              bordercolor=[("focus", p["primary"])])
    style.configure("TEntry", fieldbackground=p["surface_alt"], foreground=p["text"],
                    padding=8, bordercolor=p["border"], insertcolor=p["text"])
    style.map("TEntry", bordercolor=[("focus", p["primary"])],
              fieldbackground=[("disabled", p["surface"])])
    style.configure("Bare.TEntry", fieldbackground=p["surface_alt"], foreground=p["text"],
                    padding=2, borderwidth=0, bordercolor=p["surface_alt"],
                    lightcolor=p["surface_alt"], darkcolor=p["surface_alt"],
                    insertcolor=p["text"])
    style.map("Bare.TEntry", bordercolor=[("focus", p["surface_alt"])],
              lightcolor=[("focus", p["surface_alt"])], darkcolor=[("focus", p["surface_alt"])])
    style.configure("TSpinbox", fieldbackground=p["surface_alt"], foreground=p["text"],
                    padding=7, bordercolor=p["border"], arrowcolor=p["muted"])
    style.map("TSpinbox", bordercolor=[("focus", p["primary"])])
    style.configure("TCheckbutton", background=p["surface"], foreground=p["text"])
    style.map("TCheckbutton", foreground=[("active", p["text"])])
    style.configure("TSeparator", background=p["border"])
    return style
