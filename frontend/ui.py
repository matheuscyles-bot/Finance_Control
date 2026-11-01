"""Componentes do design system (sobre widgets.py): botão circular, painel com
ações, chips, avatares, badges, seletor em pílula, busca, switch, seletor de
mês, dicas (tooltip) e popover."""

import tkinter as tk

from frontend import motion
from frontend.draw import round_rect, star_points
from frontend.theme import c, font, icon, icon_font, mix
from frontend.widgets import Card, bg_of, linespace, measure, pointer_inside, put_icon
from backend.utils import formatters


# ----------------------------------------------------------------------
# Dicas (equivalente ao aria-label/title dos botões de ícone)
# ----------------------------------------------------------------------

_TIP = {"widget": None}


def show_tip(root, text, x, y, anchor="n"):
    """Mostra a dica com o ponto de ancoragem em (x, y), coordenadas da janela."""
    hide_tip()
    f = font(10, "medium")
    w, h = measure(f, text) + 22, linespace(f) + 12
    if anchor == "n":
        x, y = x - w / 2, y
    elif anchor == "w":
        y = y - h / 2
    x = min(max(int(x), 6), max(root.winfo_width() - w - 6, 6))
    y = min(max(int(y), 6), max(root.winfo_height() - h - 6, 6))
    under = root.winfo_containing(root.winfo_rootx() + x + 2, root.winfo_rooty() + y + 2)
    tip = tk.Canvas(root, width=w, height=h, highlightthickness=0, bd=0,
                    bg=bg_of(under) if under is not None else c("bg"))
    round_rect(tip, 1, 1, w - 1, h - 1, h / 2, c("toast"), mix(c("toast"), c("text"), 0.12))
    tip.create_text(w / 2, h / 2, text=text, font=f, fill=c("toast_text"))
    tip.place(x=x, y=y)
    tip.lift()
    _TIP["widget"] = tip


def hide_tip(*_args):
    tip = _TIP.get("widget")
    if tip is not None:
        try:
            tip.destroy()
        except tk.TclError:
            pass
        _TIP["widget"] = None


class Tooltip:
    def __init__(self, widget, text, side="bottom"):
        self.widget, self.text, self.side = widget, text, side
        self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel, add="+")
        widget.bind("<ButtonPress>", self._cancel, add="+")
        widget.bind("<FocusIn>", self._schedule, add="+")
        widget.bind("<FocusOut>", self._cancel, add="+")

    def _schedule(self, _e=None):
        self._cancel()
        self.job = self.widget.after(420, self._show)

    def _cancel(self, _e=None):
        if self.job:
            try:
                self.widget.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None
        hide_tip()

    def _show(self):
        self.job = None
        w = self.widget
        try:
            root = w.winfo_toplevel()
            x = w.winfo_rootx() - root.winfo_rootx()
            y = w.winfo_rooty() - root.winfo_rooty()
        except tk.TclError:
            return
        text = self.text() if callable(self.text) else self.text
        if self.side == "right":
            show_tip(root, text, x + w.winfo_width() + 10, y + w.winfo_height() / 2, "w")
        else:
            show_tip(root, text, x + w.winfo_width() / 2, y + w.winfo_height() + 8, "n")


# ----------------------------------------------------------------------
# Botão circular (ícone)
# ----------------------------------------------------------------------

