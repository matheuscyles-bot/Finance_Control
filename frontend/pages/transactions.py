"""Movimentações: busca, filtros, ordenação e ações por linha. Os totais do
período aparecem nos KPIs do cabeçalho; a lista é paginada (Carregar mais)."""

import tkinter as tk
from datetime import date, timedelta
from tkinter import filedialog

from backend import config
from backend.services import accounts, categories, importer, transactions as tx
from frontend import dialogs
from frontend.pages.base import Page, kpi, money_fmt
from frontend.pages.dashboard import clip
from frontend.theme import c, font, mix
from frontend.ui import CircleButton, Panel, PillSelect, SearchField, popup_menu
from frontend.widgets import Button, DateField, EmptyState, ScrollFrame, Segmented, label
from backend.utils import formatters
from backend.utils.formatters import money
from backend.utils.i18n import category_label, t

# opção de ordenação -> (coluna, descendente)
SORTS = {"date_desc": ("date", True), "date_asc": ("date", False),
         "amount_desc": ("amount", True), "amount_asc": ("amount", False)}
SORT_KEY = {"date_desc": "transactions.sort_date_desc", "date_asc": "transactions.sort_date_asc",
            "amount_desc": "transactions.sort_amount_desc", "amount_asc": "transactions.sort_amount_asc"}


