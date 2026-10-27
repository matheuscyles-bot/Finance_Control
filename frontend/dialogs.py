"""Janelas de diálogo (formulários e confirmações)."""

import tkinter as tk
from tkinter import filedialog, ttk

from backend import config
from backend.services import (accounts, budgets, categories, importer, recurring,
                      transactions as tx)
from frontend import theme
from frontend.theme import SPACING, c, font
from frontend.widgets import (Button, ChoiceCombo, DateField, Segmented, label, separator)
from backend.utils import formatters
from backend.utils.money import minor_to_text


class Dialog(tk.Toplevel):
    """Base: janela modal com título, corpo, mensagem de erro e botões."""

    def __init__(self, app, title, subtitle=None, width=460, save_text="Salvar",
                 danger=False):
        super().__init__(app.root)
        self.app = app
        self.withdraw()
        self.title(title)
        self.configure(bg=c("surface"))
        self.resizable(False, False)
        self.transient(app.root)
        self.result = None

        head = tk.Frame(self, bg=c("surface"))
        head.pack(fill="x", padx=28, pady=(SPACING["xl"], 6))
        label(head, title, 17, "bold").pack(fill="x")
        if subtitle:
            tk.Label(head, text=subtitle, bg=c("surface"), fg=c("muted"), font=font(11),
                     justify="left", anchor="w", wraplength=width - 50).pack(fill="x", pady=(4, 0))
        self.body = tk.Frame(self, bg=c("surface"))
        self.body.pack(fill="both", expand=True, padx=28, pady=(14, 6))
        self.error = tk.Label(self, text="", bg=c("surface"), fg=c("danger"), font=font(11),
                              anchor="w", justify="left", wraplength=width - 50)
        self.error.pack(fill="x", padx=28)
        foot = tk.Frame(self, bg=c("surface_alt"))
        foot.pack(fill="x", pady=(14, 0))
        inner = tk.Frame(foot, bg=c("surface_alt"))
        inner.pack(fill="x", padx=28, pady=14)
        self.save_button = Button(inner, save_text, self.submit, "danger" if danger else "primary")
        self.save_button.pack(side="right")
        Button(inner, "Cancelar", self.close, "secondary").pack(side="right", padx=(0, 10))
        self.bind("<Escape>", lambda e: self.close())
        self.bind("<Return>", lambda e: self.submit())
        self.minsize(width, 0)
        self._width = width

    def present(self, focus=None):
        self.update_idletasks()
        root = self.app.root
        x = root.winfo_rootx() + (root.winfo_width() - self.winfo_reqwidth()) // 2
        y = root.winfo_rooty() + max(30, (root.winfo_height() - self.winfo_reqheight()) // 3)
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.grab_set()
        if focus is not None:
            focus.focus_set()
        return self

    def wait(self):
        self.app.root.wait_window(self)
        return self.result

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def show_error(self, message):
        self.error.configure(text=message)

    def field(self, text, builder, hint=None):
        frame = tk.Frame(self.body, bg=c("surface"))
        frame.pack(fill="x", pady=(0, SPACING["md"]))
        label(frame, text, 10, "bold", "muted").pack(fill="x", pady=(0, 3))
        widget = builder(frame)
        widget.pack(fill="x", anchor="w")
        if hint:
            label(frame, hint, 9, color="muted").pack(fill="x", pady=(2, 0))
        return widget

    def submit(self):
        try:
            if self.save() is not False:
                self.close()
        except ValueError as exc:
            self.show_error(str(exc))

    def save(self):  # sobrescrito
        return True


def confirm(app, title, message, confirm_text="Excluir", danger=True):
    class _Confirm(Dialog):
        def save(self_inner):
            self_inner.result = True
    dlg = _Confirm(app, title, message, width=420, save_text=confirm_text, danger=danger)
    dlg.present(dlg.save_button)
    return bool(dlg.wait())


def prompt_text(app, title, label_text, initial="", save_text="Salvar", subtitle=None):
    class _Prompt(Dialog):
        def save(self_inner):
            self_inner.result = self_inner.entry.get()
    dlg = _Prompt(app, title, subtitle, width=420, save_text=save_text)
    dlg.entry = dlg.field(label_text, lambda p: ttk.Entry(p, font=font(11)))
    dlg.entry.insert(0, initial)
    dlg.present(dlg.entry)
    return dlg.wait()


def _cat_items(kind):
    return [(r["id"], r["name"]) for r in categories.get_categories(kind)]


def _account_items(include=None):
    rows = accounts.list_accounts()
    items = [(r["id"], r["name"]) for r in rows]
    if include and include not in [i for i, _ in items]:
        row = accounts.get_account(include)
        if row:
            items.append((row["id"], row["name"] + " (arquivada)"))
    return items


class TransactionDialog(Dialog):
    def __init__(self, app, transaction=None, defaults=None, kind="expense"):
        self.transaction = transaction
        editing = transaction is not None
        super().__init__(app, "Editar movimentação" if editing else "Nova movimentação",
                         width=480)
        source = dict(transaction or defaults or {})
        self.kind = source["kind"] if source else kind
        self.segment = Segmented(self.body, [("expense", "Despesa"), ("income", "Receita")],
                                 self.kind, self._kind_changed)
        self.segment.pack(anchor="w", pady=(0, 12))
        locked = editing and transaction["installment_total"]
        if locked:
            for lbl in self.segment.items.values():
                lbl.unbind("<Button-1>")

        self.amount = self.field(
            "Valor", lambda p: ttk.Entry(p, font=font(13, "bold")))
        if source:
            self.amount.insert(0, minor_to_text(source["amount"]).replace(".", ","))
        self.description = self.field("Descrição", lambda p: ttk.Entry(p, font=font(11)))
        if source:
            self.description.insert(0, source["description"])
        row = tk.Frame(self.body, bg=c("surface"))
        row.pack(fill="x")
        left = tk.Frame(row, bg=c("surface"))
        left.pack(side="left", fill="x", expand=True, padx=(0, 8))
        right = tk.Frame(row, bg=c("surface"))
        right.pack(side="left", fill="x", expand=True)
        label(left, "Categoria", 10, "bold", "muted").pack(fill="x", pady=(0, 3))
        self.installments = None
        self.category = ChoiceCombo(left, [], width=20)
        self.category.pack(fill="x")
        label(right, "Conta", 10, "bold", "muted").pack(fill="x", pady=(0, 3))
        self.account = ChoiceCombo(right, _account_items(source.get("account_id") if source else None), width=20)
        self.account.pack(fill="x")
        if source and source.get("account_id"):
            self.account.set_id(source["account_id"])
        self._kind_changed(self.kind, initial=source.get("category_id") if source else None)

        row2 = tk.Frame(self.body, bg=c("surface"))
        row2.pack(fill="x", pady=(12, 0))
        dleft = tk.Frame(row2, bg=c("surface"))
        dleft.pack(side="left", padx=(0, 16))
        label(dleft, "Data", 10, "bold", "muted").pack(fill="x", pady=(0, 3))
        self.date = DateField(dleft, source.get("transaction_date") if source else None)
        self.date.pack(anchor="w")
        if not editing:
            dright = tk.Frame(row2, bg=c("surface"))
            dright.pack(side="left")
            label(dright, "Parcelas (despesas)", 10, "bold", "muted").pack(fill="x", pady=(0, 3))
            self.installments = ttk.Spinbox(dright, from_=1, to=config.MAX_INSTALLMENTS,
                                            width=5, font=font(11))
            self.installments.set(1)
            self.installments.pack(anchor="w")
            self._kind_changed(self.kind)
        self.notes = self.field("Observações (opcional)",
                                lambda p: ttk.Entry(p, font=font(11)))
        self.notes.master.pack_configure(pady=(12, 10))
        if source:
            self.notes.insert(0, source.get("notes") or "")
        self.present(self.amount)

    def _kind_changed(self, kind, initial=None):
        self.kind = kind
        self.category.set_items(_cat_items(kind), keep=False)
        if initial:
            self.category.set_id(initial)
        if self.installments is not None:
            self.installments.configure(state="normal" if kind == "expense" else "disabled")
            if kind != "expense":
                self.installments.set(1)

    def save(self):
        notes = self.notes.get()
        date_iso = self.date.get_iso()
        if self.transaction:
            tx.update_transaction(self.transaction["id"], self.description.get(),
                                  self.amount.get(), self.kind, self.category.get_id(),
                                  date_iso, notes, self.account.get_id())
            self.result = "updated"
        else:
            parts = int(self.installments.get() or 1) if self.installments else 1
            tx.add_transaction(self.description.get(), self.amount.get(), self.kind,
                               self.category.get_id(), date_iso, notes,
                               self.account.get_id(), parts)
            self.result = "created"


class TransferDialog(Dialog):
    def __init__(self, app, transfer=None):
        self.transfer = transfer
        super().__init__(app, "Editar transferência" if transfer else "Nova transferência",
                         "Mover dinheiro entre contas não conta como receita nem despesa.",
                         width=460)
        items = _account_items()
        if transfer:
            for aid in (transfer["from_account_id"], transfer["to_account_id"]):
                if aid not in [i for i, _ in items]:
                    items = _account_items(aid)
        self.origin = self.field("De", lambda p: ChoiceCombo(p, items, width=30))
        self.target = self.field("Para", lambda p: ChoiceCombo(p, items, width=30))
        if len(items) > 1:
            self.target.current(1)
        self.amount = self.field("Valor", lambda p: ttk.Entry(p, font=font(13, "bold")))
        row = tk.Frame(self.body, bg=c("surface"))
        row.pack(fill="x")
        label(row, "Data", 10, "bold", "muted").pack(fill="x", pady=(0, 3))
        self.date = DateField(row, transfer["transfer_date"] if transfer else None)
        self.date.pack(anchor="w")
        self.notes = self.field("Observações (opcional)", lambda p: ttk.Entry(p, font=font(11)))
        self.notes.master.pack_configure(pady=(12, 10))
        if transfer:
            self.origin.set_id(transfer["from_account_id"])
            self.target.set_id(transfer["to_account_id"])
            self.amount.insert(0, minor_to_text(transfer["amount"]).replace(".", ","))
            self.notes.insert(0, transfer["notes"] or "")
        self.present(self.amount)

    def save(self):
        args = (self.origin.get_id(), self.target.get_id(), self.amount.get(),
                self.date.get_iso(), self.notes.get())
        if self.transfer:
            accounts.update_transfer(self.transfer["id"], *args)
        else:
            accounts.add_transfer(*args)
        self.result = True


class AccountDialog(Dialog):
    def __init__(self, app, account=None):
        self.account = account
        super().__init__(app, "Editar conta" if account else "Nova conta", width=440)
        self.name = self.field("Nome", lambda p: ttk.Entry(p, font=font(11)))
        types = list(config.ACCOUNT_TYPES.items())
        self.type = self.field("Tipo", lambda p: ChoiceCombo(p, types, width=30))
        self.opening = self.field(
            "Saldo inicial", lambda p: ttk.Entry(p, font=font(11)),
            "O saldo da conta quando você começou a usar o app (pode ser negativo).")
        if account:
            self.name.insert(0, account["name"])
            self.type.set_id(account["type"])
            self.opening.insert(0, minor_to_text(account["opening_balance"]).replace(".", ","))
        else:
            self.opening.insert(0, "0,00")
        self.present(self.name)

    def save(self):
        if self.account:
            accounts.update_account(self.account["id"], self.name.get(),
                                    self.type.get_id(), self.opening.get())
        else:
            accounts.add_account(self.name.get(), self.type.get_id(), self.opening.get())
        self.result = True


class BudgetDialog(Dialog):
    def __init__(self, app, month, category_id=None, amount=None):
        self.month = month
        super().__init__(app, "Orçamento do mês",
                         f"{formatters.month_label(month)} · limite de gasto por categoria",
                         width=420)
        items = _cat_items("expense")
        self.category = self.field("Categoria", lambda p: ChoiceCombo(p, items, width=30))
        if category_id:
            self.category.set_id(category_id)
        self.amount = self.field("Limite do mês", lambda p: ttk.Entry(p, font=font(13, "bold")))
        if amount:
            self.amount.insert(0, minor_to_text(amount).replace(".", ","))
        self.present(self.amount)

    def save(self):
        budgets.save_budget(self.month, self.category.get_id(), self.amount.get())
        self.result = True


class RecurringDialog(Dialog):
    def __init__(self, app, rule=None):
        self.rule = rule
        super().__init__(app, "Editar recorrência" if rule else "Nova recorrência",
                         "Lançamentos criados automaticamente (aluguel, assinaturas, salário...).",
                         width=480)
        self.kind = rule["kind"] if rule else "expense"
        self.segment = Segmented(self.body, [("expense", "Despesa"), ("income", "Receita")],
                                 self.kind, self._kind_changed)
        self.segment.pack(anchor="w", pady=(0, 12))
        self.amount = self.field("Valor", lambda p: ttk.Entry(p, font=font(13, "bold")))
        self.description = self.field("Descrição", lambda p: ttk.Entry(p, font=font(11)))
        row = tk.Frame(self.body, bg=c("surface"))
        row.pack(fill="x")
        a = tk.Frame(row, bg=c("surface"))
        a.pack(side="left", fill="x", expand=True, padx=(0, 8))
        b = tk.Frame(row, bg=c("surface"))
        b.pack(side="left", fill="x", expand=True)
        label(a, "Categoria", 10, "bold", "muted").pack(fill="x", pady=(0, 3))
        self.category = ChoiceCombo(a, [], width=20)
        self.category.pack(fill="x")
        label(b, "Conta", 10, "bold", "muted").pack(fill="x", pady=(0, 3))
        self.account = ChoiceCombo(b, _account_items(rule["account_id"] if rule else None), width=20)
        self.account.pack(fill="x")
        row2 = tk.Frame(self.body, bg=c("surface"))
        row2.pack(fill="x", pady=(12, 0))
        f1 = tk.Frame(row2, bg=c("surface"))
        f1.pack(side="left", padx=(0, 12))
        label(f1, "Frequência", 10, "bold", "muted").pack(fill="x", pady=(0, 3))
        self.frequency = ChoiceCombo(f1, list(config.FREQUENCIES.items()), width=11)
        self.frequency.pack()
        self.frequency.set_id("monthly")
        f2 = tk.Frame(row2, bg=c("surface"))
        f2.pack(side="left", padx=(0, 12))
        label(f2, "Próxima data" if rule else "Começa em", 10, "bold", "muted").pack(fill="x", pady=(0, 3))
        self.start = DateField(f2, rule["next_date"] if rule else None, width=11)
        self.start.pack()
        f3 = tk.Frame(row2, bg=c("surface"))
        f3.pack(side="left")
        label(f3, "Termina em (opcional)", 10, "bold", "muted").pack(fill="x", pady=(0, 3))
        self.end = DateField(
            f3, rule["end_date"] if rule and rule["end_date"] else None,
            width=11, optional=True
        )
        self.end.pack()
        self.notes = self.field("Observações (opcional)", lambda p: ttk.Entry(p, font=font(11)))
        self.notes.master.pack_configure(pady=(12, 10))
        if rule:
            self.amount.insert(0, minor_to_text(rule["amount"]).replace(".", ","))
            self.description.insert(0, rule["description"])
            self.frequency.set_id(rule["frequency"])
            self.notes.insert(0, rule["notes"] or "")
        self._kind_changed(self.kind, rule["category_id"] if rule else None)
        self.present(self.amount)

    def _kind_changed(self, kind, initial=None):
        self.kind = kind
        self.category.set_items(_cat_items(kind), keep=False)
        if initial:
            self.category.set_id(initial)

    def save(self):
        end = self.end.get() or None
        end_iso = formatters.parse_date(end) if end else None
        args = (self.description.get(), self.amount.get(), self.kind,
                self.category.get_id(), self.account.get_id(), self.frequency.get_id(),
                self.start.get_iso(), end_iso, self.notes.get())
        if self.rule:
            recurring.update_recurring(self.rule["id"], *args)
        else:
            recurring.add_recurring(*args)
        self.result = True


class MoveCategoryDialog(Dialog):
    """Escolhe para onde mover os dados antes de excluir a categoria."""

    def __init__(self, app, category, count):
        self.category = category
        super().__init__(app, "Excluir categoria",
                         f"“{category['name']}” tem {count} registro(s) associado(s). "
                         "Escolha a categoria que vai recebê-los.",
                         width=440, save_text="Mover e excluir", danger=True)
        items = [(i, n) for i, n in _cat_items(category["kind"]) if i != category["id"]]
        self.target = self.field("Mover para", lambda p: ChoiceCombo(p, items, width=30))
        if not items:
            self.show_error("Crie outra categoria do mesmo tipo antes de excluir esta.")
        self.present(self.target)

    def save(self):
        if self.target.get_id() is None:
            raise ValueError("Escolha uma categoria de destino.")
        categories.delete_category(self.category["id"], move_to=self.target.get_id())
        self.result = True


class ImportDialog(Dialog):
    """Escolhe o CSV, mostra um resumo e só grava depois da confirmação."""

    def __init__(self, app):
        super().__init__(app, "Importar movimentações (CSV)",
                         "A primeira linha deve ter: Data, Descrição, Valor e, se quiser, "
                         "Tipo, Categoria e Observações.", width=560, save_text="Importar")
        self.prep = None
        items = _account_items()
        self.account = self.field("Importar para a conta", lambda p: ChoiceCombo(p, items, width=34))
        self.account.bind("<<ComboboxSelected>>", lambda e: self._reload())
        self.path = None
        self.file_label = label(self.body, "Nenhum arquivo selecionado.", 11, color="muted")
        self.file_label.pack(fill="x", pady=(0, 6))
        Button(self.body, "Escolher arquivo…", self.choose, "secondary", icon="upload").pack(anchor="w")
        self.summary = tk.Label(self.body, text="", bg=c("surface"), fg=c("text"), font=font(11),
                                justify="left", anchor="w", wraplength=500)
        self.summary.pack(fill="x", pady=(12, 0))
        self.skip = tk.BooleanVar(value=True)
        tk.Checkbutton(self.body, text="Ignorar movimentações que já existem", variable=self.skip,
                       bg=c("surface"), fg=c("text"), selectcolor=c("surface"),
                       activebackground=c("surface"), font=font(11),
                       anchor="w").pack(fill="x", pady=(6, 0))
        self.present()

    def choose(self):
        path = filedialog.askopenfilename(parent=self, title="Escolha o arquivo CSV",
                                          filetypes=[("CSV", "*.csv *.txt"), ("Todos", "*.*")])
        if path:
            self.path = path
            self._reload()

    def _reload(self):
        if not self.path:
            return
        self.file_label.configure(text=self.path.split("/")[-1].split("\\")[-1], fg=c("text"))
        try:
            self.prep = importer.prepare_import(self.path, self.account.get_id())
        except (ValueError, OSError) as exc:
            self.prep = None
            self.summary.configure(text="")
            self.show_error(str(exc))
            return
        self.show_error("")
        p = self.prep
        text = (f"{len(p['rows'])} linha(s) válida(s), {p['duplicates']} já existente(s), "
                f"{len(p['errors'])} com problema.")
        if p["errors"]:
            first = "\n".join(f"Linha {n}: {m}" for n, m in p["errors"][:4])
            text += "\n" + first + ("\n…" if len(p["errors"]) > 4 else "")
        self.summary.configure(text=text)

    def save(self):
        if not self.prep:
            raise ValueError("Escolha um arquivo CSV válido.")
        result = importer.commit_import(self.prep["rows"], self.account.get_id(), self.skip.get())
        self.result = result
