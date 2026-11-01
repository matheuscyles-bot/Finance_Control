"""Consultas das telas novas (vencimentos, agenda, contas, relatórios)."""

import unittest

from tests.base import DbTestCase

from backend.services import accounts, budgets, planning, recurring
from backend.services import transactions as tx


class ProjectionTests(DbTestCase):
    def test_monthly_rule_projects_each_occurrence_until_end_date(self):
        recurring.add_recurring("Aluguel", "1200,00", "expense", self.food, self.account,
                                "monthly", "2026-11-05", end_date="2026-12-31")
        items = planning.projected_recurring("2026-11-01", "2027-02-28")
        self.assertEqual([i["date"] for i in items], ["2026-11-05", "2026-12-05"])
        self.assertTrue(all(i["amount"] == 120000 and i["source"] == "recurring" for i in items))

    def test_paused_rules_and_other_kinds_are_left_out(self):
        rid = recurring.add_recurring("Streaming", "39,90", "expense", self.food, self.account,
                                      "monthly", "2026-11-10")
        recurring.add_recurring("Salário", "2500", "income", self.salary, self.account,
                                "monthly", "2026-11-28")
        recurring.set_active(rid, False)
        self.assertEqual(planning.projected_recurring("2026-11-01", "2026-11-30", "expense"), [])
        self.assertEqual(len(planning.projected_recurring("2026-11-01", "2026-11-30")), 1)


class BoardTests(DbTestCase):
    def test_columns_split_by_date_and_kind(self):
        today = "2026-11-10"
        tx.add_transaction("Mercado", "50", "expense", self.food, "2026-11-02")
        tx.add_transaction("Salário", "3000", "income", self.salary, "2026-11-05")
        tx.add_transaction("Luz", "80", "expense", self.food, "2026-11-14")
        tx.add_transaction("Seguro", "200", "expense", self.food, "2026-12-01")
        tx.add_transaction("Mês passado", "10", "expense", self.food, "2026-10-30")
        recurring.add_recurring("Internet", "100", "expense", self.food, self.account,
                                "monthly", "2026-11-12")
        board = planning.bills_board(today=today)
        self.assertEqual([r["description"] for r in board["paid"]], ["Mercado"])
        self.assertEqual([r["description"] for r in board["received"]], ["Salário"])
        self.assertEqual([r["description"] for r in board["due_soon"]], ["Internet", "Luz"])
        self.assertIn("Seguro", [r["description"] for r in board["to_pay"]])
        self.assertIn("Internet", [r["description"] for r in board["to_pay"]])  # 12/12

        without = planning.bills_board(today=today, include_recurring=False)
        self.assertEqual([r["description"] for r in without["due_soon"]], ["Luz"])

    def test_transfers_never_appear(self):
        other = accounts.add_account("Poupança", "savings")
        accounts.add_transfer(self.account, other, "100", "2026-11-03")
        board = planning.bills_board(today="2026-11-10")
        self.assertEqual(board["paid"] + board["received"], [])


class SummaryTests(DbTestCase):
    def test_account_activity_uses_transactions_and_transfers(self):
        other = accounts.add_account("Poupança", "savings")
        tx.add_transaction("Mercado", "10", "expense", self.food, "2026-03-01")
        accounts.add_transfer(self.account, other, "5", "2026-04-02")
        activity = planning.account_activity()
        self.assertEqual(activity[self.account], "2026-04-02")
        self.assertEqual(activity[other], "2026-04-02")

    def test_top_transactions_by_amount(self):
        for value in ("10", "300", "45,50", "120", "5"):
            tx.add_transaction(f"Item {value}", value, "expense", self.food, "2026-03-04")
        tx.add_transaction("Outro mês", "999", "expense", self.food, "2026-04-01")
        rows = planning.top_transactions("2026-03", 3)
        self.assertEqual([r["amount"] for r in rows], [30000, 12000, 4550])

    def test_budget_totals_fill_missing_months(self):
        budgets.save_budget("2026-02", self.food, "400")
        totals = planning.budget_totals("2026-01", 3)
        self.assertEqual(totals, {"2026-01": 0, "2026-02": 40000, "2026-03": 0})

    def test_category_by_month_keeps_leaders_and_groups_the_rest(self):
        from backend.services import categories
        names = {c["name"]: c["id"] for c in categories.get_categories("expense")}
        tx.add_transaction("A", "100", "expense", names["Moradia"], "2026-01-05")
        tx.add_transaction("B", "50", "expense", names["Transporte"], "2026-02-05")
        tx.add_transaction("C", "10", "expense", names["Lazer"], "2026-02-06")
        months, series = planning.category_by_month("2026-01", 2, top=2)
        self.assertEqual(months, ["2026-01", "2026-02"])
        self.assertEqual(series[0], ("Moradia", [10000, 0]))
        self.assertEqual(series[1], ("Transporte", [0, 5000]))
        self.assertEqual(series[2], (None, [0, 1000]))


if __name__ == "__main__":
    unittest.main()