class CircleButton(tk.Canvas):
    """Botão redondo só com ícone. ``kind``: glass (cinza translúcido),
    primary (verde-limão) ou plain (sem fundo até passar o mouse)."""

    def __init__(self, parent, icon_name, command=None, size=36, tooltip=None,
                 kind="glass", bg=None, badge=None, fg=None, icon_size=None):
        self._parent_bg = bg or bg_of(parent)
        super().__init__(parent, width=size, height=size, bg=self._parent_bg,
                         highlightthickness=0, bd=0, cursor="hand2", takefocus=1)
        self.size, self.icon_name, self.command = size, icon_name, command
        self.kind, self.badge = kind, badge
        self.active = False
        self._fg = fg
        self._icon_size = icon_size or max(int(size * 0.44), 11)
        self._hot = 0.0
        self._focused = False
        self._chan = motion.Channel()
        self.bind("<Enter>", lambda e: self._animate(1.0))
        self.bind("<Leave>", lambda e: self._animate(0.0))
        self.bind("<Button-1>", self._click)
        self.bind("<Return>", self._click)
        self.bind("<space>", self._click)
        self.bind("<FocusIn>", lambda e: self._focus(True))
        self.bind("<FocusOut>", lambda e: self._focus(False))
        if tooltip:
            Tooltip(self, tooltip)
        self._draw()

    def _colors(self):
        if self.kind == "primary":
            return mix(c("primary"), c("primary_hover"), self._hot), c("primary_text"), None
        if self.kind == "plain":
            base = self._parent_bg if not self.active else c("surface_hi")
            return mix(base, c("surface_hi"), self._hot), (self._fg or (c("text") if self.active else c("muted"))), None
        fill = mix(c("surface_alt"), c("surface_hi"), max(self._hot, 0.8 if self.active else 0))
        return fill, self._fg or c("text"), c("border")

    def _draw(self):
        self.delete("all")
        s = self.size
        fill, fg, border = self._colors()
        outline = c("primary") if self._focused else (border or fill)
        self.create_oval(1, 1, s - 1, s - 1, fill=fill, outline=outline,
                         width=1.5 if self._focused else 1)
        put_icon(self, s / 2, s / 2, self.icon_name, fg, self._icon_size)
        if self.badge:
            r = max(s * 0.11, 3)
            x, y = s * 0.72, s * 0.28
            self.create_oval(x - r - 1.5, y - r - 1.5, x + r + 1.5, y + r + 1.5, fill=fill, outline=fill)
            self.create_oval(x - r, y - r, x + r, y + r, fill=c(self.badge), outline=c(self.badge))

    def _animate(self, target):
        def step(v):
            self._hot = v
            self._draw()
        self._chan.run(self, self._hot, target, 0.16, "power2.out", step)

    def _focus(self, on):
        self._focused = on
        self._draw()

    def _click(self, _e=None):
        hide_tip()
        if self.command:
            self.command()
        return "break"

    def set_badge(self, badge):
        self.badge = badge
        self._draw()

    def set_active(self, active):
        self.active = active
        self._draw()


def popup_menu(widget, items):
    """Menu nativo sob o widget. items: [(rótulo, função) | None (separador)]."""
    menu = tk.Menu(widget, tearoff=0)
    for item in items:
        if item is None:
            menu.add_separator()
        else:
            text, command = item
            menu.add_command(label=text, command=command)
    try:
        menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height() + 4)
    finally:
        menu.grab_release()


# ----------------------------------------------------------------------
# Painel: card com cabeçalho (título, subtítulo e ações "…", "↗", "+")
# ----------------------------------------------------------------------

class Panel(Card):
    def __init__(self, parent, title=None, subtitle=None, actions=(), fill=None, hover=True,
                 padx=22, pady=20, title_size=13, **kw):
        super().__init__(parent, padx=padx, pady=pady, fill=fill, hover=hover, **kw)
        body = self.body
        self.header = None
        if title or actions:
            self.header = tk.Frame(body, bg=self.fill)
            self.header.pack(fill="x")
            text = tk.Frame(self.header, bg=self.fill)
            text.pack(side="left", fill="x", expand=True)
            if title:
                self.title = tk.Label(text, text=title, bg=self.fill, fg=c("text"),
                                      font=font(title_size, "semibold"), anchor="w")
                self.title.pack(fill="x")
            if subtitle:
                self.subtitle = tk.Label(text, text=subtitle, bg=self.fill, fg=c("muted"),
                                         font=font(10), anchor="w", justify="left")
                self.subtitle.pack(fill="x", pady=(2, 0))
            self.actions = tk.Frame(self.header, bg=self.fill)
            self.actions.pack(side="right", anchor="n")
            for action in actions:
                self.add_action(*action)
        self.content = tk.Frame(body, bg=self.fill)
        self.content.pack(fill="both", expand=True, pady=(14 if self.header else 0, 0))

    def add_action(self, kind, target, tooltip=None):
        """kind: "more" (target = itens do menu), "expand", "plus" ou um ícone."""
        names = {"more": "ellipsis", "expand": "arrow-up-right", "plus": "plus"}
        btn = CircleButton(self.actions, names.get(kind, kind), None, size=32, bg=self.fill,
                           tooltip=tooltip)
        if kind == "more":
            btn.command = lambda b=btn: popup_menu(b, target() if callable(target) else target)
        else:
            btn.command = target
        btn.pack(side="left", padx=(6, 0))
        return btn


