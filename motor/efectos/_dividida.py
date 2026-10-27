"""La pantalla dividida (lo comparten los efectos «grafico» y «edicion»; empieza por «_» y no cuenta como efecto).

La pantalla se parte en dos: arriba baja un panel animado y abajo queda tu clip en una tarjeta con las esquinas redondas.
Tu cabeza sale por encima del borde de la tarjeta y queda delante del panel, como si estuvieras de pie entre las dos
pantallas. Al empezar, el cuadro entero se encoge y baja hasta la tarjeta mientras el panel baja desde arriba, con un
pelín de rebote al llegar; al acabar, lo mismo al revés. Detrás de todo, un degradado suave.

La cara nunca queda tapada: el clip se coloca para que lo más alto de la cabeza quede `asoma` píxeles por encima de la
tarjeta, y lo que es persona por encima del borde se pinta delante del panel (el fondo del clip, nunca).

Los dos paneles:
- grafico: barras sobre un panel oscuro (índigo y violeta, con luces magenta, una cuadrícula muy tenue y brillo de
  cristal). Crecen una detrás de otra con un degradado de violeta a rosa y el número de encima va contando («4 h»,
  «1 h 30 min», o «243 mil» sin unidad). La destacada va en dorado con un halo y una insignia que la señala.
- edicion: un panel oscuro de «editando»: el clip en pequeño con su código de tiempo, los pasos que se van marcando, las
  pistas (toma, subtítulos, color y sonido) con un cabezal que avanza y una barra de progreso que acaba en 100 %.
"""
import math

import cv2               # el motor ya lo necesita para leer y guardar el vídeo
import numpy as np
from PIL import Image, ImageDraw

import base as B

# Las opciones que comparten los dos paneles (cada efecto añade las suyas)
COMUNES = {
    # el color de detrás: «auto» (el de cada panel), un color («#1D0F3D») o dos para un degradado («#4C1D95,#1D0F3D»)
    'fondo': 'auto',
    # dónde acaba el panel, en fracción del alto (0,5 = la mitad)
    'alto': '0.5',
    # cuánto se acerca el clip dentro de la tarjeta: «auto» (por el tamaño de la cara) o un número (1 = como está, 1,3…)
    'zoom': 'auto',
    # cuántos píxeles (a 1080 de ancho) sale la cabeza por encima de la tarjeta
    'asoma': '120',
}

# Medidas a 1080 de ancho (se multiplican por u)
PANEL_X0, PANEL_X1, PANEL_Y0 = 50, 1030, 110
HUECO = 22               # entre el panel y la tarjeta
ABAJO = 40               # de la tarjeta al borde de abajo
R_PANEL, R_TARJETA = 36, 40
CARA_OBJETIVO = 215      # el ancho de la cara dentro de la tarjeta con zoom=auto
SOLAPE = 4               # cuánto baja la cabeza que sale por dentro de la tarjeta (tapa el filo del borde)

MORADO = (124, 58, 237)       # #7C3AED
MORADO_HONDO = (46, 16, 101)  # #2E1065
LILA_VIVO = (196, 181, 253)   # #C4B5FD
AMARILLO = (250, 204, 21)     # #FACC15
AMBAR = (245, 158, 11)        # #F59E0B
VERDE = (34, 197, 94)
SS = 4                        # los iconos se dibujan 4 veces más grandes y se reducen: bordes suaves


# ── Curvas y números ────────────────────────────────────────────────────────────────────────────────────────────────
def llegada(x):
    """De 0 a 1 arrancando y frenando suave, con un pelín de rebote al llegar: llega al 80 % del tiempo, se pasa un 1,7 %
    y vuelve a su sitio sin golpe (arranca y acaba quieto)."""
    x = min(1.0, max(0.0, x))
    if x >= 1.0:
        return 1.0
    base = B.suave(x / 0.8)
    s = max(0.0, (x - 0.5) / 0.5)
    return base + 0.018 * math.sin(math.pi * s) ** 2


def numero(v, defecto):
    try:
        return float(str(v).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return defecto


def _decimal(x):
    """10,5 → «10,5»; 10,0 → «10» (una cifra decimal como mucho, con coma)."""
    txt = f'{x:.1f}'
    if txt.endswith('.0'):
        txt = txt[:-2]
    return txt.replace('.', ',')


def cifra(v):
    """Un número como se dice en español, en dos trozos (número, unidad): 1043688 → («1», «M»), 242975 → («243», «mil»),
    9855 → («9,9», «mil»), 850 → («850», «»)."""
    v = max(0.0, float(v))
    if v >= 999_500:
        m = v / 1e6
        return (_decimal(m) if m < 9.95 else f'{m:.0f}'), 'M'
    if v >= 99_950:
        return f'{v / 1000:.0f}', 'mil'
    if v >= 999.5:
        return _decimal(v / 1000), 'mil'
    return f'{v:.0f}', ''


def _erf(x):
    """La función de error (para las sombras): de -1 a 1. Aproximación de Abramowitz y Stegun, error < 2e-7."""
    s = np.sign(x)
    x = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return (s * y).astype(np.float32)


# ── Pegar capas (con decimales: sin saltitos) ───────────────────────────────────────────────────────────────────────
class Rotulo:
    """Un texto listo para colocar: su capa y dónde cae la tinta dentro de ella (para alinear de verdad, no la caja)."""

    def __init__(self, s, tam, peso, relleno, espacio=0.0):
        self.capa = B.texto(s, tam, peso, relleno, espacio=espacio)
        f = B.fuente(peso, tam)
        asc, desc = f.getmetrics()
        self.pad = (self.capa.height - (asc + desc)) / 2          # texto() deja el mismo aire por los cuatro lados
        caja_h = f.getbbox('H')
        self.medio = self.pad + (caja_h[1] + caja_h[3]) / 2        # la mitad de la altura de las mayúsculas
        self.mayus = caja_h[3] - caja_h[1]
        if espacio:
            self.ancho = sum(f.getlength(ch) for ch in s) + espacio * tam * max(0, len(s) - 1)
        else:
            self.ancho = f.getlength(s)
        self.w, self.h = self.capa.size

    def esquina(self, x, y, alinear='izq'):
        """La esquina de la capa para que la tinta empiece en x (o acabe, o se centre) y las mayúsculas queden centradas en
        y. Redondeada: quieto, el texto cae justo en los píxeles (nítido)."""
        if alinear == 'izq':
            x0 = x - self.pad
        elif alinear == 'der':
            x0 = x - self.pad - self.ancho
        else:
            x0 = x - self.pad - self.ancho / 2
        return round(x0), round(y - self.medio)


_PREMULT = {}


def premult(capa):
    """La capa PIL en números (color ya multiplicado por su transparencia, y la transparencia), guardada para no
    convertirla en cada cuadro."""
    clave = id(capa)
    hecho = _PREMULT.get(clave)
    if hecho is None or hecho[0] is not capa:
        arr = np.asarray(capa, np.float32) / 255.0
        a = np.ascontiguousarray(arr[..., 3:4])
        hecho = (capa, arr[..., :3] * a, a)
        if len(_PREMULT) > 600:
            _PREMULT.clear()
        _PREMULT[clave] = hecho
    return hecho[1], hecho[2]


def _desplazar(arr, f, eje):
    """Mueve una capa una fracción de píxel (0 ≤ f < 1) a lo largo de un eje, repartiéndola entre dos píxeles vecinos."""
    forma = list(arr.shape)
    forma[eje] += 1
    out = np.zeros(forma, np.float32)
    if eje == 0:
        out[:-1] += arr * (1 - f)
        out[1:] += arr * f
    else:
        out[:, :-1] += arr * (1 - f)
        out[:, 1:] += arr * f
    return out


def sobre(dest, rgbp, a, x0, y0, alfa=1.0, recorte=None):
    """Pega encima de `dest` (alto × ancho × 3, de 0 a 1) un color premultiplicado con su transparencia (alto × ancho × 1),
    con la esquina en (x0, y0). Con decimales, la capa se reparte entre los píxeles vecinos (sin saltitos).
    `recorte` = (x0, y0, x1, y1): solo pinta dentro. `rgbp=None`: solo oscurece (una sombra)."""
    if alfa <= 0.003:
        return
    xi, yi = int(math.floor(x0)), int(math.floor(y0))
    fx, fy = x0 - xi, y0 - yi
    if fy > 1e-3:
        a = _desplazar(a, fy, 0)
        rgbp = None if rgbp is None else _desplazar(rgbp, fy, 0)
    if fx > 1e-3:
        a = _desplazar(a, fx, 1)
        rgbp = None if rgbp is None else _desplazar(rgbp, fx, 1)
    h, w = a.shape[:2]
    H, W = dest.shape[:2]
    X0, Y0, X1, Y1 = max(0, xi), max(0, yi), min(W, xi + w), min(H, yi + h)
    if recorte is not None:
        X0, Y0 = max(X0, int(math.floor(recorte[0]))), max(Y0, int(math.floor(recorte[1])))
        X1, Y1 = min(X1, int(math.ceil(recorte[2]))), min(Y1, int(math.ceil(recorte[3])))
    if X1 <= X0 or Y1 <= Y0:
        return
    sx, sy = X0 - xi, Y0 - yi
    al = a[sy:sy + Y1 - Y0, sx:sx + X1 - X0]
    zona = dest[Y0:Y1, X0:X1]
    zona *= (1.0 - al * alfa) if alfa < 0.999 else (1.0 - al)
    if rgbp is not None:
        col = rgbp[sy:sy + Y1 - Y0, sx:sx + X1 - X0]
        zona += col * alfa if alfa < 0.999 else col


def pegar_opaco(dest, rgb, a, x0, y0, borde):
    """Como sobre(), para una capa opaca salvo en sus `borde` filas de arriba y de abajo (las esquinas redondas del
    panel): si cae en píxeles enteros, el medio se copia tal cual (mucho más rápido)."""
    if abs(x0 - round(x0)) > 1e-3 or abs(y0 - round(y0)) > 1e-3:
        sobre(dest, rgb, a, x0, y0)
        return
    x0, y0 = int(round(x0)), int(round(y0))
    h, w = a.shape[:2]
    b = min(h // 2, int(math.ceil(borde)) + 1)
    sobre(dest, rgb[:b], a[:b], x0, y0)
    sobre(dest, rgb[h - b:], a[h - b:], x0, y0 + h - b)
    H, W = dest.shape[:2]
    Y0, Y1 = max(0, y0 + b), min(H, y0 + h - b)
    X0, X1 = max(0, x0), min(W, x0 + w)
    if Y1 > Y0 and X1 > X0:
        dest[Y0:Y1, X0:X1] = rgb[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]


def capa(dest, im, x0, y0, alfa=1.0, recorte=None):
    """Pega una imagen PIL RGBA con su esquina en (x0, y0)."""
    rgbp, a = premult(im)
    sobre(dest, rgbp, a, x0, y0, alfa, recorte)


class Hoja:
    """Un lienzo suelto (el del panel) para usar base.poner (que escala y gira) fuera del cuadro."""

    def __init__(self, img):
        self.img = img
        self.H, self.W = img.shape[:2]
        self.mascara = None


def alfa_caja(x0, y0, x1, y1, r, X0, Y0, X1, Y1):
    """La transparencia (de 0 a 1, con el borde suavizado) de un rectángulo de esquinas redondas (x0, y0)–(x1, y1) de radio
    r, medida en los píxeles de la ventana X0..X1 × Y0..Y1. Acepta decimales: así se mueve sin saltitos."""
    xs = np.arange(X0, X1, dtype=np.float32) + 0.5
    ys = np.arange(Y0, Y1, dtype=np.float32) + 0.5
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    r = max(0.0, min(r, hw, hh))
    ax = np.clip(0.5 - (np.abs(xs - cx) - hw), 0, 1)
    ay = np.clip(0.5 - (np.abs(ys - cy) - hh), 0, 1)
    A = np.minimum(ay[:, None], ax[None, :])
    if r > 0.5:                                    # las cuatro esquinas, con su curva
        for sx in (-1, 1):
            for sy in (-1, 1):
                ccx, ccy = cx + sx * (hw - r), cy + sy * (hh - r)
                cols = np.nonzero((xs - ccx) * sx > 0)[0]
                filas = np.nonzero((ys - ccy) * sy > 0)[0]
                if len(cols) and len(filas):
                    c0, c1, f0, f1 = cols[0], cols[-1] + 1, filas[0], filas[-1] + 1
                    dx, dy = xs[c0:c1] - ccx, ys[f0:f1] - ccy
                    d = np.sqrt(dy[:, None] ** 2 + dx[None, :] ** 2) - r
                    A[f0:f1, c0:c1] = np.clip(0.5 - d, 0, 1)
    return A


def rellenar(dest, x0, y0, x1, y1, r, color, opacidad=1.0):
    """Pinta un rectángulo de esquinas redondas de un color liso sobre `dest`."""
    H, W = dest.shape[:2]
    X0, Y0 = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
    X1, Y1 = min(W, int(math.ceil(x1))), min(H, int(math.ceil(y1)))
    if X1 <= X0 or Y1 <= Y0:
        return
    a = alfa_caja(x0, y0, x1, y1, r, X0, Y0, X1, Y1)[..., None] * opacidad
    zona = dest[Y0:Y1, X0:X1]
    zona *= 1 - a
    zona += np.asarray(color, np.float32)[:3] / 255.0 * a


def sombra_caja(dest, x0, y0, x1, y1, sigma, dy, fuerza, tapado=None):
    """La sombra suave de un rectángulo (un rectángulo desenfocado sale exacto con dos curvas: barato aunque se mueva).
    `tapado` = (x0, y0, x1, y1): un trozo que después se tapa entero, y ahí no hace falta oscurecer."""
    if fuerza <= 0.003:
        return
    H, W = dest.shape[:2]
    pad = 3 * sigma
    X0, X1 = max(0, int(math.floor(x0 - pad))), min(W, int(math.ceil(x1 + pad)))
    Y0, Y1 = max(0, int(math.floor(y0 + dy - pad))), min(H, int(math.ceil(y1 + dy + pad)))
    if X1 <= X0 or Y1 <= Y0:
        return
    k = 1.0 / (sigma * math.sqrt(2))
    xs = np.arange(X0, X1, dtype=np.float32) + 0.5
    ys = np.arange(Y0, Y1, dtype=np.float32) + 0.5
    fx = fuerza * 0.5 * (_erf((xs - x0) * k) - _erf((xs - x1) * k))
    fy = 0.5 * (_erf((ys - y0 - dy) * k) - _erf((ys - y1 - dy) * k))

    def oscurecer(a, b, c_, d):
        if b > a and d > c_:
            dest[a:b, c_:d] *= (1.0 - fy[a - Y0:b - Y0, None] * fx[None, c_ - X0:d - X0])[..., None]
    if tapado is None:
        oscurecer(Y0, Y1, X0, X1)
        return
    tx0, ty0 = min(max(X0, int(tapado[0])), X1), min(max(Y0, int(tapado[1])), Y1)
    tx1, ty1 = max(tx0, min(X1, int(tapado[2]))), max(ty0, min(Y1, int(tapado[3])))
    oscurecer(Y0, ty0, X0, X1)
    oscurecer(ty1, Y1, X0, X1)
    oscurecer(ty0, ty1, X0, tx0)
    oscurecer(ty0, ty1, tx1, X1)


def mezclar_en(dest, src, a):
    """dest pasa a src en la medida de a (alto × ancho, de 0 a 1)."""
    d = src - dest
    d *= a[..., None]
    dest += d


# ── Iconos (dibujados aquí, a mano) ─────────────────────────────────────────────────────────────────────────────────
def _bajar(im, d):
    return im.resize((max(1, round(d)), max(1, round(d))), Image.LANCZOS)


def icono_giro(d, u, col):
    """El círculo que gira mientras un paso se está haciendo."""
    D = int(round(d * SS))
    g = 3.6 * u * SS
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, D - 1, D - 1], outline=(255, 255, 255, 60), width=int(round(g)))
    dr.arc([0, 0, D - 1, D - 1], start=-90, end=40, fill=col, width=int(round(g)))
    rr = (D - g) / 2
    for ang in (-90, 40):                                   # las puntas del arco, redondas
        a = math.radians(ang)
        x, y = D / 2 + rr * math.cos(a), D / 2 + rr * math.sin(a)
        dr.ellipse([x - g / 2, y - g / 2, x + g / 2, y + g / 2], fill=col)
    return _bajar(im, d)


