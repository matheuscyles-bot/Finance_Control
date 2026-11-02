"""Agenda: calendário mensal (com o painel do dia) ou lista por semana com os
lançamentos e as projeções das recorrências, e embaixo as regras de
recorrência (pausar/ativar, editar, excluir). Substitui a tela Recorrências."""

import calendar
import tkinter as tk
from datetime import date, timedelta

from backend import config
from backend.services import planning, recurring
from frontend import dialogs, motion
from frontend.draw import round_rect
from frontend.pages.base import Page, kpi, money_fmt
from frontend.pages.dashboard import clip
from frontend.theme import c, font
from frontend.ui import Chip, CircleButton, MonthSwitcher, SearchField
from frontend.widgets import Button, Card, EmptyState, Icon, ScrollFrame, Segmented, label
from backend.utils import formatters
from backend.utils.formatters import money
from backend.utils.i18n import category_label, t

RISE = 12          # px de subida na entrada
RISE_TIME = 0.45   # s
STEP = 0.05        # atraso entre semanas e regras
HEAD_H = 26        # linha dos dias da semana
CELL_H = 96        # altura de cada semana na grade
PANEL_W = 300      # painel lateral do dia
RULE_COLS = 3
PILLS = 2          # lançamentos desenhados em cada dia (o resto vira "+n")


def _monday(iso):
    day = date.fromisoformat(iso)
    return (day - timedelta(days=day.weekday())).isoformat()


def _signed(r):
    return r["amount"] if r["kind"] == "income" else -r["amount"]


