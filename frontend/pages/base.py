"""Base das páginas e componentes compartilhados entre elas."""

import tkinter as tk

from frontend.theme import c, font
from frontend.widgets import Button, Card, label
from backend.utils import formatters


class Page(tk.Frame):
    title = ""
    subtitle = ""

    def __init__(self, parent, app):
        super().__init__(parent, bg=c("bg"))
        self.app = app
        self.dirty = True
        self.build()

    def build(self):
        pass

    def refresh(self):
        self.dirty = False

    def header_actions(self, parent):
        """Botões mostrados no cabeçalho (sobrescreva se necessário)."""
        return []

    def on_show(self):
        if self.dirty:
            self.refresh()

    def guarded(self, func):
        """Executa uma ação de usuário mostrando erros de validação no aviso."""
        try:
            return func()
        except ValueError as exc:
            self.app.toast(str(exc), "error")
        except Exception as exc:  # erro inesperado: registra e avisa sem dados
            self.app.report_error(exc)


class MonthBar(tk.Frame):
    def __init__(self, parent, on_change, bg=None):
        super().__init__(parent, bg=bg or c("bg"))
        self.month = formatters.current_month()
        self.on_change = on_change
        self.prev = self._arrow("‹", -1)
        self.text = tk.Label(self, bg=bg or c("bg"), fg=c("text"), font=font(13, "bold"),
                             width=16)
        self.text.pack(side="left")
        self.next = self._arrow("›", 1)
        today = tk.Label(self, text="Hoje", bg=bg or c("bg"), fg=c("primary"),
                         font=font(11, "bold"), cursor="hand2", padx=10)
        today.pack(side="left")
        today.bind("<Button-1>", lambda e: self.set(formatters.current_month()))
        self._paint()

    def _arrow(self, text, delta):
        b = tk.Label(self, text=text, bg=c("surface"), fg=c("text"), font=font(14, "bold"),
                     width=2, cursor="hand2", highlightthickness=1,
                     highlightbackground=c("border"))
        b.bind("<Button-1>", lambda e: self.set(formatters.shift_month(self.month, delta)))
        b.pack(side="left") if delta < 0 else None
        if delta > 0:
            b.pack(side="left")
        return b

    def _paint(self):
        self.text.configure(text=formatters.month_label(self.month))

    def set(self, month):
        self.month = month
        self._paint()
        self.on_change()


def kpi_card(parent, title, value, color="text", note=None, note_color="muted"):
    card = Card(parent, 20, 17)
    label(card.body, title, 10, "bold", "muted").pack(fill="x")
    label(card.body, value, 20, "bold", color).pack(fill="x", pady=(6, 0))
    n = label(card.body, note or " ", 10, color=note_color)
    n.pack(fill="x", pady=(4, 0))
    return card


def change_note(change, good_when_up=True):
    """Texto e cor para a variação percentual em relação ao período anterior."""
    if change is None:
        return "sem base de comparação", "muted"
    arrow = "▲" if change > 0 else "▼" if change < 0 else "•"
    pct = f"{abs(change) * 100:.0f}%".replace(".", ",")
    good = (change >= 0) == good_when_up
    color = "muted" if change == 0 else ("income" if good else "expense")
    return f"{arrow} {pct} vs. período anterior", color
