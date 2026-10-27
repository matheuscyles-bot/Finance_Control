"""Recorrências: lançamentos criados automaticamente."""

import tkinter as tk

from backend import config
from backend.services import recurring
from frontend import dialogs
from frontend.pages.base import Page
from frontend.theme import c, font
from frontend.widgets import Button, Card, EmptyState, SortableTree, label
from backend.utils import formatters
from backend.utils.formatters import money


class RecurringPage(Page):
    title = "Recorrências"

    def build(self):
        self.card = Card(self, 0, 0)
        self.card.pack(fill="both", expand=True, padx=32, pady=(0, 28))
        self.tree = SortableTree(self.card.body, [
            ("next", "Próxima data", 110, "w", False),
            ("description", "Descrição", 260, "w", False),
            ("category", "Categoria", 150, "w", False),
            ("account", "Conta", 140, "w", False),
            ("frequency", "Frequência", 100, "w", False),
            ("amount", "Valor", 120, "e", False),
            ("status", "Situação", 90, "w", False),
        ], on_open=self.edit, height=14)
        self.empty = EmptyState(self.card.body, "repeat", "Nenhuma recorrência",
                                "Cadastre o aluguel, assinaturas ou salário uma única vez e o app "
                                "cria os lançamentos nas datas certas.",
                                "Nova recorrência", self.new)
        foot = tk.Frame(self.card.body, bg=c("surface"))
        self.foot = foot
        self.pause_btn = Button(foot, "Pausar", self.toggle, "secondary", pad=(12, 5))
        self.pause_btn.pack(side="right", padx=(8, 0))
        Button(foot, "Excluir", self.delete, "secondary", pad=(12, 5)).pack(side="right", padx=(8, 0))
        Button(foot, "Editar", self.edit, "secondary", pad=(12, 5)).pack(side="right")
        label(foot, "Os lançamentos vencidos são criados ao abrir o app.", 10, color="muted").pack(side="left")
        self.tree.tree.bind("<<TreeviewSelect>>", lambda e: self._sync_button())
        self.rows = {}

    def header_actions(self, parent):
        return [Button(parent, "Nova recorrência", self.new, "primary", icon="plus")]

    def refresh(self):
        super().refresh()
        rows = recurring.list_recurring()
        self.rows = {str(r["id"]): r for r in rows}
        self.tree.clear()
        self.empty.pack_forget()
        self.tree.pack_forget()
        self.foot.pack_forget()
        if not rows:
            self.empty.pack(fill="both", expand=True, ipady=60)
            return
        self.tree.pack(fill="both", expand=True)
        self.foot.pack(fill="x", padx=14, pady=10)
        for r in rows:
            income = r["kind"] == "income"
            self.tree.add(r["id"], (
                formatters.format_date(r["next_date"]), r["description"],
                r["category_name"] or "Sem categoria", r["account_name"],
                config.FREQUENCIES[r["frequency"]],
                money(r["amount"]) if income else "-" + money(r["amount"]),
                "Ativa" if r["active"] else "Pausada"),
                tags=("income" if income else "expense",) if r["active"] else ("muted",))
        self._sync_button()

    def _selected(self):
        iid = self.tree.selected()
        if iid is None:
            self.app.toast("Selecione uma recorrência na lista.", "info")
            return None
        return self.rows.get(iid)

    def _sync_button(self):
        iid = self.tree.selected()
        row = self.rows.get(iid) if iid else None
        self.pause_btn.set_text("Reativar" if row and not row["active"] else "Pausar")

    def new(self):
        if dialogs.RecurringDialog(self.app).wait():
            self.app.after_change(run_recurring=True)
            self.app.toast("Recorrência criada.", "success")

    def edit(self):
        row = self._selected()
        if row and dialogs.RecurringDialog(self.app, row).wait():
            self.app.after_change(run_recurring=True)
            self.app.toast("Recorrência atualizada.", "success")

    def toggle(self):
        row = self._selected()
        if row:
            self.guarded(lambda: (recurring.set_active(row["id"], not row["active"]),
                                  self.app.after_change(run_recurring=True)))

    def delete(self):
        row = self._selected()
        if row and dialogs.confirm(
                self.app, "Excluir recorrência",
                f"Excluir “{row['description']}”? Os lançamentos já criados são mantidos."):
            def run():
                recurring.delete_recurring(row["id"])
                self.app.after_change()
                self.app.toast("Recorrência excluída.", "success")
            self.guarded(run)
