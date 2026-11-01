"""Testes de revisão: cálculos, saldos, orçamentos, atomicidade e banco inválido.

Todos usam banco temporário (tests.base.DbTestCase), nunca o banco real.
"""

import os
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from tests.base import DbTestCase, ROOT  # noqa: F401  (ajusta sys.path)

import database
from backend.services import accounts, budgets, reports
from backend.services import transactions as tx
from backend.utils.formatters import add_months

FAR_FUTURE = "2099-01-01"


class SaldoETransacoesTests(DbTestCase):
    def test_receita_e_despesa_atualizam_saldo(self):
        tx.add_transaction("Salário", "1000,00", "income", self.salary, "2026-03-01")
        tx.add_transaction("Mercado", "250,10", "expense", self.food, "2026-03-05")
        saldo = accounts.get_account(self.account, today=FAR_FUTURE)["balance"]
        self.assertEqual(saldo, 74990)

    def test_editar_despesa_recalcula_saldo(self):
        tx.add_transaction("Salário", "1000,00", "income", self.salary, "2026-03-01")
        tid = tx.add_transaction("Mercado", "250,10", "expense", self.food, "2026-03-05")
        tx.update_transaction(tid, "Mercado", "300,00", "expense", self.food,
                              "2026-03-05", "", self.account)
        saldo = accounts.get_account(self.account, today=FAR_FUTURE)["balance"]
        self.assertEqual(saldo, 70000)

    def test_excluir_receita_e_desfazer(self):
        tx.add_transaction("Mercado", "300,00", "expense", self.food, "2026-03-05")
        rid = tx.add_transaction("Salário", "1000,00", "income", self.salary, "2026-03-01")
        removed = tx.delete_transaction(rid)
        self.assertEqual(accounts.get_account(self.account, today=FAR_FUTURE)["balance"], -30000)
        tx.restore_transactions(removed)
        self.assertEqual(accounts.get_account(self.account, today=FAR_FUTURE)["balance"], 70000)

    def test_transferencia_nao_e_receita_nem_despesa(self):
        outra = accounts.add_account("Poupança", "savings")
        accounts.add_transfer(self.account, outra, "100,00", "2026-03-10")
        origem = accounts.get_account(self.account, today=FAR_FUTURE)["balance"]
        destino = accounts.get_account(outra, today=FAR_FUTURE)["balance"]
        self.assertEqual(origem, -10000)
        self.assertEqual(destino, 10000)
        resumo = reports.period_summary("2026-03-01", "2026-03-31")
        self.assertEqual(resumo["income"], 0)
        self.assertEqual(resumo["expense"], 0)

    def test_orcamento_gasto_e_restante(self):
        budgets.save_budget("2026-03", self.food, "500,00")
        tx.add_transaction("Mercado", "120,50", "expense", self.food, "2026-03-10")
        tx.add_transaction("Mercado", "30,00", "expense", self.food, "2026-04-01")
        resumo = budgets.budget_summary("2026-03")
        self.assertEqual(resumo["budget"], 50000)
        self.assertEqual(resumo["spent"], 12050)
        self.assertEqual(resumo["remaining"], 37950)

    def test_totais_mensais_e_anuais(self):
        tx.add_transaction("Salário", "2000,00", "income", self.salary, "2026-01-31")
        tx.add_transaction("Mercado", "100,01", "expense", self.food, "2026-01-31")
        tx.add_transaction("Mercado", "50,00", "expense", self.food, "2026-02-01")
        tx.add_transaction("Salário", "2000,00", "income", self.salary, "2026-12-31")
        jan = reports.period_summary("2026-01-01", "2026-01-31")
        self.assertEqual((jan["income"], jan["expense"]), (200000, 10001))
        ano = reports.period_summary("2026-01-01", "2026-12-31")
        self.assertEqual((ano["income"], ano["expense"]), (400000, 15001))

    def test_centavo_minimo_e_parcelas_somam_exato(self):
        tid = tx.add_transaction("Centavo", "0,01", "expense", self.food, "2026-03-01")
        self.assertEqual(tx.get_transaction(tid)["amount"], 1)
        tx.add_transaction("Tênis", "100,00", "expense", self.food,
                           "2026-01-31", installments=3)
        parcelas = [p for p in tx.list_transactions(kind="expense", category_id=self.food)
                    if p["installment_group"]]
        self.assertEqual(len(parcelas), 3)
        self.assertEqual(sum(p["amount"] for p in parcelas), 10000)

    def test_parcela_mensal_respeita_fim_do_mes(self):
        self.assertEqual(str(add_months(date(2026, 1, 31), 1, anchor_day=31)), "2026-02-28")

    def test_filtro_sem_resultado_devolve_lista_vazia(self):
        tx.add_transaction("Mercado", "10,00", "expense", self.food, "2026-03-05")
        self.assertEqual(tx.list_transactions(start_date="2030-01-01", end_date="2030-12-31"), [])
        self.assertEqual(tx.list_transactions(kind="income"), [])


