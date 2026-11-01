"""Base das páginas e peças compartilhadas entre elas."""

import tkinter as tk

from frontend.theme import c, font
from backend.utils import formatters
from backend.utils.i18n import t


class Page(tk.Frame):
    """Uma tela. O cabeçalho (título em 2 linhas, 3 KPIs e ações) é desenhado
    pela casca do app; a página só informa o que mostrar:

    - ``title_key``: chave do título (com ``\\n`` separando as 2 linhas);
    - ``header_actions(parent)``: botões do canto direito do cabeçalho;
    - ``publish(kpis)``: KPIs atuais (veja ``kpi``).
    """

    title_key = ""

    def __init__(self, parent, app):
        super().__init__(parent, bg=c("bg"))
        self.app = app
        self.dirty = True
        self.kpis = []
        self.build()

    def build(self):
        pass

    def refresh(self):
        self.dirty = False

    def header_actions(self, parent):
        return []

    def on_show(self):
        if self.dirty:
            self.refresh()

    def publish(self, kpis):
        """Atualiza os KPIs do cabeçalho (com contagem animada)."""
        self.kpis = list(kpis)
        if self.app.pages.get(self.app.current) is self:
            self.app.header_kpis(self.kpis)

    def guarded(self, func):
        """Executa uma ação de usuário mostrando erros de validação no aviso."""
        try:
            return func()
        except ValueError as exc:
            self.app.toast(str(exc), "error")
        except Exception as exc:  # erro inesperado: registra e avisa sem dados
            self.app.report_error(exc)


def kpi(icon, value, caption, fmt=None, badge=None, toggle=None):
    """Um KPI do cabeçalho. ``value`` é um inteiro (centavos, contagem ou
    porcentagem x100) que conta até o valor final; ``fmt`` o transforma em
    texto. ``badge`` = (texto, tom); ``toggle`` = (ligado, função, dica)."""
    return {"icon": icon, "value": value, "caption": caption,
            "fmt": fmt or (lambda v: f"{v}"), "badge": badge, "toggle": toggle}


def money_fmt(signed=False):
    return lambda v: formatters.money(v, signed=signed)


def percent_fmt(v):
    return f"{v}%"


def change_badge(change, good_when_up=True, suffix_key="common.vs_previous_month"):
    """Badge com a variação percentual (None quando não há base)."""
    if change is None:
        return None
    pct = round(change * 100)
    if pct == 0:
        return (f"0% {t(suffix_key)}", "neutral")
    good = (pct > 0) == good_when_up
    sign = "+" if pct > 0 else "−"
    return (f"{sign}{abs(pct)}% {t(suffix_key)}", "lime" if good else "coral")


def change_note(change, good_when_up=True):
    """Texto e cor para a variação percentual em relação ao período anterior."""
    if change is None:
        return t("common.no_comparison"), "muted"
    arrow = "▲" if change > 0 else "▼" if change < 0 else "•"
    pct = f"{abs(change) * 100:.0f}%"
    good = (change >= 0) == good_when_up
    color = "muted" if change == 0 else ("income" if good else "expense")
    return f"{arrow} {pct} {t('common.vs_previous_period')}", color


def relative_day(iso, today=None):
    """"hoje", "ontem", "há 3 dias", "em 2 dias"…"""
    from datetime import date
    if not iso:
        return t("common.never")
    day = date.fromisoformat(iso)
    base = today or date.today()
    delta = (base - day).days
    if delta == 0:
        return t("common.today_lower")
    if delta == 1:
        return t("common.yesterday")
    if delta > 1:
        return t("common.days_ago", count=delta)
    if delta == -1:
        return t("common.tomorrow")
    return t("common.in_days", count=-delta)


# ---- peças das páginas antigas (saem quando cada página for redesenhada) ----
class MonthBar(tk.Frame):
    def __init__(self, parent, on_change, bg=None):
        from frontend.ui import MonthSwitcher
        super().__init__(parent, bg=bg or c("bg"))
        self.switch = MonthSwitcher(self, on_change, bg=bg or c("bg"))
        self.switch.pack(side="left")

    @property
    def month(self):
        return self.switch.month

    def set(self, month):
        self.switch.set(month)


def kpi_card(parent, title, value, color="text", note=None, note_color="muted"):
    from frontend.widgets import Card, label
    card = Card(parent, 20, 17)
    label(card.body, title, 10, "semibold", "muted").pack(fill="x")
    label(card.body, value, 20, "semibold", color).pack(fill="x", pady=(6, 0))
    label(card.body, note or " ", 10, color=note_color).pack(fill="x", pady=(4, 0))
    return card
