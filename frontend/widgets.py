"""Componentes visuais reutilizáveis: botões em pílula, cards de vidro, ícones
(fonte Lucide), segmented control, campos, tabela, estados vazios e avisos."""
from PIL import Image, ImageDraw, ImageTk
import calendar
import tkinter as tk
import tkinter.font as tkfont
from datetime import date
from tkinter import ttk

from frontend import motion
from frontend.draw import round_rect
from frontend.theme import c, font, has_icons, icon, icon_font, mix
from backend.utils import formatters
from backend.utils.i18n import t


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------

_FONTS = {}


def _font_obj(spec):
    # a chave inclui a janela Tk atual: fontes de uma janela destruída não servem
    key = (spec, id(tk._default_root))
    obj = _FONTS.get(key)
    if obj is None:
        if len(_FONTS) > 200:
            _FONTS.clear()
        obj = _FONTS[key] = tkfont.Font(font=spec)
    return obj


def measure(spec, text):
    """Largura do texto em pixels com a fonte ``spec``."""
    return _font_obj(spec).measure(text)


def linespace(spec):
    return _font_obj(spec).metrics("linespace")


def bg_of(widget, fallback="bg"):
    try:
        return widget.cget("bg")
    except tk.TclError:
        return c(fallback)


def pointer_inside(widget):
    try:
        x, y = widget.winfo_pointerxy()
        rx, ry = widget.winfo_rootx(), widget.winfo_rooty()
        return rx <= x < rx + widget.winfo_width() and ry <= y < ry + widget.winfo_height()
    except tk.TclError:
        return False


# ----------------------------------------------------------------------
# Ícones: fonte Lucide quando disponível; desenho simples como reserva
# ----------------------------------------------------------------------

def draw_icon(canvas, name, color, s=20):
    w = 2
    k = s / 20
    d = canvas.create_line
    r = canvas.create_rectangle
    o = canvas.create_oval
    if name == "dashboard":
        for x, y, ww, hh in ((2, 2, 7, 9), (11, 2, 7, 5), (2, 13, 7, 5), (11, 9, 7, 9)):
            r(x * k, y * k, (x + ww) * k, (y + hh) * k, outline=color, width=w)
    elif name == "list":
        for y in (5, 10, 15):
            d(7 * k, y * k, 18 * k, y * k, fill=color, width=w, capstyle="round")
            o(2 * k, (y - 1) * k, 4 * k, (y + 1) * k, fill=color, outline=color)
    elif name == "wallet":
        r(2 * k, 5 * k, 18 * k, 16 * k, outline=color, width=w)
        d(2 * k, 8 * k, 18 * k, 8 * k, fill=color, width=w)
        o(13 * k, 11 * k, 15.5 * k, 13.5 * k, fill=color, outline=color)
    elif name == "target":
        o(2 * k, 2 * k, 18 * k, 18 * k, outline=color, width=w)
        o(6 * k, 6 * k, 14 * k, 14 * k, outline=color, width=w)
        o(9 * k, 9 * k, 11 * k, 11 * k, fill=color, outline=color)
    elif name == "chart":
        for x, h in ((3, 7), (9, 12), (15, 9)):
            r(x * k, (18 - h) * k, (x + 3) * k, 18 * k, fill=color, outline=color)
    elif name == "repeat":
        canvas.create_arc(3 * k, 3 * k, 17 * k, 17 * k, start=30, extent=240,
                          style="arc", outline=color, width=w)
        canvas.create_polygon(14 * k, 1 * k, 19 * k, 6 * k, 12 * k, 7 * k, fill=color, outline=color)
    elif name in ("plus",):
        d(10 * k, 4 * k, 10 * k, 16 * k, fill=color, width=w + 1, capstyle="round")
        d(4 * k, 10 * k, 16 * k, 10 * k, fill=color, width=w + 1, capstyle="round")
    elif name == "search":
        o(3 * k, 3 * k, 13 * k, 13 * k, outline=color, width=w)
        d(12 * k, 12 * k, 17 * k, 17 * k, fill=color, width=w + 1, capstyle="round")
    else:
        o(4 * k, 4 * k, 16 * k, 16 * k, outline=color, width=w)


