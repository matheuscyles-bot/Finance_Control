"""Componentes visuais reutilizáveis (apenas biblioteca padrão)."""
from PIL import Image, ImageDraw, ImageTk
import calendar
import tkinter as tk
from datetime import date
from tkinter import ttk

from frontend.theme import c, font
from backend.utils import formatters
from backend.utils.i18n import t


# ----------------------------------------------------------------------
# Ícones desenhados em canvas (não dependem de fontes nem de imagens)
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
    elif name == "gear":
        o(6 * k, 6 * k, 14 * k, 14 * k, outline=color, width=w)
        for dx, dy in ((10, 1), (10, 19), (1, 10), (19, 10)):
            d(10 * k, 10 * k, dx * k, dy * k, fill=color, width=w)
        o(7.5 * k, 7.5 * k, 12.5 * k, 12.5 * k, fill=c("sidebar"), outline=color, width=w)
    elif name == "plus":
        d(10 * k, 4 * k, 10 * k, 16 * k, fill=color, width=w + 1, capstyle="round")
        d(4 * k, 10 * k, 16 * k, 10 * k, fill=color, width=w + 1, capstyle="round")
    elif name == "transfer":
        d(3 * k, 7 * k, 17 * k, 7 * k, fill=color, width=w)
        d(13 * k, 3 * k, 17 * k, 7 * k, 13 * k, 11 * k, fill=color, width=w)
        d(17 * k, 14 * k, 3 * k, 14 * k, fill=color, width=w)
        d(7 * k, 10 * k, 3 * k, 14 * k, 7 * k, 18 * k, fill=color, width=w)
    elif name == "search":
        o(3 * k, 3 * k, 13 * k, 13 * k, outline=color, width=w)
        d(12 * k, 12 * k, 17 * k, 17 * k, fill=color, width=w + 1, capstyle="round")
    elif name == "download":
        d(10 * k, 3 * k, 10 * k, 13 * k, fill=color, width=w)
        d(5 * k, 9 * k, 10 * k, 14 * k, 15 * k, 9 * k, fill=color, width=w)
        d(3 * k, 17 * k, 17 * k, 17 * k, fill=color, width=w)
    elif name == "upload":
        d(10 * k, 14 * k, 10 * k, 4 * k, fill=color, width=w)
        d(5 * k, 8 * k, 10 * k, 3 * k, 15 * k, 8 * k, fill=color, width=w)
        d(3 * k, 17 * k, 17 * k, 17 * k, fill=color, width=w)
    elif name == "moon":
        canvas.create_arc(3 * k, 3 * k, 17 * k, 17 * k, start=60, extent=240,
                          style="arc", outline=color, width=w)
    elif name == "sun":
        o(6 * k, 6 * k, 14 * k, 14 * k, outline=color, width=w)
    else:
        o(4 * k, 4 * k, 16 * k, 16 * k, outline=color, width=w)


class Icon(tk.Canvas):
    def __init__(self, parent, name, color, bg, size=20):
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self.name, self.size = name, size
        self.set_color(color, bg)

    def set_color(self, color, bg):
        self.configure(bg=bg)
        self.delete("all")
        draw_icon(self, self.name, color, self.size)


# ----------------------------------------------------------------------
# Botões
# ----------------------------------------------------------------------

class Button(tk.Frame):
    """Botão plano (tk.Button ignora cores no macOS, por isso é desenhado)."""

    KINDS = {
        "primary": ("primary", "primary_hover", "primary_text", None),
        "danger": ("danger", "danger_hover", "primary_text", None),
        "secondary": ("surface", "surface_alt", "text", "border"),
        "ghost": ("bg", "surface_alt", "muted", None),
    }

    def __init__(self, parent, text, command=None, kind="secondary", icon=None,
                 pad=(14, 8), parent_bg=None):
        bg_key, hover_key, fg_key, border = self.KINDS[kind]
        self._bg, self._hover = c(bg_key), c(hover_key)
        fg = self._fg = c(fg_key)
        super().__init__(parent, bg=self._bg, cursor="hand2",
                         highlightthickness=1 if border else 0,
                         highlightbackground=c(border) if border else self._bg,
                         highlightcolor=c(border) if border else self._bg)
        self.command = command
        self.enabled = True
        self._parts = []
        inner = tk.Frame(self, bg=self._bg)
        inner.pack(padx=pad[0], pady=pad[1])
        if icon:
            ic = Icon(inner, icon, fg, self._bg, 16)
            ic.pack(side="left", padx=(0, 6))
            self._parts.append(ic)
        self.label = tk.Label(inner, text=text, bg=self._bg, fg=fg,
                              font=font(11, "bold" if kind in ("primary", "danger") else "normal"))
        self.label.pack(side="left")
        self._inner = inner
        self._parts += [inner, self.label]
        for w in [self] + self._parts:
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.bind("<Button-1>", self._click)
        self.configure(takefocus=1)
        self.bind("<Return>", self._click)
        self.bind("<space>", self._click)

    def _paint(self, color):
        self.configure(bg=color)
        for w in self._parts:
            w.configure(bg=color)
            if isinstance(w, Icon):
                w.configure(bg=color)

    def _enter(self, _e):
        if self.enabled:
            self._paint(self._hover)

    def _leave(self, _e):
        self._paint(self._bg)

    def _click(self, _e=None):
        if self.enabled and self.command:
            self.command()
        return "break"

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self.label.configure(fg=self._fg if enabled else c("muted"))

    def set_text(self, text):
        self.label.configure(text=text)

