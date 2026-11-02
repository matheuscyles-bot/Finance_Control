"""Configurações: idioma, aparência e moeda, categorias, backups e sobre o app.
Cada assunto é um painel; idioma e aparência ficam lado a lado."""

import tkinter as tk
from tkinter import filedialog

from backend import config
import database
from backend.services import backup, categories
from frontend import dialogs
from frontend.pages.base import Page
from frontend.theme import c, font, mix
from frontend.ui import PillSelect, Panel
from frontend.widgets import Button, ScrollFrame, Segmented, label
from backend.utils import formatters
from backend.utils import i18n
from backend.utils.i18n import category_label, t


class _CategoryList(tk.Frame):
    """Lista de categorias: uma linha por item, clicável; ``selection()``
    devolve o id da linha escolhida, como o Treeview que substitui."""

    def __init__(self, parent, bg):
        super().__init__(parent, bg=bg)
        self.base = bg
        self._rows = {}
        self._selected = None

    def add(self, iid, text):
        row = tk.Frame(self, bg=self.base, cursor="hand2")
        row.pack(fill="x")
        name = tk.Label(row, text=text, bg=self.base, fg=c("text"), font=font(12), anchor="w",
                        padx=12, pady=8, cursor="hand2")
        name.pack(fill="x")
        for w in (row, name):
            w.bind("<Button-1>", lambda e, i=iid: self.select(i))
        self._rows[iid] = (row, name)

    def select(self, iid):
        if self._selected in self._rows:
            for w in self._rows[self._selected]:
                w.configure(bg=self.base)
        self._selected = iid
        for w in self._rows[iid]:
            w.configure(bg=mix(self.base, c("text"), 0.08))

    def selection(self):
        return (self._selected,) if self._selected in self._rows else ()


def _size(n):
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


