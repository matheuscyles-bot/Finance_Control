"""Fluxo de ponta a ponta pela interface real (precisa de tkinter e de uma
tela; em servidor sem tela use ``xvfb-run``). Usa banco temporário."""

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tests.base import ROOT  # noqa: F401  (ajusta sys.path)

try:
    import tkinter as tk
    _probe = tk.Tk()
    _probe.destroy()
    HAS_DISPLAY = True
except Exception:  # sem tkinter ou sem tela
    HAS_DISPLAY = False

import database  # noqa: E402


@unittest.skipUnless(HAS_DISPLAY, "sem tkinter/tela disponível")
class UiFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fc_ui_")
        self.old = database.DB_PATH
        database.set_db_path(Path(self.tmp) / "ui.db")
        database.init_db()
        from frontend import dialogs
        from frontend.app import App
        self.dialogs = dialogs
        self.app = App()
        self.app.root.update()

    def tearDown(self):
        self.app.root.destroy()
        database.set_db_path(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fill(self, entry, text):
        entry.delete(0, "end")
        entry.insert(0, text)

    def test_every_page_opens_empty(self):
        from frontend.app import NAV
        for key, *_ in NAV:
            self.app.navigate(key)
            self.app.root.update()
        self.assertTrue(self.app.is_empty())

    def test_pipeline_board_and_list(self):
        from datetime import timedelta
        from backend.services import accounts, categories
        from backend.services import transactions as tx
        from frontend.pages.pipeline import STAGE_KEYS
        account = accounts.add_account("Conta")
        category = categories.add_category("Contas", "expense")
        tx.add_transaction("Luz", "80", "expense", category, (date.today() + timedelta(days=3)).isoformat(),
                           account_id=account)
        self.app.navigate("pipeline")
        page = self.app.pages["pipeline"]
        self.assertEqual(len(page.groups["due_soon"]), 1)
        self.assertEqual(page.kpis[1]["value"], 8000)
        page.query.set("luz")
        self.assertEqual(len(page._visible()), 1)
        page.query.set("zzz")
        self.assertEqual(page._visible(), [])
        page.query.set("")
        page._set_view("list")
        self.assertEqual(len(page.table.tree.get_children()), 1)
        self.assertEqual(sorted(page.groups), sorted(STAGE_KEYS))

    def test_transaction_flow(self):
        from backend.services import transactions as tx
        d = self.dialogs.TransactionDialog(self.app)
        self.fill(d.amount, "1.234,56")
        self.fill(d.description, "Mercado")
        d.submit()
        self.assertEqual(d.result, "created")
        row = tx.list_transactions()[0]
        self.assertEqual(row["amount"], 123456)
        self.assertEqual(row["transaction_date"], date.today().isoformat())

        # valor inválido mostra erro e não grava
        d = self.dialogs.TransactionDialog(self.app)
        self.fill(d.amount, "abc")
        self.fill(d.description, "X")
        d.submit()
        self.assertIsNone(d.result)
        self.assertTrue(d.error.cget("text"))
        d.close()
        self.assertEqual(tx.count_transactions(), 1)

        # edição
        d = self.dialogs.TransactionDialog(self.app, transaction=tx.get_transaction(row["id"]))
        self.fill(d.amount, "10")
        d.submit()
        self.assertEqual(tx.get_transaction(row["id"])["amount"], 1000)

        # parcelas
        d = self.dialogs.TransactionDialog(self.app)
        self.fill(d.amount, "100")
        self.fill(d.description, "TV")
        d.installments.set(3)
        d.submit()
        parts = [r for r in tx.list_transactions() if r["installment_total"] == 3]
        self.assertEqual(sorted(p["amount"] for p in parts), [3333, 3333, 3334])

        # exclusão e desfazer
        deleted = tx.delete_transaction(row["id"])
        self.assertEqual(tx.count_transactions(), 3)
        tx.restore_transactions(deleted)
        self.assertEqual(tx.count_transactions(), 4)
        self.app.after_change()
        for key in ("dashboard", "transactions", "reports"):
            self.app.navigate(key)
            self.app.root.update()

    def test_accounts_transfer_budget_recurring(self):
        from backend.services import accounts, budgets, categories, recurring
        d = self.dialogs.AccountDialog(self.app)
        self.fill(d.name, "Poupança")
        self.fill(d.opening, "500,00")
        d.submit()
        self.assertEqual(d.result, True)
        first, second = [a["id"] for a in accounts.list_accounts()][:2]

        d = self.dialogs.TransferDialog(self.app)
        d.origin.set_id(second)
        d.target.set_id(first)
        self.fill(d.amount, "200")
        d.submit()
        by_id = {a["id"]: a["balance"] for a in accounts.list_accounts()}
        self.assertEqual(by_id[first], 20000)
        self.assertEqual(by_id[second], 30000)
        from backend.services import transactions as tx
        self.assertEqual(tx.get_totals()["income"], 0)  # transferência não é receita

        month = date.today().strftime("%Y-%m")
        food = next(c["id"] for c in categories.get_categories("expense") if c["name"] == "Alimentação")
        d = self.dialogs.BudgetDialog(self.app, month)
        d.category.set_id(food)
        self.fill(d.amount, "300")
        d.submit()
        self.assertEqual(budgets.list_budgets(month)[0]["budget"], 30000)

        d = self.dialogs.RecurringDialog(self.app)
        self.fill(d.amount, "50")
        self.fill(d.description, "Streaming")
        d.submit()
        self.assertEqual(len(recurring.list_recurring()), 1)
        self.assertEqual(recurring.run_due_recurring(), 1)
        self.assertEqual(recurring.run_due_recurring(), 0)

        self.app.after_change()
        from frontend.app import NAV
        for key, *_ in NAV:
            self.app.navigate(key)
            self.app.root.update()

    def test_theme_and_currency_persist(self):
        from backend.services import settings
        self.app.set_currency("R$")
        self.app.set_theme("light")
        self.assertEqual(settings.get_theme(), "light")
        self.app.set_theme("dark")
        self.app.root.update()
        self.assertEqual(settings.get_currency_symbol(), "R$")
        self.assertEqual(settings.get_theme(), "dark")

    def test_language_switch_rebuilds_every_page(self):
        from backend.utils import i18n
        from backend.utils.i18n import t
        from frontend.app import NAV

        for code in i18n.SUPPORTED_LOCALES:
            with self.subTest(locale=code):
                self.app.set_language(code)
                self.app.root.update()
                for key, *_ in NAV:
                    self.app.navigate(key)
                    self.app.root.update()
                    page = self.app.pages[key]
                    self.assertEqual(self.app.title_label.cget("text"), t(page.title_key))
                if i18n._preference_path.exists():
                    saved = i18n._preference_path.read_text(encoding="utf-8")
                    self.assertEqual(json.loads(saved)["language"], code)
                else:
                    self.assertEqual(i18n.get_locale(), code)

    def test_date_picker_takes_and_restores_modal_grab(self):
        dialog = self.dialogs.TransactionDialog(self.app)
        self.app.root.update()
        self.assertEqual(self.app.root.grab_current(), dialog)

        popup = dialog.date.open_picker()
        self.app.root.update()
        self.assertEqual(self.app.root.grab_current(), popup)

        before = popup.current
        popup.values["day"][1].event_generate("<MouseWheel>", delta=-1)
        self.app.root.update()
        self.assertNotEqual(popup.current, before)

        popup.close()
        self.app.root.update()
        self.assertEqual(self.app.root.grab_current(), dialog)
        dialog.close()

    def test_accounts_grid_table_filters_and_share(self):
        from backend.services import accounts
        checking = accounts.add_account("Nubank", "checking", "1000")  # a conta padrão também existe
        accounts.add_account("Reserva", "savings", "500")
        accounts.add_account("Carteira", "cash")
        total = accounts.total_balance()
        self.app.navigate("accounts")
        self.app.root.update()
        page = self.app.pages["accounts"]
        self.assertEqual(page.kpis[0]["value"], len(accounts.list_accounts()))
        self.assertEqual(page.kpis[1]["value"], total)
        nubank = next(a for a in page.rows if a["id"] == checking)
        self.assertAlmostEqual(page._share(nubank), nubank["balance"] / total)
        page.query.set("res")
        self.assertEqual([a["name"] for a in page._visible()], ["Reserva"])
        page.query.set("")
        page._pick_kind("cash")
        self.assertEqual([a["name"] for a in page._visible()], ["Carteira"])
        page._pick_kind(None)
        page._set_view("table")
        self.app.root.update()
        self.assertEqual(len(page.accounts_table.tree.get_children()), len(accounts.list_accounts()))
        page._sort("balance", True)
        self.assertEqual(page.accounts_table.tree.get_children()[0], str(checking))
        page.total = 0
        self.assertEqual(page._share(page.rows[0]), 0.0)
        page._set_view("grid")
        self.app.root.update()


if __name__ == "__main__":
    unittest.main()
