"""Orçamentos mensais por categoria: quanto de cada limite já foi gasto no mês.
Os totais do mês ficam nos KPIs do cabeçalho; cada categoria vira um card."""

import tkinter as tk

from backend.services import budgets
from frontend import dialogs
from frontend.charts import ProgressBar
from frontend.pages.base import Page, kpi, money_fmt
from frontend.theme import c
from frontend.ui import CircleButton, MonthSwitcher, Panel, popup_menu
from frontend.widgets import Button, EmptyState, ScrollFrame, label
from backend.utils.formatters import money
from backend.utils.i18n import category_label, t

COLUMNS = 2


class BudgetsPage(Page):
    title_key = "nav.budgets"

    def build(self):
        top = tk.Frame(self, bg=c("bg"))
        top.pack(fill="x", pady=(0, 14))
        self.months = MonthSwitcher(top, self.refresh, bg=c("bg"))
        self.months.pack(side="left")
        self.scroll = ScrollFrame(self, bg=c("bg"))
        self.scroll.pack(fill="both", expand=True)
        self.content = tk.Frame(self.scroll.inner, bg=c("bg"))
        self.content.pack(fill="both", expand=True)

    def header_actions(self, parent):
        return [
            Button(parent, t("budgets.copy_previous"), self.copy_previous, "secondary"),
            Button(parent, t("common.new_budget"), lambda: self.edit(None), "primary", icon="plus"),
        ]

    def refresh(self):
        super().refresh()
        for w in self.content.winfo_children():
            w.destroy()
        month = self.months.month
        rows = budgets.list_budgets(month)
        if not rows:
            self.publish([])
            panel = Panel(self.content, hover=False)
            panel.pack(fill="both", expand=True)
            EmptyState(panel.content, "target", t("budgets.none_title"), t("budgets.none_text"),
                       t("common.new_budget"), lambda: self.edit(None)).pack(fill="both", expand=True)
            return
        s = budgets.budget_summary(month)
        self.publish([
            kpi("target", s["budget"], t("budgets.total"), money_fmt()),
            kpi("trending-down", s["spent"], t("budgets.spent"), money_fmt(),
                (t("budgets.over_limit", count=s["over"]), "coral") if s["over"] else None),
            kpi("wallet", s["remaining"], t("budgets.available"), money_fmt(signed=True)),
        ])
        grid = tk.Frame(self.content, bg=c("bg"))
        grid.pack(fill="both", expand=True)
        for i in range(COLUMNS):
            grid.grid_columnconfigure(i, weight=1, uniform="budget")
        last = COLUMNS - 1
        for i, r in enumerate(rows):
            col = i % COLUMNS
            card = self._card(grid, r)
            card.grid(row=i // COLUMNS, column=col, sticky="nsew",
                      padx=(0 if col == 0 else 7, 0 if col == last else 7), pady=(0, 14))

    def _card(self, parent, r):
        over = r["spent"] > r["budget"]
        ratio = r["spent"] / r["budget"]
        panel = Panel(parent, hover=True, padx=20, pady=16)
        fill = panel.fill
        head = tk.Frame(panel.content, bg=fill)
        head.pack(fill="x")
        label(head, category_label(r["category_name"]), 13, "semibold", bg=fill).pack(side="left")
        more = CircleButton(head, "ellipsis", None, size=26, kind="plain", bg=fill, icon_size=13)
        more.command = lambda r=r, m=more: popup_menu(m, [
            (t("common.edit"), lambda: self.edit(r)),
            None,
            (t("common.remove"), lambda: self.remove(r)),
        ])
        more.pack(side="right")
        label(panel.content, t("budgets.spent_of", spent=money(r["spent"]), budget=money(r["budget"])),
              16, "semibold", "expense" if over else "text", bg=fill).pack(fill="x", pady=(10, 0))
        status = (t("budgets.over_by", amount=money(r["spent"] - r["budget"])) if over
                  else t("budgets.remaining", amount=money(r["budget"] - r["spent"])))
        label(panel.content, f"{int(ratio * 100)}%  ·  {status}", 11,
              color="expense" if over else "muted", bg=fill).pack(fill="x", pady=(2, 10))
        bar = ProgressBar(panel.content, height=10)
        bar.pack(fill="x")
        bar.set(ratio, c("expense") if over else c("warning") if ratio > 0.8 else c("primary"))
        return panel

    def edit(self, row):
        dlg = dialogs.BudgetDialog(self.app, self.months.month,
                                   row["category_id"] if row else None, row["budget"] if row else None)
        if dlg.wait():
            self.app.after_change()
            self.app.toast(t("toast.budget_saved"), "success")

    def remove(self, row):
        if dialogs.confirm(self.app, t("budgets.remove_title"),
                           t("budgets.remove_prompt", category=category_label(row["category_name"])),
                           t("common.remove")):
            budgets.delete_budget(self.months.month, row["category_id"])
            self.app.after_change()

    def copy_previous(self):
        def run():
            n = budgets.copy_from_previous(self.months.month)
            self.app.after_change()
            self.app.toast(t("budgets.copied", count=n) if n else t("budgets.nothing_to_copy"), "success")
        self.guarded(run)
