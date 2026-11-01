"""Contas e transferências entre contas.

Transferências NÃO são receitas nem despesas: elas só movem dinheiro entre
contas e por isso ficam fora dos totais de receitas/despesas.
"""

import sqlite3
from datetime import date

from backend.config import ACCOUNT_TYPES
from database import fetch_all, fetch_one, get_connection
from backend.utils.validators import (
    validate_amount,
    validate_date,
    validate_name,
    validate_notes,
    validate_optional_amount,
)


def _balance_sql(today_clause):
    """Expressão SQL do saldo: saldo inicial + movimentações + transferências."""
    where_t = " AND t.transaction_date <= :today" if today_clause else ""
    where_x = " AND x.transfer_date <= :today" if today_clause else ""
    return f"""
        a.opening_balance
        + COALESCE((SELECT SUM(CASE t.kind WHEN 'income' THEN t.amount
                                           ELSE -t.amount END)
                    FROM transactions t
                    WHERE t.account_id = a.id{where_t}), 0)
        + COALESCE((SELECT SUM(x.amount) FROM transfers x
                    WHERE x.to_account_id = a.id{where_x}), 0)
        - COALESCE((SELECT SUM(x.amount) FROM transfers x
                    WHERE x.from_account_id = a.id{where_x}), 0)
    """


_ACCOUNT_SELECT = f"""
    SELECT a.id, a.name, a.type, a.opening_balance, a.archived,
           {_balance_sql(True)} AS balance,
           {_balance_sql(False)} AS projected_balance
    FROM accounts a
"""


def list_accounts(include_archived=False, today=None):
    """Contas com saldo atual (até hoje) e saldo previsto (com lançamentos
    futuros)."""
    today = today or date.today().isoformat()
    query = _ACCOUNT_SELECT
    if not include_archived:
        query += " WHERE a.archived = 0"
    query += " ORDER BY a.archived, a.id"
    return fetch_all(query, {"today": today})


def get_account(account_id, today=None):
    today = today or date.today().isoformat()
    return fetch_one(
        _ACCOUNT_SELECT + " WHERE a.id = :id", {"id": account_id, "today": today}
    )


def get_default_account_id():
    row = fetch_one(
        "SELECT id FROM accounts WHERE archived = 0 ORDER BY id LIMIT 1"
    )
    if not row:
        raise ValueError("Cadastre uma conta antes de registrar movimentações.")
    return row["id"]


def total_balance(today=None):
    """Saldo consolidado de todas as contas ativas, até hoje."""
    today = today or date.today().isoformat()
    row = fetch_one(
        f"SELECT COALESCE(SUM({_balance_sql(True)}), 0) AS total "
        "FROM accounts a WHERE a.archived = 0",
        {"today": today},
    )
    return row["total"]


def _validate_type(account_type):
    if account_type not in ACCOUNT_TYPES:
        raise ValueError("Tipo de conta inválido.")
    return account_type


def _name_taken(conn, name, ignore_id=None):
    return conn.execute(
        "SELECT 1 FROM accounts WHERE name = ? COLLATE NOCASE AND id IS NOT ?",
        (name, ignore_id),
    ).fetchone() is not None


def add_account(name, account_type="checking", opening_balance="0"):
    name = validate_name(name, "O nome da conta")
    account_type = _validate_type(account_type)
    opening = validate_optional_amount(opening_balance)
    with get_connection() as conn:
        if _name_taken(conn, name):
            raise ValueError("Já existe uma conta com esse nome.")
        return conn.execute(
            "INSERT INTO accounts (name, type, opening_balance) VALUES (?, ?, ?)",
            (name, account_type, opening),
        ).lastrowid


def update_account(account_id, name, account_type, opening_balance="0"):
    name = validate_name(name, "O nome da conta")
    account_type = _validate_type(account_type)
    opening = validate_optional_amount(opening_balance)
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM accounts WHERE id = ?", (account_id,)
        ).fetchone():
            raise ValueError("Conta não encontrada.")
        if _name_taken(conn, name, ignore_id=account_id):
            raise ValueError("Já existe uma conta com esse nome.")
        conn.execute(
            "UPDATE accounts SET name = ?, type = ?, opening_balance = ? "
            "WHERE id = ?",
            (name, account_type, opening, account_id),
        )


def account_usage(account_id):
    with get_connection() as conn:
        def count(query):
            return conn.execute(query, (account_id,)).fetchone()[0]

        return {
            "transactions": count(
                "SELECT COUNT(*) FROM transactions WHERE account_id = ?"
            ),
            "transfers": conn.execute(
                "SELECT COUNT(*) FROM transfers "
                "WHERE from_account_id = ? OR to_account_id = ?",
                (account_id, account_id),
            ).fetchone()[0],
            "recurring": count(
                "SELECT COUNT(*) FROM recurring WHERE account_id = ?"
            ),
        }


