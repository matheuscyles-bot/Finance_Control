"""Receitas e despesas: cadastro, edição, exclusão, busca e totais."""

import sqlite3
import uuid
from datetime import date, datetime

from backend.utils.i18n import t
from backend.config import MAX_INSTALLMENTS
from database import fetch_all, fetch_one, get_connection
from backend.utils.formatters import add_months
from backend.utils.money import split_installments
from backend.utils.text import escape_like, normalize_text
from backend.utils.validators import (
    validate_amount,
    validate_date,
    validate_description,
    validate_kind,
    validate_notes,
)

UNCATEGORIZED = -1  # valor especial do filtro de categoria

_BASE_SELECT = """
    SELECT t.*, c.name AS category_name, a.name AS account_name
    FROM transactions t
    LEFT JOIN categories c ON c.id = t.category_id
    JOIN accounts a ON a.id = t.account_id
"""

_ORDER_COLUMNS = {
    "date": "t.transaction_date",
    "description": "norm(t.description)",
    "category": "norm(COALESCE(c.name, ''))",
    "account": "norm(a.name)",
    "amount": "CASE WHEN t.kind = 'income' THEN t.amount ELSE -t.amount END",
}

_COLUMNS = (
    "id", "description", "amount", "kind", "category_id", "account_id",
    "transaction_date", "notes", "installment_group", "installment_no",
    "installment_total", "recurring_id", "created_at",
)


def describe(row):
    """Descrição para exibir: acrescenta (parcela/total) quando houver."""
    text = row["description"]
    if row["installment_total"]:
        text += f" ({row['installment_no']}/{row['installment_total']})"
    return text


def _check_category(conn, category_id, kind):
    if category_id is None:
        raise ValueError(t("error.category_required"))
    category = conn.execute(
        "SELECT id, kind FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    if not category or category["kind"] != kind:
        raise ValueError(t("error.category_kind_invalid"))


def _resolve_account(conn, account_id):
    if account_id is None:
        row = conn.execute(
            "SELECT id FROM accounts WHERE archived = 0 ORDER BY id LIMIT 1"
        ).fetchone()
        if not row:
            raise ValueError(t("error.create_account_first"))
        return row["id"]
    row = conn.execute(
        "SELECT id, archived FROM accounts WHERE id = ?", (account_id,)
    ).fetchone()
    if not row:
        raise ValueError(t("error.account_not_found"))
    if row["archived"]:
        raise ValueError(t("error.account_archived"))
    return row["id"]


def add_transaction(description, amount, kind, category_id, transaction_date,
                    notes="", account_id=None, installments=1):
    """Cadastra uma movimentação. Com ``installments`` > 1 cria as parcelas
    mensais (a soma das parcelas é exatamente o valor total).

    Devolve o id da movimentação (ou da primeira parcela)."""
    description = validate_description(description)
    amount = validate_amount(amount)
    transaction_date = validate_date(transaction_date)
    notes = validate_notes(notes)
    validate_kind(kind)

    try:
        installments = int(installments or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError(t("validation.installments_invalid")) from exc
    if installments < 1 or installments > MAX_INSTALLMENTS:
        raise ValueError(t("error.installments_range", max=MAX_INSTALLMENTS))
    if installments > 1 and kind != "expense":
        raise ValueError(t("error.installments_expense_only"))

    with get_connection() as conn:
        _check_category(conn, category_id, kind)
        account_id = _resolve_account(conn, account_id)

        if installments == 1:
            return conn.execute(
                "INSERT INTO transactions (description, amount, kind, "
                "category_id, account_id, transaction_date, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (description, amount, kind, category_id, account_id,
                 transaction_date, notes),
            ).lastrowid

        group = uuid.uuid4().hex
        first_date = datetime.strptime(transaction_date, "%Y-%m-%d").date()
        first_id = None
        for number, part in enumerate(split_installments(amount, installments), 1):
            due = add_months(first_date, number - 1, anchor_day=first_date.day)
            new_id = conn.execute(
                "INSERT INTO transactions (description, amount, kind, "
                "category_id, account_id, transaction_date, notes, "
                "installment_group, installment_no, installment_total) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (description, part, kind, category_id, account_id,
                 due.isoformat(), notes, group, number, installments),
            ).lastrowid
            first_id = first_id or new_id
        return first_id


def update_transaction(transaction_id, description, amount, kind, category_id,
                       transaction_date, notes="", account_id=None):
    description = validate_description(description)
    amount = validate_amount(amount)
    transaction_date = validate_date(transaction_date)
    notes = validate_notes(notes)
    validate_kind(kind)

    with get_connection() as conn:
        current = conn.execute(
            "SELECT account_id, installment_total FROM transactions WHERE id = ?",
            (transaction_id,),
        ).fetchone()
        if not current:
            raise ValueError(t("error.transaction_not_found"))
        if current["installment_total"] and kind != "expense":
            raise ValueError(t("error.installment_is_expense"))
        _check_category(conn, category_id, kind)
        if account_id is None or account_id == current["account_id"]:
            account_id = current["account_id"]  # mantém mesmo se arquivada
        else:
            account_id = _resolve_account(conn, account_id)

        conn.execute(
            "UPDATE transactions SET description = ?, amount = ?, kind = ?, "
            "category_id = ?, account_id = ?, transaction_date = ?, notes = ? "
            "WHERE id = ?",
            (description, amount, kind, category_id, account_id,
             transaction_date, notes, transaction_id),
        )