class SettingsPage(Page):
    title_key = "nav.settings"

    def build(self):
        self.scroll = ScrollFrame(self, bg=c("bg"))
        self.scroll.pack(fill="both", expand=True)
        self.content = tk.Frame(self.scroll.inner, bg=c("bg"))
        self.content.pack(fill="both", expand=True)
        self.content.grid_columnconfigure(0, weight=1, uniform="settings")
        self.content.grid_columnconfigure(1, weight=1, uniform="settings")

    def _panel(self, title, hint, row, col=0, span=1):
        panel = Panel(self.content, title=title, subtitle=hint, hover=False)
        panel.grid(row=row, column=col, columnspan=span, sticky="nsew",
                   padx=(0 if col == 0 else 7, 0 if col == 1 or span == 2 else 7), pady=(0, 14))
        return panel.content

    def refresh(self):
        super().refresh()
        for w in self.content.winfo_children():
            w.destroy()
        self._language(0, 0)
        self._appearance(0, 1)
        self._categories(1, 0, span=2)
        self._backups(2, 0, span=2)
        self._about(3, 0, span=2)

    def _language(self, row, col):
        body = self._panel(t("settings.language.title"), t("settings.language.hint"), row, col)
        row_frame = tk.Frame(body, bg=c("surface"))
        row_frame.pack(fill="x", pady=(8, 0))
        self.language = PillSelect(row_frame, [(code, t(f"language.{code}")) for code in i18n.SUPPORTED_LOCALES],
                                   icon_name="layout-grid", bg=c("surface"))
        self.language.set_id(i18n.get_locale())
        self.language.pack(side="left")
        self.language.bind("<<ComboboxSelected>>",
                           lambda _event: self.app.set_language(self.language.get_id()))

    # ---- aparência e moeda ----
    def _appearance(self, row, col):
        body = self._panel(t("settings.appearance_currency"), None, row, col)
        from frontend import theme
        label(body, t("settings.theme"), 11, "bold", "muted").pack(fill="x", pady=(8, 4))
        Segmented(body, list(config.THEMES.items()), theme.theme_name(),
                  lambda k: self.app.set_theme(k), bg=c("surface")).pack(anchor="w")
        label(body, t("settings.currency_symbol"), 11, "bold", "muted").pack(fill="x", pady=(14, 4))
        Segmented(body, [(s, s) for s in config.CURRENCY_OPTIONS], formatters.get_currency_symbol(),
                  lambda k: self.app.set_currency(k), bg=c("surface")).pack(anchor="w")
        label(body, t("settings.currency_hint"), 11, color="muted").pack(fill="x", pady=(8, 0))

    # ---- categorias ----
    def _categories(self, row, col, span=1):
        body = self._panel(t("settings.categories"), t("settings.category_delete_hint"), row, col, span)
        cols = tk.Frame(body, bg=c("surface"))
        cols.pack(fill="x", pady=(8, 0))
        for i, kind in enumerate(("expense", "income")):
            box = tk.Frame(cols, bg=c("surface"))
            box.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 12, 0))
            label(box, t(f"common.{kind}"), 11, "bold").pack(fill="x", pady=(0, 6))
            tree = _CategoryList(box, c("surface"))
            tree.pack(fill="x")
            for cat in categories.get_categories(kind):
                tree.add(str(cat["id"]), category_label(cat["name"]))
            tools = tk.Frame(box, bg=c("surface"))
            tools.pack(fill="x", pady=(8, 0))
            Button(tools, t("settings.add_category"), lambda k=kind: self.add_category(k), "secondary",
                   pad=(10, 4)).pack(side="left")
            Button(tools, t("settings.rename_category"), lambda tr=tree: self.rename_category(tr), "secondary",
                   pad=(10, 4)).pack(side="left", padx=6)
            Button(tools, t("common.delete"), lambda tr=tree: self.delete_category(tr), "secondary",
                   pad=(10, 4)).pack(side="left")

    def add_category(self, kind):
        name = dialogs.prompt_text(
            self.app, t("settings.new_category"), t("settings.category_name"),
            save_text=t("settings.add_category"))
        if name is not None:
            self.guarded(lambda: (categories.add_category(name, kind), self.app.after_change(),
                                  self.app.toast(t("toast.category_created"), "success")))

    def _chosen(self, tree):
        sel = tree.selection()
        if not sel:
            self.app.toast(t("settings.select_category"), "info")
            return None
        return categories.get_category(int(sel[0]))

    def rename_category(self, tree):
        cat = self._chosen(tree)
        if not cat:
            return
        name = dialogs.prompt_text(
            self.app, t("settings.rename_title"), t("settings.new_name"),
            cat["name"], save_text=t("common.save"))
        if name is not None:
            self.guarded(lambda: (categories.rename_category(cat["id"], name), self.app.after_change(),
                                  self.app.toast(t("toast.category_renamed"), "success")))

    def delete_category(self, tree):
        cat = self._chosen(tree)
        if not cat:
            return

        def run():
            usage = categories.category_usage(cat["id"])
            in_use = sum(usage.values())
            if in_use:
                if dialogs.MoveCategoryDialog(self.app, cat, in_use).wait():
                    self.app.after_change()
                    self.app.toast(t("toast.category_deleted"), "success")
            elif dialogs.confirm(self.app, t("settings.delete_category"),
                                 t("settings.delete_category_prompt", category=category_label(cat["name"]))):
                categories.delete_category(cat["id"])
                self.app.after_change()
                self.app.toast(t("toast.category_deleted"), "success")
        self.guarded(run)

    # ---- backups ----
    def _backups(self, row, col, span=1):
        body = self._panel(t("settings.backup_restore"), t("settings.backup_hint"), row, col, span)
        buttons = tk.Frame(body, bg=c("surface"))
        buttons.pack(fill="x", pady=(8, 8))
        Button(buttons, t("settings.backup_now"), self.make_backup, "primary", icon="download").pack(side="left")
        Button(buttons, t("settings.save_copy"), self.save_copy, "secondary").pack(side="left", padx=8)
        Button(buttons, t("settings.restore_file"), lambda: self.restore(None), "secondary",
               icon="upload").pack(side="left")
        items = backup.list_backups()
        if not items:
            label(body, t("settings.no_backups"), 11, color="muted").pack(fill="x", pady=6)
        for item in items[:6]:
            line = tk.Frame(body, bg=c("surface"))
            line.pack(fill="x", pady=2)
            label(line, item["modified"].strftime("%d/%m/%Y %H:%M"), 11, "bold").pack(side="left")
            label(line, f"   {item['name']}  ·  {_size(item['size'])}", 11, color="muted").pack(side="left")
            link = tk.Label(line, text=t("settings.restore"), fg=c("primary"), bg=c("surface"),
                            font=font(11, "bold"), cursor="hand2")
            link.pack(side="right")
            link.bind("<Button-1>", lambda e, p=item["path"]: self.restore(p))
        if len(items) > 6:
            label(body, t("settings.old_backups", count=len(items) - 6), 11, color="muted").pack(fill="x", pady=(4, 0))

    def make_backup(self):
        self.guarded(lambda: (backup.manual_backup(), self.app.toast(t("toast.backup_created"), "success"),
                              self.refresh()))

    def save_copy(self):
        def run():
            path = filedialog.asksaveasfilename(
                parent=self.app.root, title=t("settings.save_copy"), defaultextension=".db",
                initialfile=f"finance_control_copia_{formatters.today_iso()}.db",
                filetypes=[("Banco SQLite", "*.db")])
            if path:
                backup.save_copy(path)
                self.app.toast(t("toast.copy_saved"), "success")
        self.guarded(run)

    def restore(self, path):
        def run():
            chosen = path or filedialog.askopenfilename(
                parent=self.app.root, title=t("settings.restore_file"),
                filetypes=[("Banco SQLite", "*.db"), ("Todos", "*.*")])
            if not chosen:
                return
            if dialogs.confirm(
                    self.app, t("settings.restore"),
                    t("settings.restore_prompt"), t("settings.restore"), False):
                backup.restore(chosen)
                self.app.after_change()
                self.app.toast(t("toast.backup_restored"), "success")
        self.guarded(run)

    def _about(self, row, col, span=1):
        body = self._panel(t("settings.about"), None, row, col, span)
        label(body, f"{config.APP_TITLE} {config.APP_VERSION}", 11, "bold").pack(fill="x", pady=(4, 0))
        label(body, t("settings.data_path", path=database.DATA_DIR), 11, color="muted", wraplength=760,
              justify="left").pack(fill="x", pady=(2, 0))
        label(body, t("settings.privacy"), 11, color="muted").pack(fill="x")