def archive_account(account_id):
    """Arquiva uma conta. Exige saldo zerado e outra conta ativa."""
    account = get_account(account_id)
    if not account:
        raise ValueError("Conta não encontrada.")
    if account["projected_balance"] != 0 or account["balance"] != 0:
        raise ValueError(
            "Para arquivar, o saldo da conta precisa estar zerado. "
            "Transfira o valor para outra conta antes."
        )
    active = fetch_one(
        "SELECT COUNT(*) AS n FROM accounts WHERE archived = 0 AND id <> ?",
        (account_id,),
    )["n"]
    if active == 0:
        raise ValueError("É preciso manter pelo menos uma conta ativa.")
    with get_connection() as conn:
        conn.execute("UPDATE accounts SET archived = 1 WHERE id = ?", (account_id,))
        # Recorrências dessa conta ficam pausadas para não gerar lançamentos.
        conn.execute(
            "UPDATE recurring SET active = 0 WHERE account_id = ?", (account_id,)
        )


def unarchive_account(account_id):
    with get_connection() as conn:
        conn.execute("UPDATE accounts SET archived = 0 WHERE id = ?", (account_id,))


def delete_account(account_id):
    """Só permite excluir contas sem nenhum histórico."""
    usage = account_usage(account_id)
    if any(usage.values()):
        raise ValueError(
            "Essa conta tem histórico e não pode ser excluída. "
            "Use 'Arquivar' para escondê-la."
        )
    with get_connection() as conn:
        target = conn.execute(
            "SELECT archived FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if not target:
            raise ValueError("Conta não encontrada.")
        others = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE archived = 0 AND id <> ?",
            (account_id,),
        ).fetchone()[0]
        if not target["archived"] and others == 0:
            raise ValueError("É preciso manter pelo menos uma conta ativa.")
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))


# ----------------------------------------------------------------------
# Transferências
# ----------------------------------------------------------------------

def _check_transfer_accounts(conn, from_id, to_id):
    if from_id == to_id:
        raise ValueError("Escolha contas de origem e destino diferentes.")
    for account_id in (from_id, to_id):
        row = conn.execute(
            "SELECT archived FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if not row:
            raise ValueError("Conta não encontrada.")
        if row["archived"]:
            raise ValueError("Não é possível transferir de/para conta arquivada.")


def add_transfer(from_account_id, to_account_id, amount, transfer_date, notes=""):
    amount = validate_amount(amount)
    transfer_date = validate_date(transfer_date)
    notes = validate_notes(notes)
    with get_connection() as conn:
        _check_transfer_accounts(conn, from_account_id, to_account_id)
        return conn.execute(
            "INSERT INTO transfers "
            "(from_account_id, to_account_id, amount, transfer_date, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (from_account_id, to_account_id, amount, transfer_date, notes),
        ).lastrowid


def update_transfer(transfer_id, from_account_id, to_account_id, amount,
                    transfer_date, notes=""):
    amount = validate_amount(amount)
    transfer_date = validate_date(transfer_date)
    notes = validate_notes(notes)
    with get_connection() as conn:
        _check_transfer_accounts(conn, from_account_id, to_account_id)
        cursor = conn.execute(
            "UPDATE transfers SET from_account_id = ?, to_account_id = ?, "
            "amount = ?, transfer_date = ?, notes = ? WHERE id = ?",
            (from_account_id, to_account_id, amount, transfer_date, notes,
             transfer_id),
        )
        if cursor.rowcount == 0:
            raise ValueError("Transferência não encontrada.")


def delete_transfer(transfer_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM transfers WHERE id = ?", (transfer_id,)
        ).fetchone()
        if not row:
            raise ValueError("Transferência não encontrada.")
        conn.execute("DELETE FROM transfers WHERE id = ?", (transfer_id,))
        return dict(row)


def restore_transfer(row):
    """Desfaz uma exclusão de transferência."""
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO transfers (id, from_account_id, to_account_id, "
                "amount, transfer_date, notes, created_at) "
                "VALUES (:id, :from_account_id, :to_account_id, :amount, "
                ":transfer_date, :notes, :created_at)",
                row,
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Não foi possível desfazer a exclusão.") from exc


def get_transfer(transfer_id):
    return fetch_one(
        _TRANSFER_SELECT + " WHERE x.id = ?", (transfer_id,)
    )


_TRANSFER_SELECT = """
    SELECT x.*, f.name AS from_name, t.name AS to_name
    FROM transfers x
    JOIN accounts f ON f.id = x.from_account_id
    JOIN accounts t ON t.id = x.to_account_id
"""


def list_transfers(limit=None, account_id=None):
    query = _TRANSFER_SELECT
    params = []
    if account_id:
        query += " WHERE x.from_account_id = ? OR x.to_account_id = ?"
        params += [account_id, account_id]
    query += " ORDER BY x.transfer_date DESC, x.id DESC"
    if limit:
        query += " LIMIT ?"
        params.append(int(limit))
    return fetch_all(query, params)