# ----------------------------------------------------------------------
# Chips, badges e avatares
# ----------------------------------------------------------------------

class Chip(tk.Canvas):
    """Pílula de filtro (ativa/inativa) ou de legenda (bolinha + nome + valor)."""

    def __init__(self, parent, text, active=False, command=None, dot=None, value=None,
                 bg=None, size=10, icon_name=None):
        self._parent_bg = bg or bg_of(parent)
        super().__init__(parent, bg=self._parent_bg, highlightthickness=0, bd=0,
                         cursor="hand2" if command else "")
        self.text, self.active, self.command = text, active, command
        self.dot, self.value, self.icon_name = dot, value, icon_name
        self._font, self._vfont = font(size, "semibold"), font(size, "bold")
        self._hot = 0.0
        self._chan = motion.Channel()
        self._layout()
        if command:
            self.bind("<Button-1>", lambda e: command())
            self.bind("<Enter>", lambda e: self._animate(1.0))
            self.bind("<Leave>", lambda e: self._animate(0.0))

    def _layout(self):
        w = 14 + measure(self._font, self.text) + 14
        if self.dot:
            w += 14
        if self.icon_name:
            w += 18
        if self.value:
            w += measure(self._vfont, self.value) + 8
        self._width, self._h = w, linespace(self._font) + 14
        self.configure(width=self._width, height=self._h)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self._width, self._h
        if self.active:
            fill, fg = mix(c("surface_alt"), c("text"), 0.16), c("text")
        else:
            fill, fg = mix(c("surface_alt"), c("surface_hi"), self._hot), c("muted")
        if self.dot and not self.command:
            fg = c("text")
        round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, h / 2, fill, c("border") if not self.active else fill)
        x = 14
        if self.dot:
            self.create_oval(x, h / 2 - 4, x + 8, h / 2 + 4, fill=self.dot, outline=self.dot)
            x += 14
        if self.icon_name:
            put_icon(self, x + 7, h / 2, self.icon_name, fg, 12)
            x += 18
        self.create_text(x, h / 2, text=self.text, font=self._font, fill=fg, anchor="w")
        if self.value:
            x += measure(self._font, self.text) + 8
            self.create_text(x, h / 2, text=self.value, font=self._vfont, fill=c("text"), anchor="w")

    def _animate(self, target):
        def step(v):
            self._hot = v
            self._draw()
        self._chan.run(self, self._hot, target, 0.15, "power2.out", step)

    def set_active(self, active):
        self.active = active
        self._draw()


class Badge(tk.Canvas):
    """Pílula pequena colorida (ex.: "+25% vs mês anterior")."""

    TONES = {"lime": "primary", "coral": "coral", "blue": "blue", "neutral": "muted",
             "mint": "mint", "amber": "amber"}

    def __init__(self, parent, text, tone="neutral", bg=None, size=9):
        bg = bg or bg_of(parent)
        f = font(size, "bold")
        w, h = measure(f, text) + 16, linespace(f) + 6
        super().__init__(parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0)
        color = c(self.TONES.get(tone, "muted"))
        if tone == "lime":
            color = c("accent_text")
        round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, h / 2, mix(bg, color, 0.18), mix(bg, color, 0.18))
        self.create_text(w / 2, h / 2, text=text, font=f, fill=color)