def put_icon(canvas, x, y, name, color, size=18, tags=()):
    """Desenha o ícone centrado em (x, y) dentro de um canvas existente."""
    glyph = icon(name)
    if has_icons() and glyph:
        return canvas.create_text(x, y, text=glyph, font=icon_font(size), fill=color, tags=tags)
    r = size * 0.32
    return canvas.create_oval(x - r, y - r, x + r, y + r, outline=color, width=2, tags=tags)


class Icon(tk.Canvas):
    def __init__(self, parent, name, color, bg, size=20):
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self.name, self.size = name, size
        self.set_color(color, bg)

    def set_color(self, color, bg):
        self.configure(bg=bg)
        self.delete("all")
        if has_icons() and icon(self.name):
            self.create_text(self.size / 2, self.size / 2, text=icon(self.name),
                             font=icon_font(max(int(self.size * 0.82), 8)), fill=color)
        else:
            draw_icon(self, self.name, color, self.size)


# ----------------------------------------------------------------------
# Botões
# ----------------------------------------------------------------------

class Button(tk.Canvas):
    """Botão em pílula (cantos totalmente arredondados), com ícone opcional.
    É desenhado em canvas porque tk.Button ignora cores no macOS."""

    KINDS = {
        "primary": ("primary", "primary_hover", "primary_text", None),
        "danger": ("danger", "danger_hover", "primary_text", None),
        "secondary": ("surface_alt", "surface_hi", "text", "border"),
        "ghost": (None, "surface_alt", "muted", None),
    }

    def __init__(self, parent, text, command=None, kind="secondary", icon=None,
                 pad=(16, 9), parent_bg=None, size=11):
        bg_key, hover_key, fg_key, border = self.KINDS[kind]
        self._parent_bg = parent_bg or bg_of(parent)
        self._bg = c(bg_key) if bg_key else self._parent_bg
        self._hover = c(hover_key)
        self._border = c(border) if border else None
        self._fg = c(fg_key)
        self.kind = kind
        super().__init__(parent, bg=self._parent_bg, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.command = command
        self.enabled = True
        self._focused = False
        self._hot = 0.0
        self._pad = pad
        self._text = text or ""
        self._icon = icon
        self._font = font(size, "semibold")
        self._ifont = icon_font(size + 4)
        self._fade = motion.Channel()
        self._layout()
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self.bind("<Return>", self._click)
        self.bind("<space>", self._click)
        self.bind("<FocusIn>", lambda e: self._set_focus(True))
        self.bind("<FocusOut>", lambda e: self._set_focus(False))

    def _layout(self):
        tw = measure(self._font, self._text) if self._text else 0
        glyph = icon(self._icon) if self._icon and has_icons() else ""
        iw = measure(self._ifont, glyph) if glyph else 0
        gap = 7 if (iw and tw) else 0
        self._metrics = (glyph, iw, gap, tw)
        height = linespace(self._font) + 2 * self._pad[1]
        width = self._pad[0] * 2 + iw + gap + tw
        if not tw:  # só ícone: botão redondo
            width = height
        self.configure(width=width, height=height)

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            w, h = int(self["width"]), int(self["height"])
        fill = mix(self._bg, self._hover, self._hot) if self.enabled else self._bg
        outline = c("primary") if self._focused else (self._border or fill)
        round_rect(self, 1, 1, w - 1, h - 1, (h - 2) / 2, fill, outline, 1.5 if self._focused else 1)
        fg = self._fg if self.enabled else c("faint")
        glyph, iw, gap, tw = self._metrics
        x = (w - (iw + gap + tw)) / 2
        if glyph:
            self.create_text(x + iw / 2, h / 2, text=glyph, font=self._ifont, fill=fg)
        x += iw + gap
        if tw:
            self.create_text(x, h / 2, text=self._text, font=self._font, fill=fg, anchor="w")

    def _animate(self, target):
        def step(value):
            self._hot = value
            self._draw()
        self._fade.run(self, self._hot, target, 0.16, "power2.out", step)

    def _enter(self, _e):
        if self.enabled:
            self._animate(1.0)

    def _leave(self, _e):
        self._animate(0.0)

    def _set_focus(self, on):
        self._focused = on
        self._draw()

    def _click(self, _e=None):
        if self.enabled and self.command:
            self.command()
        return "break"

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_text(self, text):
        self._text = text or ""
        self._layout()
        self._draw()


_RR_CACHE = {}  # "gaveta" de imagens já prontas (cache)


def rounded_image(w, h, radius, fill, outline, bg, master, S=4):
    """Retângulo arredondado suavizado como imagem (fundo ``bg`` nos cantos)."""
    key = (id(master.tk), w, h, radius, fill, outline, bg)
    if key in _RR_CACHE:
        return _RR_CACHE[key]
    img = Image.new("RGBA", (w * S, h * S), bg)
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, w * S - 1, h * S - 1), radius=radius * S, fill=fill,
        outline=outline, width=S if outline else 0)
    img = img.resize((w, h), Image.LANCZOS)
    photo = ImageTk.PhotoImage(img, master=master)
    _RR_CACHE[key] = photo
    return photo


