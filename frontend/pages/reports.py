"""Relatórios: resultado do período com comparação ao anterior, receitas x
despesas nos últimos meses e maiores categorias. Os KPIs ficam no cabeçalho."""

import tkinter as tk
from datetime import date, timedelta

from backend.services import accounts, reports
from frontend.charts import GroupedBars, ProgressBar
from frontend.pages.base import Page, change_badge, kpi, money_fmt
from frontend.theme import c
from frontend.ui import Panel, PillSelect
from frontend.widgets import Button, DateField, EmptyState, ScrollFrame, Segmented, label
from backend.utils import formatters
from backend.utils.formatters import money
from backend.utils.i18n import category_label, t


class ReportsPage(Page):
    title_key = "nav.reports"

    def build(self):
        self.kind = "expense"
        self.bar = tk.Frame(self, bg=c("bg"))
        self.bar.pack(fill="x", pady=(0, 14))
        periods = [
            ("month", t("common.month_current")),
            ("last_month", t("common.month_previous")),
            ("90", t("common.last_90_days")),
            ("year", t("common.year_current")),
            ("custom", t("common.custom")),
        ]
        self.period = PillSelect(self.bar, periods, icon_name="calendar-days", bg=c("bg"))
        self.period.set_id("month")
        self.period.pack(side="left", padx=(0, 10))
        self.period.bind("<<ComboboxSelected>>", lambda e: self._period_changed())
        self.account = PillSelect(self.bar, [], allow_empty=t("common.all_accounts"), icon_name="wallet",
                                  bg=c("bg"))
        self.account.pack(side="left")
        self.account.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        self.custom = tk.Frame(self, bg=c("bg"))
        label(self.custom, t("common.from"), 11, color="muted", bg="bg").pack(side="left", padx=(0, 4))
        self.start = DateField(self.custom, width=10)
        self.start.pack(side="left", padx=(0, 10))
        label(self.custom, t("common.until"), 11, color="muted", bg="bg").pack(side="left", padx=(0, 4))
        self.end = DateField(self.custom, width=10)
        self.end.pack(side="left")
        Button(self.custom, t("common.apply"), self.refresh, "secondary", pad=(10, 4)).pack(side="left", padx=10)

        self.scroll = ScrollFrame(self, bg=c("bg"))
        self.scroll.pack(fill="both", expand=True)
        self.content = tk.Frame(self.scroll.inner, bg=c("bg"))
        self.content.pack(fill="both", expand=True)

    def _period_changed(self):
        if self.period.get_id() == "custom":
            self.custom.pack(fill="x", pady=(0, 14), before=self.scroll)
        else:
            self.custom.pack_forget()
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
        self.publish([
            kpi("trending-up", s["income"], t("common.income"), money_fmt(),
                change_badge(s["income_change"], True)),
            kpi("trending-down", s["expense"], t("common.expense"), money_fmt(),
                change_badge(s["expense_change"], False)),
            kpi("wallet", s["net"], t("reports.result"), money_fmt(signed=True)),
            kpi("calendar-days", s["daily_expense"], t("reports.daily_average"), money_fmt()),
        ])
        if s["count"] == 0:
            panel = Panel(self.content, hover=False)
            panel.pack(fill="both", expand=True)
            EmptyState(panel.content, "chart", t("reports.no_data_title"),
                       t("reports.no_data_text")).pack(fill="both", expand=True)
            return

        row = tk.Frame(self.content, bg=c("bg"))
        row.pack(fill="both", expand=True)
        left = Panel(row, title=t("reports.monthly_chart"), hover=False)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        chart = GroupedBars(left.content, height=300)
        chart.pack(fill="both", expand=True, pady=(8, 0))
        chart.set_data(reports.monthly_series(end[:7], 6, account_id))

        right = Panel(row, hover=False)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        fill = right.fill
        head = tk.Frame(right.content, bg=fill)
        head.pack(fill="x")
        label(head, t("reports.categories_period"), 13, "bold", bg=fill).pack(side="left")
        Segmented(head, [("expense", t("common.expense")), ("income", t("common.income"))], self.kind,
                  self._set_kind, bg=fill).pack(side="right")
        rows = reports.category_report(start, end, self.kind, account_id)
        if not rows:
            label(right.content, t("reports.no_category_data"), 11, color="muted", bg=fill).pack(fill="x", pady=24)
        tone = c("expense") if self.kind == "expense" else c("income")
        for r in rows:
            line = tk.Frame(right.content, bg=fill)
            line.pack(fill="x", pady=(12, 0))
            label(line, category_label(r["category_name"]), 11, bg=fill).pack(side="left")
            label(line, f"{money(r['total'])}  ·  {r['share'] * 100:.0f}%", 11, "bold", bg=fill).pack(side="right")
            bar = ProgressBar(right.content)
            bar.pack(fill="x", pady=(5, 0))
            bar.set(r["share"], tone)