def icono_aro(d, u):
    """El paso que falta: un aro apagado."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([0, 0, D - 1, D - 1], outline=(255, 255, 255, 85), width=int(round(2.8 * u * SS)))
    return _bajar(im, d)


def icono_marca(d, p):
    """El círculo verde con la marca dibujada hasta `p` (0–1)."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, D - 1, D - 1], fill=VERDE + (255,))
    if p > 0:
        R = D / 2
        pts = [(D / 2 + x * R, D / 2 + y * R) for x, y in ((-0.40, 0.02), (-0.12, 0.30), (0.42, -0.27))]
        g = 0.19 * R
        largos = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        queda = p * sum(largos)
        dr.ellipse([pts[0][0] - g / 2, pts[0][1] - g / 2, pts[0][0] + g / 2, pts[0][1] + g / 2], fill=(255, 255, 255, 255))
        for i, L in enumerate(largos):
            if queda <= 0:
                break
            k = min(1.0, queda / L)
            a, b = pts[i], pts[i + 1]
            fin = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            dr.line([a, fin], fill=(255, 255, 255, 255), width=int(round(g)))
            dr.ellipse([fin[0] - g / 2, fin[1] - g / 2, fin[0] + g / 2, fin[1] + g / 2], fill=(255, 255, 255, 255))
            queda -= L
    return _bajar(im, d)