def get_transaction(transaction_id):
    return fetch_one(_BASE_SELECT + " WHERE t.id = ?", (transaction_id,))


def delete_transaction(transaction_id, whole_group=False):
    """Exclui a movimentação (ou todas as parcelas do grupo). Devolve as
    linhas excluídas, para que a exclusão possa ser desfeita."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
        if not row:
            raise ValueError(t("error.transaction_not_found"))

        if whole_group and row["installment_group"]:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE installment_group = ?",
                (row["installment_group"],),
            ).fetchall()
            conn.execute(
                "DELETE FROM transactions WHERE installment_group = ?",
                (row["installment_group"],),
            )
        else:
            rows = [row]
            conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        return [dict(r) for r in rows]


def restore_transactions(rows):
    """Desfaz uma exclusão, recriando as linhas com os mesmos ids."""
    try:
        with get_connection() as conn:
            for row in rows:
                data = {key: row.get(key) for key in _COLUMNS}
                if data["category_id"] is not None and not conn.execute(
                    "SELECT 1 FROM categories WHERE id = ?", (data["category_id"],)
                ).fetchone():
                    data["category_id"] = None
                conn.execute(
                    f"INSERT INTO transactions ({', '.join(_COLUMNS)}) "
                    f"VALUES ({', '.join(':' + c for c in _COLUMNS)})",
                    data,
                )
    except sqlite3.IntegrityError as exc:
        raise ValueError(t("error.undo_failed_missing")) from exc


def _build_filters(start_date=None, end_date=None, kind=None, category_id=None,
                   search=None, account_id=None):
    clauses, params = [], []

    if start_date:
        clauses.append("t.transaction_date >= ?")
        params.append(validate_date(start_date))
    if end_date:
        clauses.append("t.transaction_date <= ?")
        params.append(validate_date(end_date))
    if kind in ("income", "expense"):
        clauses.append("t.kind = ?")
        params.append(kind)
    if category_id == UNCATEGORIZED:
        clauses.append("t.category_id IS NULL")
    elif category_id:
        clauses.append("t.category_id = ?")
        params.append(category_id)
    if account_id:
        clauses.append("t.account_id = ?")
        params.append(account_id)
    if search and search.strip():
        for term in search.split():
            like = "%" + escape_like(normalize_text(term)) + "%"
            clauses.append(
                "(norm(t.description) LIKE ? ESCAPE '\\' "
                "OR norm(t.notes) LIKE ? ESCAPE '\\')"
            )
            params += [like, like]

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_transactions(start_date=None, end_date=None, kind=None,
                      category_id=None, search=None, account_id=None,
                      order_by="date", descending=True, limit=None, offset=0):
    where, params = _build_filters(
        start_date, end_date, kind, category_id, search, account_id
    )
    column = _ORDER_COLUMNS.get(order_by, _ORDER_COLUMNS["date"])
    direction = "DESC" if descending else "ASC"
    query = f"{_BASE_SELECT}{where} ORDER BY {column} {direction}, t.id {direction}"
    if limit is not None:
        limit = int(limit)
        offset = int(offset or 0)
        if limit < 0 or offset < 0:
            raise ValueError(t("error.limit_negative"))
        query += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    return fetch_all(query, params)


def summarize_transactions(start_date=None, end_date=None, kind=None,
                           category_id=None, search=None, account_id=None):
    """Quantidade e totais do conjunto filtrado (não só da página atual)."""
    where, params = _build_filters(
        start_date, end_date, kind, category_id, search, account_id
    )
    row = fetch_one(
        "SELECT COUNT(*) AS count, "
        "COALESCE(SUM(CASE WHEN t.kind = 'income' THEN t.amount END), 0) AS income, "
        "COALESCE(SUM(CASE WHEN t.kind = 'expense' THEN t.amount END), 0) AS expense "
        f"FROM transactions t{where}",
        params,
    )
    return {
        "count": row["count"],
        "income": row["income"],
        "expense": row["expense"],
        "net": row["income"] - row["expense"],
    }


def count_transactions():
    return fetch_one("SELECT COUNT(*) AS n FROM transactions")["n"]


def get_totals(start_date=None, end_date=None, account_id=None):
    """Receitas, despesas e resultado do período (transferências não entram)."""
    summary = summarize_transactions(
        start_date=start_date, end_date=end_date, account_id=account_id
    )
    return {
        "income": summary["income"],
        "expense": summary["expense"],
        "net": summary["net"],
    }


def duplicate_transaction_defaults(transaction_id):
    """Dados para pré-preencher uma nova movimentação a partir de outra."""
    row = get_transaction(transaction_id)
    if not row:
        raise ValueError(t("error.transaction_not_found"))
    data = dict(row)
    data["transaction_date"] = date.today().isoformat()
    return data
