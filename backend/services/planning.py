"""Leituras para as telas de planejamento (só consulta; nada é gravado).

- Ocorrências futuras das recorrências (projeção a partir de ``next_date``).
- Quadro de vencimentos: a pagar, vencendo, pago e recebido.
- Última movimentação de cada conta, maiores lançamentos do mês,
  orçamento total por mês e gastos por categoria mês a mês.

Transferências nunca contam como receita ou despesa.
"""

from datetime import date, datetime, timedelta

from backend.utils.i18n import t

from database import fetch_all
from backend.services import recurring as recurring_service
from backend.services import transactions as tx
from backend.utils.formatters import month_range, shift_month
from backend.utils.validators import validate_date, validate_month

DUE_SOON_DAYS = 7
HORIZON_DAYS = 45
MAX_OCCURRENCES = 400


def _date(iso):
    return datetime.strptime(validate_date(iso), "%Y-%m-%d").date()


def _today(today):
    return _date(today) if today else date.today()


def projected_recurring(start_date, end_date, kind=None, account_id=None):
    """Lançamentos que as recorrências ativas ainda vão criar entre as datas
    (inclusive). Ocorrências já criadas não entram: a projeção começa em
    ``next_date``, que é sempre a próxima a ser gerada."""
    start, end = _date(start_date), _date(end_date)
    items = []
    for rule in recurring_service.list_recurring():
        if not rule["active"]:
            continue
        if kind and rule["kind"] != kind:
            continue
        if account_id and rule["account_id"] != account_id:
            continue
        current = datetime.strptime(rule["next_date"], "%Y-%m-%d").date()
        stop = datetime.strptime(rule["end_date"], "%Y-%m-%d").date() if rule["end_date"] else None
        count = 0
        while current <= end and count < MAX_OCCURRENCES:
            if stop and current > stop:
                break
            if current >= start:
                items.append({
                    "source": "recurring", "id": None, "recurring_id": rule["id"],
                    "description": rule["description"], "amount": rule["amount"],
                    "kind": rule["kind"], "date": current.isoformat(),
                    "category_name": rule["category_name"], "account_name": rule["account_name"],
                    "account_id": rule["account_id"], "frequency": rule["frequency"],
                    "installment_no": None, "installment_total": None,
                })
            current = recurring_service.next_occurrence(current, rule["frequency"], rule["anchor_day"])
            count += 1
    items.sort(key=lambda r: (r["date"], r["description"].lower()))
    return items


def _from_transaction(row):
    return {
        "source": "transaction", "id": row["id"], "recurring_id": row["recurring_id"],
        "description": row["description"], "amount": row["amount"], "kind": row["kind"],
        "date": row["transaction_date"], "category_name": row["category_name"],
        "account_name": row["account_name"], "account_id": row["account_id"],
        "frequency": None, "installment_no": row["installment_no"],
        "installment_total": row["installment_total"],
    }


def collapse_recurring(items):
    """Uma linha por recorrência: a ocorrência mais próxima, com
    ``repeat_count`` = ocorrências escondidas. Transações passam sem mudança.
    Não altera os itens recebidos."""
    out, first_of = [], {}
    for item in sorted(items, key=lambda r: (r["date"], r["description"].lower())):
        if item["source"] != "recurring":
            out.append(item)
        elif item["recurring_id"] in first_of:
            first_of[item["recurring_id"]]["repeat_count"] += 1
        else:
            first_of[item["recurring_id"]] = dict(item, repeat_count=0)
            out.append(first_of[item["recurring_id"]])
    return out


def scheduled_items(start_date, end_date, kind=None, account_id=None, include_recurring=True):
    """Lançamentos já cadastrados no período + projeção das recorrências."""
    rows = tx.list_transactions(start_date=start_date, end_date=end_date, kind=kind,
                                account_id=account_id, order_by="date", descending=False)
    items = [_from_transaction(r) for r in rows]
    if include_recurring:
        items += projected_recurring(start_date, end_date, kind, account_id)
    items.sort(key=lambda r: (r["date"], r["description"].lower()))
    return items


def bills_board(today=None, horizon_days=HORIZON_DAYS, include_recurring=True, account_id=None):
    """Colunas do quadro de vencimentos.

    - to_pay: despesas previstas depois dos próximos 7 dias (até o horizonte);
    - due_soon: despesas previstas nos próximos 7 dias;
    - paid: despesas do mês atual com data até hoje;
    - received: receitas do mês atual com data até hoje.
    """
    day = _today(today)
    first = day.replace(day=1).isoformat()
    soon_end = day + timedelta(days=DUE_SOON_DAYS)
    horizon = day + timedelta(days=max(horizon_days, DUE_SOON_DAYS))
    future = scheduled_items((day + timedelta(days=1)).isoformat(), horizon.isoformat(),
                             "expense", account_id, include_recurring)
    past = tx.list_transactions(start_date=first, end_date=day.isoformat(),
                                account_id=account_id, order_by="date", descending=True)
    past = [_from_transaction(r) for r in past]
    return {
        "to_pay": [r for r in future if r["date"] > soon_end.isoformat()],
        "due_soon": [r for r in future if r["date"] <= soon_end.isoformat()],
        "paid": [r for r in past if r["kind"] == "expense"],
        "received": [r for r in past if r["kind"] == "income"],
        "today": day.isoformat(),
        "horizon": horizon.isoformat(),
    }


