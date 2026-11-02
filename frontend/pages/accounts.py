"""Contas: cards em grade (ou tabela ordenável), filtros por tipo e busca,
transferências entre contas. Arquivadas aparecem no fim, esmaecidas."""

import csv
import tkinter as tk
from datetime import date
from tkinter import filedialog

from backend.services import accounts, planning
from frontend import dialogs, motion
from frontend.charts import ProgressBar
from frontend.pages.base import Page, kpi, money_fmt, relative_day
from frontend.pages.dashboard import clip
from frontend.theme import c, font
from frontend.ui import Chip, CircleButton, PillSelect, SearchField, Star, Tooltip, avatar_color, initials, popup_menu
from frontend.widgets import Button, Card, EmptyState, ScrollFrame, Segmented, SortableTree, label, linespace, measure
from backend.utils import formatters
from backend.utils.formatters import money
from backend.utils.i18n import t

TYPES = ["checking", "savings", "cash", "credit_card"]
SORT_DESC = {"last": True, "balance": True, "name": False}  # ordem inicial de cada critério
RISE = 12          # px de subida na entrada
RISE_TIME = 0.45   # s
CARD_STEP = 0.04   # atraso entre cards
CARD_MIN = 262     # largura mínima de um card (px); cabem até 4 por linha
MAX_COLS = 4


def fit_text(text, spec, limit):
    """Corta o texto com "…" até caber em limit px, medido com a fonte spec."""
    if measure(spec, text) <= limit:
        return text
    cut = text
    while cut and measure(spec, cut + "…") > limit:
        cut = cut[:-1]
    return cut.rstrip() + "…"


