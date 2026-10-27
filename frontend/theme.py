"""Paletas, fontes e estilos ttk. Uma única fonte de verdade para o visual."""

import sys
import tkinter.font as tkfont
from tkinter import ttk

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "page": 32}

PALETTES = {
    "light": {
        "bg": "#F4F6F9", "surface": "#FFFFFF", "surface_alt": "#EDF1F6",
        "border": "#D9E0E8", "text": "#17212E", "muted": "#5F6E7F",
        "primary": "#315FAF", "primary_hover": "#254C91", "primary_text": "#FFFFFF",
        "primary_soft": "#E7EDF8",
        "sidebar": "#172333", "sidebar_hover": "#24354A", "sidebar_active": "#2E4562",
        "sidebar_text": "#B2BECC", "sidebar_text_active": "#FFFFFF",
        "income": "#20784D", "expense": "#A83D45", "warning": "#936018",
        "danger": "#A83D45", "danger_hover": "#873039",
        "income_soft": "#E4F1E9", "expense_soft": "#F7E9E9", "warning_soft": "#F4EEDC",
        "select": "#DCE6F3", "stripe": "#F7F9FB", "toast": "#172333", "toast_text": "#FFFFFF",
        "chart": ["#315FAF", "#278A75", "#B17A2D", "#7766A8", "#A85F78",
                  "#6486B7", "#64748B", "#718A49"],
    },
    "dark": {
        "bg": "#0B0F14", "surface": "#151D28", "surface_alt": "#1B2634",
        "border": "#2A3545", "text": "#F3F6FA", "muted": "#9AA8B8",
        "primary": "#5B8DEF", "primary_hover": "#79A2F2", "primary_text": "#0B0F14",
        "primary_soft": "#1C2B42",
        "sidebar": "#101720", "sidebar_hover": "#192431", "sidebar_active": "#202F41",
        "sidebar_text": "#9AA8B8", "sidebar_text_active": "#F3F6FA",
        "income": "#70C49B", "expense": "#E58A8A", "warning": "#D5AA65",
        "danger": "#D97575", "danger_hover": "#E58A8A",
        "income_soft": "#193329", "expense_soft": "#382329", "warning_soft": "#372F20",
        "select": "#253A57", "stripe": "#18212D", "toast": "#1B2634", "toast_text": "#F3F6FA",
        "chart": ["#6F9CF1", "#69BDA4", "#D5AA65", "#A493D1", "#D58BA4",
                  "#8AA6D4", "#9AA8B8", "#A5B77D"],
    },
}

_state = {"name": "light", "colors": PALETTES["light"], "font": "TkDefaultFont"}
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


def font(size=11, weight="normal"):
    return (_state["font"], size, weight)


def _pick_family(root):
    available = set(tkfont.families(root))
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
    _state["name"] = name if name in PALETTES else "light"
    _state["colors"] = PALETTES[_state["name"]]
    _state["font"] = _pick_family(root)
    p = _state["colors"]
    f = _state["font"]

    for fname in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(fname).configure(family=f, size=11)

    root.configure(bg=p["bg"])
    root.option_add("*TCombobox*Listbox.background", p["surface"])
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
                    foreground=p["text"], rowheight=36, borderwidth=0,
                    font=(f, 11), relief="flat", padding=(2, 2))
    style.configure("Treeview.Heading", background=p["surface_alt"],
                    foreground=p["muted"], font=(f, 10, "bold"), relief="flat",
                    borderwidth=0, padding=(12, 10))
    style.map("Treeview.Heading", background=[("active", p["surface_alt"])],
              foreground=[("active", p["text"])])
    style.map("Treeview", background=[("selected", p["select"])],
              foreground=[("selected", p["text"])])
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure("TCombobox", fieldbackground=p["surface"], background=p["surface"],
                    foreground=p["text"], arrowcolor=p["muted"], padding=6,
                    bordercolor=p["border"], selectbackground=p["surface"],
                    selectforeground=p["text"])
    style.map("TCombobox", fieldbackground=[("readonly", p["surface"])],
              foreground=[("readonly", p["text"])],
              bordercolor=[("focus", p["primary"])])
    style.configure("TEntry", fieldbackground=p["surface"], foreground=p["text"],
                    padding=7, bordercolor=p["border"], insertcolor=p["text"])
    style.map("TEntry", bordercolor=[("focus", p["primary"])],
              fieldbackground=[("disabled", p["surface_alt"])])
    style.configure("TSpinbox", fieldbackground=p["surface"], foreground=p["text"],
                    padding=6, bordercolor=p["border"], arrowcolor=p["muted"])
    style.map("TSpinbox", bordercolor=[("focus", p["primary"])])
    style.configure("TCheckbutton", background=p["surface"], foreground=p["text"])
    style.map("TCheckbutton", foreground=[("active", p["text"])])
    style.configure("Vertical.TScrollbar", background=p["border"], troughcolor=p["bg"],
                    bordercolor=p["bg"], arrowcolor=p["muted"], relief="flat")
    style.configure("TSeparator", background=p["border"])
    return style