# ----------------------------------------------------------------------
# Card de vidro
# ----------------------------------------------------------------------

class Card(tk.Canvas):
    """Card de vidro: cantos bem arredondados, borda clara fina, sem sombra.
    O conteúdo vai em ``.body``. Com ``hover=True`` o card sobe levemente e a
    borda ganha brilho com o mouse por cima."""

    RADIUS = 24
    LIFT = 3

    def __init__(self, parent, padx=22, pady=20, fill=None, hover=False, radius=None,
                 border=None, **kw):
        self._parent_bg = bg_of(parent)
        super().__init__(parent, bg=self._parent_bg, highlightthickness=0, bd=0, **kw)
        self.fill = fill or c("surface")
        self._border = border or (mix(self.fill, c("text"), 0.08) if fill else c("border"))
        self._radius = radius or self.RADIUS
        self._padx, self._pady = padx, pady
        self._space = self.LIFT if hover else 0
        self._lift = 0.0
        self._size = (0, 0)
        self.body = tk.Frame(self, bg=self.fill)
        self._win = self.create_window(padx, pady + self._space, window=self.body, anchor="nw")
        self.bind("<Configure>", self._on_configure)
        self.body.bind("<Configure>", self._fit)
        self._watch = None
        if hover:
            self._chan = motion.Channel()
            for w in (self, self.body):
                w.bind("<Enter>", self._enter, add="+")

    def _fit(self, _e=None):
        self.configure(width=self.body.winfo_reqwidth() + 2 * self._padx,
                       height=self.body.winfo_reqheight() + 2 * self._pady + self._space)

    def _on_configure(self, e):
        self._size = (e.width, e.height)
        # o conteúdo ocupa todo o card (não só a altura pedida)
        self.itemconfigure(self._win, width=max(e.width - 2 * self._padx, 1),
                           height=max(e.height - 2 * self._pady - self._space, 1))
        self._draw()

    def _draw(self):
        w, h = self._size
        if w < 4 or h < 4:
            return
        off = self._space * (1 - self._lift)
        self.delete("bg")
        border = mix(self._border, c("border_hi"), self._lift)
        round_rect(self, 1, 1 + off, w - 1, h - 1 - self._space + off, self._radius,
                   self.fill, border, 1, tags="bg")
        self.tag_lower("bg")
        self.coords(self._win, self._padx, self._pady + off)

    def _set_lift(self, value):
        self._lift = value
        self._draw()

    def _enter(self, _e=None):
        if self._watch is None:
            self._chan.run(self, self._lift, 1.0, 0.2, "power2.out", self._set_lift)
            self._watch = self.after(120, self._poll)

    def _poll(self):
        self._watch = None
        if pointer_inside(self):
            self._watch = self.after(120, self._poll)
        else:
            self._chan.run(self, self._lift, 0.0, 0.25, "power2.out", self._set_lift)


