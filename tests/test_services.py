import csv
import sqlite3
import unittest

from tests.base import DbTestCase
import database
from backend.services import (accounts, backup, budgets, importer, recurring, reports,
                      transactions as tx, categories)


class TransactionTests(DbTestCase):
    def add(self, amount="10", kind="expense", d="2026-10-05", desc="Teste", **kw):
        cat = self.food if kind == "expense" else self.salary
        return tx.add_transaction(desc, amount, kind, cat, d, account_id=self.account, **kw)

    def test_crud_exact_amount(self):
        tid = self.add("19.99")
        self.assertEqual(tx.get_transaction(tid)["amount"], 1999)
        tx.update_transaction(tid, "Novo", "20,05", "expense", self.food, "06/10/2026")
        row = tx.get_transaction(tid)
        self.assertEqual((row["amount"], row["transaction_date"], row["description"]),
                         (2005, "2026-10-06", "Novo"))
        deleted = tx.delete_transaction(tid)
        self.assertIsNone(tx.get_transaction(tid))
        tx.restore_transactions(deleted)
        self.assertEqual(tx.get_transaction(tid)["amount"], 2005)

    def test_validation(self):
        for amount in ("0", "-1", "abc", ""):
            with self.assertRaises(ValueError):
                self.add(amount)
        with self.assertRaises(ValueError):
            tx.add_transaction("x", "5", "expense", self.salary, "2026-10-01")  # tipo errado
        with self.assertRaises(ValueError):
            tx.add_transaction("", "5", "expense", self.food, "2026-10-01")
        with self.assertRaises(ValueError):
            tx.add_transaction("x", "5", "expense", self.food, "2026-13-01")
        with self.assertRaises(ValueError):
            tx.add_transaction("x", "5", "income", self.salary, "2026-10-01", installments=3)

    def test_totals_and_filters(self):
        self.add("100", "income", "2026-10-01", "Pagamento")
        self.add("30.10", "expense", "2026-10-02", "Café com leite")
        self.add("20", "expense", "2026-11-02", "Mercado")
        t = tx.get_totals("2026-10-01", "2026-10-31")
        self.assertEqual((t["income"], t["expense"], t["net"]), (10000, 3010, 6990))
        self.assertEqual(len(tx.list_transactions(kind="expense")), 2)
        self.assertEqual(len(tx.list_transactions(search="cafe")), 1)   # sem acento
        self.assertEqual(len(tx.list_transactions(search="CAFÉ leite")), 1)
        self.assertEqual(len(tx.list_transactions(search="100%")), 0)   # % literal
        self.assertEqual(len(tx.list_transactions(start_date="2026-11-01")), 1)
        self.assertEqual(len(tx.list_transactions(category_id=self.food)), 2)
        self.assertEqual(tx.list_transactions(order_by="amount", descending=False)[0]["amount"], 3010)  # ordem por valor com sinal: maior despesa primeiro
        page = tx.list_transactions(limit=2, offset=0)
        rest = tx.list_transactions(limit=2, offset=2)
        self.assertEqual((len(page), len(rest)), (2, 1))
        self.assertEqual(tx.list_transactions(limit=0), [])
        with self.assertRaises(ValueError):
            tx.list_transactions(limit=-1)
        with self.assertRaises(ValueError):
            tx.list_transactions(limit=1, offset=-1)
        s = tx.summarize_transactions(kind="expense")
        self.assertEqual((s["count"], s["expense"]), (2, 5010))

    def test_installments(self):
        first = self.add("100", d="2026-01-31", installments=3)
        rows = tx.list_transactions(order_by="date", descending=False)
        self.assertEqual([r["amount"] for r in rows], [3334, 3333, 3333])
        self.assertEqual(sum(r["amount"] for r in rows), 10000)
        self.assertEqual([r["transaction_date"] for r in rows],
                         ["2026-01-31", "2026-02-28", "2026-03-31"])
        self.assertEqual(tx.describe(rows[0]), "Teste (1/3)")
        deleted = tx.delete_transaction(first, whole_group=True)
        self.assertEqual(len(deleted), 3)
        self.assertEqual(tx.count_transactions(), 0)
        tx.restore_transactions(deleted)
        self.assertEqual(tx.count_transactions(), 3)

    def test_category_deletion_keeps_transactions(self):
        extra = categories.add_category("Pets", "expense")
        tid = tx.add_transaction("Ração", "10", "expense", extra, "2026-10-01")
        with self.assertRaises(ValueError):
            categories.delete_category(extra)
        categories.delete_category(extra, move_to=self.food)
        self.assertEqual(tx.get_transaction(tid)["category_id"], self.food)
        with self.assertRaises(ValueError):
            categories.add_category("alimentação", "expense")  # duplicada

    def test_category_deletion_moves_budgets(self):
        extra = categories.add_category("Serviços", "expense")
        budgets.save_budget("2026-10", extra, "30")
        with self.assertRaises(ValueError):
            categories.delete_category(extra)

        categories.delete_category(extra, move_to=self.food)

        rows = budgets.list_budgets("2026-10")
        self.assertEqual(
            [(row["category_id"], row["budget"]) for row in rows],
            [(self.food, 3000)],
        )

    def test_category_deletion_rejects_budget_conflict(self):
        extra = categories.add_category("Serviços", "expense")
        budgets.save_budget("2026-10", extra, "30")
        budgets.save_budget("2026-10", self.food, "20")

        with self.assertRaisesRegex(ValueError, "Já existe um orçamento"):
            categories.delete_category(extra, move_to=self.food)

        self.assertIsNotNone(categories.get_category(extra))
        rows = budgets.list_budgets("2026-10")
        self.assertEqual(
            {row["category_id"]: row["budget"] for row in rows},
            {extra: 3000, self.food: 2000},
        )


