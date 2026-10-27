"""Orçamentos mensais por categoria de despesa."""

from database import fetch_all, fetch_one, get_connection
from backend.utils.formatters import month_range, shift_month
from backend.utils.validators import validate_amount, validate_month


def save_budget(month, category_id, amount):
    """Define (ou altera) o orçamento de uma categoria de despesa no mês."""
    month = validate_month(month)
    amount = validate_amount(amount)
    with get_connection() as conn:
        category = conn.execute(
            "SELECT kind FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if not category:
            raise ValueError("Categoria não encontrada.")
        if category["kind"] != "expense":
            raise ValueError("Orçamentos só podem ser definidos para despesas.")
        conn.execute(
            """
            INSERT INTO budgets (category_id, month, amount) VALUES (?, ?, ?)
            ON CONFLICT(category_id, month) DO UPDATE SET amount = excluded.amount
            """,
            (category_id, month, amount),
        )


def delete_budget(month, category_id):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM budgets WHERE month = ? AND category_id = ?",
            (validate_month(month), category_id),
        )


def list_budgets(month):
    """Orçamentos do mês com o valor já gasto (despesas do mês na categoria)."""
    month = validate_month(month)
    start, end = month_range(month)
    return fetch_all(
        """
        SELECT b.category_id, c.name AS category_name, b.amount AS budget,
               COALESCE((SELECT SUM(t.amount) FROM transactions t
                         WHERE t.category_id = b.category_id
                           AND t.kind = 'expense'
                           AND t.transaction_date BETWEEN ? AND ?), 0) AS spent
        FROM budgets b JOIN categories c ON c.id = b.category_id
        WHERE b.month = ?
        ORDER BY spent * 1.0 / b.amount DESC, c.name COLLATE NOCASE
        """,
        (start, end, month),
    )


def budget_summary(month):
    rows = list_budgets(month)
    budget = sum(r["budget"] for r in rows)
    spent = sum(r["spent"] for r in rows)
    return {
        "budget": budget,
        "spent": spent,
        "remaining": budget - spent,
        "over": sum(1 for r in rows if r["spent"] > r["budget"]),
        "count": len(rows),
    }


def copy_budgets(from_month, to_month):
    """Copia os orçamentos de um mês para outro, sem sobrescrever os
    que já existem. Devolve quantos foram copiados."""
    from_month = validate_month(from_month)
    to_month = validate_month(to_month)
    if from_month == to_month:
        raise ValueError("Escolha meses diferentes.")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO budgets (category_id, month, amount)
            SELECT category_id, ?, amount FROM budgets WHERE month = ?
            """,
            (to_month, from_month),
        )
        return cursor.rowcount


def copy_from_previous(month):
    return copy_budgets(shift_month(validate_month(month), -1), month)


def has_budgets(month):
    return fetch_one(
        "SELECT 1 FROM budgets WHERE month = ?", (validate_month(month),)
    ) is not None
