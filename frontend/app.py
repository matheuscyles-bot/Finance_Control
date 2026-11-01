"""Janela principal: navegação lateral, cabeçalho, atalhos e avisos."""

import logging
import tkinter as tk

from backend import config
import database
from backend.services import backup, recurring, settings, transactions as tx
from frontend import dialogs, theme
from frontend.pages.accounts import AccountsPage
from frontend.pages.budgets import BudgetsPage
from frontend.pages.dashboard import DashboardPage
from frontend.pages.recurring import RecurringPage
from frontend.pages.reports import ReportsPage
from frontend.pages.settings import SettingsPage
from frontend.pages.transactions import TransactionsPage
from frontend.theme import MOD, SPACING, c, font
from frontend.widgets import Icon, rounded_image, Toasts
from backend.utils import formatters
from backend.utils import i18n
from backend.utils.i18n import t

log = logging.getLogger("finance_control.ui")

NAV = [
    ("dashboard", "dashboard", DashboardPage),
    ("transactions", "list", TransactionsPage),
    ("accounts", "wallet", AccountsPage),
    ("budgets", "target", BudgetsPage),
    ("reports", "chart", ReportsPage),
    ("recurring", "repeat", RecurringPage),
    ("settings", "gear", SettingsPage),
]


class App:
    def __init__(self, root=None):
        self.root = root or tk.Tk()
        try:
            i18n.configure(database.DATA_DIR, database.BASE_DIR)
            self._language_load_error = False
        except i18n.LocaleConfigError as exc:
            log.error("Não foi possível carregar a preferência de idioma: %s", type(exc).__name__)
            self._language_load_error = True
        self.root.title(config.APP_TITLE)
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.minsize(config.MIN_WIDTH, config.MIN_HEIGHT)
        self.root.report_callback_exception = self._tk_exception
        self.current = "dashboard"
        self.shell = None
        self._last_undo = None
        formatters.set_currency_symbol(settings.get_currency_symbol())
        theme.apply(self.root, settings.get_theme())
        self.toasts = Toasts(self.root)
        self._startup_tasks()
        if self._language_load_error:
            self.startup_notes.append(t("toast.language_load_error"))
        self._build_shell()
        self._bind_shortcuts()
        self.navigate("dashboard")
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---- inicialização ----
    def _startup_tasks(self):
        self.startup_notes = []
        try:
            created = backup.auto_backup_if_needed()
            if created:
                log.info("Backup automático criado")
        except Exception as exc:
            log.warning("Backup automático falhou: %s", type(exc).__name__)
            self.startup_notes.append("Não foi possível criar o backup automático de hoje.")
        try:
            made = recurring.run_due_recurring()
            if made:
                self.startup_notes.append(f"{made} lançamento(s) recorrente(s) criado(s).")
        except Exception as exc:
            log.warning("Recorrências falharam: %s", type(exc).__name__)
            self.startup_notes.append("Não foi possível processar as recorrências.")

    def run(self):
        self.root.update_idletasks()
        for note in self.startup_notes:
            self.root.after(400, lambda n=note: self.toast(n, "info"))
        self.root.mainloop()

    def quit(self):
        self.toasts.dismiss()
        self.root.destroy()

    # ---- estrutura visual ----
    def _build_shell(self):
        if self.shell is not None:
            self.shell.destroy()
        self.pages, self.nav_items = {}, {}
        self.collapsed = False
        self.hideables = []   # widgets que somem quando o menu recolhe
        self.nav_labels = []  # textos dos itens do menu
        self.nav_rows = []    # (canvas, id da janela interna) de cada item
        self.shell = tk.Frame(self.root, bg=c("bg"))
        self.shell.pack(fill="both", expand=True)

        self.side = side = tk.Frame(self.shell, bg=c("sidebar"), width=226)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        self.brand = brand = tk.Frame(side, bg=c("sidebar"))
        brand.pack(fill="x", padx=22, pady=(27, 28))
        self.mark = mark = tk.Frame(brand, bg=c("primary"), width=34, height=34)
        mark.pack(side="left", padx=(0, 10))
        mark.pack_propagate(False)
        tk.Label(mark, text="F", bg=c("primary"), fg=c("primary_text"),
                 font=font(17, "bold")).pack(expand=True)
        identity = tk.Frame(brand, bg=c("sidebar"))
        identity.pack(side="left", fill="y")
        tk.Label(identity, text="FINANCE", bg=c("sidebar"), fg=c("sidebar_text"),
                 font=font(8, "bold")).pack(anchor="w")
        tk.Label(identity, text="Control", bg=c("sidebar"), fg=c("text"),
                 font=font(15, "bold")).pack(anchor="w", pady=(1, 0))
        self.hideables.append(identity)

        self.toggle_btn = tk.Label(side, text="«", bg=c("sidebar"), fg=c("sidebar_text"),
                                   font=font(16, "bold"), cursor="hand2", anchor="e")
        self.toggle_btn.pack(fill="x", padx=20, pady=(0, 10))
        self.toggle_btn.bind("<Button-1>", lambda e: self.toggle_sidebar())

        nav_label = tk.Label(side, text=t("app.workspace"), bg=c("sidebar"),
                             fg=c("muted"), font=font(8, "bold"), anchor="w")
        nav_label.pack(fill="x", padx=24, pady=(0, 8))
        self.hideables.append(nav_label)
        for key, icon, _cls in NAV:
            if key != "settings":
                self._nav_item(side, key, t(f"nav.{key}"), icon)
        tk.Frame(side, bg=c("sidebar")).pack(fill="both", expand=True)
        tk.Frame(side, bg=c("border"), height=1).pack(fill="x", padx=18, pady=(0, 12))
        self._nav_item(side, "settings", t("nav.settings"), "gear")
        footer = tk.Label(side, text=f"FINANCE CONTROL  ·  {config.APP_VERSION}",
                          bg=c("sidebar"), fg=c("muted"), font=font(8))
        footer.pack(anchor="w", padx=22, pady=(12, 16))
        self.hideables.append(footer)

        main = tk.Frame(self.shell, bg=c("bg"))
        main.pack(side="left", fill="both", expand=True)
        self.header = tk.Frame(main, bg=c("bg"))
        self.header.pack(fill="x", padx=SPACING["page"], pady=(27, SPACING["lg"]))
        self.title_label = tk.Label(self.header, bg=c("bg"), fg=c("text"), font=font(22, "bold"))
        self.title_label.pack(side="left")
        self.actions = tk.Frame(self.header, bg=c("bg"))
        self.actions.pack(side="right")
        tk.Frame(main, bg=c("border"), height=1).pack(
            fill="x", padx=SPACING["page"], pady=(0, SPACING["lg"]))
        self.body = tk.Frame(main, bg=c("bg"))
        self.body.pack(fill="both", expand=True)
        self.toasts.dismiss()

    def toggle_sidebar(self):
        self.collapsed = col = not self.collapsed
        self.side.configure(width=64 if col else 226)
        self.brand.pack_configure(padx=15 if col else 22)
        self.mark.pack_configure(padx=0 if col else (0, 10))
        self.toggle_btn.configure(text="»" if col else "«",
                                  anchor="center" if col else "e")
        for w in self.hideables:
            if isinstance(w, tk.Label):
                if not hasattr(w, "_full"):
                    w._full = w.cget("text")
                w.configure(text="" if col else w._full)
            elif col:
                w.pack_forget()
            else:
                w.pack(side="left", fill="y")
        for lbl in self.nav_labels:
            if col:
                lbl.pack_forget()
            else:
                lbl.pack(side="left", padx=(11, 0))
        for row, win in self.nav_rows:
            row.coords(win, 12 if col else 14, 22)

    def _nav_item(self, parent, key, text, icon):
        H = 44
        row = tk.Canvas(parent, bg=c("sidebar"), height=H,
                        highlightthickness=0, bd=0, cursor="hand2")
        row.pack(fill="x", padx=10, pady=3)
        inner = tk.Frame(row, bg=c("sidebar"))
        win = row.create_window(14, H // 2, window=inner, anchor="w")
        self.nav_rows.append((row, win))
        ic = Icon(inner, icon, c("sidebar_text"), c("sidebar"), 20)
        ic.pack(side="left")
        lbl = tk.Label(inner, text=text, bg=c("sidebar"), fg=c("sidebar_text"), font=font(12))
        lbl.pack(side="left", padx=(11, 0))
        self.nav_labels.append(lbl)
        parts = (row, inner, ic, lbl)
        st = {"v": "idle", "w": 0}

        def draw():
            if st["w"] < 2:
                return
            bg = {"active": c("sidebar_active"), "hover": c("sidebar_hover")}.get(st["v"], c("sidebar"))
            row.delete("bg")
            img = rounded_image(st["w"], H, 10, bg, None, c("sidebar"), master=row)
            row.create_image(0, 0, image=img, anchor="nw", tags="bg")
            row.tag_lower("bg")

        row.bind("<Configure>", lambda e: (st.update(w=e.width), draw()))

        def paint(state):
            st["v"] = state
            bg = {"active": c("sidebar_active"), "hover": c("sidebar_hover")}.get(state, c("sidebar"))
            fg = c("sidebar_text_active") if state == "active" else c("sidebar_text")
            for w in (inner, lbl):
                w.configure(bg=bg)
            lbl.configure(fg=fg, font=font(12, "bold" if state == "active" else "normal"))
            ic.set_color(fg, bg)
            draw()

        for w in parts:
            w.bind("<Button-1>", lambda e, k=key: self.navigate(k))
            w.bind("<Enter>", lambda e, k=key: paint("hover") if k != self.current else None)
            w.bind("<Leave>", lambda e, k=key: paint("active" if k == self.current else "idle"))
        self.nav_items[key] = paint

    # ---- navegação ----
    def navigate(self, key):
        self.current = key
        for k, paint in self.nav_items.items():
            paint("active" if k == key else "idle")
        for page in self.pages.values():
            page.pack_forget()
        page = self.pages.get(key)
        if page is None:
            cls = next(n[2] for n in NAV if n[0] == key)
            page = cls(self.body, self)
            self.pages[key] = page
        self.title_label.configure(text=t(page.title_key))
        for w in self.actions.winfo_children():
            w.destroy()
        for b in page.header_actions(self.actions):
            b.pack(side="left", padx=(8, 0))
        page.pack(fill="both", expand=True)
        self.guarded_show(page)

    def guarded_show(self, page):
        try:
            page.on_show()
        except Exception as exc:
            self.report_error(exc)

    def after_change(self, run_recurring=False):
        """Chame depois de qualquer alteração de dados."""
        if run_recurring:
            try:
                recurring.run_due_recurring()
            except Exception as exc:
                self.report_error(exc)
        for page in self.pages.values():
            page.dirty = True
        page = self.pages.get(self.current)
        if page:
            self.guarded_show(page)

    # ---- ações compartilhadas ----
    def is_empty(self):
        return tx.count_transactions() == 0

    def new_transaction(self, defaults=None, kind="expense"):
        dlg = dialogs.TransactionDialog(self, defaults=defaults, kind=kind)
        result = dlg.wait()
        if result:
            self.after_change()
            self.toast("Movimentação salva." if result == "created" else "Movimentação atualizada.", "success")

    def edit_transaction(self, row):
        if dialogs.TransactionDialog(self, transaction=row).wait():
            self.after_change()
            self.toast("Movimentação atualizada.", "success")

    def new_transfer(self):
        if dialogs.TransferDialog(self).wait():
            self.after_change()
            self.toast("Transferência registrada.", "success")

    def undoable(self, text, undo):
        def run():
            try:
                undo()
            except ValueError as exc:
                self.toast(str(exc), "error")
                return
            self.after_change()
            self.toast("Ação desfeita.", "success")
        self.toasts.show(text, "success", "Desfazer", run, ms=7000)

    def toast(self, text, kind="info"):
        self.toasts.show(text, kind)

    def set_theme(self, name):
        if name == theme.theme_name():
            return
        settings.set_setting("theme", name)
        theme.apply(self.root, name)
        self._build_shell()
        self.navigate("settings")

    def set_currency(self, symbol):
        settings.set_setting("currency_symbol", symbol)
        formatters.set_currency_symbol(symbol)
        self.after_change()

    def set_language(self, code):
        if code == i18n.get_locale():
            return
        try:
            i18n.set_locale(code)
        except i18n.LocaleConfigError:
            self.toast(t("toast.language_save_error"), "error")
            return
        theme.apply(self.root, settings.get_theme())
        self._build_shell()
        self.navigate("settings")

    # ---- erros ----
    def report_error(self, exc):
        # Registra só o tipo e o local do erro: nunca valores financeiros.
        log.error("Erro inesperado: %s", type(exc).__name__, exc_info=True)
        self.toast("Algo deu errado. Seus dados não foram afetados. "
                   "Detalhes técnicos foram salvos no registro do app.", "error")

    def _tk_exception(self, exc_type, exc, tb):
        log.error("Erro na interface: %s", exc_type.__name__, exc_info=(exc_type, exc, tb))
        self.toast("Algo deu errado. Seus dados não foram afetados.", "error")

    # ---- atalhos ----
    def _bind_shortcuts(self):
        r = self.root
        r.bind_all(f"<{MOD}-n>", lambda e: self.new_transaction())
        r.bind_all(f"<{MOD}-f>", lambda e: self._focus_search())
        r.bind_all(f"<{MOD}-comma>", lambda e: self.navigate("settings"))
        for i, (key, *_rest) in enumerate(NAV[:6], 1):
            r.bind_all(f"<{MOD}-Key-{i}>", lambda e, k=key: self.navigate(k))

    def _focus_search(self):
        self.navigate("transactions")
        self.pages["transactions"].focus_search()