class AtomicidadeTests(DbTestCase):
    def test_parcelas_com_falha_no_meio_nao_deixam_registros(self):
        contagem_antes = tx.count_transactions()
        with mock.patch("backend.services.transactions.split_installments",
                        return_value=[10000, 0, 10000]):
            with self.assertRaises(Exception):
                tx.add_transaction("Tênis", "200,00", "expense", self.food,
                                   "2026-01-31", installments=3)
        self.assertEqual(tx.count_transactions(), contagem_antes)


class PersistenciaTests(DbTestCase):
    def test_dados_sobrevivem_a_reabertura_em_outro_processo(self):
        tx.add_transaction("Salário", "1234,56", "income", self.salary, "2026-03-01")
        codigo = (
            "import sys; from pathlib import Path; import database;"
            f"database.set_db_path(Path({str(database.DB_PATH)!r})); database.init_db();"
            "from backend.services import transactions as tx;"
            "print(tx.count_transactions())"
        )
        res = subprocess.run([sys.executable, "-c", codigo], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "1", res.stdout)


class BancoInvalidoTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = Path(tempfile.mkdtemp(prefix="fc_invalido_"))
        self._old = database.DB_PATH
        database.set_db_path(self._tmp / "ruim.db")

    def tearDown(self):
        import shutil
        database.set_db_path(self._old)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_arquivo_corrompido_gera_erro_claro(self):
        (self._tmp / "ruim.db").write_bytes(b"isto nao e um banco sqlite" * 200)
        with self.assertRaises(database.DatabaseError) as ctx:
            database.init_db()
        self.assertIn("danificado", str(ctx.exception))

    def test_mensagem_de_erro_aponta_pasta_de_backups_correta(self):
        (self._tmp / "ruim.db").write_bytes(b"isto nao e um banco sqlite" * 200)
        with self.assertRaises(database.DatabaseError) as ctx:
            database.init_db()
        # A pasta real de backups é database.BACKUP_DIR (dentro da pasta de dados).
        self.assertIn(str(database.BACKUP_DIR), str(ctx.exception),
                      f"mensagem cita pasta fixa: {ctx.exception}")

    def test_banco_novo_inicializa_em_pasta_vazia(self):
        database.init_db()
        self.assertTrue((self._tmp / "ruim.db").exists())


class CaminhoDoBancoTests(unittest.TestCase):
    def test_no_mac_dados_ficam_em_application_support(self):
        env = {k: v for k, v in os.environ.items() if k != "FINANCE_CONTROL_DATA"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(sys, "platform", "darwin"):
            caminho = database.default_data_dir()
        self.assertEqual(caminho, Path.home() / "Library" / "Application Support" / "Finance Control")


if __name__ == "__main__":
    unittest.main()
