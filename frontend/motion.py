"""Animações: um pequeno equivalente ao gsap feito com ``after`` do Tk.

``tween(widget, start, end, duration, ease, on_update)`` anima um número e
chama ``on_update(valor)`` a cada quadro (~60 fps). As curvas seguem as do
gsap (power3.out, power3.inOut). Respeita o "Reduzir movimento" do macOS:
nesse caso tudo pula direto para o valor final.
"""

import os
import subprocess
import sys
import time
import tkinter as tk

FRAME_MS = 16


# ---------------------------------------------------------------- curvas
def power3_out(t):
    return 1 - (1 - t) ** 3


def power3_in_out(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def power2_out(t):
    return 1 - (1 - t) ** 2


def linear(t):
    return t


EASES = {"power3.out": power3_out, "power3.inOut": power3_in_out,
         "power2.out": power2_out, "linear": linear}


# ---------------------------------------------------------------- acessibilidade
_reduced = {"value": None}


def reduced_motion():
    """True quando o usuário pediu menos movimento (macOS: Acessibilidade >
    Tela > Reduzir movimento) ou definiu FINANCE_CONTROL_REDUCED_MOTION=1."""
    if _reduced["value"] is None:
        value = os.environ.get("FINANCE_CONTROL_REDUCED_MOTION") == "1"
        if not value and sys.platform == "darwin":
            try:
                out = subprocess.run(
                    ["defaults", "read", "com.apple.universalaccess", "reduceMotion"],
                    capture_output=True, text=True, timeout=2)
                value = out.stdout.strip() == "1"
            except (OSError, subprocess.SubprocessError):
                value = False
        _reduced["value"] = value
    return _reduced["value"]


# ---------------------------------------------------------------- tween
class Tween:
    def __init__(self, widget, start, end, duration, ease, on_update, on_done=None, delay=0):
        self.widget = widget
        self.start, self.end = start, end
        self.duration = max(duration, 0.0001)
        self.ease = EASES.get(ease, ease) if isinstance(ease, str) else ease
        self.on_update, self.on_done = on_update, on_done
        self.job = None
        self.alive = True
        self.t0 = None
        if reduced_motion() or duration <= 0:
            self._finish()
        else:
            self.job = widget.after(max(int(delay * 1000), 0), self._begin)

    def _begin(self):
        self.t0 = time.perf_counter()
        self._step()

    def _step(self):
        self.job = None
        if not self.alive:
            return
        try:
            if not self.widget.winfo_exists():
                self.alive = False
                return
        except tk.TclError:
            self.alive = False
            return
        progress = min((time.perf_counter() - self.t0) / self.duration, 1.0)
        value = self.start + (self.end - self.start) * self.ease(progress)
        try:
            self.on_update(value)
        except tk.TclError:
            self.alive = False
            return
        if progress >= 1.0:
            self.alive = False
            if self.on_done:
                self.on_done()
            return
        self.job = self.widget.after(FRAME_MS, self._step)

    def _finish(self):
        self.alive = False
        try:
            self.on_update(self.end)
        except tk.TclError:
            return
        if self.on_done:
            self.on_done()

    def cancel(self):
        self.alive = False
        if self.job is not None:
            try:
                self.widget.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None


def tween(widget, start, end, duration, ease="power3.out", on_update=None, on_done=None, delay=0):
    return Tween(widget, start, end, duration, ease, on_update or (lambda v: None), on_done, delay)


class Channel:
    """Guarda o tween ativo de uma propriedade: iniciar outro cancela o anterior
    (como ``gsap.to`` sobre a mesma propriedade)."""

    def __init__(self):
        self.current = None

    def run(self, *args, **kwargs):
        if self.current is not None:
            self.current.cancel()
        self.current = tween(*args, **kwargs)
        return self.current


class EdgeSlider:
    """Pílula que desliza entre itens como no vídeo (src/ui.ts): ``l`` e ``r``
    são as distâncias da pílula às bordas esquerda e direita do contêiner
    (o ``inset`` do clip-path). A borda que lidera vai primeiro e mais rápido;
    a que segue alcança depois.

        right = L > prev_l
        l: duração 0.55 (power3.inOut) indo para a direita, 0.36 (power3.out) voltando
        r: duração 0.36 (power3.out) indo para a direita, 0.55 (power3.inOut) voltando
    """

    def __init__(self, widget, on_update):
        self.widget = widget
        self.on_update = on_update
        self.l = self.r = None
        self._l, self._r = Channel(), Channel()

    def jump(self, left, right):
        for ch in (self._l, self._r):
            if ch.current is not None:
                ch.current.cancel()
        self.l, self.r = left, right
        self.on_update(left, right)

    def go(self, left, right):
        if self.l is None:
            self.jump(left, right)
            return
        moving_right = left > self.l

        def set_l(value):
            self.l = value
            self.on_update(self.l, self.r)

        def set_r(value):
            self.r = value
            self.on_update(self.l, self.r)

        self._l.run(self.widget, self.l, left, 0.55 if moving_right else 0.36,
                    "power3.inOut" if moving_right else "power3.out", set_l)
        self._r.run(self.widget, self.r, right, 0.36 if moving_right else 0.55,
                    "power3.out" if moving_right else "power3.inOut", set_r)


# ---------------------------------------------------------------- utilidades
def count_up(widget, target, formatter, setter, duration=0.8, start=0, delay=0):
    """Conta um número de ``start`` até ``target`` exibindo com ``formatter``."""
    return tween(widget, start, target, duration, "power3.out",
                 lambda v: setter(formatter(round(v))), delay=delay)