class AccountTests(DbTestCase):
    def test_transfer_not_income_or_expense(self):
        savings = accounts.add_account("Poupança", "savings", "50")
        tx.add_transaction("Salário", "1000", "income", self.salary, "2026-10-01", account_id=self.account)
        accounts.add_transfer(self.account, savings, "300", "2026-10-02")
        totals = tx.get_totals("2026-10-01", "2026-10-31")
        self.assertEqual((totals["income"], totals["expense"]), (100000, 0))
        by_name = {a["name"]: a for a in accounts.list_accounts(today="2026-10-31")}
        self.assertEqual(by_name["Conta principal"]["balance"], 70000)
        self.assertEqual(by_name["Poupança"]["balance"], 35000)
        self.assertEqual(accounts.total_balance("2026-10-31"), 105000)  # soma preservada
        rep = reports.category_report("2026-10-01", "2026-10-31", "expense")
        self.assertEqual(rep, [])

    def test_transfer_rules(self):
        other = accounts.add_account("Outra")
        with self.assertRaises(ValueError):
            accounts.add_transfer(self.account, self.account, "5", "2026-10-01")
        with self.assertRaises(ValueError):
            accounts.add_transfer(self.account, other, "0", "2026-10-01")
        tid = accounts.add_transfer(self.account, other, "5", "2026-10-01")
        row = accounts.delete_transfer(tid)
        accounts.restore_transfer(row)
        self.assertEqual(len(accounts.list_transfers()), 1)
        accounts.update_transfer(tid, other, self.account, "7,50", "2026-10-03")
        self.assertEqual(accounts.get_transfer(tid)["amount"], 750)

    def test_future_items_do_not_change_current_balance(self):
        tx.add_transaction("Futuro", "10", "expense", self.cat("Alimentação", "expense"), "2026-12-01")
        acc = accounts.get_account(self.account, today="2026-10-01")
        self.assertEqual((acc["balance"], acc["projected_balance"]), (0, -1000))

    def test_archive_and_delete_rules(self):
        other = accounts.add_account("Reserva", opening_balance="10")
        with self.assertRaises(ValueError):
            accounts.archive_account(other)          # saldo != 0
        accounts.update_account(other, "Reserva", "savings", "0")
        accounts.archive_account(other)
        self.assertEqual(len(accounts.list_accounts()), 1)
        with self.assertRaises(ValueError):
            tx.add_transaction("x", "1", "expense", self.cat("Alimentação", "expense"), "2026-10-01", account_id=other)
        with self.assertRaises(ValueError):
            accounts.archive_account(self.account)   # única ativa
        with self.assertRaises(ValueError):
            accounts.add_account("reserva")          # nome duplicado
        tx.add_transaction("h", "1", "expense", self.cat("Alimentação", "expense"), "2026-10-01")
        with self.assertRaises(ValueError):
            accounts.delete_account(self.account)    # tem histórico
        accounts.delete_account(other)

    def test_cannot_delete_last_active_account_even_with_archived_ones(self):
        extra = accounts.add_account("Extra")
        accounts.archive_account(extra)
        with self.assertRaises(ValueError):
            accounts.delete_account(self.account)
        self.assertEqual(len(accounts.list_accounts()), 1)


