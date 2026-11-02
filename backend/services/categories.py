"""Categorias de receitas e despesas."""

import sqlite3

from backend.utils.i18n import t
from backend.config import FALLBACK_CATEGORY
from database import fetch_all, fetch_one, get_connection
from backend.utils.validators import validate_kind, validate_name


def get_categories(kind=None):
    if kind:
        return fetch_all(
            "SELECT * FROM categories WHERE kind = ? ORDER BY name COLLATE NOCASE",
            (kind,),
        )
    return fetch_all(
        "SELECT * FROM categories ORDER BY kind, name COLLATE NOCASE"
    )


def get_category(category_id):
    return fetch_one("SELECT * FROM categories WHERE id = ?", (category_id,))


def _name_taken(conn, name, kind, ignore_id=None):
    row = conn.execute(
        "SELECT id FROM categories "
        "WHERE LOWER(name) = LOWER(?) AND kind = ? AND id IS NOT ?",
        (name, kind, ignore_id),
    ).fetchone()
    return row is not None


def add_category(name, kind):
    name = validate_name(name, t("validation.label_category_name"))
    validate_kind(kind)
    with get_connection() as conn:
        if _name_taken(conn, name, kind):
            raise ValueError(t("error.category_name_taken"))
        try:
            return conn.execute(
                "INSERT INTO categories (name, kind) VALUES (?, ?)",
                (name, kind),
            ).lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError(t("error.category_name_taken")) from exc


def rename_category(category_id, name):
    name = validate_name(name, t("validation.label_category_name"))
    with get_connection() as conn:
        row = conn.execute(
            "SELECT kind FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if not row:
            raise ValueError(t("error.category_not_found"))
        if _name_taken(conn, name, row["kind"], ignore_id=category_id):
            raise ValueError(t("error.category_name_taken"))
        conn.execute(
            "UPDATE categories SET name = ? WHERE id = ?", (name, category_id)
        )


def category_usage(category_id):
    """Quantos registros usam a categoria."""
    with get_connection() as conn:
        def count(table):
            return conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE category_id = ?",
                (category_id,),
            ).fetchone()[0]

        return {
            "transactions": count("transactions"),
            "recurring": count("recurring"),
            "budgets": count("budgets"),
        }


def delete_category(category_id, move_to=None):
    """Exclui a categoria. Se houver lançamentos, é preciso informar para
    qual categoria do mesmo tipo eles serão movidos."""
    with get_connection() as conn:
        category = conn.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if not category:
            raise ValueError(t("error.category_not_found"))

        in_use = conn.execute(
            "SELECT (SELECT COUNT(*) FROM transactions WHERE category_id = ?) "
            "+ (SELECT COUNT(*) FROM recurring WHERE category_id = ?) "
            "+ (SELECT COUNT(*) FROM budgets WHERE category_id = ?)",
            (category_id, category_id, category_id),
        ).fetchone()[0]

        if in_use:
            if move_to is None:
                raise ValueError(t("error.category_in_use", count=in_use))
            target = conn.execute(
                "SELECT * FROM categories WHERE id = ?", (move_to,)
            ).fetchone()
            if not target or target["id"] == category_id:
                raise ValueError(t("error.category_target_invalid"))
            if target["kind"] != category["kind"]:
                raise ValueError(t("error.category_target_kind"))
            budget_conflict = conn.execute(
                "SELECT 1 FROM budgets source "
                "JOIN budgets target ON target.month = source.month "
                "WHERE source.category_id = ? AND target.category_id = ? "
                "LIMIT 1",
                (category_id, move_to),
            ).fetchone()
            if budget_conflict:
                raise ValueError(t("error.category_budget_conflict"))
            conn.execute(
                "UPDATE transactions SET category_id = ? WHERE category_id = ?",
                (move_to, category_id),
            )
            conn.execute(
                "UPDATE recurring SET category_id = ? WHERE category_id = ?",
                (move_to, category_id),
            )
            conn.execute(
                "UPDATE budgets SET category_id = ? WHERE category_id = ?",
                (move_to, category_id),
            )

        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def ensure_fallback_category(conn, kind):
    """Id da categoria 'Outras receitas/despesas'; cria se não existir."""
    name = FALLBACK_CATEGORY[kind]
    row = conn.execute(
        "SELECT id FROM categories WHERE LOWER(name) = LOWER(?) AND kind = ?",
        (name, kind),
    ).fetchone()
    if row:
        return row["id"]
    return conn.execute(
        "INSERT INTO categories (name, kind) VALUES (?, ?)", (name, kind)
    ).lastrowid
