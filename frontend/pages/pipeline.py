"""Vencimentos: quadro com as colunas do ``planning.bills_board`` (a pagar,
vencendo, lançado, recebido) ou uma lista ordenável com as mesmas linhas.
Projeções de recorrências (source=recurring) aparecem, mas não são editáveis."""

import tkinter as tk
from datetime import date
from tkinter import filedialog

from backend.services import accounts, importer, planning, transactions as tx
from frontend import motion
from frontend.pages.base import Page, kpi, money_fmt
from frontend.pages.dashboard import clip
from frontend.theme import STAGES, c, mix
from frontend.ui import Chip, CircleButton, SearchField, popup_menu
from frontend.widgets import Button, Card, Icon, ScrollFrame, Segmented, SortableTree, label
from backend.utils import formatters
from backend.utils.formatters import money
from backend.utils.i18n import category_label, t

STAGE_KEYS = ["to_pay", "due_soon", "paid", "received"]
DATE_KEY = {"to_pay": "due_on", "due_soon": "due_on", "paid": "posted_on", "received": "received_on"}
RISE = 12          # px de subida na entrada
RISE_TIME = 0.45   # s
COLUMN_STEP = 0.06  # atraso entre colunas
CARD_STEP = 0.04    # atraso entre cards


class PipelinePage(Page):
    title_key = "page.pipeline.title"

    def build(self):
        self.view, self.account_id = "board", None
        self.sort_key, self.descending = "date", False
        self.groups = {k: [] for k in STAGE_KEYS}
        self._row_by_iid = {}
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self._render())

        self.bar = tk.Frame(self, bg=c("bg"))
        self.bar.pack(fill="x", pady=(0, 16))
        Button(self.bar, t("common.new_transaction"), lambda: self.app.new_transaction(), "primary",
               icon="plus", pad=(14, 8)).pack(side="right")
        CircleButton(self.bar, "download", self.export_csv, size=36, tooltip=t("rail.export"),
                     bg=c("bg")).pack(side="right", padx=(0, 10))
        Segmented(self.bar, [("board", t("pipeline.view_board")), ("list", t("pipeline.view_list"))],
                  self.view, self._set_view, bg=c("bg"), size=11).pack(side="right", padx=(0, 10))
        SearchField(self.bar, variable=self.query, placeholder=t("pipeline.search"), width=240,
                    bg=c("bg")).pack(side="left")
        self.chip_row = tk.Frame(self.bar, bg=c("bg"))
        self.chip_row.pack(side="left", fill="x", expand=True, padx=(14, 0))

        self.body = tk.Frame(self, bg=c("bg"))
        self.body.pack(fill="both", expand=True)

    # ---------------------------------------------------------------- dados
    def refresh(self):
        super().refresh()
        self._build_chips()
        self._load()
        self._render()

    def _load(self):
        data = planning.bills_board(account_id=self.account_id)
        self.groups = {k: data[k] for k in STAGE_KEYS}

        def total(rows):
            return sum(r["amount"] for r in rows)
        self.publish([
            kpi("calendar-clock", total(data["to_pay"]) + total(data["due_soon"]),
                t("pipeline.kpi_to_pay"), money_fmt()),
            kpi("bell", total(data["due_soon"]), t("pipeline.kpi_due_soon"), money_fmt()),
            kpi("circle-check", total(data["paid"]), t("pipeline.kpi_paid"), money_fmt()),
        ])

    def _visible(self):
        """[(situação, linha)] das colunas que passam pela busca."""
        q = self.query.get().strip().lower()
        out = []
        for key in STAGE_KEYS:
            for r in self.groups[key]:
                haystack = f"{r['description']} {r['category_name'] or ''} {r['account_name']}".lower()
                if not q or q in haystack:
                    out.append((key, r))
        return out

    def _build_chips(self):
        for w in self.chip_row.winfo_children():
            w.destroy()
        options = [(None, t("pipeline.all_accounts"), "layout-grid")]
        options += [(a["id"], clip(a["name"], 18), "wallet") for a in accounts.list_accounts()]
        for account_id, name, icon in options:
            Chip(self.chip_row, name, active=self.account_id == account_id,
                 command=lambda i=account_id: self._pick(i), icon_name=icon,
                 bg=c("bg")).pack(side="left", padx=(0, 8))

    def _pick(self, account_id):
        self.account_id = account_id
        self.refresh()

    def _set_view(self, view):
        self.view = view
        self._render()

    def _sort(self, key, descending):
        self.sort_key, self.descending = key, descending
        self._render()

    # ---------------------------------------------------------------- telas
    def _render(self):
        for w in self.body.winfo_children():
            w.destroy()
        visible = self._visible()
        if not visible and (self.query.get().strip() or self.account_id):
            label(self.body, t("pipeline.no_match"), 11, color="muted", bg=c("bg")).pack(fill="x", pady=24)
        if self.view == "list":
            self._list(visible)
        else:
            self._board(visible)

    def _board(self, visible):
        scroll = ScrollFrame(self.body)
        scroll.pack(fill="both", expand=True)
        grid = scroll.inner
        for i in range(len(STAGE_KEYS)):
            grid.grid_columnconfigure(i, weight=1, uniform="stage")
        for i, key in enumerate(STAGE_KEYS):
            rows = [r for stage, r in visible if stage == key]
            column = self._column(grid, key, rows, i)
            column.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 3 else 6),
                        pady=(0, 16))
            self._rise(column, i * COLUMN_STEP, lambda w, v: w.grid_configure(pady=(v, 16)))

    def _column(self, parent, key, rows, index):
        dot_name, tint = STAGES[key]
        tone = c(tint)
        column = Card(parent, 16, 16, fill=mix(c("bg"), tone, 0.45), radius=24, hover=False)
        b, f = column.body, column.fill
        head = tk.Frame(b, bg=f)
        head.pack(fill="x")
        dot = tk.Canvas(head, width=10, height=10, bg=f, highlightthickness=0)
        dot.create_oval(1, 1, 9, 9, fill=c(dot_name), outline=c(dot_name))
        dot.pack(side="left")
        label(head, t(f"pipeline.col_{key}"), 12, "semibold", bg=f).pack(side="left", padx=(8, 0))
        label(head, str(len(rows)), 10, "semibold", color="muted", bg=f).pack(side="right")
        label(b, money(sum(r["amount"] for r in rows)), 18, "medium", bg=f).pack(fill="x", pady=(6, 14))
        if not rows:
            label(b, t("pipeline.column_empty"), 10, color="muted", bg=f).pack(fill="x", pady=12)
        for j, r in enumerate(rows):
            card = self._card(b, key, r, tone, f)
            self._rise(card, index * COLUMN_STEP + 0.05 + j * CARD_STEP,
                       lambda w, v: w.pack_configure(pady=(v, 10)))
        return column

    def _card(self, parent, key, r, tone, fill):
        card = Card(parent, 14, 12, fill=tone, radius=18, hover=True)
        card.pack(fill="x", pady=(0, 10))
        b, f = card.body, card.fill
        head = tk.Frame(b, bg=f)
        head.pack(fill="x")
        label(head, t(f"pipeline.{DATE_KEY[key]}", date=formatters.format_date_short(r["date"])),
              9, "semibold", color="muted", bg=f).pack(side="left")
        more = CircleButton(head, "ellipsis", None, size=24, kind="plain", bg=f, icon_size=13)
        more.command = lambda r=r, m=more: popup_menu(m, self._menu(r))
        more.pack(side="right")
        label(b, clip(tx.describe(r), 24), 12, "semibold", bg=f).pack(fill="x", pady=(6, 0))
        category = category_label(r["category_name"]) if r["category_name"] else t("common.no_category")
        label(b, clip(f"{category} · {r['account_name']}", 30), 9, color="muted", bg=f).pack(fill="x")
        foot = tk.Frame(b, bg=f)
        foot.pack(fill="x", pady=(12, 0))
        label(foot, money(r["amount"]), 16, "semibold",
              "income" if r["kind"] == "income" else "text", bg=f).pack(side="left")
        if r["recurring_id"]:
            Icon(foot, "repeat", c("muted"), f, size=14).pack(side="right", anchor="s")
        if r["installment_total"]:
            label(foot, f"{r['installment_no']}/{r['installment_total']}", 9, "semibold",
                  color="muted", bg=f).pack(side="right", anchor="s", padx=(0, 8))
        return card

    def _list(self, visible):
        card = Card(self.body, 20, 16)
        card.pack(fill="both", expand=True)
        columns = [
            ("date", t("common.date"), 110, "w", True),
            ("description", t("common.description"), 260, "w", True),
            ("category", t("common.category"), 150, "w", True),
            ("account", t("common.account"), 140, "w", True),
            ("status", t("pipeline.col_status"), 120, "w", True),
            ("amount", t("common.amount"), 120, "e", True),
        ]
        self.table = SortableTree(card.body, columns, self._sort, self._open_selected, height=16)
        self.table.pack(fill="both", expand=True)
        self.table.mark_sort(self.sort_key, self.descending)
        rank = {k: i for i, k in enumerate(STAGE_KEYS)}
        keys = {
            "date": lambda sr: sr[1]["date"],
            "description": lambda sr: sr[1]["description"].lower(),
            "category": lambda sr: (sr[1]["category_name"] or "").lower(),
            "account": lambda sr: sr[1]["account_name"].lower(),
            "status": lambda sr: rank[sr[0]],
            "amount": lambda sr: sr[1]["amount"],
        }
        self._row_by_iid = {}
        for i, (stage, r) in enumerate(sorted(visible, key=keys[self.sort_key], reverse=self.descending)):
            self._row_by_iid[str(i)] = r
            category = category_label(r["category_name"]) if r["category_name"] else t("common.no_category")
            sign = "+" if r["kind"] == "income" else "−"
            self.table.add(i, (formatters.format_date_short(r["date"]), clip(tx.describe(r), 40), category,
                               r["account_name"], t(f"pipeline.col_{stage}"), sign + money(r["amount"])))

    def _open_selected(self):
        r = self._row_by_iid.get(self.table.selected())
        if r and r["source"] == "transaction":
            self.app.edit_transaction(tx.get_transaction(r["id"]))

    def _menu(self, r):
        if r["source"] == "recurring":
            return [(t("pipeline.open_recurring"), lambda: self.app.navigate("recurring"))]
        fresh = lambda: tx.get_transaction(r["id"])  # noqa: E731
        return [(t("common.edit"), lambda: self.app.edit_transaction(fresh())),
                (t("common.duplicate"), lambda: self.app.duplicate_transaction(r)),
                None,
                (t("common.delete"), lambda: self.app.delete_transaction(fresh()))]

    def _rise(self, widget, delay, place):
        """Sobe o widget ~12 px com atraso (ease power3.out); sem animação se
        o usuário pediu movimento reduzido."""
        if motion.reduced_motion():
            return
        place(widget, RISE)

        def step(v):
            try:
                place(widget, round(v))
            except tk.TclError:  # a tela foi redesenhada antes do fim
                pass
        motion.tween(widget, RISE, 0, RISE_TIME, "power3.out", on_update=step, delay=delay)

    # ---------------------------------------------------------------- ações
    def export_csv(self):
        def run():
            rows = [{"transaction_date": r["date"], "kind": r["kind"], "description": r["description"],
                     "category_name": r["category_name"], "account_name": r["account_name"],
                     "amount": r["amount"], "notes": ""} for _, r in self._visible()]
            if not rows:
                self.app.toast(t("pipeline.no_match"))
                return
            path = filedialog.asksaveasfilename(
                parent=self.app.root, title=t("rail.export"), defaultextension=".csv",
                initialfile=f"vencimentos_{date.today().isoformat()}.csv",
                filetypes=[("CSV", "*.csv")])
            if path:
                n = importer.export_csv(path, rows)
                self.app.toast(t("pipeline.exported", count=n), "success")
        self.guarded(run)