def initials(name):
    parts = [p for p in str(name).replace("·", " ").split() if p[:1].isalnum()]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def avatar_color(text):
    palette = c("avatar")
    return palette[sum(ord(ch) for ch in str(text)) % len(palette)]


class AvatarStack(tk.Canvas):
    """Círculos sobrepostos com iniciais. items: [texto ou (texto, cor)]."""

    def __init__(self, parent, items, size=26, overlap=9, bg=None, limit=3):
        bg = bg or bg_of(parent)
        items = list(items)[:limit]
        w = size + max(len(items) - 1, 0) * (size - overlap) + 2
        super().__init__(parent, width=w, height=size + 2, bg=bg, highlightthickness=0, bd=0)
        f = font(max(int(size * 0.36), 8), "bold")
        for i, item in enumerate(items):
            text, color = item if isinstance(item, tuple) else (item, avatar_color(item))
            x = 1 + i * (size - overlap)
            self.create_oval(x, 1, x + size, 1 + size, fill=color, outline=bg, width=2)
            self.create_text(x + size / 2, 1 + size / 2, text=initials(text), font=f, fill="#15120F")


class Avatar(AvatarStack):
    def __init__(self, parent, text, size=44, bg=None, color=None):
        super().__init__(parent, [(text, color or avatar_color(text))], size=size, bg=bg)


class Star(tk.Canvas):
    """Estrela: preenchida em verde-limão (destaque) ou só contorno."""

    def __init__(self, parent, filled=False, size=18, bg=None):
        bg = bg or bg_of(parent)
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        pts = star_points(size / 2, size / 2 + 0.5, size / 2 - 1.5)
        color = c("primary") if filled else c("faint")
        self.create_polygon(pts, fill=color if filled else bg, outline=color, width=1.4,
                            joinstyle="round")


# ----------------------------------------------------------------------
# Seletor em pílula (substitui o combobox nas barras de filtro)
# ----------------------------------------------------------------------

class PillSelect(tk.Canvas):
    """Pílula com o item atual e uma seta; abre um menu. Mesma interface do
    ChoiceCombo: set_items, get_id, set_id, current e <<ComboboxSelected>>."""

    def __init__(self, parent, items=(), allow_empty=None, icon_name=None, bg=None,
                 max_width=220, prefix=None):
        self._parent_bg = bg or bg_of(parent)
        super().__init__(parent, bg=self._parent_bg, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self._empty = allow_empty
        self._icon = icon_name
        self._prefix = prefix
        self._max = max_width
        self._ids, self._texts, self._index = [], [], -1
        self._font = font(11, "semibold")
        self._hot = 0.0
        self._chan = motion.Channel()
        self.bind("<Button-1>", lambda e: self.open())
        self.bind("<Return>", lambda e: self.open())
        self.bind("<Enter>", lambda e: self._animate(1.0))
        self.bind("<Leave>", lambda e: self._animate(0.0))
        self.set_items(items)

    def set_items(self, items, keep=True):
        previous = self.get_id() if keep else None
        entries = list(items)
        if self._empty is not None:
            entries = [(None, self._empty)] + entries
        self._ids = [i for i, _ in entries]
        self._texts = [text for _, text in entries]
        if previous in self._ids and keep:
            self._index = self._ids.index(previous)
        else:
            self._index = 0 if entries else -1
        self._draw()

    def get_id(self):
        return self._ids[self._index] if 0 <= self._index < len(self._ids) else None

    def set_id(self, value):
        if value in self._ids:
            self._index = self._ids.index(value)
            self._draw()

    def current(self, index=None):
        if index is None:
            return self._index
        if 0 <= index < len(self._ids):
            self._index = index
            self._draw()

    def _label(self):
        text = self._texts[self._index] if 0 <= self._index < len(self._texts) else ""
        return f"{self._prefix} {text}" if self._prefix else text

    def _draw(self):
        self.delete("all")
        text = self._label()
        while text and measure(self._font, text) > self._max and len(text) > 4:
            text = text[:-2].rstrip() + "…" if not text.endswith("…") else text[:-2] + "…"
        left = 16 + (20 if self._icon else 0)
        w = left + measure(self._font, text) + 34
        h = linespace(self._font) + 16
        self.configure(width=w, height=h)
        fill = mix(c("surface_alt"), c("surface_hi"), self._hot)
        round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, h / 2, fill, c("border"))
        if self._icon:
            put_icon(self, 24, h / 2, self._icon, c("muted"), 13)
        self.create_text(left, h / 2, text=text, font=self._font, fill=c("text"), anchor="w")
        put_icon(self, w - 18, h / 2 + 1, "chevron-down", c("muted"), 13)

    def _animate(self, target):
        def step(v):
            self._hot = v
            self._draw()
        self._chan.run(self, self._hot, target, 0.15, "power2.out", step)

    def open(self):
        menu = tk.Menu(self, tearoff=0)
        var = tk.IntVar(value=self._index)
        for i, text in enumerate(self._texts):
            menu.add_radiobutton(label=text, variable=var, value=i,
                                 command=lambda i=i: self._choose(i))
        try:
            menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + 4)
        finally:
            menu.grab_release()

    def _choose(self, index):
        self._index = index
        self._draw()
        self.event_generate("<<ComboboxSelected>>")


