"""Janela principal: barra superior com abas (pílula deslizante), barra lateral
de ícones, cabeçalho da página (título + KPIs + ações), transições e avisos.

Tudo o que fica "sobre o degradê" é desenhado num único canvas (``stage``):
assim os elementos de vidro parecem translúcidos de verdade, já que o Tk não
tem transparência por widget. As páginas entram num quadro posicionado nele.
"""

import getpass
import logging
import os
import tkinter as tk

from backend import config
import database
from backend.services import backup, planning, recurring, settings, transactions as tx
from frontend import dialogs, fonts, motion, theme
from frontend.draw import Backdrop, round_rect
from frontend.pages.accounts import AccountsPage
from frontend.pages.budgets import BudgetsPage
from frontend.pages.dashboard import DashboardPage
from frontend.pages.recurring import RecurringPage
from frontend.pages.reports import ReportsPage
from frontend.pages.settings import SettingsPage
from frontend.pages.transactions import TransactionsPage
from frontend.theme import MOD, c, font, mix
from frontend.ui import CircleButton, Popover, Tooltip, hide_tip, initials
from frontend.widgets import Toasts, bg_of, label, linespace, measure, put_icon
from backend.utils import formatters
from backend.utils import i18n
from backend.utils.i18n import t

log = logging.getLogger("finance_control.ui")

# (chave, ícone, classe) — todas menos "settings" viram abas.
# Pipeline (vencimentos) e Agenda entram nas próximas etapas do redesign.
NAV = [
    ("dashboard", "layout-dashboard", DashboardPage),
    ("transactions", "list", TransactionsPage),
    ("accounts", "wallet", AccountsPage),
    ("budgets", "target", BudgetsPage),
    ("reports", "chart-column", ReportsPage),
    ("recurring", "repeat", RecurringPage),
    ("settings", "settings", SettingsPage),
]
TABS = [key for key, *_ in NAV if key != "settings"]

TOP_H = 78          # barra superior
RAIL_X, RAIL_W = 18, 60
CONTENT_X = RAIL_X + RAIL_W + 24
RIGHT_PAD = 26
HEADER_H = 118      # cabeçalho com título em 2 linhas e KPIs ao lado
HEADER_H_STACKED = 192


class _TextItem:
    """Expõe um texto do canvas com ``cget("text")`` (como um Label)."""

    def __init__(self, canvas, item):
        self.canvas, self.item = canvas, item

    def cget(self, option):
        return self.canvas.itemcget(self.item, option)