def capa_cifra(num, unidad, tam, peso, col_num, col_uni):
    """El número grande y la unidad pequeña («243» + «mil») en una capa, sobre la misma línea de base.
    Devuelve (capa, x de la tinta, y de la línea de base, ancho de la tinta)."""
    f1 = B.fuente(peso, tam)
    f2 = B.fuente('medium', tam * 0.6)
    w1 = f1.getlength(num)
    esp = tam * 0.14 if unidad else 0.0
    w2 = f2.getlength(unidad) if unidad else 0.0
    asc, desc = f1.getmetrics()
    pad = int(math.ceil(tam * 0.12))
    ancho = w1 + esp + w2
    im = Image.new('RGBA', (int(math.ceil(ancho)) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((pad, pad + asc), num, font=f1, fill=col_num, anchor='ls')
    if unidad:
        d.text((pad + w1 + esp, pad + asc), unidad, font=f2, fill=col_uni, anchor='ls')
    return im, pad, pad + asc, ancho


# ── Dónde va cada cosa (se calcula una vez) ─────────────────────────────────────────────────────────────────────────
def _coronilla(c):
    """Lo más alto de la cabeza, en el cuadro: la primera fila en la que la persona llena la franja de la cara (una gorra o
    un peinado alto cuentan; un dedo levantado, no, porque no llena la franja). Si no hay silueta, sale de la cara."""
    cx, cy, ac = (float(v) for v in c.cara)
    por_cara = cy - 1.25 * ac
    x0, x1 = int(max(0, cx - 0.5 * ac)), int(min(c.W, cx + 0.5 * ac))
    if x1 - x0 < 4:
        return max(0.0, por_cara)
    filas = np.nonzero((c.mascara[:, x0:x1] > 0.5).mean(axis=1) > 0.3)[0]
    if not len(filas):
        return max(0.0, por_cara)
    return max(0.0, float(np.clip(filas[0], cy - 2.2 * ac, cy - 0.7 * ac)))


def _fondo(c, spec, oscuro):
    """El fondo de detrás: un degradado suave en diagonal, calculado con decimales y un poquito de grano fijo para que
    no se vean escalones al guardarlo en 8 bits. El «auto» oscuro (el del gráfico) va de índigo hondo a casi negro, con
    una luz magenta muy suave arriba a la derecha."""
    spec = str(spec or 'auto').strip()
    luz = False
    if spec.lower() in ('', 'auto'):
        a, b = ((32, 14, 70), (8, 6, 22)) if oscuro else ((246, 243, 255), (221, 214, 254))
        luz = oscuro
    elif ',' in spec:
        x, y = spec.split(',')[:2]
        a, b = B.color(x)[:3], B.color(y)[:3]
    else:
        base = np.asarray(B.color(spec)[:3], np.float32)
        a = tuple(base + (255 - base) * 0.08)
        b = tuple(base * 0.86)
    a = np.asarray(a, np.float32) / 255.0
    b = np.asarray(b, np.float32) / 255.0
    W, H = c.W, c.H
    xs = np.linspace(0, 1, W, dtype=np.float32)
    ys = np.linspace(0, 1, H, dtype=np.float32)
    g = 0.68 * (1 - ys)[:, None] + 0.32 * xs[None, :]        # 1 arriba a la derecha, 0 abajo a la izquierda
    g = g * g * (3 - 2 * g)
    img = b + (a - b) * g[..., None]
    if luz:
        k = 0.24 * np.exp(-(((xs[None, :] - 0.92) / 0.55) ** 2 + ((ys[:, None] - 0.0) / 0.32) ** 2))
        img = 1 - (1 - img) * (1 - (np.float32([217, 70, 239]) / 255.0) * k[..., None])
    rng = np.random.default_rng(11)
    img += (rng.random((H, W, 1), dtype=np.float32) - 0.5) * (1.0 / 255.0)
    return img


def _preparar(c, tipo):
    u, W, H = c.u, c.W, c.H
    op = c.op
    L = {'tipo': tipo}
    alto = min(0.7, max(0.3, numero(op.get('alto'), 0.5)))
    asoma = min(400.0, max(0.0, numero(op.get('asoma'), 120))) * u
    L['entra'] = min(0.45, 0.25 * c.dur)
    L['sale'] = min(0.32, 0.2 * c.dur)

    # el panel y la tarjeta (en píxeles enteros: quietos, nítidos)
    px0, px1, py0 = round(PANEL_X0 * u), round(PANEL_X1 * u), round(PANEL_Y0 * u)
    py1 = round(alto * H)
    L.update(px0=px0, px1=px1, py0=py0, py1=py1, pw=px1 - px0, ph=py1 - py0)
    kx0, kx1 = px0, px1
    ky0, ky1 = py1 + round(HUECO * u), H - round(ABAJO * u)
    L.update(kx0=kx0, kx1=kx1, ky0=ky0, ky1=ky1, kr=R_TARJETA * u)
    L['zona'] = ky0 - py0                    # hasta dónde puede salir la persona por encima de la tarjeta

    # el clip dentro de la tarjeta: lo más alto de la cabeza, `asoma` por encima del borde, y la cara centrada
    cx, cy, ac = (float(v) for v in c.cara)
    arriba = _coronilla(c)
    z = str(op.get('zoom', 'auto')).strip().lower()
    s = numero(z, 0.0) if z not in ('', 'auto') else CARA_OBJETIVO * u / max(ac, 1.0)
    s = min(2.5, max(1.0, s))
    s = max(s, (ky1 - ky0 + asoma) / max(1.0, H - arriba))    # que el clip llegue hasta abajo de la tarjeta
    tx = (kx0 + kx1) / 2 - s * cx
    tx = min(kx0, max(kx1 - s * W, tx))
    ty = ky0 - asoma - s * arriba
    L.update(s=s, tx=tx, ty=ty)
    L['fondo'] = _fondo(c, op.get('fondo'), oscuro=(tipo == 'grafico'))
    L['sombra_panel'] = 0.50 if tipo == 'grafico' else 0.30
    L['sombra_tarjeta'] = 0.45 if tipo == 'grafico' else 0.30
    # quieto, el fondo con sus dos sombras no cambia: se hace una vez, y cada cuadro solo se copia lo que se ve de él
    bp, bk = int(math.ceil(R_PANEL * u)) + 1, int(math.ceil(R_TARJETA * u)) + 1
    L['tapa_panel'], L['tapa_tarjeta'] = bp, bk
    quieto = L['fondo'].copy()
    sombra_caja(quieto, kx0, ky0, kx1, ky1, 26 * u, 16 * u, L['sombra_tarjeta'], (kx0, ky0 + bk, kx1, ky1 - bk))
    sombra_caja(quieto, px0, py0, px1, py1, 26 * u, 14 * u, L['sombra_panel'], (px0, py0 + bp, px1, py1 - bp))
    L['fondo_quieto'] = quieto
    trozos = [(0, py0 + bp, 0, W), (py0 + bp, py1 - bp, 0, px0), (py0 + bp, py1 - bp, px1, W),
              (py1 - bp, ky0 + bk, 0, W), (ky0 + bk, ky1 - bk, 0, kx0), (ky0 + bk, ky1 - bk, kx1, W), (ky1 - bk, H, 0, W)]
    L['trozos'] = [(a, b, c_, d) for a, b, c_, d in trozos if b > a and d > c_]
    if tipo == 'grafico':
        _preparar_grafico(c, L, asoma)
    else:
        _preparar_edicion(c, L)
    c.estado['dividida'] = L
    return L


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def dibujar(c, tipo):
    L = c.estado.get('dividida') or _preparar(c, tipo)
    u, W, H = c.u, c.W, c.H
    p = min(llegada(B.tramo(c.t, 0, L["entra"])), llegada(B.tramo(c.queda, 0, L["sale"])))
    if p <= 1e-4:
        return                                              # al principio y al final, el cuadro tal cual
    quieto = p == 1.0

    # dónde está todo en este momento (p = 0: el cuadro entero; p = 1: en su sitio)
    s = 1 + (L['s'] - 1) * p
    tx, ty = L['tx'] * p, L['ty'] * p
    rx0, ry0 = L['kx0'] * p, L['ky0'] * p
    rx1, ry1 = W + (L['kx1'] - W) * p, H + (L['ky1'] - H) * p
    rr = L['kr'] * min(1.0, p)
    xa, xb = max(0, int(math.floor(rx0))), min(W, int(math.ceil(rx1)))
    yb = min(H, int(math.ceil(ry1)))

    def matriz(X0, Y0):
        return np.float32([[s, 0, tx - X0], [0, s, ty - Y0]])

    # 1. lo que de la persona queda por encima del borde de la tarjeta (eso se pinta delante del panel). Baja `SOLAPE` px
    #    por DENTRO de la tarjeta: así la cabeza tapa también el filo del borde (sin eso, en la fila del borde la persona
    #    y la tarjeta quedaban a medias y se colaba el fondo: una raya que cruzaba la gorra). Dentro de la tarjeta el clip
    #    es el mismo, así que el solape no se ve.
    sale_arriba = None
    solape = SOLAPE * u
    ya = max(0, int(math.floor(ry0)))
    z0 = max(0, int(math.floor(ry0 - L['zona'] * min(1.0, p))))
    z1 = min(H, int(math.ceil(ry0 + solape + 2 * u)) + 1)
    if z1 > z0 + 1:
        M = cv2.warpAffine(c.mascara, matriz(xa, z0), (xb - xa, z1 - z0), flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        ys = np.arange(z0, z1, dtype=np.float32) + 0.5
        arriba = np.clip((ry0 + solape - ys) / (2 * u) + 0.5, 0, 1)  # 1 hasta el solape, 0 más abajo (suave)
        xs = np.arange(xa, xb, dtype=np.float32) + 0.5
        dentro = np.clip(np.minimum(xs - rx0, rx1 - xs) + 0.5, 0, 1)
        M *= arriba[:, None]
        M *= dentro[None, :]
        filas = np.nonzero(M.max(axis=1) > 0.004)[0]
        if len(filas):
            ya = z0 + int(filas[0])
            sale_arriba = M[filas[0]:]

    # 2. el clip, colocado (antes de pisar el cuadro) y, en el panel de edición, el clip en pequeño
    clip = cv2.warpAffine(c.img, matriz(xa, ya), (xb - xa, yb - ya), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)
    mini = mini_clip(c, L) if L['tipo'] == 'edicion' else None

    # 3. el fondo, las sombras y el panel
    off = (L['py1'] + 70 * u) * (p - 1)                     # el panel baja pegado encima de la tarjeta
    py = L['py0'] + off
    bp = L['tapa_panel']
    if quieto:
        f = L['fondo_quieto']
        for a, b, x0, x1 in L['trozos']:
            c.img[a:b, x0:x1] = f[a:b, x0:x1]
    else:
        np.copyto(c.img, L['fondo'])
        sombra_caja(c.img, rx0, ry0, rx1, ry1, 26 * u, 16 * u, L['sombra_tarjeta'] * min(1.0, p) ** 2,
                    (math.ceil(rx0) + 1, math.ceil(ry0 + rr) + 1, math.floor(rx1) - 1, math.floor(ry1 - rr) - 1))
        if py + L['ph'] > 0:
            sombra_caja(c.img, L['px0'], py, L['px1'], py + L['ph'], 26 * u, 14 * u, L['sombra_panel'],
                        (L['px0'], math.ceil(py) + bp, L['px1'], math.floor(py + L['ph']) - bp))
    if py + L['ph'] > 0:
        lienzo = L['panel_rgb'].copy()
        if L['tipo'] == 'grafico':
            pintar_grafico(c, L, lienzo)
        else:
            pintar_edicion(c, L, lienzo, mini)
        pegar_opaco(c.img, lienzo, L['panel_a'], L['px0'], py, bp)

    # 4. una sombra suave alrededor de la cabeza que sale (la separa del panel)
    if sale_arriba is not None:
        sg = 12 * u
        pad = int(3 * sg)
        y0, y1 = max(0, ya - pad), min(H, ya + len(sale_arriba) + pad)
        bh, bw_ = -(-(y1 - y0) // 4) * 4, -(-(xb - xa) // 4) * 4    # múltiplos de 4: reducir así es rapidísimo
        buf = np.zeros((bh, bw_), np.float32)
        buf[ya - y0:ya - y0 + len(sale_arriba), :xb - xa] = sale_arriba
        peq = cv2.resize(buf, (bw_ // 4, bh // 4), interpolation=cv2.INTER_AREA)
        peq = cv2.GaussianBlur(peq, (0, 0), sg / 4)            # se desenfoca pequeño (es suave: no se nota) y se agranda
        buf = cv2.resize(peq, (bw_, bh), interpolation=cv2.INTER_LINEAR)[:y1 - y0, :xb - xa]
        c.img[y0:y1, xa:xb] *= (1.0 - 0.32 * buf)[..., None]

    # 5. el clip en su tarjeta, y la persona por encima del borde
    ra = max(ya, int(math.floor(ry0)))
    clave = (ra, yb, xa, xb)
    if quieto and L.get('R_clave') == clave:
        R = L['R']
    else:
        R = alfa_caja(rx0, ry0, rx1, ry1, rr, xa, ra, xb, yb)
        if quieto:
            L['R'], L['R_clave'] = R, clave
    # por dentro (lejos de las esquinas y de lo que sale) se copia tal cual; el resto se mezcla
    iy0 = max(ra, int(math.ceil(ry0 + rr + 1)), ya + (len(sale_arriba) if sale_arriba is not None else 0))
    iy1 = max(iy0, min(yb, int(math.floor(ry1 - rr - 1))))
    ix0, ix1 = min(xb, int(math.ceil(rx0 + 1))), max(xa, int(math.floor(rx1 - 1)))
    if iy0 > ya:                                            # la banda de arriba
        A = np.zeros((iy0 - ya, xb - xa), np.float32)
        if iy0 > ra:
            A[ra - ya:] = R[:iy0 - ra]
        banda = clip[:iy0 - ya]
        if sale_arriba is not None:
            n = len(sale_arriba)
            np.maximum(A[:n], sale_arriba, out=A[:n])
            # la cabeza que sale va con su color de verdad en el filo (`base.color_persona`): si no, el fondo de la toma
            # deja un filo de pared alrededor de la gorra encima del panel. Dentro de la tarjeta, el clip tal cual.
            Mb = cv2.warpAffine(c.mascara, matriz(xa, ya), (xb - xa, iy0 - ya), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            Fb, _ = B.color_persona(banda, Mb, u)
            Rb = np.zeros_like(A)
            if iy0 > ra:
                Rb[ra - ya:] = R[:iy0 - ra]
            Rb = Rb[..., None]
            banda = banda * Rb + Fb * (1.0 - Rb)
        mezclar_en(c.img[ya:iy0, xa:xb], banda, A)
    if iy1 > iy0:                                           # el medio: los dos bordes se mezclan, el centro se copia
        if ix0 > xa:
            mezclar_en(c.img[iy0:iy1, xa:ix0], clip[iy0 - ya:iy1 - ya, :ix0 - xa], R[iy0 - ra:iy1 - ra, :ix0 - xa])
        if ix1 > ix0:
            c.img[iy0:iy1, ix0:ix1] = clip[iy0 - ya:iy1 - ya, ix0 - xa:ix1 - xa]
        if xb > ix1:
            mezclar_en(c.img[iy0:iy1, ix1:xb], clip[iy0 - ya:iy1 - ya, ix1 - xa:], R[iy0 - ra:iy1 - ra, ix1 - xa:])
    if yb > iy1:                                            # la banda de abajo
        mezclar_en(c.img[iy1:yb, xa:xb], clip[iy1 - ya:], R[iy1 - ra:])


# ── Panel 1: el gráfico de barras ───────────────────────────────────────────────────────────────────────────────────
INDIGO = (79, 70, 229)        # #4F46E5
FUCSIA = (217, 70, 239)       # #D946EF
ROSA = (244, 114, 182)        # #F472B6
LILA_CLARO = (216, 180, 254)  # #D8B4FE
ORO = (252, 211, 77)          # #FCD34D
NARANJA = (251, 146, 60)      # #FB923C
TINTA_HONDA = (40, 14, 70)    # el texto sobre la insignia dorada
UNI, ESP_UNI, ESP_TROZO = 0.55, 0.1, 0.24   # en las cifras: la unidad (en proporción al número) y los espacios
HUECO_BARRAS, LADO_BARRAS = 0.6, 0.12       # el hueco entre barras y el margen a los lados, en anchos de barra


def leer_datos(s):
    """«etiqueta:número|…» → [(etiqueta, número)]."""
    out = []
    for trozo in str(s or '').split('|'):
        etiqueta, _, num = trozo.rpartition(':')
        if not etiqueta.strip():
            continue
        limpio = num.strip().replace(' ', '').replace('.', '').replace(',', '.')
        try:
            out.append((etiqueta.strip(), max(0.0, float(limpio))))
        except ValueError:
            continue
    return out or [('A', 3.0), ('B', 2.0), ('C', 1.0)]


def tiempo(v):
    """Minutos como se leen en español, en trozos (número, unidad): 240 → «4 h», 90 → «1 h 30 min», 45 → «45 min»,
    0,5 → «30 s». De un minuto para arriba va en minutos enteros."""
    v = max(0.0, float(v))
    if v * 60 < 59.5:
        return [(f'{v * 60:.0f}', 's')]
    h, m = divmod(int(round(v)), 60)
    out = [(str(h), 'h')] if h else []
    if m or not h:
        out.append((str(m), 'min'))
    return out


def trozos_de(v, unidad):
    """Un valor en trozos (número, unidad): con unidad «min», como tiempo(); sin unidad, como cifra() («243 mil»)."""
    return tiempo(v) if unidad == 'min' else [cifra(v)]


def capa_trozos(trozos, tam, peso, col_num, col_uni):
    """Los trozos («1» «h» «30» «min») en una capa sobre la misma línea de base: el número grande y la unidad pequeña.
    Devuelve (capa, x de la tinta, y de la línea de base, ancho de la tinta)."""
    f1, f2 = B.fuente(peso, tam), B.fuente('medium', tam * UNI)
    piezas, x = [], 0.0
    for k, (num, uni) in enumerate(trozos):
        if k:
            x += tam * ESP_TROZO
        piezas.append((x, num, f1, col_num))
        x += f1.getlength(num)
        if uni:
            x += tam * ESP_UNI
            piezas.append((x, uni, f2, col_uni))
            x += f2.getlength(uni)
    asc, desc = f1.getmetrics()
    pad = int(math.ceil(tam * 0.12))
    im = Image.new('RGBA', (int(math.ceil(x)) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x0, s, f, col in piezas:
        d.text((pad + x0, pad + asc), s, font=f, fill=col, anchor='ls')
    return im, pad, pad + asc, x


def ancho_trozos(trozos, peso, tabular=False):
    """Lo que ocupa a lo ancho capa_trozos a tamaño 1. `tabular`: como si todas las cifras fueran igual de anchas (las
    de Poppins no lo son: un «1» es mucho más estrecho que un «0»)."""
    f1, f2 = B.fuente(peso, 100), B.fuente('medium', 100 * UNI)
    x = 0.0
    for k, (num, uni) in enumerate(trozos):
        if tabular:
            ancho_num = sum(f1.getlength('0') if ch.isdigit() else f1.getlength(ch) for ch in num)
        else:
            ancho_num = f1.getlength(num)
        x += (100 * ESP_TROZO if k else 0) + ancho_num + (100 * ESP_UNI + f2.getlength(uni) if uni else 0)
    return x / 100.0


def _partir(s, largo):
    """Un texto en una o dos líneas, cortando por el espacio que deja las dos líneas más parejas."""
    palabras = s.split()
    if len(palabras) < 2:
        return [s]
    mejor, ancho = [s], largo(s)
    for k in range(1, len(palabras)):
        a, b = ' '.join(palabras[:k]), ' '.join(palabras[k:])
        w = max(largo(a), largo(b))
        if w < ancho:
            mejor, ancho = [a, b], w
    return mejor


def _dos_colores(spec, defecto):
    """«#abajo,#arriba» → los dos colores del degradado (de 0 a 1). Con un solo color, abajo va algo más hondo y arriba
    más claro."""
    try:
        cols = [np.asarray(B.color(x)[:3], np.float32) / 255 for x in str(spec or defecto).split(',')[:2] if x.strip()]
    except ValueError:
        cols = []
    if not cols:
        return _dos_colores(defecto, defecto)
    if len(cols) == 1:
        return cols[0] * 0.8, cols[0] + (1 - cols[0]) * 0.35
    return cols[0], cols[1]


def _que_destacar(spec, datos):
    """Qué barra va destacada: «ultima» (la de fábrica), «menor», «mayor», un número (0 = la primera) o «ninguna»/-1."""
    s = str(spec if spec is not None else 'ultima').strip().lower()
    n = len(datos)
    if s in ('ultima', 'última', 'ultimo', 'último', 'last'):
        return n - 1
    if s in ('menor', 'minimo', 'mínimo', 'min'):
        return min(range(n), key=lambda i: datos[i][1])
    if s in ('mayor', 'maximo', 'máximo', 'max'):
        return max(range(n), key=lambda i: datos[i][1])
    d = int(numero(s, -1))
    return d if 0 <= d < n else -1


def _grano(forma, semilla):
    """Medio nivel de grano fijo (de un vídeo de 8 bits): los degradados no hacen escalones al guardarse."""
    return (np.random.default_rng(semilla).random(forma, dtype=np.float32) - 0.5) * np.float32(1.0 / 255.0)


def _pantalla(rgb, col, k):
    """Mezcla en modo «pantalla» (aclara como una luz): rgb ← 1 − (1 − rgb)·(1 − col·k). k: alto × ancho."""
    rgb[:] = 1 - (1 - rgb) * (1 - (np.asarray(col, np.float32) / 255.0) * k[..., None])


def _panel_grafico(pw, ph, u):
    """El fondo del panel: un degradado hondo (índigo arriba, violeta abajo) con luces suaves (violeta arriba a la
    izquierda, magenta abajo a la derecha), una cuadrícula muy tenue, un reflejo de cristal en diagonal y un filo de luz.
    Todo con decimales y con grano fijo. → (rgb ya multiplicado por su transparencia, transparencia)."""
    X = (np.arange(pw, dtype=np.float32) + 0.5)[None, :]
    Y = (np.arange(ph, dtype=np.float32) + 0.5)[:, None]
    x, y = X / pw, Y / ph
    k = (y * y * (3 - 2 * y))[..., None]
    arriba, abajo = np.float32([19, 12, 46]) / 255, np.float32([25, 9, 50]) / 255
    rgb = np.repeat(arriba + (abajo - arriba) * k, pw, axis=1)

    def luz(cx, cy, rx, ry, col, fuerza):
        _pantalla(rgb, col, fuerza * np.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)))
    luz(0.06, -0.10, 0.72, 0.60, MORADO, 0.38)
    luz(0.98, 1.10, 0.60, 0.52, FUCSIA, 0.32)
    luz(0.45, 0.50, 0.55, 0.45, INDIGO, 0.08)

    # la cuadrícula, muy tenue (algo más arriba que abajo)
    paso, g = 54 * u, 1.2 * u

    def perfil(n):
        t = np.arange(n, dtype=np.float32) + 0.5
        d = np.abs(((t - paso / 2) % paso) - paso / 2)
        return np.clip(g / 2 + 0.5 - d, 0, 1)
    rejilla = np.maximum(perfil(ph)[:, None], perfil(pw)[None, :]) * (0.05 - 0.022 * y)
    rgb += (1 - rgb) * rejilla[..., None]

    # el reflejo del cristal: una banda en diagonal muy suave y un poco más de luz arriba del todo
    d = (X + 0.9 * Y) / (pw + 0.9 * ph)
    _pantalla(rgb, (255, 255, 255), 0.05 * np.exp(-((d - 0.30) / 0.11) ** 2) + 0.045 * (1 - y) ** 5)

    # el filo de luz del borde (más claro arriba)
    A = alfa_caja(0, 0, pw, ph, R_PANEL * u, 0, 0, pw, ph)
    e = 1.6 * u
    filo = A - alfa_caja(e, e, pw - e, ph - e, R_PANEL * u - e, 0, 0, pw, ph)
    rgb += (np.float32([0.93, 0.89, 1.0]) - rgb) * (filo * (0.36 - 0.26 * y))[..., None]

    rgb += _grano((ph, pw, 1), 7)
    A = A[..., None]
    rgb *= A
    return rgb, A


def _capa_barra(bw, alto, r, abajo, arriba, u, semilla):
    """Una barra con las esquinas de arriba redondas y un degradado vertical (de `abajo` a `arriba`), con su brillo de
    cristal: una franja de luz a la izquierda, el canto derecho algo más hondo y un filo claro arriba. → (rgbp, a)"""
    alto = max(1, int(round(alto)))
    a = alfa_caja(0, 0, bw, alto + r + 2, r, 0, 0, bw, alto)      # la caja sigue por debajo: abajo queda recta
    yy = (np.arange(alto, dtype=np.float32) + 0.5)[:, None]
    xx = (np.arange(bw, dtype=np.float32) + 0.5)[None, :] / bw
    k = (1 - yy / alto)[..., None]
    col = np.repeat(abajo + (arriba - abajo) * k, bw, axis=1)
    _pantalla(col, (255, 255, 255), np.broadcast_to(0.24 * np.exp(-((xx - 0.26) / 0.12) ** 2), (alto, bw)))
    col *= (1 - 0.2 * np.clip((xx - 0.7) / 0.3, 0, 1) ** 1.5)[..., None]
    _pantalla(col, (255, 255, 255), np.broadcast_to(0.32 * np.exp(-yy / (4 * u)), (alto, bw)))
    col += _grano((alto, bw, 1), semilla)
    a = a[..., None]
    return np.ascontiguousarray(np.clip(col, 0, 1) * a), np.ascontiguousarray(a)


def _degradar(capa_, c0, c1):
    """Un texto (capa RGBA) pintado con un degradado de izquierda (c0) a derecha (c1)."""
    arr = np.asarray(capa_, np.float32)
    w = arr.shape[1]
    k = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
    col = np.asarray(c0, np.float32) + (np.asarray(c1, np.float32) - np.asarray(c0, np.float32)) * k
    out = np.concatenate([np.broadcast_to(col, arr.shape[:2] + (3,)), arr[..., 3:4]], axis=2)
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), 'RGBA')


def _trazo(ancho, grosor, col, u):
    """El subrayado de rotulador: una pincelada que se afina en las puntas y sube un pelín hacia la derecha."""
    k = SS
    pad = grosor
    W, H = int(math.ceil(ancho + 2 * pad)), int(math.ceil(grosor * 2.6 + 2 * pad))
    im = Image.new('RGBA', (W * k, H * k), (0, 0, 0, 0))
    n = 60
    arriba_, abajo_ = [], []
    for i in range(n + 1):
        t = i / n
        x = pad + t * ancho
        yc = pad + grosor * 1.3 - grosor * 0.55 * t + grosor * 0.18 * math.sin(t * math.pi * 1.6)
        g = grosor * (0.35 + 0.65 * math.sin(math.pi * min(1.0, t / 0.12) / 2) * math.sin(
            math.pi * min(1.0, (1 - t) / 0.2) / 2))
        arriba_.append((x * k, (yc - g / 2) * k))
        abajo_.append((x * k, (yc + g / 2) * k))
    ImageDraw.Draw(im).polygon(arriba_ + abajo_[::-1], fill=col)
    return im.resize((W, H), Image.LANCZOS), pad, pad + grosor * 1.3


def _insignia(texto_, tam, u):
    """La pastilla dorada que señala la barra destacada, con su piquito abajo. → (capa, alto hasta la punta)"""
    rt = Rotulo(texto_, tam, 'bold', TINTA_HONDA + (255,))
    h = int(round(tam * 1.85))
    w = int(round(rt.ancho + tam * 1.3))
    pico = int(round(tam * 0.42))
    k = SS
    im = Image.new('RGBA', (w * k, (h + pico) * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=h * k / 2, fill=ORO + (255,))
    cx = w * k / 2
    d.polygon([(cx - pico * 1.1 * k, h * k - 2 * k), (cx + pico * 1.1 * k, h * k - 2 * k), (cx, (h + pico) * k - 1)],
              fill=ORO + (255,))
    im = im.resize((w, h + pico), Image.LANCZOS)
    im.alpha_composite(rt.capa, rt.esquina(w / 2, h / 2, 'centro'))
    return im


def _preparar_grafico(c, L, asoma):
    u, op = c.u, c.op
    pw, ph = L['pw'], L['ph']
    datos = leer_datos(op.get('datos'))
    n = len(datos)
    unidad = str(op.get('unidad') or '').strip().lower()
    unidad = 'min' if unidad in ('min', 'mins', 'minuto', 'minutos') else ''
    L['unidad'] = unidad
    PAD, ARRIBA = 46 * u, 46 * u
    L['dest'] = dest = _que_destacar(op.get('destacar'), datos)
    abajo, arriba = _dos_colores(op.get('color'), '#6D28D9,#EC4899')
    abajo_d, arriba_d = _dos_colores(op.get('color_destacado'), '#F97316,#FDE68A')
    titulo = str(op.get('titulo') or '').replace('{n}', str(n))
    t1, _, t2 = titulo.partition('/')
    t1, t2 = t1.strip(), t2.strip()

    util = pw - 2 * PAD
    vmax = max(v for _, v in datos) or 1.0
    fr = [v / vmax for _, v in datos]

    # a lo ancho: las barras, todas iguales y juntas en el centro; el hueco entre dos es el 60 % de una barra y a los
    # lados queda un 12 %. Con pocas barras salen anchas (con 2, unos 310 px a 1080) y sin huecos grandes a los lados
    bw = int(round(min(util / (n + (n - 1) * HUECO_BARRAS + 2 * LADO_BARRAS), 340 * u)))
    hueco_b = HUECO_BARRAS * bw
    x_ini = PAD + (util - n * bw - (n - 1) * hueco_b) / 2
    cxs = [x_ini + bw / 2 + i * (bw + hueco_b) for i in range(n)]
    celda = bw + hueco_b if n > 1 else util                # lo que pueden ocupar a lo ancho su número y su etiqueta
    pocas = n <= 3                                         # con pocas barras, los números y las letras, más grandes

    # los números: el mismo tamaño para todos (el que quepa mientras cuentan) y el destacado algo más grande
    def mas_ancho(v, peso):
        return max(ancho_trozos(trozos_de(v * e, unidad), peso) for e in np.linspace(0, 1, 97))
    anchos = [mas_ancho(v, 'extrabold') for _, v in datos]
    tam_max = max(56.0, min(76.0, 88.0 - 7.0 * n)) * u
    tam_num = min(tam_max, min((celda - 12 * u) / max(w, 1e-3) for w in anchos))
    tams = [tam_num] * n
    if dest >= 0:
        tams[dest] = min(tam_num * 1.2, (celda * 1.1) / max(anchos[dest], 1e-3))
    gap_num = round(14 * u)

    def alto_num(tam):
        caja_ = B.fuente('extrabold', tam).getbbox('0')
        return caja_[3] - caja_[1] + gap_num

    # la insignia de la destacada (encima de su número)
    texto_ins = str(op.get('insignia') or '').strip()
    L['insignia'] = _insignia(texto_ins, (30 if pocas else 27) * u, u) if (texto_ins and dest >= 0) else None
    alto_ins = L['insignia'].height + 12 * u if L['insignia'] is not None else 0.0

    # las etiquetas de abajo: en una o dos líneas, todas al mismo tamaño (≥ 30 px a 1080 si caben)
    f100 = B.fuente('medium', 100)
    largo = lambda s_: f100.getlength(s_) / 100.0                                  # noqa: E731
    tam_lab = (36 if pocas else 32) * u
    lineas = []
    for et, _ in datos:
        ls = [et] if largo(et) * tam_lab <= celda - 12 * u else _partir(et, largo)
        lineas.append(ls)
    mas_ancha = max(largo(x) for ls in lineas for x in ls)
    tam_lab = min(tam_lab, (celda - 10 * u) / max(mas_ancha, 1e-3))
    filas_lab = max(len(ls) for ls in lineas)
    paso_lab = 1.2 * tam_lab
    zona_cabeza = max(0.0, asoma - HUECO * u) + 18 * u      # abajo del panel queda sitio para la cabeza que sale
    y_base = int(round(ph - zona_cabeza - filas_lab * paso_lab - 16 * u))

    # el título: arriba a la izquierda, encima de todo, o arriba a la derecha (si así las barras pueden subir más)
    def titulo_en(tam):
        r1 = Rotulo(t1, tam, 'extrabold', (255, 255, 255, 255))
        r2 = Rotulo(t2, tam, 'extrabold', (255, 255, 255, 255)) if t2 else None
        c1 = ARRIBA + r1.mayus / 2
        c2 = c1 + 1.16 * tam if r2 else c1
        fondo_t = c2 + r1.mayus / 2 + (0.42 * tam if r2 else 0.2 * tam)
        ancho = max(r1.ancho, r2.ancho if r2 else 0)
        return r1, r2, c1, c2, fondo_t, ancho

    def alto_max(x_t, fondo_t):
        mejor = 1e9
        for i in range(n):
            if fr[i] <= 0:
                continue
            derecha = cxs[i] + max(bw, anchos[i] * tams[i], L['insignia'].width if (
                i == dest and L['insignia'] is not None) else 0) / 2
            bajo_titulo = derecha > x_t - 14 * u
            tope = fondo_t + 16 * u if bajo_titulo else ARRIBA * 0.6
            extra = alto_ins if i == dest else 0.0
            mejor = min(mejor, (y_base - tope - alto_num(tams[i]) - extra) / fr[i])
        return mejor

    w100 = max(B.fuente('extrabold', 100).getlength(t1), B.fuente('extrabold', 100).getlength(t2) if t2 else 0) / 100
    w100 = max(w100, 1e-3)
    tam_b = min(66 * u, util / w100)
    tb = titulo_en(tam_b)
    h_b = alto_max(-1e9, tb[4])
    # a la derecha, dos tamaños posibles: el de siempre y el que deja libre la barra más alta (si no queda muy pequeño)
    i_alta = max(range(n), key=lambda i: fr[i])
    libre = pw - PAD - (cxs[i_alta] + max(bw, anchos[i_alta] * tams[i_alta]) / 2 + 36 * u)
    mejor_a = None
    for tam in {min(66 * u, 0.6 * util / w100), min(66 * u, libre / w100)}:
        if tam < 44 * u:
            continue
        ta = titulo_en(tam)
        x_a = pw - PAD - ta[5]
        h_a = alto_max(x_a, ta[4])
        if mejor_a is None or h_a > mejor_a[0]:
            mejor_a = (h_a, ta, x_a)
    if mejor_a is not None and mejor_a[0] > 1.1 * h_b:
        h_a, ta, x_a = mejor_a
        r1, r2, c1, c2, _, _ = ta
        x_t, hmax = x_a, h_a
    else:
        r1, r2, c1, c2, _, _ = tb
        x_t, hmax = PAD, h_b
    hmax = max(40 * u, hmax)

    # el panel quieto: el fondo y la primera línea del título
    rgb, a = _panel_grafico(pw, ph, u)
    capa(rgb, r1.capa, *r1.esquina(x_t, c1))
    L['t2'] = None
    if r2:
        # la segunda línea, con un degradado de rosa a lila, y su subrayado de rotulador (se dibuja al llegar)
        L['t2'] = (_degradar(r2.capa, ROSA, LILA_CLARO), r2.esquina(x_t, c2))
        grosor = 0.21 * r2.mayus / 0.7
        tr, tpad, tmed = _trazo(r2.ancho + 8 * u, grosor, FUCSIA + (235,), u)
        L['marcador'] = (tr, round(x_t - 4 * u - tpad), round(c2 + r2.mayus / 2 + 0.24 * r2.mayus / 0.7 - tmed))

    # las barras, sus etiquetas y su reflejo en el suelo
    minimo = 24 * u                                       # las muy pequeñas se quedan con este alto para que se vean
    refl = int(round(30 * u))
    barras, etiquetas = [], []
    for i, ((et, v), ls) in enumerate(zip(datos, lineas)):
        cxb = cxs[i]
        es = i == dest
        for k_, linea in enumerate(ls):
            rt = Rotulo(linea, tam_lab, 'bold' if es else 'medium', (ORO + (255,)) if es else (255, 255, 255, 205))
            etiquetas.append((rt.capa, rt.esquina(cxb, y_base + 20 * u + rt.mayus / 2 + k_ * paso_lab, 'centro')))
        alto_b = max(round(minimo), round(hmax * fr[i]))
        r = max(1, int(min(max(18 * u, 0.08 * bw), bw / 2, alto_b / 2)))
        if es:
            ab, ar = abajo_d, arriba_d
        else:
            ab, ar = abajo, abajo + (arriba - abajo) * (0.35 + 0.65 * alto_b / hmax)
        # el reflejo: un charco del color de abajo de la barra que se apaga hacia abajo
        kk = (1 - (np.arange(refl, dtype=np.float32) + 0.5) / refl) ** 2
        ra = np.repeat((0.2 * kk)[:, None, None], bw, axis=1)
        barras.append({'x0': int(round(cxb - bw / 2)), 'cx': cxb, 'alto': alto_b, 'v': v, 'dest': es,
                       'capa': _capa_barra(bw, alto_b, r, ab, ar, u, 20 + i), 'tam': tams[i],
                       'refl': (ab * ra, ra)})
    L['panel_rgb'], L['panel_a'] = rgb, a
    L['barras'], L['etiquetas'], L['y_base'], L['gap_num'], L['refl'] = barras, etiquetas, y_base, gap_num, refl
    linea = np.empty((max(1, round(2 * u)), int(round(util + 12 * u)), 3), np.float32)
    linea[:] = 1.0
    L['linea_base'] = (linea * 0.24, np.full(linea.shape[:2] + (1,), 0.24, np.float32), round(PAD - 6 * u))
    L['cifras'] = {}

    # el halo de la barra destacada (sale cuando termina de crecer)
    if dest >= 0:
        bd = barras[dest]
        sg = max(24 * u, 0.1 * bw)
        pad = int(3 * sg)
        forma = np.zeros((bd['alto'] + 2 * pad, bw + 2 * pad), np.float32)
        forma[pad:pad + bd['alto'], pad:pad + bw] = bd['capa'][1][..., 0]
        brillo = cv2.GaussianBlur(forma, (0, 0), sg)
        brillo = np.clip(brillo / max(1e-3, float(brillo.max())), 0, 1)[..., None] * 0.62
        halo = np.asarray(NARANJA, np.float32) / 255.0 * brillo + _grano(brillo.shape, 31) * brillo
        L['brillo'] = (halo, brillo, bd['x0'] - pad, y_base - bd['alto'] - pad)

    # cuándo crece cada barra (cabe en lo que dura el efecto; si hay insignia, queda un rato quieto para leerla)
    t0 = L['entra'] * 0.9
    t_fin = max(t0 + 0.5, c.dur - L['sale'] - (0.85 if L['insignia'] is not None else 0.55))
    crece = min(0.7, max(0.3, 0.4 * (t_fin - t0)))
    paso = (t_fin - t0 - crece) / max(1, n - 1)
    if paso < 0:
        crece, paso = t_fin - t0, 0.0
    L['tiempos'] = [(t0 + i * paso, crece) for i in range(n)]
    L['marcador_t'] = (L['entra'] * 0.8, L['entra'] * 0.8 + 0.45)


def _cifra_capa(L, trozos, tam, dest):
    clave = (tuple(trozos), round(tam, 2), dest)
    hecho = L['cifras'].get(clave)
    if hecho is None:
        if dest:
            col_n, col_u = ORO + (255,), ORO + (225,)
        else:
            col_n, col_u = (255, 255, 255, 255), (255, 255, 255, 185)
        im, px, base, ancho = capa_trozos(trozos, tam, 'extrabold', col_n, col_u)
        caja_ = B.fuente('extrabold', tam).getbbox('0')
        hecho = (premult(im), px, base, ancho, caja_[3] - caja_[1], im, ancho_trozos(trozos, 'extrabold', True) * tam)
        if len(L['cifras']) > 500:
            L['cifras'].clear()
        L['cifras'][clave] = hecho
    return hecho


def pintar_grafico(c, L, lienzo):
    t, u = c.t, c.u
    # la segunda línea del título, con su subrayado que se dibuja de izquierda a derecha
    if L['t2'] is not None:
        im, mx, my = L['marcador']
        k = B.sale(B.tramo(t, *L['marcador_t']))
        if k > 0:
            capa(lienzo, im, mx, my, recorte=(mx, 0, mx + im.width * k, lienzo.shape[0]))
        capa(lienzo, L['t2'][0], *L['t2'][1])
    y_base = L['y_base']
    # el halo de la destacada, detrás de su barra
    if 'brillo' in L:
        i0, dur_c = L['tiempos'][L['dest']]
        g = B.suave(B.tramo(t, i0 + dur_c * 0.6, i0 + dur_c + 0.35))
        if g > 0:
            rgbp, a, bx, by = L['brillo']
            sobre(lienzo, rgbp, a, bx, by, g)
    # las barras (suben desde la línea de base), su reflejo y sus números (cuentan mientras suben)
    tope_dest = None
    for (i0, dur_c), b in zip(L['tiempos'], L['barras']):
        e = B.sale(B.tramo(t, i0, i0 + dur_c))
        if e <= 0:
            continue
        h = b['alto'] * e
        rgbp, a = b['capa']
        sobre(lienzo, rgbp, a, b['x0'], y_base - h, recorte=(0, 0, lienzo.shape[1], y_base))
        rr, ra = b['refl']
        sobre(lienzo, rr, ra, b['x0'], y_base, min(1.0, h / L['refl']))
        (crgb, ca), px, base, ancho, mayus, _, ancho_tab = _cifra_capa(L, trozos_de(b['v'] * e, L['unidad']), b['tam'],
                                                                        b['dest'])
        # mientras cuenta, se centra como si las cifras fueran igual de anchas (así no tiembla de lado a lado al cambiar
        # de cifra); al llegar, se desliza suave a su centro de verdad
        k = B.suave(B.tramo(t, i0 + 0.8 * dur_c, i0 + dur_c + 0.15))
        yb = y_base - h - L['gap_num']
        sobre(lienzo, crgb, ca, round(b['cx'] - px - (ancho_tab + (ancho - ancho_tab) * k) / 2), yb - base,
              B.tramo(t, i0, i0 + 0.12))
        if b['dest']:
            tope_dest = yb - mayus
    # las etiquetas y la línea de base
    for im, (x, y) in L['etiquetas']:
        capa(lienzo, im, x, y)
    lrgb, la, lx = L['linea_base']
    sobre(lienzo, lrgb, la, lx, y_base - lrgb.shape[0] // 2)
    # la insignia de la destacada: aparece con un rebote cuando la barra ya llegó
    ins = L['insignia']
    if ins is not None and tope_dest is not None:
        i0, dur_c = L['tiempos'][L['dest']]
        q = B.tramo(t, i0 + dur_c, i0 + dur_c + 0.35)
        if q > 0:
            bd = L['barras'][L['dest']]
            esc = 0.55 + 0.45 * B.rebote(q, 1.5)
            punta = tope_dest - 12 * u                      # la punta del piquito se queda quieta: crece desde ahí
            B.poner(Hoja(lienzo), ins, bd['cx'], punta - ins.height * esc / 2, escala=esc, alfa=B.tramo(q, 0, 0.4))


# ── Panel 2: el panel de edición ────────────────────────────────────────────────────────────────────────────────────
def leer_pasos(s):
    out = []
    for trozo in str(s or '').split('|'):
        trozo = trozo.strip()
        if not trozo:
            continue
        nombre, _, dato = trozo.partition('::')
        out.append((nombre.strip(), dato.strip()))
    return out or [('listo', '')]


def _duracion_video(ruta):
    if not ruta:
        return 30.0
    try:
        cap = cv2.VideoCapture(ruta)
        n, f = cap.get(cv2.CAP_PROP_FRAME_COUNT), cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        if n > 0 and f > 0:
            return n / f
    except Exception:
        pass
    return 30.0


def _reloj(seg):
    seg = max(0, int(seg))
    return f'{seg // 60}:{seg % 60:02d}'


def _miniaturas(c, n, w, h):
    """n cuadros del propio vídeo, recortados alrededor de la cara al tamaño w × h y con las esquinas redondas."""
    sacar = c.estado.get('sacar_cuadros')
    cuadros = []
    if sacar:
        try:
            cuadros = sacar(n, 360)
        except Exception:
            cuadros = []
    cx, cy, ac = (float(v) for v in c.cara)
    out = []
    for im in cuadros:
        k = im.width / c.W
        fx, fy, fa = cx * k, cy * k, ac * k
        ch = 2.6 * fa
        cw = ch * w / h
        if cw > im.width:
            cw, ch = im.width, im.width * h / w
        x0 = min(max(0.0, fx - cw / 2), im.width - cw)
        y0 = min(max(0.0, fy + 0.3 * fa - ch / 2), im.height - ch)
        trozo = im.crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch))).resize((w, h), Image.LANCZOS)
        out.append(B.recortar_redondo(trozo, max(2, h * 0.14)))
    return out


def _preparar_edicion(c, L):
    u, op = c.u, c.op
    pw, ph = L['pw'], L['ph']
    e = min(1.15, max(0.72, ph / (850 * u)))          # si el panel es más bajo o más alto, todo se ajusta
    fe = min(1.0, e)
    PAD = 30 * u
    acento = B.color(op.get('color') or '#8B5CF6')[:3]
    pasos = leer_pasos(op.get('pasos'))
    n = len(pasos)

    # el fondo del panel: violeta muy oscuro, un poco más claro arriba, y un filo claro
    k = np.linspace(0, 1, ph, dtype=np.float32)[:, None, None]
    arriba, abajo = np.float32([36, 20, 68]) / 255, np.float32([20, 11, 40]) / 255
    rgb = np.empty((ph, pw, 3), np.float32)
    rgb[:] = arriba + (abajo - arriba) * k
    a = alfa_caja(0, 0, pw, ph, R_PANEL * u, 0, 0, pw, ph)
    filo = a - alfa_caja(1.6 * u, 1.6 * u, pw - 1.6 * u, ph - 1.6 * u, R_PANEL * u - 1.6 * u, 0, 0, pw, ph)
    rgb += (1 - rgb) * (filo * 0.16)[..., None]
    a = a[..., None]
    rgb *= a

    # el título: lo de antes de «/» gordo y blanco, lo de después fino y lila, en una línea
    titulo = str(op.get('titulo') or 'Claude / lo edita')
    t1, _, t2 = titulo.partition('/')
    t1, t2 = t1.strip(), t2.strip()
    tam_t = 58 * u * fe
    w100 = (B.fuente('extrabold', 100).getlength(t1 + ' ') + (B.fuente('light', 100).getlength(t2) if t2 else 0)) / 100
    tam_t = min(tam_t, (pw - 2 * PAD) / max(w100, 1e-3))
    r1 = Rotulo(t1, tam_t, 'extrabold', (255, 255, 255, 255))
    yt = 30 * u * e + r1.mayus / 2 + 4 * u
    capa(rgb, r1.capa, *r1.esquina(PAD, yt))
    if t2:
        r2 = Rotulo(t2, tam_t, 'light', LILA_VIVO + (255,))
        capa(rgb, r2.capa, *r2.esquina(PAD + B.fuente('extrabold', tam_t).getlength(t1 + ' '), yt))

    # la barra de arriba: tres puntos, el estado (cambia) y «4K · 30 FPS»
    hy0, hy1 = 112 * u * e, 164 * u * e
    hc = (hy0 + hy1) / 2
    rellenar(rgb, PAD, hy0, pw - PAD, hy1, 14 * u, (255, 255, 255), 0.06)
    for i, op_ in enumerate((1.0, 0.6, 0.3)):
        x = PAD + 22 * u + i * 20 * u
        rellenar(rgb, x - 5.5 * u, hc - 5.5 * u, x + 5.5 * u, hc + 5.5 * u, 5.5 * u, LILA_VIVO, op_)
    tam_h = 23 * u * fe
    rf = Rotulo(f'4K · {int(round(c.fps))} FPS', tam_h, 'medium', (255, 255, 255, 190), espacio=0.06)
    capa(rgb, rf.capa, *rf.esquina(pw - PAD - 20 * u, hc, 'der'))
    L['estado_x'] = PAD + 104 * u
    L['estado_y'] = hc
    L['editando'] = Rotulo('EDITANDO', tam_h, 'bold', LILA_VIVO + (255,), espacio=0.14)
    L['listo'] = Rotulo('LISTO', tam_h, 'bold', VERDE + (255,), espacio=0.14)
    L['punto'] = B.caja(10 * u, 10 * u, 5 * u, AMARILLO + (255,))
    L['punto_v'] = B.caja(10 * u, 10 * u, 5 * u, VERDE + (255,))

    # el cuerpo: el clip en pequeño a la izquierda y los pasos a la derecha
    by0 = 182 * u * e
    th = int(round(300 * u * e))
    tw = int(round(th * 9 / 16))
    L['mini'] = (round(PAD), round(by0), tw, th)
    L['mini_a'] = alfa_caja(0, 0, tw, th, 16 * u, 0, 0, tw, th)[..., None]
    sx0, sx1 = PAD + tw + 18 * u, pw - PAD
    fila = th / n
    ICO = min(36 * u * fe, fila * 0.6)
    tam_paso = min(31 * u * fe, fila * 0.52)
    tam_dato = min(26 * u * fe, fila * 0.43)
    filas = []
    for i, (nombre, dato) in enumerate(pasos):
        y0, y1 = by0 + i * fila + 4 * u * e, by0 + (i + 1) * fila - 4 * u * e
        rellenar(rgb, sx0, y0, sx1, y1, 12 * u, (255, 255, 255), 0.05)
        yc = (y0 + y1) / 2
        rd = Rotulo(dato, tam_dato, 'regular', LILA_VIVO + (255,)) if dato else None
        libre = sx1 - sx0 - 32 * u - ICO - 14 * u - (rd.ancho + 24 * u if rd else 0)
        tam_n = min(tam_paso, libre / max(B.fuente('medium', 100).getlength(nombre) / 100, 1e-3))
        rn = Rotulo(nombre, tam_n, 'medium', (255, 255, 255, 255))
        filas.append({'y': yc, 'nombre': rn, 'nombre_xy': rn.esquina(sx0 + 16 * u + ICO + 14 * u, yc),
                      'dato': rd, 'dato_xy': rd.esquina(sx1 - 18 * u, yc, 'der') if rd else None})
    L['filas'], L['ico'] = filas, ICO
    L['ico_x'] = sx0 + 16 * u + ICO / 2
    L['resalte'] = (B.caja(sx1 - sx0, fila - 8 * u * e, 12 * u, (255, 255, 255, 30)), sx0, by0 + 4 * u * e, fila)
    L['giro'] = icono_giro(ICO, u, acento + (255,))
    L['aro'] = icono_aro(ICO, u)
    L['marcas'] = {}

    # la barra de progreso y su «%»
    pc = by0 + th + 30 * u * e
    tam_pc = 40 * u * fe
    L['pc'] = pc
    L['pc_x1'] = pw - PAD
    bx0, bx1 = PAD, pw - PAD - 150 * u
    L['barra'] = (bx0, bx1, pc - 6 * u, pc + 6 * u)
    rellenar(rgb, bx0, pc - 6 * u, bx1, pc + 6 * u, 6 * u, (255, 255, 255), 0.10)
    bw = int(math.ceil(bx1 - bx0)) + 1
    kx = np.linspace(0, 1, bw, dtype=np.float32)[None, :, None]
    c0 = np.asarray(acento, np.float32) / 255
    c1 = np.asarray(LILA_VIVO, np.float32) / 255
    L['barra_col'] = np.repeat(c0 + (c1 - c0) * kx, int(math.ceil(12 * u)) + 2, axis=0)
    L['tam_pc'] = tam_pc
    L['cifras'] = {}

    # las pistas: TOMA, SUBTÍTULOS, COLOR y SONIDO
    ty0 = pc + 36 * u * e
    altos = [54, 40, 40, 54]
    gap = 12 * u * e
    lx0, lx1 = PAD + 172 * u, pw - PAD
    lw = int(round(lx1 - lx0))
    ys = []
    y = ty0
    for h in altos:
        ys.append((y, y + h * u * e))
        y += h * u * e + gap
    ty1 = ys[-1][1]
    L['pistas_y'] = (ty0, ty1)
    L['pistas_x'] = (round(lx0), lw)
    tam_l = 21 * u * fe
    for (y0, y1), nombre in zip(ys, ('TOMA', 'SUBTÍTULOS', 'COLOR', 'SONIDO')):
        rt = Rotulo(nombre, tam_l, 'bold', LILA_VIVO + (170,), espacio=0.08)
        capa(rgb, rt.capa, *rt.esquina(PAD, (y0 + y1) / 2))
    pista = Image.new('RGBA', (lw, int(math.ceil(ty1 - ty0)) + 1), (0, 0, 0, 0))
    # TOMA: cuadros del propio vídeo
    (y0, y1) = ys[0]
    hh = int(round(y1 - y0))
    nmin = 8
    wmin = int((lw - (nmin - 1) * 4 * u) / nmin)
    for i, im in enumerate(_miniaturas(c, nmin, wmin, hh)):
        pista.alpha_composite(im, (int(round(i * (wmin + 4 * u))), int(round(y0 - ty0))))
    # SUBTÍTULOS: pastillas con palabras
    (y0, y1) = ys[1]
    palabras = [x.strip() for x in str(op.get('subtitulos') or '').split('|') if x.strip()] or ['…']
    trozo = lw / len(palabras)
    for i, pal in enumerate(palabras):
        x0, x1 = i * trozo + 2 * u, (i + 1) * trozo - 10 * u
        pas = B.caja(x1 - x0, y1 - y0, 10 * u, LILA_VIVO + (255,))
        rt = Rotulo(pal, min(20 * u * fe, (y1 - y0) * 0.5), 'bold', MORADO_HONDO + (255,))
        if rt.ancho > pas.width - 20 * u:
            rt = Rotulo(pal, min(20 * u * fe, (y1 - y0) * 0.5) * (pas.width - 20 * u) / rt.ancho, 'bold',
                        MORADO_HONDO + (255,))
        pas.alpha_composite(rt.capa, rt.esquina(12 * u, pas.height / 2))
        pista.alpha_composite(pas, (int(round(x0)), int(round(y0 - ty0))))
    # COLOR: una pastilla con el degradado del color (del morado al ámbar)
    (y0, y1) = ys[2]
    gh = int(round(y1 - y0))
    kk = np.linspace(0, 1, lw - int(4 * u), dtype=np.float32)[None, :, None]
    grad = np.asarray(MORADO, np.float32) + (np.asarray(AMBAR, np.float32) - np.asarray(MORADO, np.float32)) * kk
    grad = np.repeat(grad, gh, axis=0)
    gim = Image.fromarray(np.clip(grad + 0.5, 0, 255).astype(np.uint8), 'RGB').convert('RGBA')
    pista.alpha_composite(B.recortar_redondo(gim, gh / 2), (int(2 * u), int(round(y0 - ty0))))
    # SONIDO: la forma de la onda
    (y0, y1) = ys[3]
    D = SS
    onda = Image.new('RGBA', (lw * D, int(round((y1 - y0) * D))), (0, 0, 0, 0))
    od = ImageDraw.Draw(onda)
    paso_o = 7.5 * u
    nb = int(lw / paso_o)
    rng = np.random.default_rng(5)
    val = np.convolve(rng.random(nb + 4), np.ones(3) / 3, mode='same')[2:nb + 2]
    frase = 0.55 + 0.45 * np.abs(np.sin(np.linspace(0, 5.3, nb)))
    alto_o = (y1 - y0) * D
    for i in range(nb):
        h = alto_o * (0.12 + 0.88 * val[i] * frase[i])
        xc = (i + 0.5) * paso_o * D
        od.rounded_rectangle([xc - 1.8 * u * D, alto_o / 2 - h / 2, xc + 1.8 * u * D, alto_o / 2 + h / 2],
                             radius=1.8 * u * D, fill=LILA_VIVO + (255,))
    onda = onda.resize((lw, int(round(y1 - y0))), Image.LANCZOS)
    pista.alpha_composite(onda, (0, int(round(y0 - ty0))))
    prgb, pa = premult(pista)
    L['pistas'] = (prgb.copy(), pa.copy(), prgb * 0.38, pa * 0.38)
    # el cabezal: una línea amarilla con su asa arriba
    alto_c = int(round(ty1 - ty0 + 26 * u))
    cab = Image.new('RGBA', (int(round(18 * u)), alto_c), (0, 0, 0, 0))
    cab.alpha_composite(B.caja(3.2 * u, alto_c - 8 * u, 1.6 * u, AMARILLO + (255,)),
                        (int(round(9 * u - 1.6 * u)), int(round(8 * u))))
    cab.alpha_composite(B.caja(18 * u, 16 * u, 5 * u, AMARILLO + (255,)), (0, 0))
    L['cabezal'] = (cab, ty0 - 14 * u)

    L['panel_rgb'], L['panel_a'] = rgb, a
    L['total'] = _duracion_video(c.estado.get('ruta_video', ''))
    L['tam_tc'] = 21 * u * fe

    # cuándo empieza y cuándo queda hecho cada paso (cabe en lo que dura el efecto)
    t0 = L['entra'] * 0.8
    t1_ = max(t0 + 0.3 * n, c.dur - L['sale'] - 0.5)
    fines = [t0 + (i + 1) * (t1_ - t0) / n for i in range(n)]
    L['inicios'], L['fines'] = [t0] + fines[:-1], fines


def mini_clip(c, L):
    """El cuadro actual en pequeño (para el panel de edición), recortado al tamaño de la miniatura."""
    _, _, tw, th = L['mini']
    W, H = c.W, c.H
    k = max(1, min(W // tw, H // th))                       # un trozo justo k veces más grande: reducir así es rápido
    x0, y0 = (W - k * tw) // 2, (H - k * th) // 2
    return cv2.resize(c.img[y0:y0 + k * th, x0:x0 + k * tw], (tw, th), interpolation=cv2.INTER_AREA)


def pintar_edicion(c, L, lienzo, mini):
    u, t = c.u, c.t
    inicios, fines = L['inicios'], L['fines']
    n = len(fines)
    prog = sum(B.tramo(t, inicios[i], fines[i]) for i in range(n)) / n
    listo = B.suave(B.tramo(t, fines[-1], fines[-1] + 0.3))
    hoja = Hoja(lienzo)

    # el estado: «EDITANDO» con un punto que late, y «LISTO» en verde al acabar
    ex, ey = L['estado_x'], L['estado_y']
    late = 0.55 + 0.45 * math.cos(t * 2 * math.pi * 1.4)
    B.poner(hoja, L['punto'], ex - 18 * u, ey, alfa=late * (1 - listo))
    B.poner(hoja, L['punto_v'], ex - 18 * u, ey, alfa=listo)
    capa(lienzo, L['editando'].capa, *L['editando'].esquina(ex, ey), alfa=1 - listo)
    capa(lienzo, L['listo'].capa, *L['listo'].esquina(ex, ey), alfa=listo)

    # el clip en pequeño, con su código de tiempo
    mx, my, tw, th = L['mini']
    if mini is not None:
        sobre(lienzo, mini * L['mini_a'], L['mini_a'], mx, my)
    tc = f'{_reloj(prog * L["total"])} / {_reloj(L["total"])}'
    clave = ('tc', tc)
    hecho = L['cifras'].get(clave)
    if hecho is None:
        rt = Rotulo(tc, L['tam_tc'], 'medium', (255, 255, 255, 255))
        fondo = B.caja(rt.ancho + 18 * u, rt.mayus + 16 * u, 8 * u, (10, 6, 22, 170))
        fondo.alpha_composite(rt.capa, rt.esquina(9 * u, fondo.height / 2))
        hecho = L['cifras'][clave] = fondo
    capa(lienzo, hecho, mx + round(8 * u), my + th - hecho.height - round(8 * u))

    # los pasos: la franja clara baja de uno al siguiente; el que toca gira y al acabar sale la marca verde
    pos = sum(B.suave(B.tramo(t, fines[i], fines[i] + 0.3)) for i in range(n - 1))
    a_res = B.suave(B.tramo(t, inicios[0], inicios[0] + 0.25)) * (1 - listo)
    res, rx, ry, fila = L['resalte']
    if a_res > 0.003:
        capa(lienzo, res, rx, ry + fila * pos, a_res)
    ICO = L['ico']
    for i, f in enumerate(L['filas']):
        activo = B.suave(B.tramo(t, inicios[i], inicios[i] + 0.2))
        hecho_ = B.suave(B.tramo(t, fines[i], fines[i] + 0.25))
        capa(lienzo, f['nombre'].capa, *f['nombre_xy'], alfa=0.45 + 0.55 * max(activo, hecho_))
        if f['dato'] is not None and hecho_ > 0:
            x, y = f['dato_xy']
            capa(lienzo, f['dato'].capa, x + (1 - hecho_) * 14 * u, y, alfa=hecho_)
        ix, iy = L['ico_x'], f['y']
        if activo < 1:
            B.poner(hoja, L['aro'], ix, iy, alfa=1 - activo)
        a_giro = activo * (1 - B.suave(B.tramo(t, fines[i], fines[i] + 0.12)))
        if a_giro > 0.003:
            B.poner(hoja, L['giro'], ix, iy, giro=(t - inicios[i]) * 400.0, alfa=a_giro)
        if t >= fines[i]:
            dt = t - fines[i]
            q = round(B.sale(B.tramo(dt, 0.08, 0.38)) * 24) / 24
            marca = L['marcas'].get(q)
            if marca is None:
                marca = L['marcas'][q] = icono_marca(ICO, q)
            B.poner(hoja, marca, ix, iy, escala=0.35 + 0.65 * B.rebote(B.tramo(dt, 0, 0.3), 1.6),
                    alfa=B.tramo(dt, 0, 0.08))

    # la barra de progreso y el «%»
    bx0, bx1, by0, by1 = L['barra']
    fw = (bx1 - bx0) * prog
    if fw > 1:
        X0, Y0 = int(math.floor(bx0)), int(math.floor(by0))
        X1, Y1 = int(math.ceil(bx0 + fw)), int(math.ceil(by1))
        a = alfa_caja(bx0, by0, bx0 + fw, by1, (by1 - by0) / 2, X0, Y0, X1, Y1)[..., None]
        col = L['barra_col'][:Y1 - Y0, :X1 - X0]
        sobre(lienzo, col * a, a, X0, Y0)
    pct = str(int(round(prog * 100)))
    clave = ('pct', pct)
    hecho = L['cifras'].get(clave)
    if hecho is None:
        im, px, base, ancho = capa_cifra(pct, '%', L['tam_pc'], 'bold', (255, 255, 255, 255), LILA_VIVO + (255,))
        caja_ = B.fuente('bold', L['tam_pc']).getbbox('0')
        hecho = L['cifras'][clave] = (im, px, base, ancho, (caja_[3] - caja_[1]))
    im, px, base, ancho, mayus = hecho
    capa(lienzo, im, round(L['pc_x1'] - px - ancho), round(L['pc'] + mayus / 2 - base))

    # las pistas: lo que ya pasó el cabezal, encendido; lo que falta, apagado
    (ty0, _), (lx0, lw) = L['pistas_y'], L['pistas_x']
    brgb, ba, drgb, da = L['pistas']
    xc = lx0 + lw * prog
    sobre(lienzo, drgb, da, lx0, round(ty0), recorte=(xc, 0, lienzo.shape[1], lienzo.shape[0]))
    sobre(lienzo, brgb, ba, lx0, round(ty0), recorte=(0, 0, xc, lienzo.shape[0]))
    cab, cy0 = L['cabezal']
    B.poner(hoja, cab, xc, cy0 + cab.height / 2, alfa=B.tramo(t, inicios[0], inicios[0] + 0.2))