# ----------------------------------------------------------------------
# Campo de busca em pílula
# ----------------------------------------------------------------------

class SearchField(tk.Canvas):
    def __init__(self, parent, variable=None, placeholder="", width=280, bg=None):
        self._parent_bg = bg or bg_of(parent)
        self.var = variable or tk.StringVar()
        f = font(11)
        h = linespace(f) + 18
        super().__init__(parent, width=width, height=h, bg=self._parent_bg,
                         highlightthickness=0, bd=0, cursor="xterm")
        self._h = h
        fill = c("surface_alt")
        self._fill = fill
        self.entry = tk.Entry(self, textvariable=self.var, font=f, bg=fill, fg=c("text"),
                              insertbackground=c("text"), relief="flat", bd=0,
                              highlightthickness=0, selectbackground=c("select"),
                              selectforeground=c("text"))
        self._ph = tk.Label(self, text=placeholder, font=f, bg=fill, fg=c("faint"), anchor="w",
                            cursor="xterm")
        self._win = self.create_window(38, h / 2, window=self.entry, anchor="w")
        self._phwin = self.create_window(38, h / 2, window=self._ph, anchor="w")
        self.bind("<Configure>", self._draw)
        for w in (self, self._ph):
            w.bind("<Button-1>", lambda e: self.focus())
        self.entry.bind("<FocusIn>", lambda e: self._sync(True))
        self.entry.bind("<FocusOut>", lambda e: self._sync(False))
        self.entry.bind("<Escape>", lambda e: self.var.set(""))
        self.var.trace_add("write", lambda *a: self._sync(self.focus_get() is self.entry))
        self._focused = False
        self._sync(False)

    def _draw(self, _e=None):
        w, h = self.winfo_width(), self._h
        self.delete("bg")
        border = c("primary") if self._focused else c("border")
        round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, h / 2, self._fill, border, tags="bg")
        put_icon(self, 21, h / 2, "search", c("muted"), 14, tags="bg")
        self.tag_lower("bg")
        self.itemconfigure(self._win, width=max(w - 52, 20))
        self.itemconfigure(self._phwin, width=max(w - 52, 20))

    def _sync(self, focused):
        self._focused = focused
        if self.var.get() or focused:
            self.itemconfigure(self._phwin, state="hidden")
        else:
            self.itemconfigure(self._phwin, state="normal")
        self._draw()

    def focus(self):
        self.entry.focus_set()
        self.entry.select_range(0, "end")

    def get(self):
        return self.var.get()


# ----------------------------------------------------------------------
# Switch
# ----------------------------------------------------------------------