def label(parent, text="", size=11, weight="normal", color="text", bg="surface", **kw):
    return tk.Label(parent, text=text, bg=c(bg) if not bg.startswith("#") else bg,
                    fg=c(color) if not color.startswith("#") else color,
                    font=font(size, weight), anchor=kw.pop("anchor", "w"), **kw)


def separator(parent, bg="border"):
    return tk.Frame(parent, bg=c(bg), height=1)


class ScrollFrame(tk.Frame):
    """Área rolável vertical, sem barra visível (use a roda do mouse ou o
    trackpad); o conteúdo acompanha a largura da janela."""

    def __init__(self, parent, bg=None):
        bg = bg or c("bg")
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<Enter>", lambda e: self._bind_wheel(True))
        self.canvas.bind("<Leave>", lambda e: self._bind_wheel(False))
        self.inner.bind("<Enter>", lambda e: self._bind_wheel(True))

    def _on_inner(self, _e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)

    def _bind_wheel(self, on):
        top = self.winfo_toplevel()
        if on:
            top.bind_all("<MouseWheel>", self._wheel)
            top.bind_all("<Button-4>", self._wheel)
            top.bind_all("<Button-5>", self._wheel)
        else:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                top.unbind_all(seq)

    def _wheel(self, e):
        if self.inner.winfo_reqheight() <= self.canvas.winfo_height():
            return  # conteúdo cabe na tela: nada para rolar
        if e.num == 4:
            step = -2
        elif e.num == 5:
            step = 2
        else:
            step = -int(e.delta / 120) * 2 if abs(e.delta) >= 120 else (-1 if e.delta > 0 else 1)
        self.canvas.yview_scroll(step, "units")


# ----------------------------------------------------------------------
# Campos
# ----------------------------------------------------------------------

def entry(parent, textvariable=None, width=None):
    e = ttk.Entry(parent, textvariable=textvariable, width=width or 20, font=font(11))
    return e


def combo(parent, values, variable=None, width=22):
    cb = ttk.Combobox(parent, values=values, textvariable=variable,
                      state="readonly", width=width, font=font(11))
    return cb


def _wheel_date(current, component, step, preferred_day):
    """Move um componente da data e mantém dia/mês/ano sempre válidos."""
    if component == "day":
        days = calendar.monthrange(current.year, current.month)[1]
        day = (current.day - 1 + step) % days + 1
        return current.replace(day=day), day

    if component == "month":
        index = current.year * 12 + current.month - 1 + step
        index = min(max(index, 12), 9999 * 12 + 11)
        year, month_index = divmod(index, 12)
        month = month_index + 1
    elif component == "year":
        year = min(max(current.year + step, 1), 9999)
        month = current.month
    else:
        raise ValueError("Componente de data inválido.")

    day = min(preferred_day, calendar.monthrange(year, month)[1])
    return date(year, month, day), preferred_day


