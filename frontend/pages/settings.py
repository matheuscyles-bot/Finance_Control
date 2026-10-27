"""Configurações: aparência, moeda, categorias e backups."""

import tkinter as tk
from tkinter import filedialog, ttk

from backend import config
import database
from backend.services import backup, categories
from frontend import dialogs
from frontend.pages.base import Page
from frontend.theme import c, font
from frontend.widgets import Button, Card, ScrollFrame, Segmented, label, separator
from backend.utils import formatters


def _size(n):
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


class SettingsPage(Page):
    title = "Configurações"

    def build(self):
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.content = tk.Frame(self.scroll.inner, bg=c("bg"))
        self.content.pack(fill="both", expand=True, padx=32, pady=(0, 28))

    def _card(self, title, hint=None):
        card = Card(self.content)
        card.pack(fill="x", pady=(0, 14))
        label(card.body, title, 13, "bold").pack(fill="x")
        if hint:
            label(card.body, hint, 10, color="muted", wraplength=760, justify="left").pack(fill="x", pady=(2, 8))
        return card.body

    def refresh(self):
        super().refresh()
        for w in self.content.winfo_children():
            w.destroy()
        self._appearance()
        self._categories()
        self._backups()
        self._about()

    # ---- aparência e moeda ----
    def _appearance(self):
        body = self._card("Aparência e moeda")
        row = tk.Frame(body, bg=c("surface"))
        row.pack(fill="x", pady=(8, 0))
        left = tk.Frame(row, bg=c("surface"))
        left.pack(side="left", padx=(0, 40))
        label(left, "Tema", 10, "bold", "muted").pack(fill="x", pady=(0, 4))
        from frontend import theme
        Segmented(left, list(config.THEMES.items()), theme.theme_name(),
                  lambda k: self.app.set_theme(k)).pack(anchor="w")
        right = tk.Frame(row, bg=c("surface"))
        right.pack(side="left")
        label(right, "Símbolo da moeda", 10, "bold", "muted").pack(fill="x", pady=(0, 4))
        Segmented(right, [(s, s) for s in config.CURRENCY_OPTIONS], formatters.get_currency_symbol(),
                  lambda k: self.app.set_currency(k)).pack(anchor="w")
        label(body, "A moeda muda só a forma de exibir; os valores guardados não são convertidos.",
              10, color="muted").pack(fill="x", pady=(8, 0))

    # ---- categorias ----
    def _categories(self):
        body = self._card(
            "Categorias",
            "Ao excluir uma categoria em uso, você escolhe para onde os "
            "lançamentos, recorrências e orçamentos vão."
        )
        cols = tk.Frame(body, bg=c("surface"))
        cols.pack(fill="x")
        for i, (kind, title) in enumerate((("expense", "Despesas"), ("income", "Receitas"))):
            box = tk.Frame(cols, bg=c("surface"))
            box.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 12, 0))
            top = tk.Frame(box, bg=c("surface"))
            top.pack(fill="x", pady=(0, 6))
            label(top, title, 11, "bold").pack(side="left")
            tree = ttk.Treeview(box, columns=("name",), show="", selectmode="browse", height=7)
            tree.column("name", width=300)
            tree.pack(fill="x")
            for cat in categories.get_categories(kind):
                tree.insert("", "end", iid=str(cat["id"]), values=(cat["name"],))
            tools = tk.Frame(box, bg=c("surface"))
            tools.pack(fill="x", pady=(8, 0))
            Button(tools, "Adicionar", lambda k=kind: self.add_category(k), "secondary", pad=(10, 4)).pack(side="left")
            Button(tools, "Renomear", lambda t=tree: self.rename_category(t), "secondary", pad=(10, 4)).pack(side="left", padx=6)
            Button(tools, "Excluir", lambda t=tree: self.delete_category(t), "secondary", pad=(10, 4)).pack(side="left")

    def add_category(self, kind):
        name = dialogs.prompt_text(self.app, "Nova categoria", "Nome da categoria", save_text="Adicionar")
        if name is not None:
            self.guarded(lambda: (categories.add_category(name, kind), self.app.after_change(),
                                  self.app.toast("Categoria criada.", "success")))

    def _chosen(self, tree):
        sel = tree.selection()
        if not sel:
            self.app.toast("Selecione uma categoria na lista.", "info")
            return None
        return categories.get_category(int(sel[0]))

    def rename_category(self, tree):
        cat = self._chosen(tree)
        if not cat:
            return
        name = dialogs.prompt_text(self.app, "Renomear categoria", "Novo nome", cat["name"])
        if name is not None:
            self.guarded(lambda: (categories.rename_category(cat["id"], name), self.app.after_change(),
                                  self.app.toast("Categoria renomeada.", "success")))

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
                    self.app.toast("Categoria excluída.", "success")
            elif dialogs.confirm(self.app, "Excluir categoria", f"Excluir “{cat['name']}”?"):
                categories.delete_category(cat["id"])
                self.app.after_change()
                self.app.toast("Categoria excluída.", "success")
        self.guarded(run)

    # ---- backups ----
    def _backups(self):
        body = self._card(
            "Backup e restauração",
            "O app guarda um backup automático por dia e um antes de cada atualização do banco. "
            "Seus dados ficam só neste computador.")
        row = tk.Frame(body, bg=c("surface"))
        row.pack(fill="x", pady=(0, 8))
        Button(row, "Criar backup agora", self.make_backup, "primary", icon="download").pack(side="left")
        Button(row, "Salvar uma cópia…", self.save_copy, "secondary").pack(side="left", padx=8)
        Button(row, "Restaurar de arquivo…", lambda: self.restore(None), "secondary", icon="upload").pack(side="left")
        items = backup.list_backups()
        if not items:
            label(body, "Ainda não há backups.", 10, color="muted").pack(fill="x", pady=6)
        for item in items[:6]:
            line = tk.Frame(body, bg=c("surface"))
            line.pack(fill="x", pady=2)
            label(line, item["modified"].strftime("%d/%m/%Y %H:%M"), 10, "bold").pack(side="left")
            label(line, f"   {item['name']}  ·  {_size(item['size'])}", 10, color="muted").pack(side="left")
            link = tk.Label(line, text="Restaurar", fg=c("primary"), bg=c("surface"),
                            font=font(10, "bold"), cursor="hand2")
            link.pack(side="right")
            link.bind("<Button-1>", lambda e, p=item["path"]: self.restore(p))
        if len(items) > 6:
            label(body, f"+ {len(items) - 6} backup(s) mais antigos na pasta de dados.", 10, color="muted").pack(fill="x", pady=(4, 0))

    def make_backup(self):
        self.guarded(lambda: (backup.manual_backup(), self.app.toast("Backup criado.", "success"), self.refresh()))

    def save_copy(self):
        def run():
            path = filedialog.asksaveasfilename(
                parent=self.app.root, title="Salvar cópia do banco", defaultextension=".db",
                initialfile=f"finance_control_copia_{formatters.today_iso()}.db",
                filetypes=[("Banco SQLite", "*.db")])
            if path:
                backup.save_copy(path)
                self.app.toast("Cópia salva.", "success")
        self.guarded(run)

    def restore(self, path):
        def run():
            chosen = path or filedialog.askopenfilename(
                parent=self.app.root, title="Escolha o backup",
                filetypes=[("Banco SQLite", "*.db"), ("Todos", "*.*")])
            if not chosen:
                return
            if dialogs.confirm(
                    self.app, "Restaurar backup",
                    "Os dados atuais serão substituídos pelos do backup. Antes disso o app guarda "
                    "uma cópia do estado atual. Continuar?", "Restaurar", False):
                backup.restore(chosen)
                self.app.after_change()
                self.app.toast("Backup restaurado.", "success")
        self.guarded(run)

    def _about(self):
        body = self._card("Sobre")
        label(body, f"{config.APP_TITLE} {config.APP_VERSION}", 11, "bold").pack(fill="x", pady=(4, 0))
        label(body, f"Dados em: {database.DATA_DIR}", 10, color="muted", wraplength=760,
              justify="left").pack(fill="x", pady=(2, 0))
        label(body, "Nenhuma informação financeira sai deste computador.", 10, color="muted").pack(fill="x")
