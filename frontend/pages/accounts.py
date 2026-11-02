"""Contas e transferências."""

import tkinter as tk

from backend import config
from backend.services import accounts
from frontend import dialogs
from frontend.pages.base import Page
from frontend.theme import c, font
from frontend.widgets import Button, Card, ScrollFrame, SortableTree, label
from backend.utils import formatters
from backend.utils.formatters import money
from backend.utils.i18n import t


class AccountsPage(Page):
    title_key = "nav.accounts"

    def build(self):
        self.show_archived = tk.BooleanVar(value=False)
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.content = tk.Frame(self.scroll.inner, bg=c("bg"))
        self.content.pack(fill="both", expand=True, padx=32, pady=(0, 28))

    def header_actions(self, parent):
        return [
            Button(parent, t("common.new_transfer"), self.new_transfer, "secondary", icon="transfer"),
            Button(parent, t("common.new_account"), self.new_account, "primary", icon="plus"),
        ]

    def refresh(self):
        super().refresh()
        for w in self.content.winfo_children():
            w.destroy()
        rows = accounts.list_accounts(include_archived=self.show_archived.get())
        total = accounts.total_balance()
        head = tk.Frame(self.content, bg=c("bg"))
        head.pack(fill="x", pady=(0, 12))
        label(head, t("common.active_accounts_balance"), 11, color="muted", bg="bg").pack(side="left")
        label(head, "  " + money(total), 16, "bold", "text" if total >= 0 else "expense", bg="bg").pack(side="left")
        tk.Checkbutton(head, text=t("common.show_archived"), variable=self.show_archived,
                       command=self.refresh, bg=c("bg"), fg=c("muted"), selectcolor=c("surface"),
                       activebackground=c("bg"), font=font(11)).pack(side="right")

        grid = tk.Frame(self.content, bg=c("bg"))
        grid.pack(fill="x")
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="a")
        for i, a in enumerate(rows):
            card = Card(grid, 18, 16)
            card.grid(row=i // 3, column=i % 3, sticky="nsew", padx=6, pady=6)
            top = tk.Frame(card.body, bg=c("surface"))
            top.pack(fill="x")
            label(top, a["name"], 13, "bold").pack(side="left")
            if a["archived"]:
                label(top, t("common.archived"), 10, color="muted", anchor="e").pack(side="right")
            label(card.body, config.ACCOUNT_TYPES.get(a["type"], ""), 11, color="muted").pack(fill="x")
            label(card.body, money(a["balance"]), 22, "bold",
                  "text" if a["balance"] >= 0 else "expense").pack(fill="x", pady=(10, 0))
            note = t("common.current_balance")
            if a["projected_balance"] != a["balance"]:
                note = t("common.projected_balance", amount=money(a["projected_balance"]))
            label(card.body, note, 11, color="muted").pack(fill="x")
            actions = tk.Frame(card.body, bg=c("surface"))
            actions.pack(fill="x", pady=(12, 0))
            Button(actions, "Editar", lambda a=a: self.edit_account(a["id"]), "secondary", pad=(10, 4)).pack(side="left")
            if a["archived"]:
                Button(actions, "Reativar", lambda a=a: self.unarchive(a["id"]), "secondary", pad=(10, 4)).pack(side="left", padx=6)
            else:
                Button(actions, "Arquivar", lambda a=a: self.archive(a), "secondary", pad=(10, 4)).pack(side="left", padx=6)
            usage = accounts.account_usage(a["id"])
            if not any(usage.values()) and len(rows) > 1:
                Button(actions, "Excluir", lambda a=a: self.delete(a), "ghost", pad=(10, 4)).pack(side="left")

        # transferências
        card = Card(self.content, 0, 0)
        card.pack(fill="x", pady=(18, 0))
        top = tk.Frame(card.body, bg=c("surface"))
        top.pack(fill="x", padx=18, pady=(14, 8))
        label(top, t("common.transfer_section"), 13, "bold").pack(side="left")
        label(top, t("common.transfer_neutral"), 11, color="muted", anchor="e").pack(side="right")
        transfers = accounts.list_transfers(limit=100)
        if not transfers:
            label(card.body, t("common.no_transfer"),
                  11, color="muted").pack(fill="x", padx=18, pady=(4, 20))
            return
        columns = [("date", t("common.date"), 100, "w", False), ("from", t("common.from"), 180, "w", False),
                   ("to", t("common.to"), 180, "w", False), ("notes", t("common.notes_optional"), 240, "w", False),
                   ("amount", t("common.amount"), 120, "e", False)]
        self.table = SortableTree(card.body, columns, None, self.edit_transfer, height=min(len(transfers), 8))
        self.table.pack(fill="x")
        for transfer_row in transfers:
            self.table.add(
                transfer_row["id"],
                (formatters.format_date(transfer_row["transfer_date"]),
                 transfer_row["from_name"], transfer_row["to_name"],
                 transfer_row["notes"] or "", money(transfer_row["amount"])),
            )
        foot = tk.Frame(card.body, bg=c("surface"))
        foot.pack(fill="x", padx=18, pady=10)
        Button(foot, "Excluir", self.delete_transfer, "secondary", pad=(12, 5)).pack(side="right")
        Button(foot, "Editar", self.edit_transfer, "secondary", pad=(12, 5)).pack(side="right", padx=8)

    # ---- contas ----
    def new_account(self):
        if dialogs.AccountDialog(self.app).wait():
            self.app.after_change()
            self.app.toast("Conta criada.", "success")

    def edit_account(self, account_id):
        if dialogs.AccountDialog(self.app, accounts.get_account(account_id)).wait():
            self.app.after_change()
            self.app.toast("Conta atualizada.", "success")

    def archive(self, account):
        def run():
            if dialogs.confirm(self.app, "Arquivar conta",
                               f"Arquivar “{account['name']}”? O histórico é mantido, mas a conta "
                               "deixa de aparecer nas listas e nas recorrências.", "Arquivar", False):
                accounts.archive_account(account["id"])
                self.app.after_change()
                self.app.toast("Conta arquivada.", "success")
        self.guarded(run)

    def unarchive(self, account_id):
        accounts.unarchive_account(account_id)
        self.app.after_change()

    def delete(self, account):
        def run():
            if dialogs.confirm(self.app, "Excluir conta", f"Excluir a conta “{account['name']}”?"):
                accounts.delete_account(account["id"])
                self.app.after_change()
                self.app.toast("Conta excluída.", "success")
        self.guarded(run)

    # ---- transferências ----
    def new_transfer(self):
        def run():
            if len(accounts.list_accounts()) < 2:
                raise ValueError("Crie pelo menos duas contas para fazer transferências.")
            if dialogs.TransferDialog(self.app).wait():
                self.app.after_change()
                self.app.toast("Transferência registrada.", "success")
        self.guarded(run)

    def _selected_transfer(self):
        table = getattr(self, "table", None)
        sel = table.selected() if table and table.winfo_exists() else None
        if not sel:
            self.app.toast("Selecione uma transferência na lista.")
            return None
        return accounts.get_transfer(int(sel))

    def edit_transfer(self):
        row = self._selected_transfer()
        if row and dialogs.TransferDialog(self.app, row).wait():
            self.app.after_change()
            self.app.toast("Transferência atualizada.", "success")

    def delete_transfer(self):
        row = self._selected_transfer()
        if not row:
            return
        if dialogs.confirm(self.app, "Excluir transferência",
                           f"Excluir a transferência de {money(row['amount'])} "
                           f"({row['from_name']} → {row['to_name']})?"):
            def run():
                deleted = accounts.delete_transfer(row["id"])
                self.app.after_change()
                self.app.undoable("Transferência excluída.", lambda: accounts.restore_transfer(deleted))
            self.guarded(run)