def upcoming(days=DUE_SOON_DAYS, today=None):
    """Próximos lançamentos (despesas e receitas) para os avisos do sino."""
    day = _today(today)
    return scheduled_items((day + timedelta(days=1)).isoformat(),
                           (day + timedelta(days=days)).isoformat())


def account_activity(today=None):
    """{id da conta: data ISO da última movimentação ou transferência até hoje}."""
    today = today or date.today().isoformat()
    rows = fetch_all(
        """
        SELECT account_id, MAX(day) AS last FROM (
            SELECT account_id, MAX(transaction_date) AS day FROM transactions
            WHERE transaction_date <= :today GROUP BY account_id
            UNION ALL
            SELECT from_account_id, MAX(transfer_date) FROM transfers
            WHERE transfer_date <= :today GROUP BY from_account_id
            UNION ALL
            SELECT to_account_id, MAX(transfer_date) FROM transfers
            WHERE transfer_date <= :today GROUP BY to_account_id
        ) GROUP BY account_id
        """,
        {"today": today},
    )
    return {r["account_id"]: r["last"] for r in rows if r["last"]}


def top_transactions(month, limit=4, kind=None):
    """Maiores lançamentos do mês (por valor)."""
    start, end = month_range(validate_month(month))
    params = [start, end]
    clause = ""
    if kind in ("income", "expense"):
        clause = " AND t.kind = ?"
        params.append(kind)
    params.append(int(limit))
    return fetch_all(
        f"""
        SELECT t.*, c.name AS category_name, a.name AS account_name
        FROM transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        JOIN accounts a ON a.id = t.account_id
        WHERE t.transaction_date BETWEEN ? AND ?{clause}
        ORDER BY t.amount DESC, t.transaction_date DESC, t.id DESC LIMIT ?
        """,
        params,
    )


def budget_totals(first_month, months):
    """{mês: soma dos orçamentos do mês} para ``months`` meses seguidos."""
    first_month = validate_month(first_month)
    last = shift_month(first_month, months - 1)
    rows = fetch_all(
        "SELECT month, SUM(amount) AS total FROM budgets WHERE month BETWEEN ? AND ? GROUP BY month",
        (first_month, last),
    )
    found = {r["month"]: r["total"] for r in rows}
    return {shift_month(first_month, i): found.get(shift_month(first_month, i), 0)
            for i in range(months)}


def category_by_month(first_month, months, kind="expense", top=3, account_id=None):
    """Totais por categoria em cada mês. Devolve (meses, [(nome, [valores])]),
    com as ``top`` maiores categorias do período e o resto somado em ``None``
    (a tela chama de "Outras")."""
    first_month = validate_month(first_month)
    month_keys = [shift_month(first_month, i) for i in range(months)]
    start, end = month_range(month_keys[0])[0], month_range(month_keys[-1])[1]
    params = [kind, start, end]
    clause = ""
    if account_id:
        clause = " AND t.account_id = ?"
        params.append(account_id)
    rows = fetch_all(
        f"""
        SELECT substr(t.transaction_date, 1, 7) AS month,
               c.name AS category_name, SUM(t.amount) AS total
        FROM transactions t LEFT JOIN categories c ON c.id = t.category_id
        WHERE t.kind = ? AND t.transaction_date BETWEEN ? AND ?{clause}
        GROUP BY month, t.category_id
        """,
        params,
    )
    totals = {}
    for r in rows:
        name = r["category_name"] or t("common.uncategorized")
        totals[name] = totals.get(name, 0) + r["total"]
    ranked = sorted(totals, key=lambda name: (-totals[name], name.lower()))
    leaders = ranked[:top]
    index = {m: i for i, m in enumerate(month_keys)}
    series = {name: [0] * months for name in leaders}
    rest = [0] * months
    for r in rows:
        i = index.get(r["month"])
        if i is None:
            continue
        name = r["category_name"] or t("common.uncategorized")
        if name in series:
            series[name][i] += r["total"]
        else:
            rest[i] += r["total"]
    result = [(name, series[name]) for name in leaders]
    if any(rest):
        result.append((None, rest))
    return month_keys, result