class TransactionsPage(Page):
    title_key = "nav.transactions"

    def build(self):
        self.limit = config.PAGE_SIZE
        self.sort = "date_desc"
        self.rows = []
        self._search_job = None
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self._debounce())

        # foot vai primeiro para ficar colado embaixo
        self.foot = tk.Frame(self, bg=c("bg"))
        self.foot.pack(side="bottom", fill="x", pady=(12, 0))
        self.summary = label(self.foot, "", 11, bg="bg", color="muted")
        self.summary.pack(side="left")
        self.more = Button(self.foot, t("common.load_more"), self._load_more, "secondary", pad=(12, 6))

        self.bar = tk.Frame(self, bg=c("bg"))
        self.bar.pack(fill="x", pady=(0, 10))
        self.search_field = SearchField(self.bar, variable=self.query,
                                        placeholder=t("common.search_placeholder"), width=240, bg=c("bg"))
        self.search_field.pack(side="left")
        self.sort_select = PillSelect(self.bar, [(k, t(SORT_KEY[k])) for k in SORTS], icon_name="list",
                                      bg=c("bg"))
        self.sort_select.set_id(self.sort)
        self.sort_select.pack(side="right")
        self.sort_select.bind("<<ComboboxSelected>>", lambda e: self._sort_changed())

        self.filters = tk.Frame(self, bg=c("bg"))
        self.filters.pack(fill="x", pady=(0, 14))
        periods = [
            ("month", t("common.month_current")),
            ("last_month", t("common.month_previous")),
            ("90", t("common.last_90_days")),
            ("year", t("common.year_current")),
            ("all", t("common.all_period")),
            ("custom", t("common.custom")),
        ]
        self.period = PillSelect(self.filters, periods, icon_name="calendar-days", bg=c("bg"))
        self.period.set_id("month")
        self.period.pack(side="left", padx=(0, 10))
        self.period.bind("<<ComboboxSelected>>", lambda e: self._period_changed())
        self.kind = Segmented(self.filters, [("all", t("common.all_types")), ("income", t("common.income")),
                                             ("expense", t("common.expense"))],
                              "all", lambda _v: self._reset(), bg=c("bg"), size=11)
        self.kind.pack(side="left", padx=(0, 10))
        self.account = PillSelect(self.filters, [], allow_empty=t("common.all_accounts"), icon_name="wallet",
                                  bg=c("bg"))
        self.account.pack(side="left", padx=(0, 10))
        self.account.bind("<<ComboboxSelected>>", lambda e: self._reset())
        self.category = PillSelect(self.filters, [], allow_empty=t("common.all_categories"),
                                   icon_name="layout-grid", bg=c("bg"))
        self.category.pack(side="left", padx=(0, 10))
        self.category.bind("<<ComboboxSelected>>", lambda e: self._reset())
        clear = tk.Label(self.filters, text=t("common.clear_filters"), fg=c("primary"), bg=c("bg"),
                         font=font(11, "bold"), cursor="hand2")
        clear.pack(side="left")
        clear.bind("<Button-1>", lambda e: self.clear_filters())

        self.custom = tk.Frame(self, bg=c("bg"))
        label(self.custom, t("common.from"), 11, color="muted", bg="bg").pack(side="left", padx=(0, 4))
        self.start = DateField(self.custom, width=10)
        self.start.pack(side="left", padx=(0, 10))
        label(self.custom, t("common.until"), 11, color="muted", bg="bg").pack(side="left", padx=(0, 4))
        self.end = DateField(self.custom, width=10)
        self.end.pack(side="left")
        for f in (self.start, self.end):
            f.bind("<<DateChanged>>", lambda e: self._reset())
        Button(self.custom, t("common.apply"), self._reset, "secondary", pad=(10, 4)).pack(side="left", padx=10)

        self.scroll = ScrollFrame(self, bg=c("bg"))
        self.scroll.pack(fill="both", expand=True)

    # ---------------------------------------------------------------- cabeçalho
    def header_actions(self, parent):
        return [
            Button(parent, t("common.import_csv"), self.import_csv, "secondary", icon="upload"),
            Button(parent, t("common.export_csv"), self.export_csv, "secondary", icon="download"),
            Button(parent, t("common.new_transaction"), self.app.new_transaction, "primary", icon="plus"),
        ]

    def focus_search(self):
        self.search_field.focus()

    # ---------------------------------------------------------------- filtros
    def _debounce(self):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(250, self._reset)

    def _sort_changed(self):
        self.sort = self.sort_select.get_id()
        self._reset()

    def _period_changed(self):
        if self.period.get_id() == "custom":
            self.custom.pack(fill="x", pady=(0, 14), before=self.scroll)
        else:
            self.custom.pack_forget()
        self._reset()

    def clear_filters(self):
        self.query.set("")
        self.period.set_id("month")
        self.kind.set("all")
        self.category.current(0)
        self.account.current(0)
        self.custom.pack_forget()
        self._reset()

    def _reset(self):
        self._search_job = None
        self.limit = config.PAGE_SIZE
        self.reload()

    def _load_more(self):
        self.limit += config.PAGE_SIZE
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
        kind = self.kind.get()
        return dict(
            start_date=start, end_date=end,
            kind=None if kind == "all" else kind,
            category_id=self.category.get_id(), search=self.query.get(),
            account_id=self.account.get_id(),
        )

    # ---------------------------------------------------------------- dados
    def refresh(self):
        super().refresh()
        cat_items = [(-1, t("common.no_category"))] + [
            (r["id"], category_label(r["name"])) for r in categories.get_categories()]
        self.category.set_items(cat_items)
        self.account.set_items([(r["id"], r["name"]) for r in accounts.list_accounts(include_archived=True)])
        self.reload()

    def reload(self):
        self._search_job = None
        try:
            filters = self._filters()
        except ValueError as exc:
            self.summary.configure(text=str(exc), fg=c("danger"))
            return
        order, descending = SORTS[self.sort]
        self.rows = tx.list_transactions(order_by=order, descending=descending,
                                         limit=self.limit, offset=0, **filters)
        total = tx.summarize_transactions(**filters)
        self.publish([
            kpi("trending-up", total["income"], t("common.income"), money_fmt()),
            kpi("trending-down", total["expense"], t("common.expense"), money_fmt()),
            kpi("wallet", total["net"], t("transactions.kpi_net"), money_fmt(signed=True)),
        ])
        self._render()
        text = t("transactions.summary", count=total["count"], income=money(total["income"]),
                 expense=money(total["expense"]), net=money(total["net"], signed=True))
        self.summary.configure(text=text, fg=c("muted"))
        if len(self.rows) < total["count"]:
            self.more.pack(side="right", padx=(0, 12))
        else:
            self.more.pack_forget()

    def _render(self):
        for w in self.scroll.inner.winfo_children():
            w.destroy()
        if not self.rows:
            EmptyState(self.scroll.inner, "list", t("common.no_transactions"), t("common.adjust_filters"),
                       t("common.new_transaction"), self.app.new_transaction).pack(fill="both", expand=True)
            return
        panel = Panel(self.scroll.inner, padx=8, pady=6, hover=False)
        panel.pack(fill="x")
        for i, r in enumerate(self.rows):
            if i:
                tk.Frame(panel.body, height=1, bg=mix(panel.fill, c("text"), 0.06)).pack(fill="x", padx=12)
            self._row(panel.body, r, panel.fill)

    def _row(self, parent, r, fill):
        income = r["kind"] == "income"
        row = tk.Frame(parent, bg=fill)
        row.pack(fill="x")
        dot = tk.Canvas(row, width=10, height=10, bg=fill, highlightthickness=0)
        tone = c("income" if income else "expense")
        dot.create_oval(1, 1, 9, 9, fill=tone, outline=tone)
        dot.pack(side="left", padx=(14, 12))
        text = tk.Frame(row, bg=fill)
        text.pack(side="left", fill="x", expand=True, pady=10)
        label(text, clip(tx.describe(r), 48), 12, "semibold", bg=fill).pack(anchor="w")
        category = category_label(r["category_name"]) if r["category_name"] else t("common.no_category")
        label(text, clip(f"{formatters.format_date_short(r['transaction_date'])} · {category} · "
                         f"{r['account_name']}", 70), 10, color="muted", bg=fill).pack(anchor="w")
        label(row, ("+" if income else "−") + money(r["amount"]), 13, "semibold",
              "income" if income else "text", bg=fill).pack(side="right", padx=(12, 0))
        # duplo clique abre a edição; o botão ⋯ concentra as outras ações
        self._bind_open(row, r)
        more = CircleButton(row, "ellipsis", None, size=24, kind="plain", bg=fill, icon_size=13)
        more.command = lambda r=r, m=more: popup_menu(m, self._menu(r))
        more.pack(side="right", padx=(0, 14))

    def _bind_open(self, widget, r):
        if isinstance(widget, (CircleButton,)):
            return
        widget.bind("<Double-Button-1>", lambda e, r=r: self._open(r))
        for child in widget.winfo_children():
            self._bind_open(child, r)

    # ---------------------------------------------------------------- ações
    def _open(self, r):
        self.app.edit_transaction(tx.get_transaction(r["id"]))

    def _menu(self, r):
        fresh = lambda: tx.get_transaction(r["id"])  # noqa: E731
        return [(t("common.edit"), lambda: self.app.edit_transaction(fresh())),
                (t("common.duplicate"), lambda: self.app.duplicate_transaction(fresh())),
                None,
                (t("common.delete"), lambda: self.app.delete_transaction(fresh()))]

    def export_csv(self):
        def run():
            rows = tx.list_transactions(order_by="date", descending=True, **self._filters())
            if not rows:
                self.app.toast(t("transactions.no_export"))
                return
            path = filedialog.asksaveasfilename(
                parent=self.app.root, title=t("common.export_csv"), defaultextension=".csv",
                initialfile=f"movimentacoes_{date.today().isoformat()}.csv",
                filetypes=[("CSV", "*.csv")])
            if path:
                n = importer.export_csv(path, rows)
                self.app.toast(t("transactions.exported", count=n), "success")
        self.guarded(run)

    def import_csv(self):
        dlg = dialogs.ImportDialog(self.app)
        result = dlg.wait()
        if result:
            self.app.after_change()
            text = t("toast.imported", count=result["imported"])
            if result["skipped"]:
                text += " " + t("toast.import_skipped", count=result["skipped"])
            if result["fallback_categories"]:
                text += " " + t("toast.import_fallback", count=result["fallback_categories"])
            self.app.toast(text, "success")
