"""Importação e exportação de movimentações em CSV."""

import csv
import io
from collections import Counter
from pathlib import Path

from database import fetch_all, get_connection
from backend.services.categories import ensure_fallback_category
from backend.utils.formatters import parse_date
from backend.utils.money import minor_to_text, parse_amount
from backend.utils.text import normalize_text
from backend.utils.validators import validate_description, validate_notes

MAX_IMPORT_ROWS = 20000
MAX_FILE_BYTES = 10 * 1024 * 1024

_HEADERS = {
    "date": {"data", "date", "dt", "dia"},
    "description": {"descricao", "description", "historico", "memo", "detalhes"},
    "amount": {"valor", "amount", "quantia", "montante", "value"},
    "kind": {"tipo", "type", "kind", "natureza"},
    "category": {"categoria", "category"},
    "notes": {"observacoes", "observacao", "notes", "nota", "notas"},
    "account": {"conta", "account"},
}
_INCOME = {"receita", "income", "entrada", "credito", "credit", "c"}
_EXPENSE = {"despesa", "expense", "saida", "debito", "debit", "d"}


def _read_text(path):
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("O arquivo é grande demais (limite de 10 MB).")
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Não foi possível ler o arquivo (codificação desconhecida).")


def _delimiter(text):
    first = text.splitlines()[0] if text.strip() else ""
    counts = {d: first.count(d) for d in (";", ",", "\t")}
    best = max(counts, key=counts.get)
    return best if counts[best] else ";"


def _map_headers(header):
    mapping = {}
    for index, name in enumerate(header):
        key = normalize_text(name).strip()
        for field, names in _HEADERS.items():
            if key in names and field not in mapping:
                mapping[field] = index
    return mapping


def _parse_signed(text):
    text = (text or "").strip()
    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    cleaned = text.strip("()").lstrip("+-").strip()
    return parse_amount(cleaned), negative


def _key(date_iso, kind, amount, description, account_id):
    return (date_iso, kind, amount, normalize_text(description), account_id)


def prepare_import(path, account_id):
    """Lê o CSV e valida linha a linha, sem gravar nada.

    Devolve ``{"rows": [...], "errors": [(linha, mensagem)], "duplicates": n}``.
    Cada linha traz ``duplicate=True`` quando já existe movimentação igual."""
    text = _read_text(path)
    if not text.strip():
        raise ValueError("O arquivo está vazio.")
    reader = csv.reader(io.StringIO(text), delimiter=_delimiter(text))
    try:
        rows = list(reader)
    except csv.Error:
        raise ValueError(
            "O arquivo não parece um CSV válido (campo grande demais ou "
            "formato inesperado)."
        ) from None
    mapping = _map_headers(rows[0])
    missing = [f for f in ("date", "description", "amount") if f not in mapping]
    if missing:
        raise ValueError(
            "Não encontrei as colunas obrigatórias: Data, Descrição e Valor. "
            "A primeira linha do arquivo deve ter os nomes das colunas."
        )
    if len(rows) - 1 > MAX_IMPORT_ROWS:
        raise ValueError(f"O arquivo tem linhas demais (limite de {MAX_IMPORT_ROWS}).")

    parsed, errors = [], []
    for line_no, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue

        def cell(field):
            index = mapping.get(field)
            return row[index].strip() if index is not None and index < len(row) else ""

        try:
            date_iso = parse_date(cell("date"))
            description = validate_description(cell("description"))
            amount, negative = _parse_signed(cell("amount"))
            kind_text = normalize_text(cell("kind")).strip()
            if kind_text in _INCOME:
                kind = "income"
            elif kind_text in _EXPENSE:
                kind = "expense"
            elif kind_text:
                raise ValueError("Tipo desconhecido (use Receita ou Despesa).")
            else:
                kind = "expense" if negative else "income"
            notes = validate_notes(cell("notes"))
        except ValueError as exc:
            errors.append((line_no, str(exc)))
            continue
        parsed.append({
            "line": line_no, "date": date_iso, "description": description,
            "amount": amount, "kind": kind, "category": cell("category"),
            "notes": notes, "duplicate": False,
        })

    existing = Counter()
    for r in fetch_all(
        "SELECT transaction_date, kind, amount, description FROM transactions "
        "WHERE account_id = ?", (account_id,)
    ):
        existing[_key(r["transaction_date"], r["kind"], r["amount"],
                      r["description"], account_id)] += 1
    duplicates = 0
    for item in parsed:  # cada transação existente "cobre" uma linha do arquivo
        key = _key(item["date"], item["kind"], item["amount"],
                   item["description"], account_id)
        if existing[key] > 0:
            existing[key] -= 1
            item["duplicate"] = True
            duplicates += 1
    return {"rows": parsed, "errors": errors, "duplicates": duplicates}


def commit_import(rows, account_id, skip_duplicates=True):
    """Grava as linhas preparadas em uma única transação (tudo ou nada).
    Devolve ``{"imported", "skipped", "new_categories_fallback"}``."""
    imported = skipped = fallback_used = 0
    with get_connection() as conn:
        account = conn.execute(
            "SELECT archived FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if not account or account["archived"]:
            raise ValueError("Escolha uma conta ativa para importar.")
        by_name = {}
        for c in conn.execute("SELECT id, name, kind FROM categories"):
            by_name[(normalize_text(c["name"]), c["kind"])] = c["id"]
        for item in rows:
            if skip_duplicates and item["duplicate"]:
                skipped += 1
                continue
            category_id = by_name.get(
                (normalize_text(item["category"]), item["kind"])
            )
            if category_id is None:
                category_id = ensure_fallback_category(conn, item["kind"])
                fallback_used += 1
            conn.execute(
                "INSERT INTO transactions (description, amount, kind, "
                "category_id, account_id, transaction_date, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (item["description"], item["amount"], item["kind"],
                 category_id, account_id, item["date"], item["notes"]),
            )
            imported += 1
    return {"imported": imported, "skipped": skipped,
            "fallback_categories": fallback_used}


def _csv_safe(value):
    """Evita injeção de fórmulas ao abrir o CSV em planilhas."""
    value = value or ""
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


def export_csv(path, rows):
    """Exporta movimentações (linhas de ``list_transactions``) para CSV
    (separador ';', decimal ',', compatível com Excel/Numbers)."""
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(
            ["Data", "Tipo", "Descrição", "Categoria", "Conta", "Valor",
             "Observações"]
        )
        for r in rows:
            writer.writerow([
                r["transaction_date"],
                "Receita" if r["kind"] == "income" else "Despesa",
                _csv_safe(r["description"]),
                _csv_safe(r["category_name"] or ""),
                _csv_safe(r["account_name"]),
                minor_to_text(r["amount"]).replace(".", ","),
                _csv_safe(r["notes"]),
            ])
    return len(rows)
