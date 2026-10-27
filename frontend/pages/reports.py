"""Relatórios: comparação de períodos e maiores categorias."""

import tkinter as tk
from datetime import date, timedelta

from backend.services import accounts, reports
from frontend.charts import BarChart, ProgressBar
from frontend.pages.base import Page, change_note, kpi_card
from frontend.theme import c, font
from frontend.widgets import (Button, Card, ChoiceCombo, DateField, EmptyState,
                        ScrollFrame, Segmented, label)
from backend.utils import formatters
from backend.utils.formatters import money

PERIODS = [
    ("month", "Este mês"), ("last_month", "Mês passado"), ("90", "Últimos 90 dias"),
    ("year", "Este ano"), ("custom", "Personalizado…"),
]


class ReportsPage(Page):
    title = "Relatórios"

    def build(self):
        self.kind = "expense"
        bar = Card(self, 14, 12)
        bar.pack(fill="x", padx=32, pady=(0, 14))
        b = bar.body
        self.period = ChoiceCombo(b, PERIODS, width=16)
        self.period.set_id("month")
        self.period.grid(row=0, column=0, padx=(0, 10))
        self.period.bind("<<ComboboxSelected>>", lambda e: self._period_changed())
        self.account = ChoiceCombo(b, [], width=18, allow_empty="Todas as contas")
        self.account.grid(row=0, column=1, padx=(0, 10))
        self.account.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.custom = tk.Frame(b, bg=c("surface"))
        label(self.custom, "De", 10, color="muted").pack(side="left", padx=(0, 4))
        self.start = DateField(self.custom, width=10)
        self.start.pack(side="left", padx=(0, 10))
        label(self.custom, "até", 10, color="muted").pack(side="left", padx=(0, 4))
        self.end = DateField(self.custom, width=10)
        self.end.pack(side="left", padx=(0, 10))
        Button(self.custom, "Aplicar", self.refresh, "secondary", pad=(10, 4)).pack(side="left")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.content = tk.Frame(self.scroll.inner, bg=c("bg"))
        self.content.pack(fill="both", expand=True, padx=32, pady=(0, 28))

    def _period_changed(self):
        if self.period.get_id() == "custom":
            self.custom.grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))
        else:
            self.custom.grid_forget()
            self.refresh()

    def _range(self):
        key, today = self.period.get_id(), date.today()
        if key == "month":
            return formatters.month_range(formatters.current_month())
        if key == "last_month":
            return formatters.month_range(formatters.shift_month(formatters.current_month(), -1))
        if key == "90":
            return (today - timedelta(days=89)).isoformat(), today.isoformat()
        if key == "year":
            return f"{today.year}-01-01", f"{today.year}-12-31"
        return self.start.get_iso(), self.end.get_iso()

    def _set_kind(self, kind):
        self.kind = kind
        self.refresh()

    def refresh(self):
        super().refresh()
        self.account.set_items([(a["id"], a["name"]) for a in accounts.list_accounts()])
        for w in self.content.winfo_children():
            w.destroy()
        try:
            start, end = self._range()
            account_id = self.account.get_id()
            s = reports.period_summary(start, end, account_id)
        except ValueError as exc:
            self.app.toast(str(exc), "error")
            return
        content = self.content
        for i in range(4):
            content.grid_columnconfigure(i, weight=1, uniform="k")
        inc_note, inc_col = change_note(s["income_change"], True)
        exp_note, exp_col = change_note(s["expense_change"], False)
        saving = ("Taxa de poupança " + f"{s['savings_rate'] * 100:.0f}%".replace(".", ",")
                  if s["savings_rate"] is not None else "sem receitas no período")
        cards = [
            kpi_card(content, "RECEITAS", money(s["income"]), "income", inc_note, inc_col),
            kpi_card(content, "DESPESAS", money(s["expense"]), "expense", exp_note, exp_col),
            kpi_card(content, "RESULTADO", money(s["net"], signed=True),
                     "income" if s["net"] >= 0 else "expense", saving),
            kpi_card(content, "GASTO MÉDIO POR DIA", money(s["daily_expense"]), "text",
                     f"{s['count']} movimentação(ões)"),
        ]
        for i, card in enumerate(cards):
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0 if i == 3 else 7), pady=(0, 14))

        if s["count"] == 0:
            empty = Card(content, 0, 0)
            empty.grid(row=1, column=0, columnspan=4, sticky="nsew", ipady=50)
            EmptyState(empty.body, "chart", "Sem movimentações no período",
                       "Escolha outro período ou registre movimentações para ver os relatórios."
                       ).pack(fill="both", expand=True)
            return

        end_month = end[:7]
        bars = Card(content)
        bars.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(0, 14))
        label(bars.body, "Receitas x despesas por mês (6 meses até o fim do período)", 13, "bold").pack(fill="x")
        chart = BarChart(bars.body)
        chart.pack(fill="both", expand=True, pady=(8, 0))
        chart.set_data(reports.monthly_series(end_month, 6, account_id))

        card = Card(content)
        card.grid(row=2, column=0, columnspan=4, sticky="nsew")
        head = tk.Frame(card.body, bg=c("surface"))
        head.pack(fill="x", pady=(0, 6))
        label(head, "Categorias do período", 13, "bold").pack(side="left")
        Segmented(head, [("expense", "Despesas"), ("income", "Receitas")], self.kind,
                  self._set_kind).pack(side="right")
        rows = reports.category_report(start, end, self.kind, account_id)
        if not rows:
            label(card.body, "Nada neste tipo de movimentação no período.", 11, color="muted").pack(fill="x", pady=24)
        for r in rows:
            line = tk.Frame(card.body, bg=c("surface"))
            line.pack(fill="x", pady=(10, 0))
            label(line, r["category_name"], 11).pack(side="left")
            label(line, f"{money(r['total'])}  ·  {r['share'] * 100:.0f}%".replace(".", ","), 11, "bold",
                  anchor="e").pack(side="right")
            bar = ProgressBar(card.body)
            bar.pack(fill="x", pady=(4, 0))
            bar.set(r["share"], c("expense") if self.kind == "expense" else c("income"))