_RR_CACHE = {}

_RR_CACHE = {}  # "gaveta" de imagens já prontas (cache)

def rounded_image(w, h, radius, fill, outline, bg, master, S=4):
    # w, h    = largura e altura do retângulo em pixels
    # radius  = quão redondo é o canto
    # fill    = cor de dentro; outline = cor da borda (ou None)
    # bg      = cor do fundo por trás (a do pai), para os cantos ficarem certos
    # S       = fator de ampliação (desenha 4x maior para suavizar)

    # monta uma "chave" que identifica esta imagem exata
    key = (id(master.tk), w, h, radius, fill, outline, bg)

    # se já criei uma imagem igual antes, devolve a guardada (evita refazer)
    if key in _RR_CACHE:
        return _RR_CACHE[key]

    # cria uma imagem em branco 4x maior que o tamanho pedido, pintada com a cor de fundo
    img = Image.new("RGBA", (w * S, h * S), bg)

    # cria o "lápis" para desenhar em cima dessa imagem
    draw = ImageDraw.Draw(img)

    # desenha o retângulo arredondado (tudo multiplicado por S por causa da ampliação)
    draw.rounded_rectangle(
        (0, 0, w * S - 1, h * S - 1),      # canto superior esquerdo até inferior direito
        radius=radius * S,                  # raio do canto, também ampliado
        fill=fill,                          # cor do preenchimento
        outline=outline,                    # cor da borda
        width=S if outline else 0)          # espessura da borda (0 se não tiver borda)

    # reduz a imagem ao tamanho real; LANCZOS é o filtro que suaviza as bordas
    # (é aqui que o serrilhado some)
    img = img.resize((w, h), Image.LANCZOS)

    # converte para um formato que o Tkinter consegue mostrar
    photo = ImageTk.PhotoImage(img, master=master)

    # guarda na gaveta (também impede o Python de descartar a imagem)
    _RR_CACHE[key] = photo

    # devolve a imagem pronta
    return photo

class Card(tk.Canvas):
    """Card com cantos arredondados. O conteúdo vai em `.body`."""
    RADIUS = 14

    def __init__(self, parent, padx=18, pady=16, **kw):
        try:
            parent_bg = parent.cget("bg")
        except tk.TclError:
            parent_bg = c("bg")
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0, **kw)
        self._padx, self._pady = padx, pady
        self.body = tk.Frame(self, bg=c("surface"))
        self._win = self.create_window(padx, pady, window=self.body, anchor="nw")
        self.bind("<Configure>", self._redraw)
        self.body.bind("<Configure>", self._fit)

    def _fit(self, _e=None):
        self.configure(width=self.body.winfo_reqwidth() + 2 * self._padx,
                       height=self.body.winfo_reqheight() + 2 * self._pady)

    def _redraw(self, e):
        self.itemconfigure(self._win, width=max(e.width - 2 * self._padx, 1))
        self.delete("bg")
        r = self.RADIUS
        x1, y1, x2, y2 = 1, 1, e.width - 2, e.height - 2
        pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
               x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        self.create_polygon(pts, smooth=True, fill=c("surface"),
                            outline=c("border"), width=1, tags="bg")
        self.tag_lower("bg")


def label(parent, text="", size=11, weight="normal", color="text", bg="surface", **kw):
    return tk.Label(parent, text=text, bg=c(bg), fg=c(color), font=font(size, weight),
                    anchor=kw.pop("anchor", "w"), **kw)