class BudgetReportTests(DbTestCase):
    def test_budget_spent(self):
        tx.add_transaction("a", "40", "expense", self.food, "2026-10-31")
        tx.add_transaction("b", "70", "expense", self.food, "2026-11-01")
        budgets.save_budget("2026-10", self.food, "100")
        budgets.save_budget("2026-10", self.food, "50")   # atualiza
        rows = budgets.list_budgets("2026-10")
        self.assertEqual((len(rows), rows[0]["budget"], rows[0]["spent"]), (1, 5000, 4000))
        with self.assertRaises(ValueError):
            budgets.save_budget("2026-10", self.salary, "10")
        self.assertEqual(budgets.copy_budgets("2026-10", "2026-11"), 1)
        self.assertEqual(budgets.list_budgets("2026-11")[0]["spent"], 7000)
        self.assertEqual(budgets.budget_summary("2026-11")["over"], 1)

    def test_reports(self):
        tx.add_transaction("a", "60", "expense", self.food, "2026-10-10")
        tx.add_transaction("b", "40", "expense", self.cat("Lazer", "expense"), "2026-10-11")
        tx.add_transaction("c", "10", "expense", self.food, "2026-09-11")
        tx.add_transaction("s", "500", "income", self.salary, "2026-10-01")
        rep = reports.category_report("2026-10-01", "2026-10-31")
        self.assertEqual([r["total"] for r in rep], [6000, 4000])
        self.assertAlmostEqual(rep[0]["share"], 0.6)
        s = reports.period_summary("2026-10-01", "2026-10-31")
        self.assertEqual((s["income"], s["expense"], s["net"]), (50000, 10000, 40000))
        self.assertEqual(s["previous"]["expense"], 1000)
        self.assertAlmostEqual(s["expense_change"], 9.0)
        self.assertEqual(reports.previous_period("2026-10-05", "2026-10-14"), ("2026-09-25", "2026-10-04"))
        series = reports.monthly_series("2026-10", 3)
        self.assertEqual([m["month"] for m in series], ["2026-08", "2026-09", "2026-10"])
        self.assertEqual(series[0]["expense"], 0)
        data = reports.dashboard_data("2026-10", today="2026-10-31")
        self.assertEqual(data["total_balance"], 50000 - 11000)
        self.assertEqual(len(data["recent"]), 4)


