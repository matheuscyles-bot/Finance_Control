"""Painel inicial."""

import tkinter as tk

from backend.services import reports
from frontend.charts import BarChart, Donut, ProgressBar, group_categories
from frontend.pages.base import MonthBar, Page, change_note, kpi_card
from frontend.theme import c, font
from frontend.widgets import Button, Card, EmptyState, ScrollFrame, label, separator
from backend.utils import formatters
from backend.utils.formatters import money


class DashboardPage(Page):
    title = "Painel"

    def build(self):
        top = tk.Frame(self, bg=c("bg"))
        top.pack(fill="x", padx=32, pady=(0, 12))
        self.monthbar = MonthBar(top, self.refresh)
        self.monthbar.pack(side="left")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.content = tk.Frame(self.scroll.inner, bg=c("bg"))
        self.content.pack(fill="both", expand=True, padx=32, pady=(0, 28))

    def header_actions(self, parent):
        return [Button(parent, "Nova movimentação", lambda: self.app.new_transaction(), "primary", icon="plus")]

    def refresh(self):
        super().refresh()
        for w in self.content.winfo_children():
            w.destroy()
        month = self.monthbar.month
        data = reports.dashboard_data(month)
        s = data["summary"]
        content = self.content
        for i in range(4):
            content.grid_columnconfigure(i, weight=1, uniform="k")

        inc_note, inc_col = change_note(s["income_change"], True)
        exp_note, exp_col = change_note(s["expense_change"], False)
        net_color = "income" if s["net"] >= 0 else "expense"
        saving = ("Taxa de poupança " + f"{s['savings_rate'] * 100:.0f}%".replace(".", ",")
                  if s["savings_rate"] is not None else "sem receitas no mês")
        cards = [
            kpi_card(content, "SALDO TOTAL (HOJE)", money(data["total_balance"]),
                     "text" if data["total_balance"] >= 0 else "expense",
                     f"{len(data['accounts'])} conta(s)"),
            kpi_card(content, "RECEITAS DO MÊS", money(s["income"]), "income", inc_note, inc_col),
            kpi_card(content, "DESPESAS DO MÊS", money(s["expense"]), "expense", exp_note, exp_col),
            kpi_card(content, "RESULTADO DO MÊS", money(s["net"], signed=True), net_color, saving),
        ]
        for i, card in enumerate(cards):
            card.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else 7, 0 if i == 3 else 7), pady=(0, 16))

        if self.app.is_empty():
            empty = Card(content, 0, 0)
            empty.grid(row=1, column=0, columnspan=4, sticky="nsew", ipady=60)
            EmptyState(empty.body, "wallet", "Bem-vindo ao Finance Control",
                       "Registre sua primeira receita ou despesa para ver o painel ganhar vida.",
                       "Nova movimentação", self.app.new_transaction).pack(fill="both", expand=True)
            return

        # gráfico de barras
        bars = Card(content)
        bars.grid(row=1, column=0, columnspan=2, sticky="nsew",
                  padx=(0, 7), pady=(0, 16))
        head = tk.Frame(bars.body, bg=c("surface"))
        head.pack(fill="x")
        label(head, "Receitas x despesas (6 meses)", 13, "bold").pack(side="left")
        for text, color in (("Despesas", "expense"), ("Receitas", "income")):
            label(head, "● " + text, 10, color=color).pack(side="right", padx=(8, 0))
        chart = BarChart(bars.body)
        chart.pack(fill="both", expand=True, pady=(8, 0))
        chart.set_data(data["series"])

        # categorias
        cat = Card(content)
        cat.grid(row=1, column=2, columnspan=2, sticky="nsew",
                 padx=(7, 0), pady=(0, 16))
        label(cat.body, "Despesas por categoria", 13, "bold").pack(fill="x")
        if not data["categories"]:
            label(cat.body, "Nenhuma despesa neste mês.", 11, color="muted").pack(fill="x", pady=30)
        else:
            row = tk.Frame(cat.body, bg=c("surface"))
            row.pack(fill="x", pady=(8, 0))
            items = group_categories(data["categories"])
            donut = Donut(row, 170)
            donut.pack(side="left")
            donut.set_data(items, "Total", formatters.money_compact(s["expense"]))
            legend = tk.Frame(row, bg=c("surface"))
            legend.pack(side="left", fill="x", expand=True, padx=(14, 0))
            for i, (name, value) in enumerate(items):
                line = tk.Frame(legend, bg=c("surface"))
                line.pack(fill="x", pady=2)
                tk.Label(line, text="●", fg=c("chart")[i % len(c("chart"))], bg=c("surface"),
                         font=font(11)).pack(side="left")
                label(line, " " + name, 10).pack(side="left")
                label(line, money(value), 10, "bold", anchor="e").pack(side="right")

        # orçamentos
        bud = Card(content)
        bud.grid(row=2, column=2, columnspan=2, sticky="nsew",
                 padx=(7, 0), pady=(0, 16))
        head = tk.Frame(bud.body, bg=c("surface"))
        head.pack(fill="x")
        label(head, "Orçamentos do mês", 13, "bold").pack(side="left")
        link = tk.Label(head, text="Ver todos", fg=c("primary"), bg=c("surface"), font=font(10, "bold"), cursor="hand2")
        link.pack(side="right")
        link.bind("<Button-1>", lambda e: self.app.navigate("budgets"))
        if not data["budgets"]:
            label(bud.body, "Defina limites por categoria para acompanhar seus gastos.",
                  11, color="muted").pack(fill="x", pady=20)
        for r in data["budgets"][:4]:
            ratio = r["spent"] / r["budget"]
            line = tk.Frame(bud.body, bg=c("surface"))
            line.pack(fill="x", pady=(10, 0))
            label(line, r["category_name"], 11).pack(side="left")
            label(line, f"{money(r['spent'])} de {money(r['budget'])}", 10,
                  color="expense" if ratio > 1 else "muted", anchor="e").pack(side="right")
            bar = ProgressBar(bud.body)
            bar.pack(fill="x", pady=(4, 0))
            bar.set(ratio, c("expense") if ratio > 1 else c("warning") if ratio > 0.8 else c("primary"))

        # saldos das contas
        acc = Card(content)
        acc.grid(row=2, column=0, columnspan=2, sticky="nsew",
                 padx=(0, 7), pady=(0, 16))
        head = tk.Frame(acc.body, bg=c("surface"))
        head.pack(fill="x", pady=(0, 6))
        label(head, "Contas", 13, "bold").pack(side="left")
        link = tk.Label(head, text="Ver contas", fg=c("primary"), bg=c("surface"),
                        font=font(10, "bold"), cursor="hand2")
        link.pack(side="right")
        link.bind("<Button-1>", lambda e: self.app.navigate("accounts"))
        for i, account in enumerate(data["accounts"]):
            line = tk.Frame(acc.body, bg=c("surface"))
            line.pack(fill="x", pady=(8, 0))
            details = tk.Frame(line, bg=c("surface"))
            details.pack(side="left", fill="x", expand=True)
            label(details, account["name"], 11, "bold").pack(fill="x")
            note = "Saldo atual"
            if account["projected_balance"] != account["balance"]:
                note = f"Previsto {money(account['projected_balance'])}"
            label(details, note, 9, color="muted").pack(fill="x", pady=(2, 0))
            label(line, money(account["balance"]), 12, "bold",
                  "income" if account["balance"] >= 0 else "expense",
                  anchor="e").pack(side="right", padx=(12, 0))
            if i < len(data["accounts"]) - 1:
                separator(acc.body).pack(fill="x", pady=(8, 0))

        # recentes
        rec = Card(content)
        rec.grid(row=3, column=0, columnspan=4, sticky="nsew",
                 pady=(0, 14))
        head = tk.Frame(rec.body, bg=c("surface"))
        head.pack(fill="x")
        label(head, "Últimas movimentações", 13, "bold").pack(side="left")
        link = tk.Label(head, text="Ver todas", fg=c("primary"), bg=c("surface"), font=font(10, "bold"), cursor="hand2")
        link.pack(side="right")
        link.bind("<Button-1>", lambda e: self.app.navigate("transactions"))
        for i, r in enumerate(data["recent"][:6]):
            line = tk.Frame(rec.body, bg=c("surface"))
            line.pack(fill="x", pady=(10, 0))
            left = tk.Frame(line, bg=c("surface"))
            left.pack(side="left")
            from backend.services.transactions import describe
            label(left, describe(r), 11).pack(fill="x")
            label(left, f"{formatters.format_date_short(r['transaction_date'])} · {r['category_name'] or 'Sem categoria'}",
                  9, color="muted").pack(fill="x")
            income = r["kind"] == "income"
            label(line, money(r["amount"], signed=True) if income else "-" + money(r["amount"]), 11, "bold",
                  "income" if income else "expense", anchor="e").pack(side="right")
            if i < min(len(data["recent"]), 6) - 1:
                separator(rec.body).pack(fill="x", pady=(8, 0))
