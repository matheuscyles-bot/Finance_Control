"""Orçamentos mensais por categoria."""

import tkinter as tk

from backend.services import budgets
from frontend import dialogs
from frontend.charts import ProgressBar
from frontend.pages.base import MonthBar, Page
from frontend.theme import c, font
from frontend.widgets import Button, Card, EmptyState, ScrollFrame, label
from backend.utils import formatters
from backend.utils.formatters import money
from backend.utils.i18n import category_label, t


class BudgetsPage(Page):
    title_key = "nav.budgets"

    def build(self):
        top = tk.Frame(self, bg=c("bg"))
        top.pack(fill="x", padx=32, pady=(0, 12))
        self.monthbar = MonthBar(top, self.refresh)
        self.monthbar.pack(side="left")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.content = tk.Frame(self.scroll.inner, bg=c("bg"))
        self.content.pack(fill="both", expand=True, padx=32, pady=(0, 28))

    def header_actions(self, parent):
        return [
            Button(parent, t("budgets.copy_previous"), self.copy_previous, "secondary"),
            Button(parent, t("common.new_budget"), lambda: self.edit(None), "primary", icon="plus"),
        ]

    def refresh(self):
        super().refresh()
        for w in self.content.winfo_children():
            w.destroy()
        month = self.monthbar.month
        rows = budgets.list_budgets(month)
        if not rows:
            card = Card(self.content, 0, 0)
            card.pack(fill="both", expand=True, ipady=70)
            EmptyState(card.body, "target", t("budgets.none_title"),
                       t("budgets.none_text"),
                       t("common.new_budget"), lambda: self.edit(None)).pack(fill="both", expand=True)
            return
        s = budgets.budget_summary(month)
        summary = Card(self.content, 18, 14)
        summary.pack(fill="x", pady=(0, 12))
        line = tk.Frame(summary.body, bg=c("surface"))
        line.pack(fill="x")
        for title, value, color in (
                (t("budgets.total"), money(s["budget"]), "text"),
                (t("budgets.spent"), money(s["spent"]), "expense" if s["spent"] > s["budget"] else "text"),
                (t("budgets.available"), money(s["remaining"]), "income" if s["remaining"] >= 0 else "expense")):
            box = tk.Frame(line, bg=c("surface"))
            box.pack(side="left", padx=(0, 48))
            label(box, title, 10, "bold", "muted").pack(fill="x")
            label(box, value, 18, "bold", color).pack(fill="x")
        if s["over"]:
            label(summary.body, t("budgets.over_limit", count=s["over"]), 11, color="expense").pack(fill="x", pady=(8, 0))

        for r in rows:
            ratio = r["spent"] / r["budget"]
            card = Card(self.content, 18, 12)
            card.pack(fill="x", pady=4)
            top = tk.Frame(card.body, bg=c("surface"))
            top.pack(fill="x")
            label(top, category_label(r["category_name"]), 12, "bold").pack(side="left")
            Button(top, t("common.remove"), lambda r=r: self.remove(r), "ghost", pad=(8, 3)).pack(side="right")
            Button(top, t("common.edit"), lambda r=r: self.edit(r), "ghost", pad=(8, 3)).pack(side="right")
            over = r["spent"] > r["budget"]
            status = (t("budgets.over_by", amount=money(r['spent'] - r['budget'])) if over
                      else t("budgets.remaining", amount=money(r['budget'] - r['spent'])))
            label(card.body, f"{money(r['spent'])} de {money(r['budget'])}  ·  {int(ratio * 100)}%  ·  {status}",
                  10, color="expense" if over else "muted").pack(fill="x", pady=(2, 6))
            bar = ProgressBar(card.body, height=10)
            bar.pack(fill="x")
            bar.set(ratio, c("expense") if over else c("warning") if ratio > 0.8 else c("primary"))

    def edit(self, row):
        dlg = dialogs.BudgetDialog(self.app, self.monthbar.month,
                                   row["category_id"] if row else None, row["budget"] if row else None)
        if dlg.wait():
            self.app.after_change()
            self.app.toast(t("toast.budget_saved"), "success")

    def remove(self, row):
        if dialogs.confirm(self.app, "Remover orçamento",
                           f"Remover o orçamento de “{row['category_name']}” neste mês? "
                           "As movimentações não são afetadas.", "Remover"):
            budgets.delete_budget(self.monthbar.month, row["category_id"])
            self.app.after_change()

    def copy_previous(self):
        def run():
            n = budgets.copy_from_previous(self.monthbar.month)
            self.app.after_change()
            self.app.toast(f"{n} orçamento(s) copiado(s) do mês anterior." if n
                           else "Nada para copiar: o mês anterior não tem orçamentos novos.", "success")
        self.guarded(run)
