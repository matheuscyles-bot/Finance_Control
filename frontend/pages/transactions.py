"""Movimentações: busca, filtros, ordenação, edição e exclusão."""

import tkinter as tk
from datetime import date, timedelta
from tkinter import filedialog, ttk

from backend import config
from backend.services import accounts, categories, importer, transactions as tx
from frontend import dialogs
from frontend.pages.base import Page
from frontend.theme import MOD, MOD_LABEL, c, font
from frontend.widgets import (Button, Card, ChoiceCombo, DateField, EmptyState,
                        SortableTree, label)
from backend.utils import formatters
from backend.utils.formatters import money

PERIODS = [
    ("month", "Este mês"), ("last_month", "Mês passado"), ("90", "Últimos 90 dias"),
    ("year", "Este ano"), ("all", "Todo o período"), ("custom", "Personalizado…"),
]


class TransactionsPage(Page):
    title = "Movimentações"

    def build(self):
        self.limit = config.PAGE_SIZE
        self.sort_key, self.descending = "date", True
        self.rows = []
        self._search_job = None

        bar = Card(self, 14, 12)
        bar.pack(fill="x", padx=32, pady=(0, 14))
        b = bar.body
        self.search = tk.StringVar()
        self.search_entry = ttk.Entry(b, textvariable=self.search, width=8, font=font(11))
        self.search_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        b.grid_columnconfigure(0, weight=1)
        self.search_entry.insert(0, "")
        self.search.trace_add("write", lambda *a: self._debounce())
        self.period = ChoiceCombo(b, PERIODS, width=13)
        self.period.set_id("month")
        self.period.grid(row=0, column=1, padx=(0, 10))
        self.period.bind("<<ComboboxSelected>>", lambda e: self._period_changed())
        self.kind = ChoiceCombo(b, [("all", "Todos os tipos"), ("income", "Receitas"), ("expense", "Despesas")], width=13)
        self.kind.grid(row=0, column=2, padx=(0, 10))
        self.kind.bind("<<ComboboxSelected>>", lambda e: self.reload())
        self.category = ChoiceCombo(b, [], width=18)
        self.category.grid(row=0, column=3, padx=(0, 10))
        self.category.bind("<<ComboboxSelected>>", lambda e: self.reload())
        self.account = ChoiceCombo(b, [], width=16)
        self.account.grid(row=0, column=4, padx=(0, 10))
        self.account.bind("<<ComboboxSelected>>", lambda e: self.reload())
        clear = tk.Label(b, text="Limpar filtros", fg=c("primary"), bg=c("surface"),
                         font=font(10, "bold"), cursor="hand2")
        clear.grid(row=0, column=5)
        clear.bind("<Button-1>", lambda e: self.clear_filters())
        self.custom = tk.Frame(b, bg=c("surface"))
        label(self.custom, "De", 10, color="muted").pack(side="left", padx=(0, 4))
        self.start = DateField(self.custom, width=10)
        self.start.pack(side="left", padx=(0, 10))
        label(self.custom, "até", 10, color="muted").pack(side="left", padx=(0, 4))
        self.end = DateField(self.custom, width=10)
        self.end.pack(side="left")
        for f in (self.start, self.end):
            f.bind("<<DateChanged>>", lambda e: self.reload())
        self.custom_btn = Button(self.custom, "Aplicar", self.reload, "secondary", pad=(10, 4))
        self.custom_btn.pack(side="left", padx=10)

        self.table_card = Card(self, 0, 0)
        self.table_card.pack(fill="both", expand=True, padx=32)
        columns = [
            ("date", "Data", 100, "w", True),
            ("description", "Descrição", 300, "w", True),
            ("category", "Categoria", 160, "w", True),
            ("account", "Conta", 140, "w", True),
            ("amount", "Valor", 130, "e", True),
        ]
        self.table = SortableTree(self.table_card.body, columns, self._sorted, self.edit_selected, height=16)
        self.table.pack(fill="both", expand=True)
        self.table.mark_sort("date", True)
        self.empty = EmptyState(self.table_card.body, "list", "Nenhuma movimentação encontrada",
                                "Ajuste os filtros ou registre uma nova movimentação.",
                                "Nova movimentação", self.app.new_transaction)

        foot = tk.Frame(self, bg=c("bg"))
        foot.pack(fill="x", padx=32, pady=12)
        self.actions = tk.Frame(foot, bg=c("bg"))
        self.actions.pack(side="right")
        self.more = Button(foot, "Carregar mais", self.load_more, "secondary", pad=(12, 6))
        self.summary = label(foot, "", 11, bg="bg", color="muted")
        self.summary.pack(side="left")
        Button(self.actions, "Excluir", self.delete_selected, "secondary", pad=(12, 6)).pack(side="right")
        Button(self.actions, "Duplicar", self.duplicate_selected, "secondary", pad=(12, 6)).pack(side="right", padx=8)
        Button(self.actions, "Editar", self.edit_selected, "secondary", pad=(12, 6)).pack(side="right")

        self.table.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.table.tree.bind("<BackSpace>", lambda e: self.delete_selected())
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Editar", command=self.edit_selected)
        self.menu.add_command(label="Duplicar", command=self.duplicate_selected)
        self.menu.add_separator()
        self.menu.add_command(label="Excluir", command=self.delete_selected)
        for seq in ("<Button-2>", "<Button-3>", "<Control-Button-1>"):
            self.table.tree.bind(seq, self._popup)

    def header_actions(self, parent):
        return [
            Button(parent, "Importar CSV", self.import_csv, "secondary", icon="upload"),
            Button(parent, "Exportar CSV", self.export_csv, "secondary", icon="download"),
            Button(parent, "Nova movimentação", self.app.new_transaction, "primary", icon="plus"),
        ]

    # ---------------- filtros ----------------
    def focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")

    def _debounce(self):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(250, self.reload)

    def _period_changed(self):
        if self.period.get_id() == "custom":
            self.custom.grid(row=1, column=0, columnspan=6, sticky="w", pady=(10, 0))
        else:
            self.custom.grid_forget()
        self.reload()

    def clear_filters(self):
        self.search.set("")
        self.period.set_id("month")
        self.kind.set_id("all")
        self.category.current(0)
        self.account.current(0)
        self.custom.grid_forget()
        self.reload()

    def _range(self):
        today = date.today()
        key = self.period.get_id()
        if key == "month":
            return formatters.month_range(formatters.current_month())
        if key == "last_month":
            return formatters.month_range(formatters.shift_month(formatters.current_month(), -1))
        if key == "90":
            return (today - timedelta(days=89)).isoformat(), today.isoformat()
        if key == "year":
            return f"{today.year}-01-01", f"{today.year}-12-31"
        if key == "custom":
            return self.start.get_iso(), self.end.get_iso()
        return None, None

    def _filters(self):
        start, end = self._range()
        kind = self.kind.get_id()
        return dict(
            start_date=start, end_date=end,
            kind=None if kind == "all" else kind,
            category_id=self.category.get_id(), search=self.search.get(),
            account_id=self.account.get_id(),
        )

    # ---------------- dados ----------------
    def refresh(self):
        super().refresh()
        cat_items = [(-1, "Sem categoria")] + [
            (r["id"], r["name"]) for r in categories.get_categories()]
        self.category._empty = "Todas as categorias"
        self.category.set_items(cat_items)
        self.account._empty = "Todas as contas"
        self.account.set_items([(r["id"], r["name"]) for r in accounts.list_accounts(include_archived=True)])
        self.reload()

    def reload(self):
        self._search_job = None
        try:
            filters = self._filters()
        except ValueError as exc:
            self.summary.configure(text=str(exc), fg=c("danger"))
            return
        selected = self.table.selected()
        self.rows = tx.list_transactions(order_by=self.sort_key, descending=self.descending,
                                         limit=self.limit, offset=0, **filters)
        total = tx.summarize_transactions(**filters)
        self.table.clear()
        for r in self.rows:
            income = r["kind"] == "income"
            self.table.add(
                r["id"],
                (formatters.format_date(r["transaction_date"]), tx.describe(r),
                 r["category_name"] or "Sem categoria", r["account_name"],
                 ("+" if income else "-") + money(r["amount"])),
                ("income" if income else "expense",))
        if selected and self.table.tree.exists(selected):
            self.table.tree.selection_set(selected)
        self._filters_active = filters
        shown = len(self.rows)
        text = (f"{total['count']} movimentação(ões) · Receitas {money(total['income'])} · "
                f"Despesas {money(total['expense'])} · Resultado {money(total['net'], signed=True)}")
        self.summary.configure(text=text, fg=c("muted"))
        if shown < total["count"]:
            self.more.configure()
            self.more.pack(side="right", padx=(0, 12))
        else:
            self.more.pack_forget()
        if not self.rows:
            self.empty.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.empty.lift()
        else:
            self.empty.place_forget()

    def load_more(self):
        self.limit += config.PAGE_SIZE
        self.reload()

    def _sorted(self, key, descending):
        self.sort_key, self.descending = key, descending
        self.limit = config.PAGE_SIZE
        self.reload()

    # ---------------- ações ----------------
    def _popup(self, event):
        row = self.table.tree.identify_row(event.y)
        if row:
            self.table.tree.selection_set(row)
            self.menu.tk_popup(event.x_root, event.y_root)

    def _selected_row(self):
        sel = self.table.selected()
        if not sel:
            self.app.toast("Selecione uma movimentação na lista.", "info")
            return None
        return tx.get_transaction(int(sel))

    def edit_selected(self):
        row = self._selected_row()
        if row:
            self.app.edit_transaction(row)

    def duplicate_selected(self):
        row = self._selected_row()
        if row:
            data = tx.duplicate_transaction_defaults(row["id"])
            self.app.new_transaction(defaults=data)

    def delete_selected(self):
        row = self._selected_row()
        if not row:
            return
        whole = False
        if row["installment_group"]:
            text = (f"“{row['description']}” é uma compra parcelada em "
                    f"{row['installment_total']} vezes. Excluir somente esta parcela?")
            if dialogs.confirm(self.app, "Excluir parcela", text, "Só esta parcela", False):
                pass
            elif dialogs.confirm(self.app, "Excluir compra parcelada",
                                 "Excluir TODAS as parcelas desta compra?", "Excluir todas"):
                whole = True
            else:
                return
        elif not dialogs.confirm(
                self.app, "Excluir movimentação",
                f"Excluir “{row['description']}” de {money(row['amount'])}? "
                "Você poderá desfazer logo em seguida."):
            return

        def run():
            deleted = tx.delete_transaction(row["id"], whole_group=whole)
            self.app.after_change()
            self.app.undoable("Movimentação excluída.", lambda: tx.restore_transactions(deleted))
        self.guarded(run)

    def export_csv(self):
        def run():
            filters = self._filters()
            rows = tx.list_transactions(order_by="date", descending=True, **filters)
            if not rows:
                self.app.toast("Não há movimentações para exportar com esses filtros.")
                return
            path = filedialog.asksaveasfilename(
                parent=self.app.root, title="Exportar movimentações", defaultextension=".csv",
                initialfile=f"movimentacoes_{date.today().isoformat()}.csv",
                filetypes=[("CSV", "*.csv")])
            if path:
                n = importer.export_csv(path, rows)
                self.app.toast(f"{n} movimentação(ões) exportada(s).", "success")
        self.guarded(run)

    def import_csv(self):
        dlg = dialogs.ImportDialog(self.app)
        result = dlg.wait()
        if result:
            self.app.after_change()
            text = f"{result['imported']} importada(s)"
            if result["skipped"]:
                text += f", {result['skipped']} ignorada(s) por já existirem"
            if result["fallback_categories"]:
                text += f". {result['fallback_categories']} sem categoria conhecida foram para “Outras”"
            self.app.toast(text + ".", "success")
