"""Gráficos desenhados em canvas, com animação de entrada.

- AreaChart: linha suave com preenchimento em degradê e meta tracejada;
  desenha-se da esquerda para a direita.
- StackedBars: barras empilhadas com trilha escura e topo arredondado;
  crescem de baixo para cima, uma depois da outra.
- GroupedBars: receitas x despesas por mês.
- Donut: rosca que preenche em arco, com texto no centro.
- Gauge: medidor circular com ponto indicador.
- ProgressBar: barra fina arredondada.
"""

import math
import tkinter as tk

from frontend import motion
from frontend.draw import area_fill_image, monotone_curve, nice_ticks, round_rect, top_round_rect_points
from frontend.theme import c, font, mix
from frontend.widgets import bg_of, linespace, measure
from backend.utils import formatters


class _Chart(tk.Canvas):
    def __init__(self, parent, height=220, width=None, bg=None):
        self.bg = bg or bg_of(parent, "surface")
        kw = {"width": width} if width else {}
        super().__init__(parent, height=height, bg=self.bg, highlightthickness=0, bd=0, **kw)
        self.progress = 1.0
        self._chan = motion.Channel()
        self._pending_animation = False
        self.bind("<Configure>", lambda e: self.draw())

    def _animate(self, duration=0.9, ease="power3.inOut"):
        self._pending_animation = False

        def step(v):
            self.progress = v
            self.draw_progress()
        self._chan.run(self, 0.0, 1.0, duration, ease, step)

    def _maybe_animate(self, duration=0.9, ease="power3.inOut"):
        if self._pending_animation and self.winfo_width() > 40:
            self.progress = 0.0
            self.draw_progress()
            self._animate(duration, ease)
            return True
        return False

    def draw_progress(self):
        self.draw()


# ----------------------------------------------------------------------
# Área com meta
# ----------------------------------------------------------------------

