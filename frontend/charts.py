"""Gráficos simples desenhados em canvas (sem dependências externas)."""

import math
import tkinter as tk

from frontend.theme import c, font
from backend.utils import formatters


class BarChart(tk.Canvas):
    """Receitas x despesas por mês."""

    def __init__(self, parent, height=230):
        super().__init__(parent, height=height, bg=c("surface"), highlightthickness=0)
        self.series = []
        self.bind("<Configure>", lambda e: self.draw())

    def set_data(self, series):
        self.series = series
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or not self.series:
            return
        left, right, top, bottom = 56, 12, 14, 34
        peak = max([max(m["income"], m["expense"]) for m in self.series] + [1])
        step = _nice_step(peak, 4)
        top_value = step * math.ceil(peak / step)
        plot_h = h - top - bottom
        for i in range(0, int(top_value // step) + 1):
            value = i * step
            y = top + plot_h - plot_h * value / top_value
            self.create_line(left, y, w - right, y, fill=c("border"))
            self.create_text(left - 8, y, text=formatters.money_compact(value),
                             anchor="e", fill=c("muted"), font=font(9))
        slot = (w - left - right) / len(self.series)
        bar_w = min(26, slot * 0.28)
        for i, m in enumerate(self.series):
            cx = left + slot * (i + 0.5)
            for offset, key, color in ((-bar_w / 2 - 1, "income", c("income")),
                                       (bar_w / 2 + 1, "expense", c("expense"))):
                height = plot_h * m[key] / top_value
                if m[key]:
                    height = max(height, 2)
                x = cx + offset
                self.create_rectangle(x - bar_w / 2, top + plot_h - height,
                                      x + bar_w / 2, top + plot_h, fill=color, width=0)
            self.create_text(cx, h - bottom + 16, text=formatters.month_label(m["month"], short=True),
                             fill=c("muted"), font=font(10))


def _nice_step(peak, parts):
    raw = max(peak / parts, 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        if raw <= factor * magnitude:
            return factor * magnitude
    return 10 * magnitude


class Donut(tk.Canvas):
    """Distribuição de despesas por categoria (até 6 fatias + 'Outras')."""

    def __init__(self, parent, size=190):
        super().__init__(parent, width=size, height=size, bg=c("surface"), highlightthickness=0)
        self.size = size

    def set_data(self, items, center_top="", center_bottom=""):
        """items: [(nome, valor)] já ordenados."""
        self.delete("all")
        total = sum(v for _, v in items)
        pad, s = 14, self.size
        box = (pad, pad, s - pad, s - pad)
        palette = c("chart")
        if not total:
            self.create_oval(*box, outline=c("border"), width=22)
        else:
            start = 90
            for i, (_, value) in enumerate(items):
                extent = -360 * value / total
                if len(items) == 1:
                    self.create_oval(*box, outline=palette[i % len(palette)], width=22)
                else:
                    self.create_arc(*box, start=start, extent=extent - 0.0, style="arc",
                                    outline=palette[i % len(palette)], width=22)
                start += extent
        self.create_text(s / 2, s / 2 - 9, text=center_top, fill=c("muted"), font=font(10))
        self.create_text(s / 2, s / 2 + 10, text=center_bottom, fill=c("text"), font=font(14, "bold"))


def group_categories(rows, limit=6):
    """Junta categorias pequenas em 'Outras'. rows: [{category_name,total}]."""
    top = [(r["category_name"], r["total"]) for r in rows[:limit]]
    rest = sum(r["total"] for r in rows[limit:])
    if rest:
        top.append(("Outras", rest))
    return top


class ProgressBar(tk.Canvas):
    def __init__(self, parent, bg=None, height=8):
        super().__init__(parent, height=height, bg=bg or c("surface"), highlightthickness=0)
        self.ratio = 0
        self.color = c("primary")
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, ratio, color=None):
        self.ratio = max(0, ratio)
        self.color = color or c("primary")
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        self.create_rectangle(0, 0, w, h, fill=c("border"), width=0)
        self.create_rectangle(0, 0, w * min(self.ratio, 1), h, fill=self.color, width=0)
