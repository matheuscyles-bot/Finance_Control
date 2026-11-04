"""Lançamentos recorrentes (assinaturas, aluguel, salário...).

Cada regra guarda a próxima data. Ao abrir o app, ``run_due_recurring``
cria os lançamentos vencidos. Um índice único (regra + data) garante que
nunca haja duplicidade, mesmo se a rotina rodar duas vezes.
"""

from datetime import date, datetime, timedelta

from backend.utils.i18n import t
from backend.config import FREQUENCIES
from database import fetch_all, fetch_one, get_connection
from backend.utils.formatters import add_months
from backend.utils.validators import (
    validate_amount,
    validate_date,
    validate_description,
    validate_kind,
    validate_notes,
)

MAX_CATCH_UP = 120  # limite de lançamentos gerados por regra em uma execução


def _parse(iso):
    return datetime.strptime(iso, "%Y-%m-%d").date()


def next_occurrence(current, frequency, anchor_day):
    """Data seguinte à ``current`` (date) conforme a frequência."""
    if frequency == "weekly":
        return current + timedelta(days=7)
    if frequency == "monthly":
        return add_months(current, 1, anchor_day=anchor_day)
    if frequency == "yearly":
        return add_months(current, 12, anchor_day=anchor_day)
    raise ValueError(t("error.frequency_invalid"))


def _validate_frequency(frequency):
    if frequency not in FREQUENCIES:
        raise ValueError(t("error.frequency_invalid"))
    return frequency


def _check(conn, kind, category_id, account_id):
    category = conn.execute(
        "SELECT kind FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    if not category or category["kind"] != kind:
        raise ValueError(t("error.category_kind_invalid"))
    account = conn.execute(
        "SELECT archived FROM accounts WHERE id = ?", (account_id,)
    ).fetchone()
    if not account:
        raise ValueError(t("error.account_not_found"))
    if account["archived"]:
        raise ValueError(t("error.account_archived"))


def _validate_end(end_date, start_iso):
    if not end_date:
        return None
    end = validate_date(end_date)
    if end < start_iso:
        raise ValueError(t("error.end_before_start"))
    return end


def add_recurring(description, amount, kind, category_id, account_id,
                  frequency, start_date, end_date=None, notes=""):
    description = validate_description(description)
    amount = validate_amount(amount)
    validate_kind(kind)
    frequency = _validate_frequency(frequency)
    start_date = validate_date(start_date)
    end_date = _validate_end(end_date, start_date)
    notes = validate_notes(notes)
    with get_connection() as conn:
        _check(conn, kind, category_id, account_id)
        return conn.execute(
            "INSERT INTO recurring (description, amount, kind, category_id, "
            "account_id, frequency, anchor_day, next_date, end_date, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (description, amount, kind, category_id, account_id, frequency,
             _parse(start_date).day, start_date, end_date, notes),
        ).lastrowid


def update_recurring(recurring_id, description, amount, kind, category_id,
                     account_id, frequency, next_date, end_date=None, notes=""):
    description = validate_description(description)
    amount = validate_amount(amount)
    validate_kind(kind)
    frequency = _validate_frequency(frequency)
    next_date = validate_date(next_date)
    end_date = _validate_end(end_date, next_date)
    notes = validate_notes(notes)
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM recurring WHERE id = ?", (recurring_id,)
        ).fetchone():
            raise ValueError(t("error.recurring_not_found"))
        _check(conn, kind, category_id, account_id)
        conn.execute(
            "UPDATE recurring SET description = ?, amount = ?, kind = ?, "
            "category_id = ?, account_id = ?, frequency = ?, anchor_day = ?, "
            "next_date = ?, end_date = ?, notes = ? WHERE id = ?",
            (description, amount, kind, category_id, account_id, frequency,
             _parse(next_date).day, next_date, end_date, notes, recurring_id),
        )


def set_active(recurring_id, active):
    with get_connection() as conn:
        if active:
            row = conn.execute(
                "SELECT a.archived FROM recurring r JOIN accounts a "
                "ON a.id = r.account_id WHERE r.id = ?", (recurring_id,)
            ).fetchone()
            if row and row["archived"]:
                raise ValueError(t("error.recurring_account_archived"))
        conn.execute(
            "UPDATE recurring SET active = ? WHERE id = ?",
            (1 if active else 0, recurring_id),
        )


def delete_recurring(recurring_id):
    """Exclui a regra. Lançamentos já gerados são mantidos."""
    with get_connection() as conn:
        conn.execute("DELETE FROM recurring WHERE id = ?", (recurring_id,))


def get_recurring(recurring_id):
    return fetch_one(
        "SELECT r.*, c.name AS category_name, a.name AS account_name "
        "FROM recurring r LEFT JOIN categories c ON c.id = r.category_id "
        "JOIN accounts a ON a.id = r.account_id WHERE r.id = ?",
        (recurring_id,),
    )


def list_recurring():
    return fetch_all(
        "SELECT r.*, c.name AS category_name, a.name AS account_name "
        "FROM recurring r LEFT JOIN categories c ON c.id = r.category_id "
        "JOIN accounts a ON a.id = r.account_id "
        "ORDER BY r.active DESC, r.next_date, r.description COLLATE NOCASE"
    )


def run_due_recurring(today=None):
    """Cria os lançamentos vencidos (até hoje). Devolve a quantidade criada."""
    today_date = _parse(today) if today else date.today()
    created = 0
    with get_connection() as conn:
        rules = conn.execute(
            "SELECT * FROM recurring WHERE active = 1 AND next_date <= ?",
            (today_date.isoformat(),),
        ).fetchall()
        for rule in rules:
            current = _parse(rule["next_date"])
            end = _parse(rule["end_date"]) if rule["end_date"] else None
            generated = 0
            while current <= today_date and generated < MAX_CATCH_UP:
                if end and current > end:
                    break
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO transactions (description, amount, "
                    "kind, category_id, account_id, transaction_date, notes, "
                    "recurring_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (rule["description"], rule["amount"], rule["kind"],
                     rule["category_id"], rule["account_id"],
                     current.isoformat(), rule["notes"], rule["id"]),
                )
                created += cursor.rowcount
                generated += 1
                current = next_occurrence(
                    current, rule["frequency"], rule["anchor_day"]
                )
            finished = bool(end and current > end)
            conn.execute(
                "UPDATE recurring SET next_date = ?, active = ? WHERE id = ?",
                (current.isoformat(), 0 if finished else 1, rule["id"]),
            )
    return created