class AccountsPage(Page):
    title_key = "page.accounts.title"

    def build(self):
        self.kind, self.view = None, "grid"
        self.sort_key, self.descending = "last", SORT_DESC["last"]
        self.rows, self.activity, self.total = [], {}, 0
        self._cols = 0
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self._render())

        self.bar = tk.Frame(self, bg=c("bg"))
        self.bar.pack(fill="x", pady=(0, 16))
        self.bar.grid_columnconfigure(1, weight=1)
        self.search = SearchField(self.bar, variable=self.query, placeholder=t("accounts.search"),
                                  width=240, bg=c("bg"))
        self.chip_row = tk.Frame(self.bar, bg=c("bg"))
        # ordenação, modo e exportar ficam juntos à direita (linha própria quando não cabem)
        self.tools = tk.Frame(self.bar, bg=c("bg"))
        Button(self.tools, t("common.new_account"), self.new_account, "primary",
               icon="plus", pad=(14, 8)).pack(side="right")
        Button(self.tools, t("common.export"), self.export_csv, "secondary",
               icon="download", pad=(14, 8)).pack(side="right", padx=(0, 10))
        Segmented(self.tools, [("grid", t("accounts.view_grid")), ("table", t("accounts.view_table"))],
                  self.view, self._set_view, bg=c("bg"), size=11).pack(side="right", padx=(0, 10))
        self.sort = PillSelect(self.tools, items=[("last", t("accounts.sort_last")),
                                                  ("balance", t("accounts.sort_balance")),
                                                  ("name", t("accounts.sort_name"))],
                               bg=c("bg"), max_width=200)
        self.sort.set_id(self.sort_key)
        self.sort.pack(side="right", padx=(0, 10))
        self.sort.bind("<<ComboboxSelected>>", lambda e: self._pick_sort(self.sort.get_id()))
        self._bar_wide = None
        self.bar.bind("<Configure>", lambda e: self._layout_bar())

        self.body = tk.Frame(self, bg=c("bg"))
        self.body.pack(fill="both", expand=True)
        self.bind("<Configure>", self._on_resize)

    def header_actions(self, parent):
        return [Button(parent, t("common.new_transfer"), self.new_transfer, "secondary", icon="transfer")]

    # ---------------------------------------------------------------- dados
    def refresh(self):
        super().refresh()
        self._build_chips()
        self.rows = accounts.list_accounts(include_archived=True)
        self.activity = planning.account_activity()
        self.total = accounts.total_balance()
        active = [a for a in self.rows if not a["archived"]]
        self.publish([
            kpi("wallet", len(active), t("accounts.kpi_active")),
            kpi("landmark", self.total, t("accounts.kpi_total"), money_fmt()),
            kpi("trending-up", sum(a["projected_balance"] for a in active),
                t("accounts.kpi_projected"), money_fmt()),
        ])
        self._render()

    def _visible(self):
        """Contas que passam pelo tipo e pela busca, ordenadas (arquivadas no fim)."""
        q = self.query.get().strip().lower()
        rows = [a for a in self.rows
                if (self.kind is None or a["type"] == self.kind)
                and (not q or q in a["name"].lower() or q in self._type_label(a).lower())]
        keys = {"last": lambda a: self.activity.get(a["id"]) or "",
                "balance": lambda a: a["balance"],
                "name": lambda a: a["name"].lower()}
        key = keys[self.sort_key]
        active = sorted((a for a in rows if not a["archived"]), key=key, reverse=self.descending)
        archived = sorted((a for a in rows if a["archived"]), key=key, reverse=self.descending)
        return active + archived

    def _type_label(self, a):
        return t(f"common.account_type.{a['type']}")

    def _share(self, a):
        """Participação no saldo total (0 se o total não for positivo ou a conta estiver arquivada)."""
        if a["archived"] or self.total <= 0:
            return 0.0
        return a["balance"] / self.total

    def _column_count(self):
        return max(1, min(MAX_COLS, self.winfo_width() // CARD_MIN))

    def _build_chips(self):
        for w in self.chip_row.winfo_children():
            w.destroy()
        options = [(None, t("accounts.type_all"))] + [(k, t(f"accounts.type_{k}")) for k in TYPES]
        for kind, text in options:
            Chip(self.chip_row, text, active=self.kind == kind,
                 command=lambda k=kind: self._pick_kind(k), bg=c("bg")).pack(side="left", padx=(0, 8))
        self._layout_bar()

    def _layout_bar(self):
        """Uma linha se busca + chips + ferramentas couberem na largura; senão, duas linhas."""
        if not self.bar.winfo_exists():
            return
        self.bar.update_idletasks()  # chips recém-criados precisam de tamanho medido
        need = self.search.winfo_reqwidth() + 14 + self.chip_row.winfo_reqwidth() + self.tools.winfo_reqwidth()
        wide = self.bar.winfo_width() >= need
        if wide == self._bar_wide:
            return
        self._bar_wide = wide
        self.search.grid_configure(row=0, column=0, sticky="w")
        self.chip_row.grid_configure(row=0, column=1, sticky="ew", padx=(14, 0))
        if wide:
            self.tools.grid_configure(row=0, column=2, columnspan=1, sticky="e", padx=0, pady=0)
        else:
            self.tools.grid_configure(row=1, column=0, columnspan=2, sticky="e", padx=0, pady=(10, 0))

    # ---------------------------------------------------------------- controles
    def _pick_kind(self, kind):
        self.kind = kind
        self._build_chips()
        self._render()

    def _pick_sort(self, key):
        self.sort_key, self.descending = key, SORT_DESC[key]
        self._render()

    def _sort(self, key, descending):
        self.sort_key, self.descending = key, descending
        self.sort.set_id(key)
        self._render()

    def _set_view(self, view):
        self.view = view
        self._render()

    def _on_resize(self, _event):
        if self.view == "grid" and self._column_count() != self._cols:
            self.after_idle(self._render)

    # ---------------------------------------------------------------- telas
    def _render(self):
        if not self.body.winfo_exists():
            return
        for w in self.body.winfo_children():
            w.destroy()
        scroll = ScrollFrame(self.body)
        scroll.pack(fill="both", expand=True)
        content = scroll.inner
        self._cols = self._column_count()
        visible = self._visible()
        if not self.rows:
            EmptyState(content, "wallet", t("accounts.empty_title"), t("accounts.empty_text"),
                       t("common.new_account"), self.new_account, bg=c("bg")).pack(fill="x", pady=24)
        elif not visible:
            label(content, t("accounts.no_match"), 11, color="muted", bg="bg").pack(fill="x", pady=24)
        elif self.view == "table":
            self._table(content, visible)
        else:
            self._grid(content, visible)
        self._transfers(content)

    def _grid(self, content, visible):
        grid = tk.Frame(content, bg=c("bg"))
        grid.pack(fill="x")
        cols = self._cols
        for i in range(cols):
            grid.grid_columnconfigure(i, weight=1, uniform="acc")
        main = next((a["id"] for a in self.rows if not a["archived"]), None)
        for i, a in enumerate(visible):
            card = self._account_card(grid, a, a["id"] == main)
            card.grid(row=i // cols, column=i % cols, sticky="nsew", padx=6, pady=6)
            self._rise(card, i * CARD_STEP, lambda w, v: w.grid_configure(pady=(6 + v, 6)))

    def _account_card(self, parent, a, main):
        archived = a["archived"]
        card = Card(parent, 18, 16, radius=24, hover=not archived)
        b, f = card.body, card.fill
        top = tk.Frame(b, bg=f)
        top.pack(fill="x")
        avatar = tk.Canvas(top, width=44, height=44, bg=f, highlightthickness=0, bd=0)
        avatar.create_oval(1, 1, 43, 43, fill=avatar_color(a["name"]), outline="")
        avatar.create_text(22, 22, text=initials(a["name"]), fill=c("bg"), font=font(13, "bold"))
        avatar.pack(side="left")
        Star(top, filled=main, size=18, bg=f).pack(side="right", anchor="n")
        # a caixa não propaga largura: um nome longo não alarga a célula da grade
        name_font = font(14, "semibold")
        name_box = tk.Frame(b, bg=f, height=linespace(name_font))
        name_box.pack(fill="x", pady=(12, 0))
        name_box.pack_propagate(False)
        name = label(name_box, a["name"], 14, "semibold", "muted" if archived else "text", bg=f)
        name.pack(fill="x")
        Tooltip(name, a["name"])
        name_box.bind("<Configure>", lambda e: name.configure(text=fit_text(a["name"], name_font, e.width)))
        if archived:
            label(b, t("common.archived"), 10, color="muted", bg=f).pack(fill="x")

        panel = Card(b, 14, 12, fill=c("surface_alt"), radius=18)
        panel.pack(fill="x", pady=(12, 0))
        pf = panel.fill
        metrics = tk.Frame(panel.body, bg=pf)
        metrics.pack(fill="x")
        left = tk.Frame(metrics, bg=pf)
        left.pack(side="left", fill="x", expand=True)
        label(left, t("accounts.sort_balance"), 10, color="muted", bg=pf).pack(anchor="w")
        label(left, money(a["balance"]), 14, "semibold",
              "expense" if a["balance"] < 0 else "text", bg=pf).pack(anchor="w")
        right = tk.Frame(metrics, bg=pf)
        right.pack(side="right")
        label(right, t("accounts.sort_last"), 10, color="muted", bg=pf).pack(anchor="e")
        label(right, relative_day(self.activity.get(a["id"])), 12, "semibold", bg=pf).pack(anchor="e")

        share = self._share(a)
        pct = round(share * 100)
        row = tk.Frame(b, bg=f)
        row.pack(fill="x", pady=(14, 0))
        bar = ProgressBar(row, bg=f, height=6)
        bar.pack(side="left", fill="x", expand=True)
        label(row, f"{pct}%", 11, "semibold", color="muted", bg=f).pack(side="right", padx=(10, 0))
        tone = {"checking": c("primary"), "savings": c("blue")}.get(a["type"], c("muted"))
        bar.set(min(1.0, max(0.0, share)), color=tone)

        foot = tk.Frame(b, bg=f)
        foot.pack(fill="x", pady=(12, 0))
        label(foot, self._type_label(a), 11, color="muted", bg=f).pack(side="left", anchor="s")
        # pack da direita para a esquerda: o primeiro empacotado fica mais à direita
        more = CircleButton(foot, "ellipsis", None, size=32, kind="plain", bg=f, icon_size=13,
                            tooltip=t("accounts.more"))
        more.command = lambda a=a, m=more: popup_menu(m, self._menu(a))
        more.pack(side="right")
        if archived:
            Button(foot, t("common.unarchive"), lambda: self.unarchive(a["id"]), "secondary",
                   pad=(10, 4)).pack(side="right", padx=(0, 6))
        else:
            CircleButton(foot, "pencil", lambda: self.edit_account(a["id"]), size=32, kind="plain",
                         bg=f, tooltip=t("common.edit")).pack(side="right", padx=(0, 4))
            CircleButton(foot, "transfer", self.new_transfer, size=32, kind="plain", bg=f,
                         tooltip=t("common.new_transfer")).pack(side="right")
        return card

    def _table(self, content, visible):
        card = Card(content, 20, 16)
        card.pack(fill="x")
        columns = [
            ("name", t("accounts.col_name"), 240, "w", True),
            ("type", t("accounts.col_type"), 180, "w", False),
            ("balance", t("accounts.sort_balance"), 140, "e", True),
            ("share", t("accounts.col_share"), 110, "e", False),
            ("last", t("accounts.sort_last"), 170, "w", True),
            ("status", t("accounts.col_status"), 110, "w", False),
        ]
        self.accounts_table = SortableTree(card.body, columns, self._sort, self._open_account,
                                           height=min(len(visible), 12))
        self.accounts_table.pack(fill="x")
        self.accounts_table.mark_sort(self.sort_key, self.descending)
        for a in visible:
            status = t("common.archived") if a["archived"] else t("accounts.status_active")
            self.accounts_table.add(str(a["id"]), (
                clip(a["name"], 32), self._type_label(a), money(a["balance"]),
                f"{round(self._share(a) * 100)}%", relative_day(self.activity.get(a["id"])), status))

    def _open_account(self):
        sel = self.accounts_table.selected()
        if sel:
            self.edit_account(int(sel))

    def _menu(self, a):
        if a["archived"]:
            items = [(t("common.unarchive"), lambda: self.unarchive(a["id"]))]
        else:
            items = [(t("common.archive"), lambda: self.archive(a))]
        if len(self.rows) > 1 and not any(accounts.account_usage(a["id"]).values()):
            items += [None, (t("common.delete"), lambda: self.delete(a))]
        return items

    def _transfers(self, content):
        card = Card(content, 0, 0)
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
        Button(foot, t("common.delete"), self.delete_transfer, "secondary", pad=(12, 5)).pack(side="right")
        Button(foot, t("common.edit"), self.edit_transfer, "secondary", pad=(12, 5)).pack(side="right", padx=8)

    def _rise(self, widget, delay, place):
        """Sobe o card ~12 px com atraso (ease power3.out); sem animação se
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

    # ---------------------------------------------------------------- contas
    def new_account(self):
        if dialogs.AccountDialog(self.app).wait():
            self.app.after_change()
            self.app.toast(t("toast.account_created"), "success")

    def edit_account(self, account_id):
        if dialogs.AccountDialog(self.app, accounts.get_account(account_id)).wait():
            self.app.after_change()
            self.app.toast(t("toast.account_updated"), "success")

    def archive(self, account):
        def run():
            if dialogs.confirm(self.app, t("common.archive"),
                               t("accounts.archive_prompt", name=account["name"]), t("common.archive"), False):
                accounts.archive_account(account["id"])
                self.app.after_change()
                self.app.toast(t("toast.account_archived"), "success")
        self.guarded(run)

    def unarchive(self, account_id):
        accounts.unarchive_account(account_id)
        self.app.after_change()

    def delete(self, account):
        def run():
            if dialogs.confirm(self.app, t("common.delete"), t("accounts.delete_prompt", name=account["name"])):
                accounts.delete_account(account["id"])
                self.app.after_change()
                self.app.toast(t("toast.account_deleted"), "success")
        self.guarded(run)

    def export_csv(self):
        def run():
            rows = self._visible()
            if not rows:
                self.app.toast(t("accounts.no_match"))
                return
            path = filedialog.asksaveasfilename(
                parent=self.app.root, title=t("common.export"), defaultextension=".csv",
                initialfile=f"contas_{date.today().isoformat()}.csv", filetypes=[("CSV", "*.csv")])
            if not path:
                return
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow([t("accounts.col_name"), t("accounts.col_type"), t("accounts.sort_balance"),
                                 t("accounts.kpi_projected"), t("accounts.sort_last"), t("accounts.col_status")])
                for a in rows:
                    writer.writerow([
                        a["name"], self._type_label(a), money(a["balance"]), money(a["projected_balance"]),
                        self.activity.get(a["id"]) or "",
                        t("common.archived") if a["archived"] else t("accounts.status_active")])
            self.app.toast(t("accounts.exported", count=len(rows)), "success")
        self.guarded(run)

    # ---------------------------------------------------------------- transferências
    def new_transfer(self):
        def run():
            if len(accounts.list_accounts()) < 2:
                raise ValueError(t("accounts.create_two_first"))
            if dialogs.TransferDialog(self.app).wait():
                self.app.after_change()
                self.app.toast(t("toast.transfer_saved"), "success")
        self.guarded(run)

    def _selected_transfer(self):
        table = getattr(self, "table", None)
        sel = table.selected() if table and table.winfo_exists() else None
        if not sel:
            self.app.toast(t("accounts.selected_transfer"))
            return None
        return accounts.get_transfer(int(sel))

    def edit_transfer(self):
        row = self._selected_transfer()
        if row and dialogs.TransferDialog(self.app, row).wait():
            self.app.after_change()
            self.app.toast(t("toast.transfer_updated"), "success")

    def delete_transfer(self):
        row = self._selected_transfer()
        if not row:
            return
        if dialogs.confirm(self.app, t("common.delete"),
                           t("accounts.transfer_delete_prompt", amount=money(row["amount"]),
                             **{"from": row["from_name"], "to": row["to_name"]})):
            def run():
                deleted = accounts.delete_transfer(row["id"])
                self.app.after_change()
                self.app.undoable("Transferência excluída.", lambda: accounts.restore_transfer(deleted))
            self.guarded(run)