class App:
    def __init__(self, root=None):
        fonts.register()
        self.root = root or tk.Tk()
        try:
            i18n.configure(database.DATA_DIR, database.BASE_DIR)
            self._language_load_error = False
        except i18n.LocaleConfigError as exc:
            log.error("Não foi possível carregar a preferência de idioma: %s", type(exc).__name__)
            self._language_load_error = True
        self.root.title(config.APP_TITLE)
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.minsize(config.MIN_WIDTH, config.MIN_HEIGHT)
        self.root.report_callback_exception = self._tk_exception
        self.current = "dashboard"
        self.stage = None
        self.pages = {}
        self._last_undo = None
        formatters.set_currency_symbol(settings.get_currency_symbol())
        theme.apply(self.root, settings.get_theme())
        self.toasts = Toasts(self.root)
        self._startup_tasks()
        if self._language_load_error:
            self.startup_notes.append(t("toast.language_load_error"))
        self._build_shell()
        self._bind_shortcuts()
        self.navigate("dashboard")
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---- inicialização ----
    def _startup_tasks(self):
        self.startup_notes = []
        try:
            created = backup.auto_backup_if_needed()
            if created:
                log.info("Backup automático criado")
        except Exception as exc:
            log.warning("Backup automático falhou: %s", type(exc).__name__)
            self.startup_notes.append(t("toast.auto_backup_failed"))
        try:
            made = recurring.run_due_recurring()
            if made:
                self.startup_notes.append(t("toast.recurring_created", count=made))
        except Exception as exc:
            log.warning("Recorrências falharam: %s", type(exc).__name__)
            self.startup_notes.append(t("toast.recurring_failed"))

    def run(self):
        self.root.update_idletasks()
        for note in self.startup_notes:
            self.root.after(500, lambda n=note: self.toast(n, "info"))
        self.root.mainloop()

    def quit(self):
        self.toasts.dismiss()
        self.root.destroy()

    def confirm_quit(self):
        if dialogs.confirm(self, t("app.quit_title"), t("app.quit_text"), t("app.quit_confirm"), False):
            self.quit()

    # ---- estrutura visual ----
    def _build_shell(self):
        if self.stage is not None:
            self.stage.destroy()
        Popover.close_all()
        self.pages = {}
        self.backdrop = Backdrop()
        self.stage = tk.Canvas(self.root, bg=c("bg"), highlightthickness=0, bd=0)
        self.stage.place(x=0, y=0, relwidth=1, relheight=1)
        self.stage.bind("<Configure>", self._on_resize)
        self._size = (0, 0)
        self._layout_job = None
        self._tab_spans = {}
        self._kpi_widgets = []
        self._kpi_tweens = []
        self._header_h = HEADER_H
        self._title_item = None
        self.title_label = _TextItem(self.stage, None)
        self.slider = motion.EdgeSlider(self.stage, self._draw_pill)

        self.body = tk.Frame(self.stage, bg=c("bg"))
        self._body_win = self.stage.create_window(CONTENT_X, TOP_H + HEADER_H, window=self.body,
                                                  anchor="nw")
        self.actions = tk.Frame(self.stage, bg=c("bg"))
        self._actions_win = self.stage.create_window(0, 0, window=self.actions, anchor="e")

        # barra superior: botões da direita
        self.right = tk.Frame(self.stage, bg=c("bg"))
        self._right_win = self.stage.create_window(0, TOP_H / 2, window=self.right, anchor="e")
        self.settings_btn = CircleButton(self.right, "settings", lambda: self.navigate("settings"),
                                         size=40, tooltip=t("top.settings"))
        self.settings_btn.pack(side="left", padx=(0, 10))
        self.bell = CircleButton(self.right, "bell", self.show_notifications, size=40,
                                 tooltip=t("top.notifications"))
        self.bell.pack(side="left", padx=(0, 10))
        name = self._user_name()
        self.avatar = tk.Canvas(self.right, width=40, height=40, highlightthickness=0, bd=0,
                                cursor="hand2", bg=c("bg"))
        self.avatar.create_oval(1, 1, 39, 39, fill=c("avatar")[0], outline=c("avatar")[0])
        self.avatar.create_text(20, 20, text=initials(name), font=font(12, "bold"), fill="#15120F")
        self.avatar.bind("<Button-1>", lambda e: self.navigate("settings"))
        Tooltip(self.avatar, name)
        self.avatar.pack(side="left")

        # barra lateral de ícones (ações rápidas)
        self.rail = tk.Frame(self.stage, bg=c("bg"))
        self._rail_win = self.stage.create_window(RAIL_X + RAIL_W / 2, TOP_H + 8, window=self.rail,
                                                  anchor="n")
        self._rail_buttons = []
        rail_items = [
            ("search", t("rail.search"), self._focus_search),
            ("plus", t("rail.new_transaction"), lambda: self.new_transaction()),
            ("arrow-left-right", t("rail.new_transfer"), self.new_transfer),
            ("repeat", t("rail.new_recurring"), self.new_recurring),
            ("target", t("rail.new_budget"), self.new_budget),
            ("upload", t("rail.import"), self.import_csv),
            ("download", t("rail.export"), self.export_csv),
            ("hard-drive-download", t("rail.backup"), self.backup_now),
            None,
            ("settings", t("rail.settings"), lambda: self.navigate("settings")),
            ("x", t("rail.quit"), self.confirm_quit),
        ]
        for item in rail_items:
            if item is None:
                tk.Frame(self.rail, height=14, bg=c("bg")).pack()
                self._rail_buttons.append(None)
                continue
            name_, tip, command = item
            btn = CircleButton(self.rail, name_, command, size=42, kind="plain", tooltip=None,
                               icon_size=18)
            Tooltip(btn, tip, side="right")
            btn.pack(pady=3)
            self._rail_buttons.append(btn)
        self.rail_settings = self._rail_buttons[-2]

        self.toasts.dismiss()
        self._on_resize()

    def _user_name(self):
        try:
            import pwd
            full = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0].strip()
        except (ImportError, KeyError, OSError):
            full = ""
        return full or getpass.getuser() or config.APP_TITLE

    # ---- layout ----
    def _on_resize(self, _e=None):
        if self._layout_job is None:
            delay = 1 if _e is None else 40
            self._layout_job = self.root.after(delay, self._layout)

    def _layout(self):
        self._layout_job = None
        stage = self.stage
        try:
            w, h = stage.winfo_width(), stage.winfo_height()
        except tk.TclError:
            return
        if w < 50 or h < 50:
            w, h = self.root.winfo_width(), self.root.winfo_height()
            if w < 50:
                w, h = config.WINDOW_WIDTH, config.WINDOW_HEIGHT
        resized = (w, h) != self._size
        self._size = (w, h)
        if self.backdrop.render(w, h) or resized:
            self._bg_photo = self.backdrop.crop(0, 0, w, h, stage)
            stage.delete("backdrop")
            stage.create_image(0, 0, image=self._bg_photo, anchor="nw", tags="backdrop")
            stage.tag_lower("backdrop")
        self._draw_topbar(w)
        self._draw_rail(h)
        self._draw_header()
        self._place_body()

    def _sample(self, x, y):
        return self.backdrop.sample(x, y)

    def _set_bg(self, frame, color):
        frame.configure(bg=color)
        for child in frame.winfo_children():
            if isinstance(child, CircleButton):
                child._parent_bg = color
                child.configure(bg=color)
                child._draw()
            elif isinstance(child, tk.Canvas):
                child.configure(bg=color)
            elif isinstance(child, tk.Frame):
                self._set_bg(child, color)

    # ---- barra superior ----
    def _draw_topbar(self, w):
        s = self.stage
        s.delete("top")
        cy = TOP_H / 2
        round_rect(s, 24, cy - 18, 60, cy + 18, 11, c("primary"), c("primary"), tags="top")
        put_icon(s, 42, cy, "leaf", c("primary_text"), 19, tags="top")
        s.create_text(72, cy, text=config.APP_TITLE, anchor="w", font=font(16, "semibold"),
                      fill=c("text"), tags=("top", "brand"))
        brand_right = 72 + measure(font(16, "semibold"), config.APP_TITLE)

        right_w = 40 * 3 + 20
        s.coords(self._right_win, w - RIGHT_PAD, cy)
        self._set_bg(self.right, self._sample(w - RIGHT_PAD - right_w / 2, cy))

        # abas
        tab_font = font(11, "medium")
        pad, inset = 18, 5
        texts = [t(f"nav.{k}") for k in TABS]
        widths = [measure(tab_font, txt) + 2 * pad for txt in texts]
        bar_w = sum(widths) + 2 * inset
        free = (w - RIGHT_PAD - right_w - 24) - (brand_right + 24)
        if bar_w > free:
            pad = max(10, pad - (bar_w - free) // (2 * len(TABS)) - 1)
            widths = [measure(tab_font, txt) + 2 * pad for txt in texts]
            bar_w = sum(widths) + 2 * inset
        x0 = max((w - bar_w) / 2, brand_right + 24)
        bar_h = 46
        y0 = cy - bar_h / 2
        self._bar = (x0, y0, bar_w, bar_h, inset)
        glass = mix(self._sample(x0 + bar_w / 2, cy), c("text"), 0.06)
        self._bar_fill = glass
        round_rect(s, x0, y0, x0 + bar_w, y0 + bar_h, bar_h / 2, glass,
                   mix(glass, c("text"), 0.07), tags="top")
        x = x0 + inset
        self._tab_spans = {}
        for key, text, width in zip(TABS, texts, widths):
            self._tab_spans[key] = (x - x0, x - x0 + width)
            item = s.create_text(x + width / 2, cy, text=text, font=tab_font, fill=c("muted"),
                                 tags=("top", "tab", f"tab:{key}"))
            s.tag_bind(f"tab:{key}", "<Button-1>", lambda e, k=key: self.navigate(k))
            s.tag_bind(f"tab:{key}", "<Enter>", lambda e, i=item: self._tab_hover(i, True))
            s.tag_bind(f"tab:{key}", "<Leave>", lambda e, i=item: self._tab_hover(i, False))
            x += width
        if self.current in self._tab_spans:
            self.slider.jump(*self._edges(self.current))
        else:
            s.delete("pill")
        self._paint_tabs()

    def _edges(self, key):
        """(l, r) da aba: distâncias às bordas esquerda e direita da barra."""
        x0, _y0, bar_w, _bar_h, _inset = self._bar
        x1, x2 = self._tab_spans[key]
        return x1, bar_w - x2

    def _draw_pill(self, left, right):
        """Desenha a pílula no recorte ``inset(T r B l round 999px)``."""
        s = self.stage
        s.delete("pill")
        if self.current not in self._tab_spans:
            return
        x0, y0, bar_w, bar_h, inset = self._bar
        x1, x2 = x0 + left, x0 + bar_w - right
        fill = mix(self._bar_fill, c("text"), 0.13)
        round_rect(s, x1, y0 + inset, x2, y0 + bar_h - inset, (bar_h - 2 * inset) / 2,
                   fill, fill, tags=("top", "pill"))
        s.tag_raise("tab")

    def _paint_tabs(self):
        for key in TABS:
            self.stage.itemconfigure(f"tab:{key}", fill=c("text") if key == self.current else c("muted"))

    def _tab_hover(self, item, on):
        self.stage.configure(cursor="hand2" if on else "")
        tags = self.stage.gettags(item)
        key = next((tg[4:] for tg in tags if tg.startswith("tab:")), None)
        if key != self.current:
            self.stage.itemconfigure(item, fill=mix(c("muted"), c("text"), 0.6) if on else c("muted"))

    # ---- barra lateral ----
    def _draw_rail(self, h):
        s = self.stage
        s.delete("rail")
        top, bottom = TOP_H + 4, h - 18
        x1, x2 = RAIL_X, RAIL_X + RAIL_W
        glass = mix(self._sample(x1 + RAIL_W / 2, top + 60), c("text"), 0.05)
        round_rect(s, x1, top, x2, bottom, RAIL_W / 2, glass, mix(glass, c("text"), 0.07), tags="rail")
        s.tag_lower("rail")
        s.tag_raise("rail", "backdrop")
        s.coords(self._rail_win, x1 + RAIL_W / 2, top + 10)
        self.rail.configure(bg=glass)
        for child in self.rail.winfo_children():
            if isinstance(child, CircleButton):
                child._parent_bg = glass
                child.configure(bg=glass)
                child._draw()
            else:
                child.configure(bg=glass)
        self.rail_settings.set_active(self.current == "settings")

    # ---- cabeçalho ----
    def _draw_header(self):
        s = self.stage
        w, _h = self._size
        s.delete("head")
        page = self.pages.get(self.current)
        title = t(page.title_key) if page else ""
        tf = font(28, "medium")
        y = TOP_H + 10
        self._title_item = s.create_text(CONTENT_X, y, text=title, anchor="nw", font=tf,
                                         fill=c("text"), tags="head")
        self.title_label = _TextItem(s, self._title_item)
        title_w = max((measure(tf, line) for line in title.split("\n")), default=0)

        actions_w = self.actions.winfo_reqwidth()
        kpis = page.kpis if page else []
        kpi_w = self._kpis_width(kpis)
        avail = w - RIGHT_PAD - CONTENT_X
        stacked = title_w + 56 + kpi_w + 24 + actions_w > avail
        self._header_h = HEADER_H_STACKED if (stacked and kpis) else HEADER_H
        title_h = 2 * linespace(tf)
        actions_y = y + title_h / 2
        s.coords(self._actions_win, w - RIGHT_PAD, actions_y)
        self._set_bg(self.actions, self._sample(w - RIGHT_PAD - max(actions_w, 40) / 2, actions_y))
        if stacked and kpis:
            self._kpi_origin = (CONTENT_X, y + title_h + 16 + 22)
        else:
            self._kpi_origin = (CONTENT_X + title_w + 56, y + title_h / 2)
        self._draw_kpis(kpis, animate=False)

    def _kpis_width(self, kpis):
        total = 0
        for k in kpis:
            total += self._kpi_block_width(k) + 40
        return max(total - 40, 0)

    def _kpi_block_width(self, k):
        value_w = measure(font(22, "semibold"), k["fmt"](k["value"]))
        cap_w = measure(font(10), k["caption"])
        extra = 0
        if k.get("badge"):
            extra += measure(font(9, "bold"), k["badge"][0]) + 16 + 10
        if k.get("toggle"):
            extra += 38 + 12
        return 44 + 14 + max(value_w + extra, cap_w)

    def _draw_kpis(self, kpis, animate=True):
        s = self.stage
        for tw in self._kpi_tweens:
            tw.cancel()
        self._kpi_tweens = []
        s.delete("kpi")
        for wdg in self._kpi_widgets:
            wdg.destroy()
        self._kpi_widgets = []
        x, cy = self._kpi_origin
        vf, cf, bf = font(22, "semibold"), font(10), font(9, "bold")
        for k in kpis:
            base = self._sample(x + 22, cy)
            circle = mix(base, c("text"), 0.08)
            s.create_oval(x, cy - 22, x + 44, cy + 22, fill=circle, outline=mix(circle, c("text"), 0.06),
                          tags=("head", "kpi"))
            put_icon(s, x + 22, cy, k["icon"], c("text"), 18, tags=("head", "kpi"))
            tx_ = x + 44 + 14
            final = k["fmt"](k["value"])
            value_item = s.create_text(tx_, cy - 9, text=final, anchor="w", font=vf, fill=c("text"),
                                       tags=("head", "kpi"))
            s.create_text(tx_, cy + 15, text=k["caption"], anchor="w", font=cf, fill=c("muted"),
                          tags=("head", "kpi"))
            after = tx_ + measure(vf, final) + 10
            if k.get("badge"):
                text, tone = k["badge"]
                tone_color = {"lime": c("accent_text"), "coral": c("coral"), "blue": c("blue"),
                              "neutral": c("muted"), "mint": c("mint"), "amber": c("amber")}.get(tone, c("muted"))
                bw, bh = measure(bf, text) + 16, linespace(bf) + 6
                fill = mix(self._sample(after + bw / 2, cy - 9), tone_color, 0.2)
                round_rect(s, after, cy - 9 - bh / 2, after + bw, cy - 9 + bh / 2, bh / 2, fill, fill,
                           tags=("head", "kpi"))
                s.create_text(after + bw / 2, cy - 9, text=text, font=bf, fill=tone_color,
                              tags=("head", "kpi"))
                after += bw + 10
            if k.get("toggle"):
                from frontend.ui import Toggle
                on, command, tip = k["toggle"]
                toggle = Toggle(s, on, command, bg=self._sample(after + 19, cy - 9), tooltip=tip)
                s.create_window(after, cy - 9, window=toggle, anchor="w", tags=("head", "kpi"))
                self._kpi_widgets.append(toggle)
            if animate and isinstance(k["value"], int) and k["value"]:
                fmt = k["fmt"]
                self._kpi_tweens.append(motion.count_up(
                    s, k["value"], fmt, lambda text, i=value_item: s.itemconfigure(i, text=text),
                    duration=theme.DURATION["count"]))
            x += self._kpi_block_width(k) + 40

    def header_kpis(self, kpis):
        """Chamado pela página quando seus KPIs mudam."""
        self._draw_header()
        self._draw_kpis(kpis, animate=True)
        self._place_body()

    def _place_body(self):
        w, h = self._size
        y = TOP_H + self._header_h
        self.stage.coords(self._body_win, CONTENT_X, y)
        self.stage.itemconfigure(self._body_win, width=max(w - CONTENT_X - RIGHT_PAD + 8, 100),
                                 height=max(h - y - 14, 100))

    # ---- navegação ----
    def navigate(self, key):
        Popover.close_all()
        hide_tip()
        previous = self.current
        self.current = key
        for page in self.pages.values():
            page.pack_forget()
        page = self.pages.get(key)
        if page is None:
            cls = next(n[2] for n in NAV if n[0] == key)
            page = cls(self.body, self)
            self.pages[key] = page
        for w in self.actions.winfo_children():
            w.destroy()
        for b in page.header_actions(self.actions):
            b.pack(side="left", padx=(10, 0))
        self.actions.update_idletasks()

        if key in self._tab_spans:
            self.slider.go(*self._edges(key))
        else:
            self.stage.delete("pill")
        self._paint_tabs()
        self.rail_settings.set_active(key == "settings")

        page.pack(fill="both", expand=True)
        self.guarded_show(page)
        self._draw_header()
        self._draw_kpis(page.kpis, animate=True)
        self._place_body()
        if previous != key or not getattr(self, "_entered", False):
            self._entered = True
            self._enter_animation(page)

    def _enter_animation(self, page):
        """O conteúdo entra de baixo (~12 px) com o texto clareando."""
        if motion.reduced_motion():
            return
        s = self.stage
        _w, _h = self._size
        y = TOP_H + self._header_h
        labels = []

        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.Label):
                    try:
                        labels.append((child, child.cget("fg"), bg_of(child)))
                    except tk.TclError:
                        pass
                collect(child)
        collect(page)

        def step(v):
            s.coords(self._body_win, CONTENT_X, y + 14 * (1 - v))
            for widget, fg, bg in labels:
                try:
                    widget.configure(fg=mix(bg, fg, 0.15 + 0.85 * v))
                except (tk.TclError, ValueError):
                    pass
            if self._title_item:
                s.itemconfigure(self._title_item, fill=mix(c("bg"), c("text"), 0.2 + 0.8 * v))

        def restore():
            for widget, fg, _bg in labels:
                try:
                    widget.configure(fg=fg)
                except tk.TclError:
                    pass
        if hasattr(self, "_enter_tween") and self._enter_tween:
            self._enter_tween.cancel()
        self._enter_tween = motion.tween(s, 0.0, 1.0, theme.DURATION["page"], "power3.out", step, restore)

    def guarded_show(self, page):
        try:
            page.on_show()
        except Exception as exc:
            self.report_error(exc)

    def after_change(self, run_recurring=False):
        """Chame depois de qualquer alteração de dados."""
        if run_recurring:
            try:
                recurring.run_due_recurring()
            except Exception as exc:
                self.report_error(exc)
        for page in self.pages.values():
            page.dirty = True
        page = self.pages.get(self.current)
        if page:
            self.guarded_show(page)
            self.header_kpis(page.kpis)
        self._update_bell()

    # ---- avisos do sino ----
    def _update_bell(self):
        try:
            due = [i for i in planning.upcoming() if i["kind"] == "expense"]
        except Exception:
            due = []
        self.bell.set_badge("coral" if due else None)

    def show_notifications(self):
        pop = Popover(self.bell, width=340)
        body = pop.body
        fill = c("surface_alt")
        label(body, t("notif.title"), 13, "semibold", bg=fill).pack(fill="x")
        label(body, t("notif.subtitle"), 10, color="muted", bg=fill).pack(fill="x", pady=(2, 10))
        items = planning.upcoming()
        if not items:
            label(body, t("notif.empty"), 11, color="muted", bg=fill).pack(fill="x", pady=(4, 8))
        for item in items[:6]:
            row = tk.Frame(body, bg=fill)
            row.pack(fill="x", pady=4)
            label(row, formatters.format_date_short(item["date"]), 10, "semibold", color="muted",
                  bg=fill, width=7).pack(side="left")
            label(row, item["description"], 11, bg=fill).pack(side="left", padx=(6, 0))
            income = item["kind"] == "income"
            label(row, ("+" if income else "−") + formatters.money(item["amount"]), 11, "semibold",
                  color="income" if income else "expense", bg=fill).pack(side="right")
        link = label(body, t("notif.view_all") + "  ↗", 10, "bold", color="accent_text", bg=fill,
                     cursor="hand2")
        link.pack(fill="x", pady=(10, 0))
        link.bind("<Button-1>", lambda e: (pop.close(), self.navigate("recurring")))

    # ---- ações compartilhadas ----
    def is_empty(self):
        return tx.count_transactions() == 0

    def new_transaction(self, defaults=None, kind="expense"):
        dlg = dialogs.TransactionDialog(self, defaults=defaults, kind=kind)
        result = dlg.wait()
        if result:
            self.after_change()
            self.toast(t("toast.transaction_saved") if result == "created"
                       else t("toast.transaction_updated"), "success")

    def edit_transaction(self, row):
        if dialogs.TransactionDialog(self, transaction=row).wait():
            self.after_change()
            self.toast(t("toast.transaction_updated"), "success")

    def new_transfer(self):
        from backend.services import accounts
        if len(accounts.list_accounts()) < 2:
            self.toast(t("toast.need_two_accounts"), "error")
            return
        if dialogs.TransferDialog(self).wait():
            self.after_change()
            self.toast(t("toast.transfer_saved"), "success")

    def new_recurring(self):
        if dialogs.RecurringDialog(self).wait():
            self.after_change(run_recurring=True)
            self.toast(t("toast.recurring_saved"), "success")

    def new_budget(self):
        page = self.pages.get("budgets")
        month = page.month.month if page is not None and hasattr(page, "month") else formatters.current_month()
        if dialogs.BudgetDialog(self, month).wait():
            self.after_change()
            self.toast(t("toast.budget_saved"), "success")

    def import_csv(self):
        dlg = dialogs.ImportDialog(self)
        result = dlg.wait()
        if result:
            self.after_change()
            text = t("toast.imported", count=result["imported"])
            if result["skipped"]:
                text += " " + t("toast.import_skipped", count=result["skipped"])
            if result["fallback_categories"]:
                text += " " + t("toast.import_fallback", count=result["fallback_categories"])
            self.toast(text, "success")

    def _page(self, key):
        page = self.pages.get(key)
        if page is None:
            cls = next(n[2] for n in NAV if n[0] == key)
            page = self.pages[key] = cls(self.body, self)
        if page.dirty:
            self.guarded_show(page)
        return page

    def export_csv(self):
        self._page("transactions").export_csv()

    def backup_now(self):
        try:
            backup.manual_backup()
            self.toast(t("toast.backup_created"), "success")
        except Exception as exc:
            self.report_error(exc)

    def undoable(self, text, undo):
        def run():
            try:
                undo()
            except ValueError as exc:
                self.toast(str(exc), "error")
                return
            self.after_change()
            self.toast(t("toast.undone"), "success")
        self.toasts.show(text, "success", t("common.undo"), run, ms=7000)

    def toast(self, text, kind="info"):
        self.toasts.show(text, kind)

    def set_theme(self, name):
        if name == theme.theme_name():
            return
        settings.set_setting("theme", name)
        theme.apply(self.root, name)
        self._build_shell()
        self.navigate("settings")

    def set_currency(self, symbol):
        settings.set_setting("currency_symbol", symbol)
        formatters.set_currency_symbol(symbol)
        self.after_change()

    def set_language(self, code):
        if code == i18n.get_locale():
            return
        try:
            i18n.set_locale(code)
        except i18n.LocaleConfigError:
            self.toast(t("toast.language_save_error"), "error")
            return
        theme.apply(self.root, settings.get_theme())
        self._build_shell()
        self.navigate("settings")

    # ---- erros ----
    def report_error(self, exc):
        # Registra só o tipo e o local do erro: nunca valores financeiros.
        log.error("Erro inesperado: %s", type(exc).__name__, exc_info=True)
        self.toast(t("toast.unexpected_error"), "error")

    def _tk_exception(self, exc_type, exc, tb):
        log.error("Erro na interface: %s", exc_type.__name__, exc_info=(exc_type, exc, tb))
        self.toast(t("toast.ui_error"), "error")

    # ---- atalhos ----
    def _bind_shortcuts(self):
        r = self.root
        r.bind_all(f"<{MOD}-n>", lambda e: self.new_transaction())
        r.bind_all(f"<{MOD}-f>", lambda e: self._focus_search())
        r.bind_all(f"<{MOD}-comma>", lambda e: self.navigate("settings"))
        for i, key in enumerate(TABS, 1):
            r.bind_all(f"<{MOD}-Key-{i}>", lambda e, k=key: self.navigate(k))

    def _focus_search(self):
        self.navigate("transactions")
        self.pages["transactions"].focus_search()
