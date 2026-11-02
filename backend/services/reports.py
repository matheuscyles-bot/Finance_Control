"""Relatórios e dados do painel. Transferências nunca entram aqui."""

from datetime import date, datetime, timedelta

from database import fetch_all, fetch_one
from backend.utils.i18n import t
from backend.services import accounts, budgets
from backend.utils.formatters import month_range, shift_month
from backend.utils.validators import validate_date, validate_month


def category_report(start_date, end_date, kind="expense", account_id=None):
    """Total por categoria no período, do maior para o menor, com a
    participação de cada uma. Inclui lançamentos sem categoria."""
    start_date = validate_date(start_date)
    end_date = validate_date(end_date)
    params = [kind, start_date, end_date]
    account_clause = ""
    if account_id:
        account_clause = " AND t.account_id = ?"
        params.append(account_id)
    rows = fetch_all(
        f"""
        SELECT t.category_id AS category_id,
               COALESCE(c.name, 'Sem categoria') AS category_name,
               SUM(t.amount) AS total, COUNT(*) AS count
        FROM transactions t LEFT JOIN categories c ON c.id = t.category_id
        WHERE t.kind = ? AND t.transaction_date BETWEEN ? AND ?{account_clause}
        GROUP BY t.category_id
        ORDER BY total DESC, category_name COLLATE NOCASE
        """,
        params,
    )
    grand = sum(r["total"] for r in rows)
    return [
        {
            "category_id": r["category_id"],
            "category_name": r["category_name"],
            "total": r["total"],
            "count": r["count"],
            "share": (r["total"] / grand) if grand else 0.0,
        }
        for r in rows
    ]


def monthly_series(end_month, months=6, account_id=None):
    """Receitas e despesas dos últimos ``months`` meses (inclui meses
    sem movimento com zero)."""
    end_month = validate_month(end_month)
    first = shift_month(end_month, -(months - 1))
    start = month_range(first)[0]
    end = month_range(end_month)[1]
    params = [start, end]
    account_clause = ""
    if account_id:
        account_clause = " AND account_id = ?"
        params.append(account_id)
    rows = fetch_all(
        f"""
        SELECT substr(transaction_date, 1, 7) AS month,
               COALESCE(SUM(CASE WHEN kind = 'income' THEN amount END), 0) AS income,
               COALESCE(SUM(CASE WHEN kind = 'expense' THEN amount END), 0) AS expense
        FROM transactions
        WHERE transaction_date BETWEEN ? AND ?{account_clause}
        GROUP BY substr(transaction_date, 1, 7)
        """,
        params,
    )
    found = {r["month"]: r for r in rows}
    series = []
    for i in range(months):
        key = shift_month(first, i)
        row = found.get(key)
        income = row["income"] if row else 0
        expense = row["expense"] if row else 0
        series.append(
            {"month": key, "income": income, "expense": expense,
             "net": income - expense}
        )
    return series


def _totals(start, end, account_id=None):
    params = [start, end]
    clause = ""
    if account_id:
        clause = " AND account_id = ?"
        params.append(account_id)
    row = fetch_one(
        f"""
        SELECT COALESCE(SUM(CASE WHEN kind = 'income' THEN amount END), 0) AS income,
               COALESCE(SUM(CASE WHEN kind = 'expense' THEN amount END), 0) AS expense,
               COUNT(*) AS count
        FROM transactions WHERE transaction_date BETWEEN ? AND ?{clause}
        """,
        params,
    )
    return {
        "income": row["income"],
        "expense": row["expense"],
        "net": row["income"] - row["expense"],
        "count": row["count"],
    }


def previous_period(start_date, end_date):
    """Período anterior com a mesma duração (para comparação). Se o período
    for um mês inteiro, devolve o mês anterior inteiro."""
    start = datetime.strptime(validate_date(start_date), "%Y-%m-%d").date()
    end = datetime.strptime(validate_date(end_date), "%Y-%m-%d").date()
    if start > end:
        raise ValueError(t("error.date_range_order"))
    month = start.strftime("%Y-%m")
    if month_range(month) == (start.isoformat(), end.isoformat()):
        return month_range(shift_month(month, -1))
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    return prev_start.isoformat(), prev_end.isoformat()


def _change(current, previous):
    """Variação percentual; None quando não há base de comparação."""
    if previous == 0:
        return None
    return (current - previous) / previous


def period_summary(start_date, end_date, account_id=None):
    """Totais do período e comparação com o período anterior."""
    start_date = validate_date(start_date)
    end_date = validate_date(end_date)
    current = _totals(start_date, end_date, account_id)
    prev_start, prev_end = previous_period(start_date, end_date)
    previous = _totals(prev_start, prev_end, account_id)
    days = (
        datetime.strptime(end_date, "%Y-%m-%d").date()
        - datetime.strptime(start_date, "%Y-%m-%d").date()
    ).days + 1
    savings_rate = (current["net"] / current["income"]) if current["income"] else None
    return {
        **current,
        "previous": previous,
        "previous_range": (prev_start, prev_end),
        "income_change": _change(current["income"], previous["income"]),
        "expense_change": _change(current["expense"], previous["expense"]),
        "savings_rate": savings_rate,
        "daily_expense": current["expense"] // days if days else 0,
    }


def daily_expenses(start_date, end_date, account_id=None):
    """Despesa por dia no período (dias sem gasto vêm como zero)."""
    start = datetime.strptime(validate_date(start_date), "%Y-%m-%d").date()
    end = datetime.strptime(validate_date(end_date), "%Y-%m-%d").date()
    params = [start.isoformat(), end.isoformat()]
    clause = ""
    if account_id:
        clause = " AND account_id = ?"
        params.append(account_id)
    rows = fetch_all(
        f"""
        SELECT transaction_date AS day, SUM(amount) AS total FROM transactions
        WHERE kind = 'expense' AND transaction_date BETWEEN ? AND ?{clause}
        GROUP BY transaction_date
        """,
        params,
    )
    found = {r["day"]: r["total"] for r in rows}
    result, day = [], start
    while day <= end:
        result.append((day.isoformat(), found.get(day.isoformat(), 0)))
        day += timedelta(days=1)
    return result


def dashboard_data(month, today=None):
    """Tudo o que o painel inicial mostra, calculado de uma vez."""
    month = validate_month(month)
    today = today or date.today().isoformat()
    start, end = month_range(month)
    summary = period_summary(start, end)
    recent = fetch_all(
        """
        SELECT t.*, c.name AS category_name, a.name AS account_name
        FROM transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        JOIN accounts a ON a.id = t.account_id
        ORDER BY t.transaction_date DESC, t.id DESC LIMIT 8
        """
    )
    upcoming = fetch_all(
        """
        SELECT r.*, c.name AS category_name FROM recurring r
        LEFT JOIN categories c ON c.id = r.category_id
        WHERE r.active = 1 ORDER BY r.next_date LIMIT 5
        """
    )
    return {
        "month": month,
        "total_balance": accounts.total_balance(today),
        "accounts": accounts.list_accounts(today=today),
        "summary": summary,
        "series": monthly_series(month, 6),
        "categories": category_report(start, end, "expense"),
        "budgets": budgets.list_budgets(month),
        "budget_summary": budgets.budget_summary(month),
        "recent": recent,
        "upcoming": upcoming,
    }