class RecurringTests(DbTestCase):
    def test_generation_idempotent_and_catch_up(self):
        rid = recurring.add_recurring("Aluguel", "500", "expense", self.food, self.account,
                                      "monthly", "2026-01-31")
        self.assertEqual(recurring.run_due_recurring("2026-03-31"), 3)
        self.assertEqual(recurring.run_due_recurring("2026-03-31"), 0)
        dates = [r["transaction_date"] for r in tx.list_transactions(order_by="date", descending=False)]
        self.assertEqual(dates, ["2026-01-31", "2026-02-28", "2026-03-31"])
        self.assertEqual(recurring.get_recurring(rid)["next_date"], "2026-04-30")
        recurring.delete_recurring(rid)
        self.assertEqual(tx.count_transactions(), 3)  # histórico preservado

    def test_end_date_and_pause(self):
        rid = recurring.add_recurring("Curso", "10", "expense", self.food, self.account,
                                      "weekly", "2026-10-01", end_date="2026-10-15")
        self.assertEqual(recurring.run_due_recurring("2026-12-01"), 3)
        self.assertEqual(recurring.get_recurring(rid)["active"], 0)
        rid2 = recurring.add_recurring("X", "10", "expense", self.food, self.account,
                                       "yearly", "2026-10-01")
        recurring.set_active(rid2, False)
        self.assertEqual(recurring.run_due_recurring("2030-01-01"), 0)


class ImporterTests(DbTestCase):
    def write(self, text, name="in.csv", enc="utf-8"):
        path = database.DATA_DIR / name
        path.write_bytes(text.encode(enc))
        return path

    def test_import_and_duplicates(self):
        tx.add_transaction("Mercado", "12,50", "expense", self.food, "2026-10-01")
        path = self.write(
            "Data;Descrição;Valor;Categoria\n"
            "01/10/2026;Mercado;-12,50;Alimentação\n"      # duplicada
            "02/10/2026;Padaria;-3,20;Inexistente\n"
            "03/10/2026;Pagamento;1.000,00;Salário\n"
            "xx;Ruim;5;\n"
            "04/10/2026;Zero;0;\n", enc="cp1252")
        prep = importer.prepare_import(path, self.account)
        self.assertEqual((len(prep["rows"]), len(prep["errors"]), prep["duplicates"]), (3, 2, 1))
        before = tx.count_transactions()
        result = importer.commit_import(prep["rows"], self.account)
        self.assertEqual((result["imported"], result["skipped"]), (2, 1))
        self.assertEqual(tx.count_transactions(), before + 2)
        # segunda importação: tudo duplicado
        again = importer.prepare_import(path, self.account)
        self.assertEqual(again["duplicates"], 3)

    def test_missing_columns(self):
        with self.assertRaises(ValueError):
            importer.prepare_import(self.write("a;b\n1;2\n"), self.account)
        with self.assertRaises(ValueError):  # campo enorme: erro amigável, não csv.Error
            importer.prepare_import(
                self.write("Data;Descrição;Valor\n01/10/2026;" + "x" * 200000 + ";5\n"),
                self.account)

    def test_export_roundtrip(self):
        tx.add_transaction("=cmd", "1.234,56" if False else "1234,56", "expense", self.food, "2026-10-01", notes="n")
        out = database.DATA_DIR / "out.csv"
        importer.export_csv(out, tx.list_transactions())
        with open(out, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f, delimiter=";"))
        self.assertEqual(rows[1][5], "1234,56")
        self.assertTrue(rows[1][2].startswith("'"))   # fórmula neutralizada


