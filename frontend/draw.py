"""Ajudantes de desenho: cantos arredondados, fundo em degradê, curvas e eixos."""

import math

from PIL import Image, ImageDraw, ImageTk

from frontend.theme import c, mix


# ---------------------------------------------------------------- formas
def round_rect_points(x1, y1, x2, y2, r):
    """Pontos para ``create_polygon(..., smooth=True)`` com cantos de raio r.
    Os pontos duplicados mantêm os lados retos; só os cantos ficam curvos."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1,
        x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2,
        x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2,
        x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1,
    ]


def round_rect(canvas, x1, y1, x2, y2, r, fill, outline="", width=1, tags=()):
    return canvas.create_polygon(round_rect_points(x1, y1, x2, y2, r), smooth=True,
                                 fill=fill, outline=outline or fill, width=width, tags=tags)


def top_round_rect_points(x1, y1, x2, y2, r):
    """Retângulo com só os cantos de cima arredondados (barras)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1)))
    return [
        x1, y2, x1, y2, x1, y1 + r, x1, y1 + r, x1, y1,
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1,
        x2, y1 + r, x2, y1 + r, x2, y2, x2, y2,
    ]


def star_points(cx, cy, outer, inner=None, points=5):
    inner = inner or outer * 0.45
    pts = []
    for i in range(points * 2):
        radius = outer if i % 2 == 0 else inner
        angle = math.pi / points * i - math.pi / 2
        pts += [cx + radius * math.cos(angle), cy + radius * math.sin(angle)]
    return pts


# ---------------------------------------------------------------- fundo
class Backdrop:
    """Degradê do fundo da janela: quase preto quente com um brilho
    azul-acinzentado no canto superior esquerdo. Os elementos "de vidro" sobre
    ele recortam o pedaço certo da imagem (``crop``) ou pedem a cor de um
    ponto (``sample``), já que o Tk não tem transparência por widget."""

    GLOW_HEIGHT = 230  # o brilho termina antes de onde começam os cards

    def __init__(self):
        self.size = (0, 0)
        self.image = None
        self._cache = {}

    def render(self, width, height):
        width, height = max(int(width), 2), max(int(height), 2)
        if (width, height) == self.size and self.image is not None:
            return False
        base = _rgb(c("bg"))
        glow = _rgb(mix(c("bg"), c("glow"), 0.9))
        img = Image.new("RGB", (width, height), base)
        rx, ry = max(int(width * 0.62), 2), self.GLOW_HEIGHT
        mask = _glow_mask().resize((rx, ry), Image.BILINEAR)
        full = Image.new("L", (width, height), 0)
        full.paste(mask.crop((0, 0, min(rx, width), min(ry, height))), (0, 0))
        img.paste(Image.new("RGB", (width, height), glow), (0, 0), full)
        self.image = img
        self.size = (width, height)
        self._cache.clear()
        return True

    def crop(self, x, y, width, height, master):
        """PhotoImage do pedaço (x, y, w, h) da janela."""
        if self.image is None or width < 1 or height < 1:
            return None
        key = (int(x), int(y), int(width), int(height), id(master.tk))
        photo = self._cache.get(key)
        if photo is None:
            box = (int(x), int(y), int(x + width), int(y + height))
            photo = ImageTk.PhotoImage(self.image.crop(box), master=master)
            if len(self._cache) > 64:
                self._cache.clear()
            self._cache[key] = photo
        return photo

    def sample(self, x, y):
        if self.image is None:
            return c("bg")
        w, h = self.size
        r, g, b = self.image.getpixel((min(max(int(x), 0), w - 1), min(max(int(y), 0), h - 1)))
        return f"#{r:02X}{g:02X}{b:02X}"


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


_GLOW = {}


def _glow_mask(sw=160, sh=60):
    """Quarto de elipse: 255 no canto (0, 0) caindo suavemente até 0 na borda."""
    if "mask" not in _GLOW:
        data = []
        for j in range(sh):
            for i in range(sw):
                d = math.hypot(i / (sw - 1), j / (sh - 1))
                data.append(int(255 * max(0.0, 1 - d) ** 2.2))
        mask = Image.new("L", (sw, sh))
        mask.putdata(data)
        _GLOW["mask"] = mask
    return _GLOW["mask"]


# ---------------------------------------------------------------- gráficos
def nice_ticks(peak, count=2):
    """Valor máximo "redondo" do eixo e o passo (ex.: 1.000, 500)."""
    peak = max(peak, 1)
    raw = peak / count
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        if raw <= factor * magnitude:
            step = factor * magnitude
            break
    top = step * math.ceil(peak / step)
    return top, step


def monotone_curve(points, samples=14):
    """Curva suave que passa por todos os pontos sem "inventar" picos ou vales
    (interpolação cúbica monótona de Fritsch–Carlson)."""
    n = len(points)
    if n < 3:
        return list(points)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    d = [(ys[i + 1] - ys[i]) / ((xs[i + 1] - xs[i]) or 1) for i in range(n - 1)]
    m = [d[0]] + [0.0] * (n - 2) + [d[-1]]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            m[i] = (d[i - 1] + d[i]) / 2
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0.0
            continue
        a, b = m[i] / d[i], m[i + 1] / d[i]
        s = a * a + b * b
        if s > 9:
            tau = 3 / math.sqrt(s)
            m[i], m[i + 1] = tau * a * d[i], tau * b * d[i]
    out = []
    for i in range(n - 1):
        h = xs[i + 1] - xs[i]
        for k in range(samples):
            t = k / samples
            h00 = 2 * t ** 3 - 3 * t ** 2 + 1
            h10 = t ** 3 - 2 * t ** 2 + t
            h01 = -2 * t ** 3 + 3 * t ** 2
            h11 = t ** 3 - t ** 2
            out.append((xs[i] + t * h, h00 * ys[i] + h10 * h * m[i] + h01 * ys[i + 1] + h11 * h * m[i + 1]))
    out.append(points[-1])
    return out


def area_fill_image(curve, width, height, color, bg, top_alpha=0.42, master=None):
    """Imagem do preenchimento sob a curva: cor em cima esmaecendo até o fundo."""
    width, height = max(int(width), 1), max(int(height), 1)
    color_rgb, bg_rgb = _rgb(color), _rgb(bg)
    gradient = Image.new("RGB", (1, height))
    for y in range(height):
        k = top_alpha * (1 - y / height) ** 1.6
        gradient.putpixel((0, y), tuple(round(b + (cc - b) * k) for cc, b in zip(color_rgb, bg_rgb)))
    gradient = gradient.resize((width, height))
    mask = Image.new("L", (width, height), 0)
    poly = [(x, y) for x, y in curve] + [(curve[-1][0], height), (curve[0][0], height)]
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    img = Image.new("RGB", (width, height), bg_rgb)
    img.paste(gradient, (0, 0), mask)
    return ImageTk.PhotoImage(img, master=master)