class Toggle(tk.Canvas):
    def __init__(self, parent, value=False, command=None, bg=None, color="blue", tooltip=None):
        bg = bg or bg_of(parent)
        super().__init__(parent, width=38, height=22, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.value, self.command, self.color = bool(value), command, color
        self._pos = 1.0 if self.value else 0.0
        self._chan = motion.Channel()
        self.bind("<Button-1>", lambda e: self.toggle())
        self.bind("<space>", lambda e: self.toggle())
        if tooltip:
            Tooltip(self, tooltip)
        self._draw()

    def _draw(self):
        self.delete("all")
        fill = mix(c("surface_hi"), c(self.color), self._pos)
        round_rect(self, 1, 1, 37, 21, 10, fill, fill)
        x = 11 + 16 * self._pos
        self.create_oval(x - 8, 3, x + 8, 19, fill=c("text") if self._pos > 0.5 else c("muted"),
                         outline="")

    def toggle(self):
        self.value = not self.value

        def step(v):
            self._pos = v
            self._draw()
        self._chan.run(self, self._pos, 1.0 if self.value else 0.0, 0.22, "power3.out", step)
        if self.command:
            self.command(self.value)

    def get(self):
        return self.value


# ----------------------------------------------------------------------
# Seletor de mês em pílula
# ----------------------------------------------------------------------

class MonthSwitcher(tk.Canvas):
    """‹ novembro 2026 › — clique no nome volta para o mês atual."""

    def __init__(self, parent, on_change, bg=None, month=None):
        self._parent_bg = bg or bg_of(parent)
        super().__init__(parent, bg=self._parent_bg, highlightthickness=0, bd=0)
        self.month = month or formatters.current_month()
        self.on_change = on_change
        self._font = font(11, "semibold")
        widest = max(measure(self._font, formatters.month_label(f"2026-{m:02d}")) for m in range(1, 13))
        self._width = 36 + widest + 36 + 16
        self._h = linespace(self._font) + 18
        self.configure(width=self._width, height=self._h)
        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", self._motion)
        Tooltip(self, lambda: formatters.month_label(formatters.current_month()))
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self._width, self._h
        round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, h / 2, c("surface_alt"), c("border"))
        put_icon(self, 22, h / 2, "chevron-left", c("text"), 15)
        put_icon(self, w - 22, h / 2, "chevron-right", c("text"), 15)
        self.create_text(w / 2, h / 2, text=formatters.month_label(self.month),
                         font=self._font, fill=c("text"))

    def _motion(self, e):
        self.configure(cursor="hand2")

    def _click(self, e):
        if e.x < 40:
            self.set(formatters.shift_month(self.month, -1))
        elif e.x > self._width - 40:
            self.set(formatters.shift_month(self.month, 1))
        else:
            self.set(formatters.current_month())

    def set(self, month):
        self.month = month
        self._draw()
        self.on_change()


# ----------------------------------------------------------------------
# Popover (painel flutuante)
# ----------------------------------------------------------------------

class Popover:
    """Painel de vidro flutuante abaixo de um widget; fecha com Esc ou
    clicando fora."""

    current = None

    def __init__(self, anchor, width=320, align="right"):
        Popover.close_all()
        self.anchor = anchor
        root = anchor.winfo_toplevel()
        self.root = root
        self.card = Card(root, padx=18, pady=16, fill=c("surface_alt"))
        self.body = self.card.body
        self.width = width
        x = anchor.winfo_rootx() - root.winfo_rootx()
        y = anchor.winfo_rooty() - root.winfo_rooty() + anchor.winfo_height() + 8
        if align == "right":
            x = x + anchor.winfo_width() - width
        self.card.place(x=max(x, 8), y=y, width=width)
        self.card.lift()
        Popover.current = self
        self._bind = root.bind_all("<Button-1>", self._outside, add="+")
        root.bind_all("<Escape>", lambda e: self.close(), add="+")

    def _outside(self, e):
        if Popover.current is not self:
            return
        if not pointer_inside(self.card) and not pointer_inside(self.anchor):
            self.card.after(1, self.close)

    def close(self):
        if Popover.current is self:
            Popover.current = None
        try:
            self.root.unbind_all("<Button-1>")
            self.root.unbind_all("<Escape>")
            self.card.destroy()
        except tk.TclError:
            pass

    @classmethod
    def close_all(cls):
        if cls.current is not None:
            cls.current.close()