class BackupMigrationTests(DbTestCase):
    def test_backup_restore(self):
        tid = tx.add_transaction("Antes", "10", "expense", self.food, "2026-10-01")
        path = database.create_backup("manual")
        tx.delete_transaction(tid)
        tx.add_transaction("Depois", "5", "expense", self.food, "2026-10-02")
        database.restore_backup(path)
        self.assertEqual([r["description"] for r in tx.list_transactions()], ["Antes"])
        self.assertTrue(any("antes_de_restaurar" in b["name"] for b in database.list_backups()))
        bad = database.DATA_DIR / "lixo.db"
        bad.write_bytes(b"isto nao e sqlite" * 100)
        with self.assertRaises(database.DatabaseError):
            database.restore_backup(bad)
        self.assertEqual(tx.count_transactions(), 1)

    def test_auto_backup_once_per_day(self):
        self.assertIsNotNone(backup.auto_backup_if_needed())
        self.assertIsNone(backup.auto_backup_if_needed())

    def test_legacy_migration_preserves_data(self):
        legacy = database.DATA_DIR / "legacy.db"
        con = sqlite3.connect(legacy)
        con.executescript("""
            CREATE TABLE categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, kind TEXT NOT NULL, type TEXT, UNIQUE(name, kind));
            CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, description TEXT NOT NULL, amount INTEGER NOT NULL, kind TEXT NOT NULL, category_id INTEGER, date TEXT NOT NULL, notes TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE budgets (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER NOT NULL, month TEXT NOT NULL, amount INTEGER NOT NULL, UNIQUE(category_id, month));
            INSERT INTO categories (name, kind) VALUES ('Food','expense'),('Salary','income'),('Minha','expense');
            INSERT INTO transactions (description, amount, kind, category_id, date) VALUES ('A',1999,'expense',1,'2026-01-02'),('B',500000,'income',2,'2026-01-03'),('C',100,'expense',NULL,'2026-01-04');
            INSERT INTO budgets (category_id, month, amount) VALUES (1,'2026-01',30000);
        """)
        con.commit(); con.close()
        database.restore_backup(legacy)      # restaura + migra (como import)
        rows = tx.list_transactions(order_by="date", descending=False)
        self.assertEqual([(r["description"], r["amount"], r["transaction_date"]) for r in rows],
                         [("A", 1999, "2026-01-02"), ("B", 500000, "2026-01-03"), ("C", 100, "2026-01-04")])
        names = {c["name"] for c in categories.get_categories()}
        self.assertTrue({"Alimentação", "Salário", "Minha"} <= names)
        self.assertEqual(budgets.list_budgets("2026-01")[0]["budget"], 30000)
        self.assertEqual(rows[2]["category_id"], None)
        self.assertEqual(database.integrity_report(), {"integrity": "ok", "foreign_key_errors": 0})
        self.assertEqual(sqlite3.connect(database.DB_PATH).execute("PRAGMA user_version").fetchone()[0], database.SCHEMA_VERSION)

    def test_future_version_rejected(self):
        con = sqlite3.connect(database.DB_PATH)
        con.execute("PRAGMA user_version = 99"); con.close()
        with self.assertRaises(database.DatabaseError):
            database.init_db()


if __name__ == "__main__":
    unittest.main()


class AdoptLegacyTests(unittest.TestCase):
    def test_adopt_copies_without_overwriting(self):
        import shutil, sqlite3, tempfile
        from pathlib import Path
        import database
        from backend import main
        tmp = Path(tempfile.mkdtemp(prefix="fc_adopt_"))
        old_base, old_path = database.BASE_DIR, database.DB_PATH
        try:
            (tmp / "proj" / "data").mkdir(parents=True)
            legacy = tmp / "proj" / "data" / "finance_control.db"
            con = sqlite3.connect(legacy)
            con.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT, kind TEXT)")
            con.execute("INSERT INTO categories (name, kind) VALUES ('X', 'expense')")
            con.commit(); con.close()
            database.BASE_DIR = tmp / "proj"
            database.set_db_path(tmp / "user" / "finance_control.db")
            self.assertTrue(main.adopt_legacy_db())
            n = sqlite3.connect(database.DB_PATH).execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            self.assertEqual(n, 1)
            self.assertTrue(legacy.exists())          # original intacto
            self.assertFalse(main.adopt_legacy_db())  # não sobrescreve
        finally:
            database.BASE_DIR = old_base
            database.set_db_path(old_path)
            shutil.rmtree(tmp, ignore_errors=True)