class SchedulePage(Page):
    title_key = "page.schedule.title"

    def build(self):
        self.kind, self.view = None, "calendar"
        self.month, self.selected = formatters.current_month(), None
        self.items, self.rules, self._shown = [], [], []
        self.cells = []  # [(x1, y1, x2, y2, iso)] da última pintura da grade
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self._render())

        self.months_row = tk.Frame(self, bg=c("bg"))
        self.months_row.pack(fill="x", pady=(0, 10))
        self.months = MonthSwitcher(self.months_row, self._month_changed, bg=c("bg"), month=self.month)
        self.months.pack(side="left")

        self.bar = tk.Frame(self, bg=c("bg"))
        self.bar.pack(fill="x", pady=(0, 16))
        Segmented(self.bar, [("calendar", t("schedule.view_calendar")), ("list", t("schedule.view_list"))],
                  self.view, self._set_view, bg=c("bg"), size=11).pack(side="right")
        SearchField(self.bar, variable=self.query, placeholder=t("schedule.search"), width=240,
                    bg=c("bg")).pack(side="left")
        self.chip_row = tk.Frame(self.bar, bg=c("bg"))
        self.chip_row.pack(side="left", padx=(14, 0))
        self._build_chips()

        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)

    def header_actions(self, parent):
        return [Button(parent, t("common.new_recurring"), self.new, "primary", icon="plus")]

    # ---------------------------------------------------------------- dados
    def refresh(self):
        super().refresh()
        if self.selected is None:
            self.selected = self._default_day()
        self._load()
        self._render()

    def _load(self):
        first, last = formatters.month_range(self.month)
        self.items = planning.scheduled_items(first, last)
        self.rules = recurring.list_recurring()
        today = date.today()
        next30 = planning.scheduled_items(today.isoformat(), (today + timedelta(days=30)).isoformat())
        dues = planning.scheduled_items(today.isoformat(), (today + timedelta(days=90)).isoformat(),
                                        kind="expense")
        if dues:
            nxt = dues[0]
            next_text = f"{formatters.format_date_short(nxt['date'])} · {clip(nxt['description'], 22)}"
        else:
            next_text = t("schedule.kpi_none")
        self.publish([
            kpi("repeat", sum(1 for r in self.rules if r["active"]), t("schedule.kpi_active")),
            kpi("calendar-clock", sum(_signed(r) for r in next30), t("schedule.kpi_next30"),
                money_fmt(signed=True)),
            kpi("bell", 0, t("schedule.kpi_next_due"), lambda _v, s=next_text: s),
        ])

    def _default_day(self):
        today = date.today().isoformat()
        return today if today[:7] == self.month else None

    def _visible(self, rows):
        """Linhas que passam pelo tipo (despesa/receita) e pela busca."""
        q = self.query.get().strip().lower()
        out = []
        for r in rows:
            if self.kind and r["kind"] != self.kind:
                continue
            haystack = f"{r['description']} {r['category_name'] or ''} {r['account_name']}".lower()
            if not q or q in haystack:
                out.append(r)
        return out

    def _build_chips(self):
        for w in self.chip_row.winfo_children():
            w.destroy()
        options = [(None, t("schedule.filter_all")), ("expense", t("schedule.filter_expense")),
                   ("income", t("schedule.filter_income"))]
        for kind, text in options:
            Chip(self.chip_row, text, active=self.kind == kind,
                 command=lambda k=kind: self._set_kind(k), bg=c("bg")).pack(side="left", padx=(0, 8))

    def _set_kind(self, kind):
        self.kind = kind
        self._build_chips()
        self._render()

    def _set_view(self, view):
        self.view = view
        self._render()

    def _month_changed(self):
        self.month = self.months.month
        self.selected = self._default_day()
        self._load()
        self._render()

    # ---------------------------------------------------------------- telas
    def _render(self):
        inner = self.scroll.inner
        for w in inner.winfo_children():
            w.destroy()
        self._shown = self._visible(self.items)
        if self.view == "list":
            self._list(inner)
        else:
            self._calendar(inner)
        self._rules(inner)

    def _calendar(self, parent):
        row = tk.Frame(parent, bg=c("bg"))
        row.pack(fill="x")
        self._rise(row, 0, lambda w, v: w.pack_configure(pady=(v, 0)))
        wrap = tk.Frame(row, width=PANEL_W, bg=c("bg"))
        wrap.pack_propagate(False)
        wrap.pack(side="right", fill="y", padx=(16, 0))
        self.panel = Card(wrap, 20, 18, hover=False)
        self.panel.pack(fill="both", expand=True)
        self._fill_panel()
        self.calendar_canvas = tk.Canvas(row, bg=c("bg"), highlightthickness=0, bd=0, height=HEAD_H)
        self.calendar_canvas.pack(side="left", fill="both", expand=True)
        self.calendar_canvas.bind("<Button-1>", self._click)
        self.calendar_canvas.bind("<Configure>", lambda e: self._draw_grid())

    def _draw_grid(self):
        cv = self.calendar_canvas
        cv.delete("all")
        year, month = (int(p) for p in self.month.split("-"))
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
        width = max(cv.winfo_width(), 1)
        col_w = width / 7
        cv.configure(height=HEAD_H + len(weeks) * CELL_H)
        by_day = {}
        for r in self._shown:
            by_day.setdefault(r["date"], []).append(r)
        today = date.today().isoformat()
        self.cells = []
        for i in range(7):
            cv.create_text(i * col_w + col_w / 2, HEAD_H / 2, text=t(f"format.weekdays_abbr.{i + 1}"),
                           fill=c("muted"), font=font(10, "semibold"))
        for w, week in enumerate(weeks):
            for i, day in enumerate(week):
                x1, y1 = i * col_w + 3, HEAD_H + w * CELL_H + 3
                x2, y2 = (i + 1) * col_w - 3, HEAD_H + (w + 1) * CELL_H - 3
                iso = day.isoformat()
                if day.month != month:
                    cv.create_text(x1 + 12, y1 + 10, text=str(day.day), anchor="nw",
                                   fill=c("faint"), font=font(10))
                    continue
                self.cells.append((x1, y1, x2, y2, iso))
                selected = iso == self.selected
                round_rect(cv, x1, y1, x2, y2, 14, c("surface_alt"),
                           c("accent_text") if selected else c("border"), width=2 if selected else 1)
                cv.create_text(x1 + 12, y1 + 10, text=str(day.day), anchor="nw",
                               fill=c("accent_text") if iso == today else c("text"),
                               font=font(11, "semibold"))
                items = by_day.get(iso, [])
                for k, r in enumerate(items[:PILLS]):
                    py = y1 + 32 + k * 18
                    dot = c("income") if r["kind"] == "income" else c("expense")
                    cv.create_oval(x1 + 12, py + 4, x1 + 18, py + 10, fill=dot, outline=dot)
                    cv.create_text(x1 + 24, py + 7, text=clip(r["description"], 14), anchor="w",
                                   fill=c("text"), font=font(9))
                if len(items) > PILLS:
                    cv.create_text(x1 + 12, y1 + 32 + PILLS * 18, text=f"+{len(items) - PILLS}",
                                   anchor="w", fill=c("muted"), font=font(9, "semibold"))
                if items:
                    net = sum(_signed(r) for r in items)
                    cv.create_text(x2 - 10, y2 - 10, text=money(net, signed=True), anchor="se",
                                   fill=c("income") if net >= 0 else c("expense"),
                                   font=font(10, "semibold"))

    def _click(self, e):
        for x1, y1, x2, y2, iso in self.cells:
            if x1 <= e.x <= x2 and y1 <= e.y <= y2:
                self._pick_day(iso)
                return

    def _pick_day(self, iso):
        self.selected = iso
        self._draw_grid()
        self._fill_panel()

    def _fill_panel(self):
        card = self.panel
        for w in card.body.winfo_children():
            w.destroy()
        b, f = card.body, card.fill
        if not self.selected:
            label(b, t("schedule.pick_day"), 11, color="muted", bg=f).pack(fill="x")
            return
        label(b, formatters.format_date(self.selected), 14, "semibold", bg=f).pack(fill="x")
        day_items = [r for r in self._shown if r["date"] == self.selected]
        net = sum(_signed(r) for r in day_items)
        head = tk.Frame(b, bg=f)
        head.pack(fill="x", pady=(4, 12))
        label(head, t("schedule.day_total"), 10, color="muted", bg=f).pack(side="left")
        label(head, money(net, signed=True), 14, "semibold", "income" if net >= 0 else "expense",
              bg=f).pack(side="right")
        if not day_items:
            label(b, t("schedule.day_empty"), 11, color="muted", bg=f).pack(fill="x", pady=12)
        for r in day_items:
            self._row(b, r, f)

    def _list(self, parent):
        today = date.today().isoformat()
        rows = self._shown
        if self.month == today[:7]:
            rows = [r for r in rows if r["date"] >= today]
        if not rows:
            label(parent, t("schedule.no_match"), 11, color="muted", bg=c("bg")).pack(fill="x", pady=24)
            return
        weeks = {}
        for r in rows:
            weeks.setdefault(_monday(r["date"]), []).append(r)
        for i, (monday, items) in enumerate(weeks.items()):
            card = Card(parent, 20, 14, hover=False)
            card.pack(fill="x", pady=(0, 12))
            b, f = card.body, card.fill
            head = tk.Frame(b, bg=f)
            head.pack(fill="x", pady=(0, 6))
            label(head, t("schedule.week_of", date=formatters.format_date_short(monday)), 12, "semibold",
                  bg=f).pack(side="left")
            label(head, str(len(items)), 11, "semibold", color="muted", bg=f).pack(side="right")
            for r in items:
                self._row(b, r, f, with_date=True)
            self._rise(card, i * STEP, lambda w, v: w.pack_configure(pady=(v, 12)))

    def _row(self, parent, r, fill, with_date=False):
        income = r["kind"] == "income"
        row = tk.Frame(parent, bg=fill)
        row.pack(fill="x", pady=5)
        if with_date:
            label(row, formatters.format_date_short(r["date"]), 11, color="muted", bg=fill,
                  ).pack(side="left", padx=(0, 14))
        Icon(row, "repeat" if r["source"] == "recurring" else "calendar", c("muted"), fill,
             size=16).pack(side="left", padx=(0, 10))
        text = tk.Frame(row, bg=fill)
        text.pack(side="left", fill="x", expand=True)
        label(text, clip(r["description"], 28), 12, "semibold", bg=fill).pack(anchor="w")
        category = category_label(r["category_name"]) if r["category_name"] else t("common.no_category")
        sub = f"{category} · {r['account_name']}"
        if r["source"] == "recurring":
            sub = f"{t('schedule.projected')} · {sub}"
        label(text, clip(sub, 34), 10, color="muted", bg=fill).pack(anchor="w")
        label(row, money(r["amount"], signed=True), 12, "semibold", "income" if income else "text",
              bg=fill).pack(side="right")

    def _rules(self, parent):
        label(parent, t("schedule.rules_title"), 15, "semibold", bg=c("bg")).pack(anchor="w", pady=(28, 10))
        if not self.rules:
            EmptyState(parent, "repeat", t("recurring.none_title"), t("recurring.none_text"),
                       t("common.new_recurring"), self.new).pack(fill="x", ipady=40)
            return
        rules = self._visible(self.rules)
        if not rules:
            label(parent, t("schedule.no_match"), 11, color="muted", bg=c("bg")).pack(fill="x", pady=12)
            return
        grid = tk.Frame(parent, bg=c("bg"))
        grid.pack(fill="x")
        for col in range(RULE_COLS):
            grid.grid_columnconfigure(col, weight=1, uniform="rule")
        for i, r in enumerate(rules):
            card = self._rule_card(grid, r)
            card.grid(row=i // RULE_COLS, column=i % RULE_COLS, sticky="nsew", padx=6, pady=6)
            self._rise(card, i * STEP, lambda w, v: w.grid_configure(pady=(6 + v, 6)))

    def _rule_card(self, parent, r):
        income, active = r["kind"] == "income", bool(r["active"])
        card = Card(parent, 18, 16, hover=True)
        b, f = card.body, card.fill
        head = tk.Frame(b, bg=f)
        head.pack(fill="x")
        label(head, clip(r["description"], 24), 12, "semibold", "text" if active else "muted",
              bg=f).pack(side="left")
        label(head, t("recurring.active") if active else t("recurring.paused"), 10, "semibold",
              "income" if active else "muted", bg=f).pack(side="right")
        label(b, money(r["amount"], signed=True), 20, "medium", "income" if income else "text",
              bg=f).pack(fill="x", pady=(10, 0))
        label(b, clip(f"{config.FREQUENCIES[r['frequency']]} · {r['account_name']}", 34), 10,
              color="muted", bg=f).pack(fill="x", pady=(2, 0))
        label(b, t("schedule.next_on", date=formatters.format_date(r["next_date"])), 10,
              color="muted", bg=f).pack(fill="x")
        foot = tk.Frame(b, bg=f)
        foot.pack(fill="x", pady=(12, 0))
        CircleButton(foot, "trash-2", lambda: self.delete(r), size=30, tooltip=t("common.delete"),
                     kind="plain", bg=f, icon_size=13).pack(side="right")
        CircleButton(foot, "pencil", lambda: self.edit(r), size=30, tooltip=t("common.edit"),
                     kind="plain", bg=f, icon_size=13).pack(side="right", padx=(0, 6))
        CircleButton(foot, "power", lambda: self.toggle(r), size=30,
                     tooltip=t("recurring.pause") if active else t("recurring.resume"),
                     kind="plain", bg=f, icon_size=13).pack(side="right", padx=(0, 6))
        return card

    def _rise(self, widget, delay, place):
        """Sobe o widget ~12 px com atraso; sem animação se o usuário pediu movimento reduzido."""
        if motion.reduced_motion():
            return
        place(widget, RISE)

        def step(v):
            try:
                place(widget, round(v))
            except tk.TclError:  # a tela foi redesenhada antes do fim
                pass
        motion.tween(widget, RISE, 0, RISE_TIME, "power3.out", on_update=step, delay=delay)

    # ---------------------------------------------------------------- ações
    def new(self):
        if dialogs.RecurringDialog(self.app).wait():
            self.app.after_change(run_recurring=True)
            self.app.toast("Recorrência criada.", "success")

    def edit(self, row):
        if dialogs.RecurringDialog(self.app, row).wait():
            self.app.after_change(run_recurring=True)
            self.app.toast("Recorrência atualizada.", "success")

    def toggle(self, row):
        self.guarded(lambda: (recurring.set_active(row["id"], not row["active"]),
                              self.app.after_change(run_recurring=True)))

    def delete(self, row):
        if dialogs.confirm(
                self.app, "Excluir recorrência",
                f"Excluir “{row['description']}”? Os lançamentos já criados são mantidos."):
            def run():
                recurring.delete_recurring(row["id"])
                self.app.after_change()
                self.app.toast("Recorrência excluída.", "success")
            self.guarded(run)