class AreaChart(_Chart):
    def __init__(self, parent, height=240, color=None, bg=None, fill=True):
        super().__init__(parent, height, bg=bg)
        self.color = color or c("coral")
        self.fill = fill
        self.labels, self.values, self.target = [], [], None
        self.formatter = formatters.money_compact
        self._img = None
        self._layout = None
        self.bind("<Motion>", self._hover)
        self.bind("<Leave>", lambda e: self.delete("hover"))

    def set_data(self, labels, values, target=None, formatter=None, animate=True):
        self.labels, self.values, self.target = list(labels), list(values), target
        if formatter:
            self.formatter = formatter
        self._pending_animation = animate
        if not self._maybe_animate(1.0):
            self.draw()

    def draw(self):
        if self._maybe_animate(1.0):
            return
        self._render()

    def draw_progress(self):
        self._render()

    def _render(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60 or not self.values:
            return
        axis_font = font(9, "medium")
        peak = max(self.values + [self.target or 0, 1])
        top_value, _step = nice_ticks(peak * 1.08, 2)
        left = max(measure(axis_font, self.formatter(top_value)), 30) + 14
        right, top, bottom = 10, 12, 30
        pw, ph = w - left - right, h - top - bottom
        n = len(self.values)
        xs = [left + (pw * i / (n - 1) if n > 1 else pw / 2) for i in range(n)]
        ys = [top + ph - ph * v / top_value for v in self.values]
        self._layout = (left, top, pw, ph, xs, ys, top_value)

        for i in range(3):
            value = top_value * i / 2
            y = top + ph - ph * i / 2
            self.create_line(left, y, w - right, y, fill=mix(self.bg, c("text"), 0.06))
            self.create_text(left - 10, y, text=self.formatter(round(value)), anchor="e",
                             fill=c("muted"), font=axis_font, tags="axis")
        step = max(1, math.ceil(n / 7))
        for i, label in enumerate(self.labels):
            if i % step == 0 or i == n - 1:
                self.create_text(xs[i], h - bottom + 18, text=label, fill=c("muted"),
                                 font=axis_font, tags="axis")

        curve = monotone_curve(list(zip(xs, ys))) if n > 2 else list(zip(xs, ys))
        curve = [(x, min(y, top + ph)) for x, y in curve]
        if self.fill and len(curve) > 1:
            shifted = [(x - left, y - top) for x, y in curve]
            self._img = area_fill_image(shifted, pw + 1, ph, self.color, self.bg, master=self)
            self.create_image(left, top, image=self._img, anchor="nw")
        if self.target:
            ty = top + ph - ph * self.target / top_value
            self.create_line(left, ty, w - right, ty, fill=mix(self.bg, c("text"), 0.7),
                             dash=(5, 5), width=1.3)
        flat = [coord for point in curve for coord in point]
        if len(flat) >= 4:
            self.create_line(*flat, fill=self.color, width=2.6, capstyle="round", joinstyle="round")
        last_x, last_y = xs[-1], ys[-1]
        self.create_oval(last_x - 4.5, last_y - 4.5, last_x + 4.5, last_y + 4.5,
                         fill=self.bg, outline=self.color, width=2.2)

        if self.progress < 1:
            cover_x = left - 2 + (pw + right + 4) * self.progress
            self.create_rectangle(cover_x, 0, w, h - bottom + 4, fill=self.bg, outline=self.bg)
            self.tag_raise("axis")

    def _hover(self, e):
        self.delete("hover")
        if not self._layout or self.progress < 1:
            return
        left, top, pw, ph, xs, ys, _ = self._layout
        if not (left - 10 <= e.x <= left + pw + 10):
            return
        i = min(range(len(xs)), key=lambda k: abs(xs[k] - e.x))
        x, y = xs[i], ys[i]
        self.create_line(x, top, x, top + ph, fill=mix(self.bg, c("text"), 0.18), tags="hover")
        self.create_oval(x - 5, y - 5, x + 5, y + 5, fill=self.color, outline=self.bg, width=2,
                         tags="hover")
        text = f"{self.labels[i]} · {self.formatter(self.values[i])}"
        f = font(10, "semibold")
        bw, bh = measure(f, text) + 20, linespace(f) + 10
        bx = min(max(x - bw / 2, 2), self.winfo_width() - bw - 2)
        by = max(y - bh - 12, 2)
        round_rect(self, bx, by, bx + bw, by + bh, bh / 2, c("toast"), c("toast"), tags="hover")
        self.create_text(bx + bw / 2, by + bh / 2, text=text, font=f, fill=c("toast_text"), tags="hover")


# ----------------------------------------------------------------------
# Barras empilhadas
# ----------------------------------------------------------------------

class StackedBars(_Chart):
    def __init__(self, parent, height=250, bg=None):
        super().__init__(parent, height, bg=bg)
        self.labels, self.series, self.percent = [], [], False
        self.formatter = formatters.money_compact

    def set_data(self, labels, series, percent=False, formatter=None, animate=True):
        """series: [(nome, cor, [valores por rótulo])], de baixo para cima."""
        self.labels, self.series, self.percent = list(labels), list(series), percent
        if formatter:
            self.formatter = formatter
        self._pending_animation = animate
        if not self._maybe_animate(0.9, "linear"):
            self.draw()

    def draw(self):
        if self._maybe_animate(0.9, "linear"):
            return
        self._render()

    def draw_progress(self):
        self._render()

    def _render(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        n = len(self.labels)
        if w < 60 or not n:
            return
        totals = [sum(s[2][i] for s in self.series) for i in range(n)]
        axis_font = font(9, "medium")
        if self.percent:
            top_value = 1.0
            fmt = lambda v: f"{v * 100:.0f}%"
        else:
            top_value, _ = nice_ticks(max(totals + [1]) * 1.05, 2)
            fmt = lambda v: self.formatter(round(v))
        left = max(measure(axis_font, fmt(top_value)), 28) + 14
        right, top, bottom = 6, 10, 30
        pw, ph = w - left - right, h - top - bottom
        for i in range(3):
            y = top + ph - ph * i / 2
            self.create_line(left, y, w - right, y, fill=mix(self.bg, c("text"), 0.06))
            self.create_text(left - 10, y, text=fmt(top_value * i / 2), anchor="e",
                             fill=c("muted"), font=axis_font)
        slot = pw / n
        bar_w = min(54, slot * 0.56)
        track = mix(self.bg, c("text"), 0.045)
        for i, label in enumerate(self.labels):
            cx = left + slot * (i + 0.5)
            x1, x2 = cx - bar_w / 2, cx + bar_w / 2
            radius = min(14, bar_w / 2)
            round_rect(self, x1, top, x2, top + ph, radius, track, track)
            local = motion.power3_out(min(max((self.progress * (1 + 0.08 * n) - 0.08 * i), 0), 1))
            total = totals[i]
            base = top + ph
            stack = [(color, value) for _name, color, values in self.series
                     for value in [values[i]] if value > 0]
            for k, (color, value) in enumerate(stack):
                share = (value / total if total else 0) if self.percent else value / top_value
                seg_h = ph * share * local
                y_top = base - seg_h
                if seg_h <= 0.5:
                    continue
                if k == len(stack) - 1:
                    self.create_polygon(top_round_rect_points(x1, y_top, x2, base, radius),
                                        smooth=True, fill=color, outline=color)
                else:
                    self.create_rectangle(x1, y_top, x2, base, fill=color, outline=color)
                base = y_top
            self.create_text(cx, h - bottom + 18, text=label, fill=c("muted"), font=axis_font)


# ----------------------------------------------------------------------
# Receitas x despesas
# ----------------------------------------------------------------------

class GroupedBars(_Chart):
    def __init__(self, parent, height=200, bg=None):
        super().__init__(parent, height, bg=bg)
        self.months = []

    def set_data(self, series, animate=True):
        """series: [{month, income, expense}]."""
        self.months = list(series)
        self._pending_animation = animate
        if not self._maybe_animate(0.8, "linear"):
            self.draw()

    def draw(self):
        if self._maybe_animate(0.8, "linear"):
            return
        self._render()

    def draw_progress(self):
        self._render()

    def _render(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        n = len(self.months)
        if w < 60 or not n:
            return
        axis_font = font(9, "medium")
        peak = max([max(m["income"], m["expense"]) for m in self.months] + [1])
        top_value, _ = nice_ticks(peak * 1.05, 2)
        left = max(measure(axis_font, formatters.money_compact(top_value)), 28) + 14
        right, top, bottom = 6, 8, 28
        pw, ph = w - left - right, h - top - bottom
        for i in range(3):
            y = top + ph - ph * i / 2
            self.create_line(left, y, w - right, y, fill=mix(self.bg, c("text"), 0.06))
            self.create_text(left - 10, y, text=formatters.money_compact(round(top_value * i / 2)),
                             anchor="e", fill=c("muted"), font=axis_font)
        slot = pw / n
        bar_w = min(16, slot * 0.22)
        for i, m in enumerate(self.months):
            cx = left + slot * (i + 0.5)
            local = motion.power3_out(min(max(self.progress * (1 + 0.1 * n) - 0.1 * i, 0), 1))
            for offset, key, color in ((-bar_w / 2 - 2, "income", c("primary")),
                                       (bar_w / 2 + 2, "expense", c("coral"))):
                value = m[key]
                if not value:
                    continue
                bh = max(ph * value / top_value * local, 2)
                x = cx + offset
                self.create_polygon(top_round_rect_points(x - bar_w / 2, top + ph - bh, x + bar_w / 2,
                                                          top + ph, bar_w / 2), smooth=True,
                                    fill=color, outline=color)
            self.create_text(cx, h - bottom + 16, text=formatters.month_label(m["month"], short=True),
                             fill=c("muted"), font=axis_font)


# ----------------------------------------------------------------------
# Rosca
# ----------------------------------------------------------------------

class Donut(_Chart):
    def __init__(self, parent, size=190, thickness=20, bg=None):
        super().__init__(parent, height=size, width=size, bg=bg)
        self.size, self.thickness = size, thickness
        self.items, self.center_top, self.center_bottom = [], "", ""

    def set_data(self, items, center_top="", center_bottom="", animate=True):
        """items: [(nome, valor, cor)] — se a cor vier None usa a paleta."""
        palette = c("chart")
        self.items = [(name, value, color or palette[i % len(palette)])
                      for i, (name, value, *rest) in enumerate(items)
                      for color in [rest[0] if rest else None]]
        self.center_top, self.center_bottom = center_top, center_bottom
        self._pending_animation = animate
        if not self._maybe_animate(1.0, "power3.out"):
            self.draw()

    def draw(self):
        if self._maybe_animate(1.0, "power3.out"):
            return
        self._render()

    def draw_progress(self):
        self._render()

    def _render(self):
        self.delete("all")
        s, t = self.size, self.thickness
        pad = t / 2 + 2
        box = (pad, pad, s - pad, s - pad)
        total = sum(v for _, v, _ in self.items)
        self.create_oval(*box, outline=mix(self.bg, c("text"), 0.06), width=t)
        sweep = 360 * self.progress
        if total:
            start = 90.0
            gap = 1.6 if len(self.items) > 1 else 0
            drawn = 0.0
            for _name, value, color in self.items:
                extent = 360 * value / total
                visible = min(extent, max(sweep - drawn, 0))
                if visible > gap:
                    if visible >= 359.9:
                        self.create_oval(*box, outline=color, width=t)
                    else:
                        self.create_arc(*box, start=start - gap / 2, extent=-(visible - gap),
                                        style="arc", outline=color, width=t)
                start -= extent
                drawn += extent
        self.create_text(s / 2, s / 2 - 10, text=self.center_top, fill=c("text"),
                         font=font(int(s / 7.2), "semibold"))
        self.create_text(s / 2, s / 2 + s / 9, text=self.center_bottom, fill=c("muted"),
                         font=font(10, "medium"), width=s - 2 * t - 16, justify="center")


# ----------------------------------------------------------------------
# Medidor
# ----------------------------------------------------------------------

class Gauge(_Chart):
    """Arco de 3/4 de volta com ponto indicador na ponta."""

    def __init__(self, parent, size=170, thickness=14, bg=None, color=None):
        super().__init__(parent, height=size, width=size, bg=bg)
        self.size, self.thickness = size, thickness
        self.color = color or c("primary")
        self.ratio, self.center_top, self.center_bottom = 0.0, "", ""

    def set(self, ratio, center_top="", center_bottom="", animate=True):
        self.ratio = max(0.0, ratio)
        self.center_top, self.center_bottom = center_top, center_bottom
        self._pending_animation = animate
        if not self._maybe_animate(1.1, "power3.out"):
            self.draw()

    def draw(self):
        if self._maybe_animate(1.1, "power3.out"):
            return
        self._render()

    def draw_progress(self):
        self._render()

    def _render(self):
        self.delete("all")
        s, t = self.size, self.thickness
        pad = t / 2 + 6
        box = (pad, pad, s - pad, s - pad)
        track = mix(self.bg, c("text"), 0.12)
        self.create_arc(*box, start=225, extent=-270, style="arc", outline=track, width=t)
        value = min(self.ratio, 1.0) * self.progress
        color = c("coral") if self.ratio > 1 else self.color
        if value > 0.005:
            self.create_arc(*box, start=225, extent=-270 * value, style="arc", outline=color, width=t)
        angle = math.radians(225 - 270 * value)
        r = (s - 2 * pad) / 2
        cx, cy = s / 2 + r * math.cos(angle), s / 2 - r * math.sin(angle)
        self.create_oval(cx - t / 2 - 3, cy - t / 2 - 3, cx + t / 2 + 3, cy + t / 2 + 3,
                         fill=c("text"), outline=self.bg, width=3)
        self.create_text(s / 2, s / 2 - 6, text=self.center_top, fill=c("text"),
                         font=font(int(s / 6.5), "semibold"))
        self.create_text(s / 2, s / 2 + s / 7.5, text=self.center_bottom, fill=c("muted"),
                         font=font(10, "medium"))


# ----------------------------------------------------------------------
# Barra de progresso
# ----------------------------------------------------------------------

class ProgressBar(tk.Canvas):
    def __init__(self, parent, bg=None, height=6, track=None):
        self.bg = bg or bg_of(parent, "surface")
        super().__init__(parent, height=height + 2, bg=self.bg, highlightthickness=0, bd=0)
        self.ratio, self.shown = 0.0, 0.0
        self.color = c("primary")
        self.track = track
        self.thickness = height
        self._chan = motion.Channel()
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, ratio, color=None, animate=True):
        self.ratio = max(0.0, ratio)
        self.color = color or c("primary")

        def step(v):
            self.shown = v
            self.draw()
        if animate:
            self._chan.run(self, 0.0, self.ratio, 0.8, "power3.out", step)
        else:
            step(self.ratio)

    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        t = self.thickness
        y = (t + 2) / 2
        track = self.track or mix(self.bg, c("text"), 0.1)
        self.create_line(t / 2 + 1, y, w - t / 2 - 1, y, fill=track, width=t, capstyle="round")
        end = t / 2 + 1 + (w - t - 2) * min(self.shown, 1)
        if self.shown > 0.002:
            self.create_line(t / 2 + 1, y, max(end, t / 2 + 1.5), y, fill=self.color, width=t,
                             capstyle="round")


BarChart = GroupedBars  # nome usado pelas páginas antigas


def group_categories(rows, limit=6, other="Outras"):
    """Junta categorias pequenas em 'Outras'. rows: [{category_name,total}]."""
    top = [(r["category_name"], r["total"]) for r in rows[:limit]]
    rest = sum(r["total"] for r in rows[limit:])
    if rest:
        top.append((other, rest))
    return top