class WheelDatePopup(tk.Toplevel):
    """Seletor de data em três colunas ajustáveis pela roda do mouse."""

    def __init__(self, anchor, current, on_pick):
        super().__init__(anchor)
        self.withdraw()
        self.transient(anchor.winfo_toplevel())
        self.configure(bg=c("border"))
        self.current = current
        self.preferred_day = current.day
        self.on_pick = on_pick
        self.previous_grab = self.grab_current()
        self.body = tk.Frame(self, bg=c("surface"), padx=18, pady=16)
        self.body.pack(padx=1, pady=1)

        tk.Label(self.body, text=t("calendar.choose_date"), bg=c("surface"),
                 fg=c("text"), font=font(13, "bold")).pack(anchor="w")
        tk.Label(
            self.body, text=t("calendar.wheel_hint"),
            bg=c("surface"), fg=c("muted"), font=font(9)
        ).pack(anchor="w", pady=(3, 12))

        wheels = tk.Frame(self.body, bg=c("surface"))
        wheels.pack(fill="x")
        self.values = {}
        for component, title, width in (
            ("day", t("calendar.day"), 5),
            ("month", t("calendar.month"), 7),
            ("year", t("calendar.year"), 7),
        ):
            column = tk.Frame(wheels, bg=c("surface"), padx=5)
            column.pack(side="left", expand=True, fill="x")
            tk.Label(column, text=title, bg=c("surface"), fg=c("muted"),
                     font=font(8, "bold")).pack(pady=(0, 5))
            previous = tk.Label(column, width=width, bg=c("surface"),
                                fg=c("muted"), font=font(10), pady=4)
            previous.pack()
            selected = tk.Label(
                column, width=width, bg=c("primary_soft"), fg=c("primary"),
                font=font(15, "bold"), pady=7, highlightthickness=1,
                highlightbackground=c("border")
            )
            selected.pack()
            following = tk.Label(column, width=width, bg=c("surface"),
                                 fg=c("muted"), font=font(10), pady=4)
            following.pack()
            self.values[component] = (previous, selected, following)
            for widget in (column, previous, selected, following):
                widget.bind(
                    "<MouseWheel>",
                    lambda event, cpt=component: self._on_wheel(event, cpt)
                )
                widget.bind(
                    "<Button-4>",
                    lambda event, cpt=component: self._step(cpt, -1)
                )
                widget.bind(
                    "<Button-5>",
                    lambda event, cpt=component: self._step(cpt, 1)
                )
            previous.configure(cursor="hand2")
            following.configure(cursor="hand2")
            previous.bind("<Button-1>", lambda _event, cpt=component: self._step(cpt, -1))
            following.bind("<Button-1>", lambda _event, cpt=component: self._step(cpt, 1))

        footer = tk.Frame(self.body, bg=c("surface"))
        footer.pack(fill="x", pady=(14, 0))
        Button(footer, t("common.cancel"), self.close, "secondary", pad=(12, 6)).pack(side="right")
        Button(footer, t("common.use_date"), self._confirm, "primary", pad=(12, 6)).pack(
            side="right", padx=(0, 8)
        )

        self._render()
        self.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = min(max(x, 0), max(screen_width - self.winfo_reqwidth(), 0))
        if y + self.winfo_reqheight() > screen_height:
            y = max(anchor.winfo_rooty() - self.winfo_reqheight() - 4, 0)
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.grab_set()
        self.focus_set()
        self.bind("<Escape>", lambda _event: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        previous = self.previous_grab
        self.destroy()
        if previous is not None:
            try:
                if previous.winfo_exists():
                    previous.grab_set()
            except tk.TclError:
                pass

    def _on_wheel(self, event, component):
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self._step(component, step)
        return "break"

    def _step(self, component, step):
        self.current, self.preferred_day = _wheel_date(
            self.current, component, step, self.preferred_day
        )
        self._render()
        return "break"

    def _render(self):
        day_text = lambda value: f"{value:02d}"
        month_text = lambda value: t(f"format.months_abbr.{value}")
        formatters_for = {
            "day": day_text, "month": month_text, "year": str,
        }
        values = {
            "day": self.current.day,
            "month": self.current.month,
            "year": self.current.year,
        }
        for component, (previous, selected, following) in self.values.items():
            value = values[component]
            fmt = formatters_for[component]
            before, _ = _wheel_date(self.current, component, -1, self.preferred_day)
            after, _ = _wheel_date(self.current, component, 1, self.preferred_day)
            before_value = getattr(before, component)
            after_value = getattr(after, component)
            previous.configure(text=fmt(before_value))
            selected.configure(text=fmt(value))
            following.configure(text=fmt(after_value))

    def _confirm(self):
        self.on_pick(self.current)
        self.close()


class DateField(tk.Frame):
    """Data escolhida em um seletor rolável de dia, mês e ano."""

    def __init__(self, parent, initial=None, bg=None, width=12, optional=False):
        super().__init__(parent, bg=bg or c("surface"))
        self._optional = optional
        self._selected = (
            date.fromisoformat(formatters.parse_date(initial))
            if initial else None if optional else date.today()
        )
        self._display = tk.Frame(
            self, bg=c("surface"), highlightthickness=1,
            highlightbackground=c("border"), cursor="hand2"
        )
        self._display.pack(side="left")
        self._date_label = tk.Label(
            self._display, text="", bg=c("surface"), fg=c("text"),
            font=font(11), width=width, anchor="w", padx=9, pady=7,
            cursor="hand2"
        )
        self._date_label.pack(side="left")
        self._icon = tk.Label(
            self._display, text="▦", bg=c("surface"), fg=c("muted"),
            font=font(12), padx=8, cursor="hand2"
        )
        self._icon.pack(side="left")
        for widget in (self, self._display, self._date_label, self._icon):
            widget.bind("<Button-1>", lambda _event: self.open_picker())
            widget.bind("<Return>", lambda _event: self.open_picker())
        self._clear_label = None
        if optional:
            self._clear_label = tk.Label(
                self, text=t("calendar.clear"), bg=bg or c("surface"), fg=c("muted"),
                font=font(9), cursor="hand2", padx=5
            )
            self._clear_label.pack(side="left")
            self._clear_label.bind("<Button-1>", lambda _event: self.clear())
        self._render()

    def open_picker(self):
        return WheelDatePopup(
            self._display, self._selected or date.today(), self._set_date
        )

    def _set_date(self, selected):
        self._selected = selected
        self._render()
        self.event_generate("<<DateChanged>>")

    def _render(self):
        self._date_label.configure(
            text=formatters.format_date(self._selected.isoformat())
            if self._selected else t("common.select_date"),
            fg=c("text") if self._selected else c("muted")
        )

    def get(self):
        return formatters.format_date(self._selected.isoformat()) if self._selected else ""

    def set_iso(self, iso):
        self._selected = date.fromisoformat(formatters.parse_date(iso))
        self._render()

    def clear(self):
        if not self._optional:
            raise ValueError(t("validation.date_required"))
        self._selected = None
        self._render()
        self.event_generate("<<DateChanged>>")

    def get_iso(self):
        if self._selected is None:
            raise ValueError(t("calendar.choose_date"))
        return formatters.parse_date(self.get())


# ----------------------------------------------------------------------
# Tabela
# ----------------------------------------------------------------------

class SortableTree(tk.Frame):
    """Tabela com cabeçalhos clicáveis (ordenação feita no banco), sem barra
    de rolagem visível (use a roda do mouse ou o trackpad).
    columns: [(id, título, largura, anchor, ordenável)]."""

    def __init__(self, parent, columns, on_sort=None, on_open=None, height=14):
        super().__init__(parent, bg=c("surface"))
        self.columns = columns
        self.on_sort = on_sort
        self.sort_key, self.descending = None, True
        ids = [col[0] for col in columns]
        self.tree = ttk.Treeview(self, columns=ids, show="headings",
                                 selectmode="browse", height=height)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        for cid, title, width, anchor, sortable in columns:
            self.tree.heading(cid, text=title, anchor=anchor if anchor != "e" else "e",
                              command=(lambda k=cid: self._sort(k)) if sortable and on_sort else "")
            self.tree.column(cid, width=width, anchor=anchor, stretch=cid == columns[1][0] or cid == columns[0][0] and len(columns) == 1)
        self.tree.tag_configure("odd", background=c("stripe"))
        self.tree.tag_configure("income", foreground=c("income"))
        self.tree.tag_configure("expense", foreground=c("expense"))
        self.tree.tag_configure("muted", foreground=c("muted"))
        if on_open:
            self.tree.bind("<Double-1>", lambda e: on_open())
            self.tree.bind("<Return>", lambda e: on_open())

    def mark_sort(self, key, descending):
        self.sort_key, self.descending = key, descending
        for cid, title, *_ in self.columns:
            arrow = (" ▼" if descending else " ▲") if cid == key else ""
            self.tree.heading(cid, text=title + arrow)

    def _sort(self, key):
        descending = (not self.descending) if key == self.sort_key else key in ("date", "amount")
        self.mark_sort(key, descending)
        self.on_sort(key, descending)

    def clear(self):
        self.tree.delete(*self.tree.get_children())

    def add(self, iid, values, tags=()):
        index = len(self.tree.get_children())
        extra = ("odd",) if index % 2 else ()
        self.tree.insert("", "end", iid=str(iid), values=values, tags=tuple(tags) + extra)

    def selected(self):
        sel = self.tree.selection()
        return sel[0] if sel else None


# ----------------------------------------------------------------------
# Estados vazios e avisos
# ----------------------------------------------------------------------

class EmptyState(tk.Frame):
    def __init__(self, parent, icon_name, title, text, action_text=None, action=None, bg=None):
        bg = bg or bg_of(parent, "surface")
        super().__init__(parent, bg=bg, height=280)
        box = tk.Frame(self, bg=bg)
        box.place(relx=0.5, rely=0.48, anchor="center")
        ring = tk.Canvas(box, width=68, height=68, bg=bg, highlightthickness=0, bd=0)
        ring.create_oval(2, 2, 66, 66, fill=c("surface_alt"), outline=c("border"))
        put_icon(ring, 34, 34, icon_name, c("accent_text"), 24)
        ring.pack()
        tk.Label(box, text=title, bg=bg, fg=c("text"), font=font(15, "semibold")).pack(pady=(16, 4))
        tk.Label(box, text=text, bg=bg, fg=c("muted"), font=font(11),
                 justify="center", wraplength=380).pack()
        if action_text:
            Button(box, action_text, action, "primary", icon="plus").pack(pady=(18, 0))


class Toasts:
    """Mensagens rápidas em pílula no rodapé; podem ter ação (Desfazer)."""

    ICONS = {"success": ("circle-check", "primary"), "error": ("circle-alert", "danger"),
             "info": ("info", "blue")}

    def __init__(self, root):
        self.root = root
        self.current = None
        self._after = None

    def show(self, text, kind="info", action_text=None, action=None, ms=5000):
        self.dismiss()
        root = self.root
        fill, fg = c("toast"), c("toast_text")
        glyph, accent = self.ICONS.get(kind, self.ICONS["info"])
        body_font, bold = font(11, "medium"), font(11, "bold")
        wrap = 520
        text_w = min(measure(body_font, text), wrap)
        rows = max(1, -(-measure(body_font, text) // wrap))
        line_h = linespace(body_font)
        action_w = measure(bold, action_text) + 28 if action_text else 0
        w = 18 + 26 + text_w + action_w + 22
        h = max(46, rows * line_h + 24)
        canvas = tk.Canvas(root, width=w, height=h, highlightthickness=0, bd=0, bg=c("bg"))
        x_root = root.winfo_rootx() + root.winfo_width() // 2
        y_root = root.winfo_rooty() + root.winfo_height() - 30 - h // 2
        under = root.winfo_containing(x_root - w // 2 + 4, y_root - h // 2 + 4)
        canvas.configure(bg=bg_of(under) if under is not None else c("bg"))
        round_rect(canvas, 1, 1, w - 1, h - 1, min(h / 2, 23), fill, mix(fill, c("text"), 0.1))
        put_icon(canvas, 18 + 10, h / 2, glyph, c(accent), 16)
        canvas.create_text(18 + 26, h / 2, text=text, font=body_font, fill=fg, anchor="w", width=wrap)
        if action_text:
            ax = 18 + 26 + text_w + 18
            canvas.create_text(ax, h / 2, text=action_text, font=bold, fill=c("primary"),
                               anchor="w", tags="action")

            def run(_e=None):
                self.dismiss()
                action()
            canvas.tag_bind("action", "<Button-1>", run)
            canvas.tag_bind("action", "<Enter>", lambda e: canvas.configure(cursor="hand2"))
            canvas.tag_bind("action", "<Leave>", lambda e: canvas.configure(cursor=""))
        canvas.place(relx=0.5, rely=1.0, anchor="s", y=-12)
        tk.Misc.lift(canvas)  # Canvas.lift move itens; aqui queremos o widget
        self.current = canvas
        motion.tween(canvas, 18, 0, 0.32, "power3.out",
                     lambda v: canvas.place_configure(y=-24 + v) if canvas.winfo_exists() else None)
        self._after = root.after(ms if kind != "error" else max(ms, 8000), self.dismiss)

    def dismiss(self):
        if self._after:
            try:
                self.root.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None
        if self.current is not None:
            try:
                self.current.destroy()
            except tk.TclError:
                pass
            self.current = None


class Segmented(tk.Canvas):
    """Seletor em pílula (ex.: 6M | 12M) com a opção ativa numa pílula clara
    que desliza entre as opções."""

    def __init__(self, parent, options, value, command=None, bg=None, size=11, pad=(14, 6)):
        self._parent_bg = bg or bg_of(parent)
        super().__init__(parent, bg=self._parent_bg, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.options = list(options)
        self.value = value
        self.command = command
        self.items = {}
        self._font = font(size, "semibold")
        inset = self._inset = 4
        x = inset
        self._spans = {}
        for key, text in self.options:
            width = measure(self._font, text) + 2 * pad[0]
            self._spans[key] = (x, x + width)
            x += width
        self._width = x + inset
        self._h = linespace(self._font) + 2 * pad[1] + 2 * inset
        self.configure(width=self._width, height=self._h)
        round_rect(self, 0.5, 0.5, self._width - 0.5, self._h - 0.5, self._h / 2,
                   c("surface_alt"), c("border"), tags="track")
        for key, text in self.options:
            x1, x2 = self._spans[key]
            self.items[key] = self.create_text((x1 + x2) / 2, self._h / 2, text=text,
                                               font=self._font, tags="label")
        self.slider = motion.EdgeSlider(self, self._move)
        if value in self._spans:
            self.slider.jump(*self._edges(value))
        self._paint()
        self.bind("<Button-1>", self._click)
        self.bind("<Left>", lambda e: self._step(-1))
        self.bind("<Right>", lambda e: self._step(1))

    def _edges(self, key):
        x1, x2 = self._spans[key]
        return x1, self._width - x2

    def _move(self, left, right):
        self.delete("pill")
        x1, x2 = left, self._width - right
        fill = mix(c("surface_alt"), c("text"), 0.15)
        round_rect(self, x1, self._inset, x2, self._h - self._inset,
                   (self._h - 2 * self._inset) / 2, fill, fill, tags="pill")
        self.tag_raise("label")

    def _paint(self):
        for key, item in self.items.items():
            self.itemconfigure(item, fill=c("text") if key == self.value else c("muted"))

    def _click(self, e):
        for key, (x1, x2) in self._spans.items():
            if x1 <= e.x < x2:
                self.select(key)
                return

    def _step(self, delta):
        keys = [k for k, _ in self.options]
        if self.value in keys:
            self.select(keys[(keys.index(self.value) + delta) % len(keys)])

    def set(self, key):
        if key in self._spans:
            self.value = key
            self._paint()
            self.slider.go(*self._edges(key))

    def select(self, key):
        changed = key != self.value
        self.set(key)
        if self.command and changed:
            self.command(key)

    def get(self):
        return self.value


class ChoiceCombo(ttk.Combobox):
    """Combobox que mostra nomes e devolve ids."""

    def __init__(self, parent, items=(), width=24, allow_empty=None):
        self._var = tk.StringVar()
        super().__init__(parent, textvariable=self._var, state="readonly",
                         width=width, font=font(11))
        self._ids = []
        self._empty = allow_empty
        self.set_items(items)

    def set_items(self, items, keep=True):
        previous = self.get_id() if keep else None
        entries = list(items)
        if self._empty is not None:
            entries = [(None, self._empty)] + entries
        self._ids = [i for i, _ in entries]
        self["values"] = [t for _, t in entries]
        if previous in self._ids:
            self.set_id(previous)
        elif entries:
            self.current(0)
        else:
            self._var.set("")

    def get_id(self):
        index = self.current()
        return self._ids[index] if 0 <= index < len(self._ids) else None

    def set_id(self, value):
        if value in self._ids:
            self.current(self._ids.index(value))

