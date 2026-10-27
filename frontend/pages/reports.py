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
from backend.utils.i18n import t, category_label

class ReportsPage(Page):
    title_key = "nav.reports"

    def build(self):
        self.kind = "expense"
        bar = Card(self, 14, 12)
        bar.pack(fill="x", padx=32, pady=(0, 14))
        b = bar.body
        periods = [
            ("month", t("common.month_current")),
            ("last_month", t("common.month_previous")),
            ("90", t("common.last_90_days")),
            ("year", t("common.year_current")),
            ("custom", t("common.custom")),
        ]
        self.period = ChoiceCombo(b, periods, width=16)
        self.period.set_id("month")
        self.period.grid(row=0, column=0, padx=(0, 10))
        self.period.bind("<<ComboboxSelected>>", lambda e: self._period_changed())
        self.account = ChoiceCombo(b, [], width=18, allow_empty=t("common.all_accounts"))
        self.account.grid(row=0, column=1, padx=(0, 10))
        self.account.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.custom = tk.Frame(b, bg=c("surface"))
        label(self.custom, t("common.from"), 10, color="muted").pack(side="left", padx=(0, 4))
        self.start = DateField(self.custom, width=10)
        self.start.pack(side="left", padx=(0, 10))
        label(self.custom, t("common.until"), 10, color="muted").pack(side="left", padx=(0, 4))
        self.end = DateField(self.custom, width=10)
        self.end.pack(side="left", padx=(0, 10))
        Button(self.custom, t("common.apply"), self.refresh, "secondary", pad=(10, 4)).pack(side="left")
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
        saving = (t("reports.savings_rate", percent=f"{s['savings_rate'] * 100:.0f}")
                  if s["savings_rate"] is not None else t("reports.no_income"))
        cards = [
            kpi_card(content, t("common.income").upper(), money(s["income"]), "income", inc_note, inc_col),
            kpi_card(content, t("common.expense").upper(), money(s["expense"]), "expense", exp_note, exp_col),
            kpi_card(content, t("reports.result"), money(s["net"], signed=True),
                     "income" if s["net"] >= 0 else "expense", saving),
            kpi_card(content, t("reports.daily_average"), money(s["daily_expense"]), "text",
                     t("reports.transaction_count", count=s["count"])),
        ]
        for i, card in enumerate(cards):
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0 if i == 3 else 7), pady=(0, 14))

        if s["count"] == 0:
            empty = Card(content, 0, 0)
            empty.grid(row=1, column=0, columnspan=4, sticky="nsew", ipady=50)
            EmptyState(empty.body, "chart", t("reports.no_data_title"),
                       t("reports.no_data_text")
                       ).pack(fill="both", expand=True)
            return

        end_month = end[:7]
        bars = Card(content)
        bars.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(0, 14))
        label(bars.body, t("reports.monthly_chart"), 13, "bold").pack(fill="x")
        chart = BarChart(bars.body)
        chart.pack(fill="both", expand=True, pady=(8, 0))
        chart.set_data(reports.monthly_series(end_month, 6, account_id))

        card = Card(content)
        card.grid(row=2, column=0, columnspan=4, sticky="nsew")
        head = tk.Frame(card.body, bg=c("surface"))
        head.pack(fill="x", pady=(0, 6))
        label(head, t("reports.categories_period"), 13, "bold").pack(side="left")
        Segmented(head, [("expense", t("common.expense")), ("income", t("common.income"))], self.kind,
                  self._set_kind).pack(side="right")
        rows = reports.category_report(start, end, self.kind, account_id)
        if not rows:
            label(card.body, t("reports.no_category_data"), 11, color="muted").pack(fill="x", pady=24)
        for r in rows:
            line = tk.Frame(card.body, bg=c("surface"))
            line.pack(fill="x", pady=(10, 0))
            label(line, category_label(r["category_name"]), 11).pack(side="left")
            label(line, f"{money(r['total'])}  ·  {r['share'] * 100:.0f}%".replace(".", ","), 11, "bold",
                  anchor="e").pack(side="right")
            bar = ProgressBar(card.body)
            bar.pack(fill="x", pady=(4, 0))
            bar.set(r["share"], c("expense") if self.kind == "expense" else c("income"))