def separator(parent, bg="border"):
    return tk.Frame(parent, bg=c(bg), height=1)


class ScrollFrame(tk.Frame):
    """Área rolável vertical; o conteúdo acompanha a largura da janela."""

    def __init__(self, parent, bg=None):
        bg = bg or c("bg")
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<Enter>", lambda e: self._bind_wheel(True))
        self.canvas.bind("<Leave>", lambda e: self._bind_wheel(False))
        self.inner.bind("<Enter>", lambda e: self._bind_wheel(True))

    def _on_inner(self, _e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._toggle_bar()

    def _on_canvas(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)
        self._toggle_bar()

    def _toggle_bar(self):
        need = self.inner.winfo_reqheight() > self.canvas.winfo_height()
        if need and not self.bar.winfo_ismapped():
            self.bar.pack(side="right", fill="y")
        elif not need and self.bar.winfo_ismapped():
            self.bar.pack_forget()

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
        if not self.bar.winfo_ismapped():
            return
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
    """Tabela com cabeçalhos clicáveis (ordenação feita no banco) e
    barra de rolagem. columns: [(id, título, largura, anchor, ordenável)]."""

    def __init__(self, parent, columns, on_sort=None, on_open=None, height=14):
        super().__init__(parent, bg=c("surface"))
        self.columns = columns
        self.on_sort = on_sort
        self.sort_key, self.descending = None, True
        ids = [col[0] for col in columns]
        self.tree = ttk.Treeview(self, columns=ids, show="headings",
                                 selectmode="browse", height=height)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.bar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.bar.grid(row=0, column=1, sticky="ns")
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
    def __init__(self, parent, icon, title, text, action_text=None, action=None):
        super().__init__(parent, bg=c("surface"))
        box = tk.Frame(self, bg=c("surface"))
        box.place(relx=0.5, rely=0.45, anchor="center")
        Icon(box, icon, c("muted"), c("surface"), 36).pack()
        label(box, title, 14, "bold", anchor="center").pack(pady=(10, 2))
        tk.Label(box, text=text, bg=c("surface"), fg=c("muted"), font=font(11),
                 justify="center", wraplength=360).pack()
        if action_text:
            Button(box, action_text, action, "primary", icon="plus").pack(pady=(14, 0))


class Toasts:
    """Mensagens rápidas no canto inferior; podem ter ação (Desfazer)."""

    def __init__(self, root):
        self.root = root
        self.current = None

    def show(self, text, kind="info", action_text=None, action=None, ms=5000):
        self.dismiss()
        bg = c("expense_soft") if kind == "error" else c("toast")
        fg = c("expense") if kind == "error" else c("toast_text")
        frame = tk.Frame(self.root, bg=bg)
        tk.Label(frame, text=text, bg=bg, fg=fg, font=font(11), padx=16, pady=10,
                 wraplength=480, justify="left").pack(side="left")
        if action_text:
            btn = tk.Label(frame, text=action_text, bg=bg, fg=fg,
                           font=font(11, "bold"), cursor="hand2", padx=14, pady=10)
            btn.pack(side="left")

            def run(_e=None):
                self.dismiss()
                action()
            btn.bind("<Button-1>", run)
        frame.place(relx=0.5, rely=1.0, anchor="s", y=-24)
        frame.lift()
        self.current = frame
        self._after = self.root.after(ms if kind != "error" else max(ms, 8000), self.dismiss)

    def dismiss(self):
        after = getattr(self, "_after", None)
        if after:
            try:
                self.root.after_cancel(after)
            except tk.TclError:
                pass
            self._after = None
        if self.current is not None:
            try:
                self.current.destroy()
            except tk.TclError:
                pass
            self.current = None


class Segmented(tk.Frame):
    """Seletor de opções lado a lado (ex.: Despesa | Receita)."""

    def __init__(self, parent, options, value, command=None, bg=None):
        super().__init__(parent, bg=c("border"), padx=1, pady=1)
        self.value, self.command, self.items = value, command, {}
        for key, text in options:
            lbl = tk.Label(self, text=text, font=font(11, "bold"), padx=18, pady=7, cursor="hand2")
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, k=key: self.select(k))
            self.items[key] = lbl
        self._paint()

    def _paint(self):
        for key, lbl in self.items.items():
            on = key == self.value
            lbl.configure(bg=c("primary") if on else c("surface"),
                          fg=c("primary_text") if on else c("muted"))

    def select(self, key):
        self.value = key
        self._paint()
        if self.command:
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
