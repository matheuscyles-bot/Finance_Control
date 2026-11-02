"""Visão geral: KPIs do mês, despesas x orçamento, maiores lançamentos,
meta do mês, composição por categoria, próximos vencimentos e recentes."""

import tkinter as tk
from datetime import date, timedelta

from backend.services import budgets, planning, reports, transactions as tx
from frontend import motion
from frontend.charts import AreaChart, Gauge, MixBar, group_categories
from frontend.pages.base import Page, change_badge, kpi, money_fmt, percent_fmt
from frontend.theme import c, font, mix
from frontend.ui import Avatar, AvatarStack, CircleButton, MonthSwitcher, Panel, popup_menu
from frontend.widgets import Button, Card, EmptyState, ScrollFrame, Segmented, label
from backend.utils import formatters
from backend.utils.formatters import money
from backend.utils.i18n import category_label, t

GUTTER = 16


def clip(text, limit):
    text = str(text)
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def count_label(widget, value, fmt):
    """Conta o número do label até o valor final (~0,8 s)."""
    motion.count_up(widget, value, fmt, lambda s: widget.configure(text=s))


class DashboardPage(Page):
    title_key = "page.dashboard.title"

    def build(self):
        self.range = 12
        self._month = formatters.current_month()
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.content = tk.Frame(self.scroll.inner, bg=c("bg"))
        self.content.pack(fill="both", expand=True, pady=(2, 24))
        self.content.bind("<Configure>", lambda e: self._relayout())
        self._cells, self._cols = [], 0

    def header_actions(self, parent):
        self.month = MonthSwitcher(parent, self._month_changed, month=self._month)
        return [self.month,
                Button(parent, t("common.new_transaction"), lambda: self.app.new_transaction(),
                       "primary", icon="plus")]

    def _month_changed(self):
        self._month = self.month.month
        self.refresh()

    def _set_range(self, months):
        self.range = months
        self.refresh()

    def _goto(self, *keys):
        from frontend.app import NAV
        known = [k for k, *_ in NAV]
        self.app.navigate(next(k for k in keys if k in known))
    
    def on_show(self):
        # Sempre refaz ao abrir: os gráficos e contadores animam de novo.
        self.refresh()
    # ---------------------------------------------------------------- dados
    def refresh(self):
        super().refresh()
        for w in self.content.winfo_children():
            w.destroy()
        self._cells, self._cols = [], 0
        month = self._month
        data = reports.dashboard_data(month)
        s, bsum = data["summary"], data["budget_summary"]
        used = round(bsum["spent"] * 100 / bsum["budget"]) if bsum["budget"] else 0
        self.publish([
            kpi("trending-up", s["income"], t("dash.kpi_income"), money_fmt(),
                change_badge(s["income_change"], True)),
            kpi("wallet", data["total_balance"], t("dash.kpi_balance"), money_fmt()),
            kpi("target", used, t("dash.kpi_budget") if bsum["budget"] else t("dash.kpi_no_budget"),
                percent_fmt, (t("dash.kpi_over", count=bsum["over"]), "coral") if bsum["over"] else None),
        ])
        if self.app.is_empty():
            card = Card(self.content, 0, 0)
            EmptyState(card.body, "wallet", t("dashboard.welcome"), t("dashboard.first_transaction"),
                       t("common.new_transaction"), self.app.new_transaction).pack(fill="both", expand=True)
            self._cells = [(card, (0, 0, 3), (0, 0, 2))]
            self._relayout(force=True)
            return
        self._cells = [
            (self._spending(month), (0, 0, 2), (0, 0, 2)),
            (self._top(month, s), (0, 2, 1), (1, 0, 2)),
            (self._goal(month, bsum), (1, 0, 1), (2, 0, 1)),
            (self._mix(data, s), (1, 1, 1), (2, 1, 1)),
            (self._upcoming(), (1, 2, 1), (3, 0, 1)),
            (self._recent(data["recent"]), (2, 0, 2), (4, 0, 2)),
            (self._accounts(data["accounts"]), (2, 2, 1), (3, 1, 1)),
        ]
        self._relayout(force=True)

    def _relayout(self, force=False):
        width = self.content.winfo_width()
        cols = 3 if width >= 1120 or width < 50 else 2
        if cols == self._cols and not force:
            return
        self._cols = cols
        for i in range(3):
            self.content.grid_columnconfigure(i, weight=1 if i < cols else 0,
                                              uniform="dash" if i < cols else "")
        for widget, wide, narrow in self._cells:
            row, col, span = wide if cols == 3 else narrow
            widget.grid(row=row, column=col, columnspan=span, sticky="nsew",
                        padx=(0 if col == 0 else GUTTER / 2, 0 if col + span == cols else GUTTER / 2),
                        pady=(0, GUTTER))

    # ---------------------------------------------------------------- cards
    def _spending(self, month):
        n = self.range
        first = formatters.shift_month(month, -(n - 1))
        series = reports.monthly_series(month, n)
        targets = planning.budget_totals(first, n)
        values = [m["expense"] for m in series]
        with_budget = [m for m in series if targets[m["month"]]]
        within = sum(1 for m in with_budget if m["expense"] <= targets[m["month"]])
        target = targets[month] or next((targets[m["month"]] for m in reversed(series) if targets[m["month"]]), 0)

        p = Panel(self.content, t("dash.spending"))
        Segmented(p.actions, [(6, "6M"), (12, "12M")], n, self._set_range, bg=p.fill,
                  size=10, pad=(11, 4)).pack(side="left")
        p.add_action("expand", lambda: self.app.navigate("reports"), t("common.view_reports"))
        f = p.fill
        big = label(p.content, money(sum(values)), 30, "medium", bg=f)
        big.pack(fill="x")
        count_label(big, sum(values), money)
        note = t("dash.spent_in_months", months=n) + "  ·  " + (
            t("dash.within_budget", count=within, total=len(with_budget)) if with_budget
            else t("dash.no_budget_target"))
        label(p.content, note, 11, color="muted", bg=f).pack(fill="x", pady=(2, 0))
        legend = tk.Frame(p.content, bg=f)
        legend.pack(fill="x", pady=(12, 0))
        dot = tk.Canvas(legend, width=10, height=10, bg=f, highlightthickness=0)
        dot.create_oval(1, 1, 9, 9, fill=c("coral"), outline=c("coral"))
        dot.pack(side="left")
        label(legend, t("common.expense"), 11, "medium", color="muted", bg=f).pack(side="left", padx=(6, 18))
        if target:
            dash = tk.Canvas(legend, width=22, height=10, bg=f, highlightthickness=0)
            dash.create_line(1, 5, 21, 5, fill=mix(f, c("text"), 0.7), dash=(4, 3), width=1.4)
            dash.pack(side="left")
            label(legend, t("dash.legend_target"), 11, "medium", color="muted", bg=f).pack(side="left", padx=(6, 6))
            label(legend, formatters.money_compact(target), 10, "bold", bg=f).pack(side="left")
        chart = AreaChart(p.content, height=232, color=c("coral"), bg=f)
        chart.pack(fill="both", expand=True, pady=(10, 0))
        chart.set_data([formatters.month_label(m["month"], short=True) for m in series], values,
                       target or None)
        return p

    def _top(self, month, s):
        p = Panel(self.content, t("dash.top_title"), t("dash.top_subtitle"),
                  actions=[("plus", lambda: self.app.new_transaction(), t("common.new_transaction")),
                           ("expand", lambda: self.app.navigate("transactions"), t("common.view_all"))])
        rows = planning.top_transactions(month, 4)
        if not rows:
            label(p.content, t("dash.no_entries_month"), 11, color="muted", bg=p.fill).pack(fill="x", pady=24)
            return p
        grid = p.content
        for i in range(2):
            grid.grid_columnconfigure(i, weight=1, uniform="top")
        for i, r in enumerate(rows):
            mini = Card(grid, 16, 14, fill=c("surface_alt"), radius=18, hover=True)
            mini.grid(row=i // 2, column=i % 2, sticky="nsew",
                      padx=(0, 5) if i % 2 == 0 else (5, 0), pady=(0, 5) if i < 2 else (5, 0))
            b, f = mini.body, mini.fill
            head = tk.Frame(b, bg=f)
            head.pack(fill="x")
            label(head, formatters.format_date_short(r["transaction_date"]), 10, "semibold",
                  color="muted", bg=f).pack(side="left")
            more = CircleButton(head, "ellipsis", None, size=24, kind="plain", bg=f, icon_size=13)
            more.command = lambda r=r, m=more: popup_menu(m, self._row_menu(r))
            more.pack(side="right")
            category = category_label(r["category_name"]) if r["category_name"] else t("common.no_category")
            label(b, clip(tx.describe(r), 24), 12, "semibold", bg=f).pack(fill="x", pady=(6, 0))
            label(b, clip(f"{category} · {r['account_name']}", 30), 10, color="muted", bg=f).pack(fill="x")
            foot = tk.Frame(b, bg=f)
            foot.pack(fill="x", pady=(12, 0))
            left = tk.Frame(foot, bg=f)
            left.pack(side="left")
            income = r["kind"] == "income"
            label(left, money(r["amount"]), 16, "semibold", "income" if income else "text", bg=f).pack(anchor="w")
            base = s["income"] if income else s["expense"]
            share = round(r["amount"] * 100 / base) if base else 0
            label(left, t("dash.share_income" if income else "dash.share_expense", percent=share),
                  10, color="muted", bg=f).pack(anchor="w")
            AvatarStack(foot, [category, r["account_name"]], size=24, bg=f).pack(side="right", anchor="s")
        return p

    def _row_menu(self, row):
        fresh = lambda: tx.get_transaction(row["id"])  # noqa: E731
        return [(t("common.edit"), lambda: self.app.edit_transaction(fresh())),
                (t("common.duplicate"), lambda: self.app.duplicate_transaction(row)),
                None,
                (t("common.delete"), lambda: self.app.delete_transaction(fresh()))]

    def _goal(self, month, bsum):
        fill = c("olive")
        soft = mix(c("text"), fill, 0.3)
        p = Panel(self.content, t("dash.goal_title"), fill=fill,
                  actions=[("more", [(t("dash.view_budgets"), lambda: self.app.navigate("budgets")),
                                     (t("budgets.copy_previous"), lambda: self._copy_budgets(month)),
                                     (t("common.new_budget"), self.app.new_budget)])])
        gauge = Gauge(p.content, size=148, bg=fill)
        gauge.pack(pady=(0, 6))
        if not bsum["budget"]:
            gauge.set(0, "—", t("dash.goal_caption"))
            label(p.content, t("dash.goal_empty"), 11, color=soft, bg=fill, anchor="center",
                  justify="center", wraplength=220).pack(fill="x")
            Button(p.content, t("common.new_budget"), self.app.new_budget, "primary", icon="plus",
                   pad=(14, 7)).pack(pady=(10, 0))
            return p
        ratio = bsum["spent"] / bsum["budget"]
        gauge.set(ratio, f"{round(ratio * 100)}%", t("dash.goal_caption"))
        label(p.content, t("dash.goal_of", spent=money(bsum["spent"]), budget=money(bsum["budget"])),
              11, "medium", color=soft, bg=fill, anchor="center").pack(fill="x")
        return p

    def _copy_budgets(self, month):
        def run():
            n = budgets.copy_from_previous(month)
            self.app.after_change()
            self.app.toast(t("toast.budget_copied", count=n) if n else t("toast.budget_nothing_to_copy"),
                           "success")
        self.guarded(run)

    def _mix(self, data, s):
        p = Panel(self.content, t("dash.mix_title"),
                  actions=[("expand", lambda: self.app.navigate("reports"), t("common.view_reports"))])
        f = p.fill
        cats = data["categories"]
        big = label(p.content, money(s["expense"]), 24, "semibold", bg=f)
        big.pack(fill="x")
        count_label(big, s["expense"], money)
        label(p.content, t("dash.mix_caption", count=len(cats)), 11, color="muted", bg=f).pack(fill="x")
        palette = c("chart")
        groups = group_categories([{**r, "category_name": category_label(r["category_name"])} for r in cats],
                                  limit=4, other=t("common.other"))
        items = [(name, value, palette[i % len(palette)]) for i, (name, value) in enumerate(groups)]
        bar = MixBar(p.content, height=12, bg=f)
        bar.pack(fill="x", pady=(16, 12))
        bar.set_data(items)
        total = sum(v for _, v, _ in items) or 1
        for name, value, color in items:
            row = tk.Frame(p.content, bg=f)
            row.pack(fill="x", pady=3)
            dot = tk.Canvas(row, width=10, height=10, bg=f, highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill=color, outline=color)
            dot.pack(side="left")
            label(row, clip(name, 22), 10, bg=f).pack(side="left", padx=(8, 0))
            label(row, f"{round(value * 100 / total)}%", 10, "semibold", bg=f).pack(side="right")
        if not items:
            label(p.content, t("dashboard.no_expenses_month"), 11, color="muted", bg=f).pack(fill="x")
        return p

    def _upcoming(self):
        p = Panel(self.content, t("dash.upcoming_title"), t("dash.upcoming_subtitle"),
                  actions=[("expand", lambda: self._goto("schedule", "pipeline", "recurring"),
                            t("common.view_all"))])
        f = p.fill
        today = date.today()
        items = planning.scheduled_items((today + timedelta(days=1)).isoformat(),
                                         (today + timedelta(days=30)).isoformat())[:5]
        if not items:
            label(p.content, t("dash.upcoming_empty"), 11, color="muted", bg=f, wraplength=240,
                  justify="left").pack(fill="x", pady=8)
        for item in items:
            row = tk.Frame(p.content, bg=f)
            row.pack(fill="x", pady=5)
            day = tk.Canvas(row, width=40, height=40, bg=f, highlightthickness=0)
            day.create_oval(1, 1, 39, 39, fill=c("surface_alt"), outline=c("border"))
            day.create_text(20, 15, text=item["date"][8:10], font=font(11, "bold"), fill=c("text"))
            day.create_text(20, 28, text=t(f"format.months_abbr.{int(item['date'][5:7])}"),
                            font=font(8, "semibold"), fill=c("muted"))
            day.pack(side="left")
            mid = tk.Frame(row, bg=f)
            mid.pack(side="left", fill="x", expand=True, padx=(10, 0))
            label(mid, clip(item["description"], 22), 11, "medium", bg=f).pack(fill="x")
            label(mid, clip(category_label(item["category_name"]) if item["category_name"]
                            else t("common.no_category"), 24), 10, color="muted", bg=f).pack(fill="x")
            income = item["kind"] == "income"
            label(row, ("+" if income else "−") + money(item["amount"]), 10, "semibold",
                  "income" if income else "text", bg=f).pack(side="right")
        return p

    def _recent(self, rows):
        p = Panel(self.content, t("dash.recent_title"),
                  actions=[("expand", lambda: self.app.navigate("transactions"), t("common.view_all"))])
        f = p.fill
        for i, r in enumerate(rows[:5]):
            row = tk.Frame(p.content, bg=f)
            row.pack(fill="x", pady=(0 if i == 0 else 10, 0))
            category = category_label(r["category_name"]) if r["category_name"] else t("common.no_category")
            Avatar(row, category, size=34, bg=f).pack(side="left")
            mid = tk.Frame(row, bg=f)
            mid.pack(side="left", fill="x", expand=True, padx=(12, 0))
            label(mid, clip(tx.describe(r), 48), 11, "medium", bg=f).pack(fill="x")
            label(mid, f"{formatters.format_date_short(r['transaction_date'])} · {category} · {r['account_name']}",
                  10, color="muted", bg=f).pack(fill="x")
            income = r["kind"] == "income"
            label(row, ("+" if income else "−") + money(r["amount"]), 11, "semibold",
                  "income" if income else "text", bg=f).pack(side="right")
        return p

    def _accounts(self, rows):
        p = Panel(self.content, t("dash.accounts_title"),
                  actions=[("expand", lambda: self.app.navigate("accounts"), t("common.view_accounts"))])
        f = p.fill
        for i, a in enumerate(rows[:5]):
            row = tk.Frame(p.content, bg=f)
            row.pack(fill="x", pady=(0 if i == 0 else 10, 0))
            mid = tk.Frame(row, bg=f)
            mid.pack(side="left", fill="x", expand=True)
            label(mid, clip(a["name"], 24), 11, "medium", bg=f).pack(fill="x")
            note = t("common.current_balance")
            if a["projected_balance"] != a["balance"]:
                note = t("dashboard.balance_predicted", amount=money(a["projected_balance"]))
            label(mid, note, 10, color="muted", bg=f).pack(fill="x")
            label(row, money(a["balance"]), 11, "semibold",
                  "text" if a["balance"] >= 0 else "expense", bg=f).pack(side="right")
        return p
