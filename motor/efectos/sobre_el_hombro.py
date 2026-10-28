"""sobre-el-hombro: la cámara se acerca hacia una esquina de arriba (la del lado de la cara donde hay más sitio) y en esa
esquina aparece una tarjeta de cristal claro con tu número subiendo y su gráfica de línea dibujándose.

Lo que pasa, con la duración de siempre (3,5 s):
  - 0–0,8 s: la cámara se acerca suave (de 1 a `zoom`, sin tirón) hacia la esquina de arriba del lado libre: la cara se
    va un poco hacia el otro lado y hacia abajo, y arriba queda sitio.
  - 0,3 s: la tarjeta sube con un rebote corto y un fundido. Lleva el título pequeño en mayúsculas (`titulo`), el
    número grande que cuenta de `inicio` a `final` escrito corto («125K», «1,2M», «9,9K») y la gráfica de línea que se
    dibuja de izquierda a derecha al mismo paso que el número (el número es siempre el valor de la punta), con un punto
    brillante en la punta y debajo un degradado suave del color de la línea (`color`).
  - Si se le dan `barras` («40,65,52,80,120»), debajo sale una tarjeta pequeña con esas barras creciendo una detrás de
    otra y su total (`titulo_barras`).
  - Los últimos 0,8 s: la cámara vuelve a como estaba, tan suave como entró (el último cuadro del efecto ya es el plano
    original: el corte no se nota), y en cuanto empieza a volver las tarjetas se van con un fundido de 0,3 s. El cristal
    se empaña al entrar y se desempaña al salir (no se funde: así no se ve nítido lo de detrás a través de él).
  - Los números que cuentan cambian cada 3 cuadros (~10 veces por segundo): si cambiaran en cada cuadro, parpadearían.

El cristal es claro: desenfoca lo que tiene detrás, lo blanquea, lleva un brillo en diagonal, un filo fino brillante
(más claro arriba) y una sombra suave. El texto va oscuro, para que se lea en el teléfono.

Nunca tapa la cara: la tarjeta va arriba, pegada al borde del lado libre, y si no cabe entre el borde y la cara (con la
cámara quieta y con la cámara cerca) se hace más pequeña; si la persona se mueve hacia ella, sube lo que pueda y, si ni
así, se desvanece antes que taparla. Todo queda en la zona segura de Instagram (de x 60 a x 1020 a 1080 de ancho y por
debajo de y 210), también con el acercamiento: las tarjetas no se acercan con la cámara.

    .venv/bin/python efectos.py sobre-el-hombro tu_video.mp4 --desde 2 --op final=125000 --fotos 2.5,4.5
"""
import math
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw

import base as B

NOMBRE = 'sobre-el-hombro'
DESCRIPCION = 'La cámara se acerca a tu lado y aparece una gráfica de cristal con tu número subiendo'
OPCIONES = {
    'titulo': 'VISTAS',                 # la línea pequeña de arriba (va en mayúsculas)
    'inicio': '0',                      # de dónde empieza a contar el número
    'final': '125000',                  # dónde acaba («125000», «125.000», «125K» o «1,2M» valen)
    'color': '#22C55E',                 # el color de la línea, su punto y su degradado
    'barras': '',                       # una segunda tarjeta con barras: sus valores («40,65,52,80»; vacía: no sale)
    'titulo_barras': 'ÚLTIMOS REELS',   # la línea pequeña de la tarjeta de las barras (encima de su total)
    'lado': 'auto',                     # dónde va la tarjeta: «auto» (el lado de la cara con más sitio), «izquierda» o «derecha»
    'zoom': '1.22',                     # cuánto se acerca la cámara (1 = nada; de 1 a 1,4)
}
DURACION = 3.5

# ── Los tiempos (segundos, para 3,5 s; si el efecto dura menos, todo se aprieta) ────────────────────────────────────
CAMARA_ENTRA = 0.8          # la cámara se acerca en esto
CAMARA_SALE = 0.8           # y vuelve en los últimos 0,8 s (tan suave como al entrar: si frena más deprisa, se nota el tirón)
TARJETA_ENTRA = (0.30, 0.58)  # cuándo sube la tarjeta y lo que tarda su rebote
FUNDIDO_ENTRA = 0.28
SEGUNDA_DESPUES = 0.22      # la de las barras sale un poco después
LINEA = (0.50, 2.15)        # la línea se dibuja (y el número cuenta) en este tramo
BARRAS = (0.75, 1.95)       # las barras crecen en este tramo, una detrás de otra
FUNDIDO_SALE = 0.30         # el fundido de las tarjetas…
FUNDIDO_DESDE = 0.65        # …que empieza cuando quedan estos segundos (la cámara ya ha empezado a volver)
SUBE = 64                   # desde cuántos px (a 1080) más abajo sube la tarjeta

# ── La colocación (a 1080 × 1920; se escala con el vídeo) ───────────────────────────────────────────────────────────
BORDE = 66                  # de la tarjeta al borde del cuadro (la zona segura empieza en 60)
ARRIBA = 230                # dónde empieza la tarjeta por arriba (lo de Instagram acaba en 210)
TECHO = 214                 # lo más arriba que puede subir si la persona se le acerca
ANCHO, ALTO = 540, 350      # la tarjeta grande, a tamaño completo
ANCHO2, ALTO2 = 330, 236    # la de las barras
TAMANO = 1.2                # las dos, a este tamaño (las medidas de arriba y las de dentro van a 1080 × 1920 × esto)
HUECO2 = 20                 # entre las dos
MENOR = 0.6                 # lo más pequeña que se hace para no tapar la cara (en proporción)
MENOR2 = 0.78               # la de las barras, más pequeña que esto ya no se lee: si no cabe, no sale
MARGEN_CARA = 0.5           # la distancia mínima de la grande a la cara, en anchos de cara (encima: no pisa la gorra)
MARGEN_BARRAS = 0.38        # la de las barras va al lado, a la altura del hombro: así no llega a la oreja
HOLGURA = 0.6               # mientras dura, solo se apartan si la cara se mete en el 60 % de ese margen
DESENFOQUE = 44             # cuánto se desenfoca lo de detrás (a 1080): mucho, para que un cuadro oscuro detrás no manche
BLANCO = 0.64               # cuánto blanquea el cristal arriba (abajo, un poco menos)
SS = 4                      # la línea se dibuja 4 veces más grande y se reduce (bordes suaves)

TINTA = (20, 17, 34)        # el texto oscuro
TINTA_SUAVE = (74, 70, 96)  # el título


# ── Números ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _leer_numero(v, defecto):
    """«125000», «125.000», «125 000», «125K», «1,2M», «9,9 mil» → número. Si no se entiende, `defecto`."""
    s = str(v or '').strip().lower().replace(' ', '').replace(' ', '')
    if not s:
        return defecto
    mult = 1.0
    for suf, m in (('mil', 1e3), ('k', 1e3), ('m', 1e6)):
        if s.endswith(suf):
            s, mult = s[:-len(suf)], m
            break
    if re.fullmatch(r'\d{1,3}(\.\d{3})+', s):          # 125.000 / 1.046.813: el punto separa los miles
        s = s.replace('.', '')
    elif re.fullmatch(r'\d{1,3}(,\d{3}){2,}', s):      # 1,046,813 (a la inglesa, con dos comas o más)
        s = s.replace(',', '')
    s = s.replace(',', '.')
    try:
        return max(0.0, float(s) * mult)
    except ValueError:
        return defecto


def _decimal(x):
    t = f'{x:.1f}'
    return (t[:-2] if t.endswith('.0') else t).replace('.', ',')


def corto(v):
    """Un número escrito corto, a la española: 850 → «850», 9936 → «9,9K», 125000 → «125K», 1200000 → «1,2M»."""
    v = max(0.0, float(v))
    if v >= 9_950_000:
        return f'{v / 1e6:.0f}M'
    if v >= 999_500:
        return _decimal(v / 1e6) + 'M'
    if v >= 9_950:
        return f'{v / 1e3:.0f}K'
    if v >= 999.5:
        return _decimal(v / 1e3) + 'K'
    return f'{v:.0f}'


def _lista(s):
    """«40,65,52» o «1,5;2,5;3» → [40, 65, 52] / [1.5, 2.5, 3]."""
    s = str(s or '').strip()
    if not s:
        return []
    trozos = s.split(';') if ';' in s else s.split(',')
    out = []
    for t in trozos:
        v = _leer_numero(t, None)
        if v is not None:
            out.append(v)
    return out[:12]


def _a_saltos(t, t0, fps, cada=3):
    """El tiempo de los números que cuentan: cambian cada `cada` cuadros (unas 10 veces por segundo), no en todos. Si
    cambiaran en cada cuadro, cada cifra estaría un solo cuadro y se vería como un parpadeo (y lo es, para el ojo)."""
    if t <= t0 or fps <= 0:
        return t
    paso = cada / fps
    return t0 + math.floor((t - t0) / paso + 1e-6) * paso


def _seno(x):
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


# ── Dibujo con números (con decimales, sin saltitos) ────────────────────────────────────────────────────────────────
def _rejilla(w, h):
    xs = np.arange(w, dtype=np.float32) + 0.5
    ys = np.arange(h, dtype=np.float32) + 0.5
    return np.meshgrid(xs, ys)


def _sdf_caja(xx, yy, cx, cy, hw, hh, r):
    r = min(r, hw, hh)
    qx = np.abs(xx - cx) - (hw - r)
    qy = np.abs(yy - cy) - (hh - r)
    return np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r


def _cob(sd):
    return np.clip(0.5 - sd, 0.0, 1.0).astype(np.float32)


def _pintar(dst, cob, rgb, alfa=1.0, x0=0, y0=0):
    """Pinta un color (0–1) con su cobertura sobre una capa premultiplicada, con su esquina en (x0, y0)."""
    h, w = cob.shape
    X0, Y0 = max(0, x0), max(0, y0)
    X1, Y1 = min(dst.shape[1], x0 + w), min(dst.shape[0], y0 + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    a = cob[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0] * np.float32(alfa)
    zona = dst[Y0:Y1, X0:X1]
    zona *= (1.0 - a)[..., None]
    zona[..., :3] += a[..., None] * np.asarray(rgb, np.float32)
    zona[..., 3] += a


def _sobre(dst, src, x0, y0):
    """Una capa premultiplicada encima de otra, con su esquina en (x0, y0) (enteros)."""
    h, w = src.shape[:2]
    X0, Y0 = max(0, x0), max(0, y0)
    X1, Y1 = min(dst.shape[1], x0 + w), min(dst.shape[0], y0 + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    s = src[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    zona = dst[Y0:Y1, X0:X1]
    zona *= (1.0 - s[..., 3:4])
    zona += s


def _premult(capa):
    a = np.asarray(capa, np.float32) * np.float32(1.0 / 255.0)
    a[..., :3] *= a[..., 3:4]
    return np.ascontiguousarray(a)


class _Rotulo:
    """Un texto premultiplicado y dónde cae su tinta (para alinear la letra, no la caja)."""

    def __init__(self, s, tam, peso, rgb, espacio=0.0):
        capa = B.texto(s, tam, peso, tuple(rgb) + (255,), espacio=espacio)
        f = B.fuente(peso, tam)
        asc, desc = f.getmetrics()
        self.pad = (capa.height - (asc + desc)) / 2
        bb = f.getbbox('H')
        self.medio = self.pad + (bb[1] + bb[3]) / 2
        self.arr = _premult(capa)

    def poner(self, dst, x, y):
        """La tinta empieza en x y las mayúsculas quedan centradas en y."""
        _sobre(dst, self.arr, int(round(x - self.pad)), int(round(y - self.medio)))


def _tam_que_cabe(s, peso, tam, ancho, espacio=0.0):
    f = B.fuente(peso, 100)
    largo = (sum(f.getlength(ch) for ch in s) + espacio * 100 * max(0, len(s) - 1)) if espacio else f.getlength(s)
    return min(tam, ancho / max(1e-3, largo / 100.0))


# ── La tarjeta de cristal claro ─────────────────────────────────────────────────────────────────────────────────────
class _Tarjeta:
    """El cristal (su forma, el blanco, el brillo y el filo), lo quieto de dentro y su sombra, en coordenadas de la
    tarjeta. `capa(t)` le añade lo que se mueve."""

    def __init__(self, w, h, r, k):
        self.w, self.h, self.k = int(round(w)), int(round(h)), k
        xx, yy = _rejilla(self.w, self.h)
        sd = _sdf_caja(xx, yy, self.w / 2, self.h / 2, self.w / 2, self.h / 2, r)
        self.forma = _cob(sd)
        dy = np.clip(yy / self.h, 0, 1)
        diag = np.clip(xx / self.w * 0.6 + yy / self.h * 0.4, 0, 1)
        # el blanco del cristal (más blanco arriba), un brillo en diagonal y el filo fino, más claro arriba
        blanco = (BLANCO - 0.12 * dy) * self.forma
        brillo = 0.16 * (1.0 - diag) ** 2.2 * self.forma
        bw = max(1.0, 1.7 * k)
        filo = (_cob(sd) - _cob(sd + bw)) * (0.95 - 0.5 * dy)
        luz = (_cob(sd + bw) - _cob(sd + 2.2 * bw)) * 0.35 * (1.0 - dy) ** 3      # una línea de luz por dentro, arriba
        a = 1.0 - (1.0 - blanco) * (1.0 - brillo) * (1.0 - filo) * (1.0 - luz)
        self.base = np.dstack([a, a, a, a]).astype(np.float32)
        # la sombra: una amplia y suave y otra corta, pegada
        p = self.pad = int(math.ceil(70 * k))
        lienzo = np.zeros((self.h + 2 * p, self.w + 2 * p), np.float32)
        s1 = lienzo.copy()
        d1 = int(round(16 * k))
        s1[p + d1:p + d1 + self.h, p:p + self.w] = self.forma
        s1 = cv2.GaussianBlur(s1, (0, 0), 20 * k) * 0.26
        s2 = lienzo.copy()
        d2 = int(round(4 * k))
        s2[p + d2:p + d2 + self.h, p:p + self.w] = self.forma
        s2 = cv2.GaussianBlur(s2, (0, 0), 5 * k) * 0.12
        self.sombra = (1.0 - (1.0 - s1) * (1.0 - s2)).astype(np.float32)
        self.animar = None

    def capa(self, t):
        c = self.base.copy()
        if self.animar is not None:
            self.animar(c, t)
        return c


def _curva(n=900):
    """La forma de la gráfica: sube cada vez más rápido, con tramos más y menos empinados (como unas vistas de verdad),
    pero sin bajar nunca, para que el número que va con la punta no retroceda. De 0 a 1 en x y en y."""
    x = np.linspace(0.0, 1.0, n)
    pendiente = np.exp(2.5 * x) * (1.0 + 0.55 * np.sin(2 * math.pi * 2.35 * x + 0.9)
                                   + 0.22 * np.sin(2 * math.pi * 5.1 * x + 2.3))
    pendiente = np.maximum(pendiente, 0.05)
    y = np.concatenate([[0.0], np.cumsum((pendiente[1:] + pendiente[:-1]) / 2)])
    return x, y / y[-1]


def _principal(c, k, col):
    """La tarjeta grande: título, número que cuenta y la gráfica de línea."""
    op = c.op
    T = _Tarjeta(ANCHO * k, ALTO * k, 42 * k, k)
    w, h = T.w, T.h
    pad = 36 * k
    colf = np.float32(col) / 255.0
    # las tres rayas muy suaves de la gráfica y el punto del color de la línea delante del título
    gx0, gx1 = pad + 4 * k, w - pad - 4 * k
    gy0, gy1 = 168 * k, h - 38 * k
    quieto = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(quieto)
    for f in (0.0, 0.5, 1.0):
        y = (gy0 + (gy1 - gy0) * f) * SS
        d.line([(pad * SS, y), ((w - pad) * SS, y)], fill=TINTA + (24 if f < 1 else 38,),
               width=max(1, round(1.3 * k * SS)))
    yt = 50 * k
    d.ellipse([pad * SS, (yt - 7 * k) * SS, (pad + 14 * k) * SS, (yt + 7 * k) * SS], fill=tuple(col) + (255,))
    _sobre(T.base, _premult(quieto.resize((w, h), Image.LANCZOS)), 0, 0)
    # el título
    titulo = ' '.join(str(op.get('titulo') or '').split()).upper()
    if titulo:
        tam = _tam_que_cabe(titulo, 'medium', 26 * k, w - 2 * pad - 24 * k, 0.12)
        _Rotulo(titulo, tam, 'medium', TINTA_SUAVE, espacio=0.12).poner(T.base, pad + 24 * k, yt)

    # la curva en píxeles de la tarjeta
    cx_, cy_ = _curva()
    arriba, abajo = gy0 + 14 * k, gy1 - 7 * k
    px = gx0 + (gx1 - gx0) * cx_
    py = abajo - (abajo - arriba) * cy_

    # la línea, su brillo y el degradado de debajo, dibujados una vez (se van destapando de izquierda a derecha)
    g = np.zeros((h, w, 4), np.float32)
    xx, yy = _rejilla(w, h)
    ycurva = np.interp(xx[0], px, py).astype(np.float32)                   # la altura de la curva en cada columna
    dentro = np.clip(yy - ycurva[None, :] + 0.5, 0, 1) * np.clip(gy1 - yy + 0.5, 0, 1)
    dentro *= ((xx >= gx0) & (xx <= gx1)).astype(np.float32)
    grad = 0.06 + 0.42 * np.clip((gy1 - yy) / max(1.0, gy1 - arriba), 0, 1) ** 1.2
    _pintar(g, (dentro * grad).astype(np.float32), colf)
    grande = Image.new('L', (w * SS, h * SS), 0)
    dg = ImageDraw.Draw(grande)
    puntos = [(float(a) * SS, float(b) * SS) for a, b in zip(px[::6], py[::6])] + [(float(px[-1]) * SS,
                                                                                 float(py[-1]) * SS)]
    grosor = 7.5 * k * SS
    dg.line(puntos, fill=255, width=int(round(grosor)), joint='curve')
    for (a, b) in (puntos[0], puntos[-1]):
        dg.ellipse([a - grosor / 2, b - grosor / 2, a + grosor / 2, b + grosor / 2], fill=255)
    linea = np.asarray(grande.resize((w, h), Image.LANCZOS), np.float32) / 255.0
    resplandor = cv2.GaussianBlur(linea, (0, 0), 7 * k) * 0.55
    _pintar(g, np.clip(resplandor, 0, 1).astype(np.float32), colf)
    _pintar(g, np.clip(linea, 0, 1).astype(np.float32), colf)
    T.grafica = g
    T.columnas = xx[0]

    # el número (sus capas se guardan por texto: cambian muchas veces y se repiten)
    inicio = _leer_numero(op.get('inicio'), 0.0)
    final = _leer_numero(op.get('final'), 125000.0)
    rotulos = {}
    tam_num = 86 * k

    def numero(s):
        if s not in rotulos:
            rotulos[s] = _Rotulo(s, tam_num, 'extrabold', TINTA)
        return rotulos[s]

    # el punto de la punta: una cobertura en un trocito, con decimales
    lado = int(math.ceil(64 * k))
    pxx, pyy = _rejilla(lado, lado)
    blanco = np.float32([1.0, 1.0, 1.0])
    l0, l1 = LINEA

    def animar(capa, t):
        q = _seno(B.tramo(t, l0 * c.estado['r'], l1 * c.estado['r']))
        xt = gx0 + (gx1 - gx0) * q
        yt_ = float(np.interp(xt, px, py))
        # destapa la línea y el degradado hasta la punta (borde suave de un píxel)
        cols = np.clip(xt - T.columnas + 0.5, 0, 1).astype(np.float32)
        hasta = min(w, int(math.ceil(xt + 2 * k + 2)))
        trozo = g[:, :hasta] * cols[None, :hasta, None]
        _sobre(capa, trozo, 0, 0)
        # el número: el valor de la gráfica en la punta (al acabar, justo el final)
        qn = _seno(B.tramo(_a_saltos(t, l0 * c.estado['r'], c.fps), l0 * c.estado['r'], l1 * c.estado['r']))
        v = inicio + (final - inicio) * float(np.interp(qn, cx_, cy_))
        numero(corto(final if q >= 1.0 else v)).poner(capa, pad - 2 * k, 112 * k)
        # el punto brillante: halo que late, aro de color y centro blanco
        ox, oy = int(round(xt - lado / 2)), int(round(yt_ - lado / 2))
        rr = np.sqrt((pxx + ox - xt) ** 2 + (pyy + oy - yt_) ** 2)
        late = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 1.15)
        halo = np.exp(-(rr / ((17 + 4 * late) * k)) ** 2) * (0.45 + 0.12 * late)
        _pintar(capa, halo.astype(np.float32), colf, 1.0, ox, oy)
        _pintar(capa, _cob(rr - 11.0 * k), colf, 1.0, ox, oy)
        _pintar(capa, _cob(rr - 5.5 * k), blanco, 1.0, ox, oy)

    T.animar = animar
    return T


def _barras(c, k, col, valores):
    """La tarjeta pequeña: su título, el total que cuenta y las barras que crecen una detrás de otra."""
    T = _Tarjeta(ANCHO2 * k, ALTO2 * k, 34 * k, k)
    w, h = T.w, T.h
    pad = 28 * k
    colf = np.float32(col) / 255.0
    claro = colf + (1.0 - colf) * 0.32
    titulo = ' '.join(str(c.op.get('titulo_barras') or '').split()).upper()
    if titulo:
        tam = _tam_que_cabe(titulo, 'medium', 21 * k, w - 2 * pad, 0.12)
        _Rotulo(titulo, tam, 'medium', TINTA_SUAVE, espacio=0.12).poner(T.base, pad, 40 * k)
    total = sum(valores)
    rotulos = {}
    tam_num = 50 * k

    def numero(s):
        if s not in rotulos:
            rotulos[s] = _Rotulo(s, tam_num, 'extrabold', TINTA)
        return rotulos[s]

    n = len(valores)
    gx0, gx1 = pad, w - pad
    gy0, gy1 = 112 * k, h - 26 * k
    paso = (gx1 - gx0) / n
    bw = paso * 0.62
    mayor = max(valores) if max(valores) > 0 else 1.0
    ox, oy = int(math.floor(gx0)), int(math.floor(gy0)) - 2
    zw, zh = int(math.ceil(gx1 - gx0)) + 2, int(math.ceil(gy1 - gy0)) + 4
    xx, yy = _rejilla(zw, zh)
    xx, yy = xx + ox, yy + oy
    b0, b1 = BARRAS
    imax = int(np.argmax(valores))

    def animar(capa, t):
        r = c.estado['r']
        dur = (b1 - b0) * r
        cada = dur / (1.0 + 0.35 * (n - 1))
        lleno = 0.0
        tn = _a_saltos(t, b0 * r, c.fps)
        for i, v in enumerate(valores):
            a = b0 * r + i * cada * 0.35
            lleno += v * min(1.0, B.rebote(B.tramo(tn, a, a + cada), 1.0) if tn > a else 0.0)
            p = B.rebote(B.tramo(t, a, a + cada), 1.0) if t > a else 0.0
            if p <= 0:
                continue
            alto = max(bw * 0.5, (gy1 - gy0) * 0.94 * (v / mayor) * p)
            cxb = gx0 + paso * (i + 0.5)
            sd = _sdf_caja(xx, yy, cxb, gy1 - alto / 2, bw / 2, alto / 2, min(bw / 2, 7 * k))
            _pintar(capa, _cob(sd), colf if i == imax else claro, min(1.0, p * 3), ox, oy)
        acabado = t >= b1 * r + 0.05
        numero(corto(total if acabado else lleno)).poner(capa, pad - 1.5 * k, 80 * k)

    T.animar = animar
    return T


# ── La colocación ───────────────────────────────────────────────────────────────────────────────────────────────────
def _caja_cara(cara, s, P):
    """La caja de la cara (x0, y0, x1, y1, ancho) con la cámara acercada `s` hacia P."""
    cx, cy, fw = (float(v) for v in cara)
    cx, cy, fw = P[0] + s * (cx - P[0]), P[1] + s * (cy - P[1]), fw * s
    return cx - 0.5 * fw, cy - 0.62 * fw, cx + 0.5 * fw, cy + 0.58 * fw, fw


def _distancia(caja, x0, y0, x1, y1):
    fx0, fy0, fx1, fy1, _ = caja
    dx = max(fx0 - x1, x0 - fx1, 0.0)
    dy = max(fy0 - y1, y0 - fy1, 0.0)
    return math.hypot(dx, dy)


def _rect(c, izq, k, ancho, alto, y0):
    u = c.u
    w, h = ancho * k * TAMANO * u, alto * k * TAMANO * u
    x0 = BORDE * u if izq else c.W - BORDE * u - w
    return x0, y0, x0 + w, y0 + h


def _cabe(cajas, rect, margen=MARGEN_CARA):
    return all(_distancia(cj, *rect) >= margen * cj[4] for cj in cajas)


def _preparar(c):
    u, W, H = c.u, c.W, c.H
    op = c.op
    L = {}
    c.estado['r'] = min(1.0, c.dur / DURACION)
    col = B.color(op.get('color') or '#22C55E')[:3]
    zoom = min(1.4, max(1.0, _leer_numero(op.get('zoom'), 1.22)))
    L['zoom'] = zoom
    cx = float(c.cara[0])
    lado = str(op.get('lado') or 'auto').strip().lower()
    izq = (cx >= W / 2) if lado not in ('izquierda', 'izq', 'derecha', 'der') else lado.startswith('izq')
    L['izq'] = izq
    # la cámara se acerca hacia la esquina de arriba del lado libre (el centro de la tarjeta grande, a su altura de
    # arriba): la cara se aparta hacia el otro lado y hacia abajo
    r0 = _rect(c, izq, 1.0, ANCHO, ALTO, ARRIBA * u)
    P = ((r0[0] + r0[2]) / 2, ARRIBA * u + 40 * u)
    L['P'] = P
    cajas = [_caja_cara(c.cara, 1.0, P), _caja_cara(c.cara, zoom, P)]
    # la tarjeta grande: del tamaño completo hacia abajo, hasta que no se acerque a la cara (quieta y acercada)
    k = MENOR
    for kk in np.arange(1.0, MENOR - 1e-6, -0.02):
        if _cabe(cajas, _rect(c, izq, kk, ANCHO, ALTO, ARRIBA * u)):
            k = float(kk)
            break
    L['k'] = k
    L['t1'] = _principal(c, k * TAMANO * u, col)
    L['r1'] = _rect(c, izq, k, ANCHO, ALTO, ARRIBA * u)
    # la de las barras, debajo y del mismo lado; si no cabe ni pequeña, no sale
    L['t2'] = None
    valores = _lista(op.get('barras'))
    if valores and max(valores) > 0:
        # primero debajo de la grande; si ahí no cabe sin hacerse ilegible, en la otra esquina de arriba
        x0, y0, x1, y1 = L['r1']
        for lado2, y2, desde in ((izq, y1 + HUECO2 * u, k), (not izq, ARRIBA * u, 1.0)):
            for kk in np.arange(desde, MENOR2 - 1e-6, -0.02):
                rect = _rect(c, lado2, kk, ANCHO2, ALTO2, y2)
                pisa = rect[0] < x1 + HUECO2 * u and rect[2] > x0 - HUECO2 * u and rect[1] < y1 + HUECO2 * u - 1
                if _cabe(cajas, rect, MARGEN_BARRAS) and rect[3] < H * 0.62 and not pisa:
                    L['t2'] = _barras(c, float(kk) * TAMANO * u, col, valores)
                    L['r2'] = rect
                    break
            if L['t2'] is not None:
                break
    c.estado['L'] = L
    return L


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _vidrio(c, X0, Y0, X1, Y1, sigma):
    """Lo que hay detrás de un trozo del cuadro, muy desenfocado (se desenfoca pequeño y se agranda: es suave)."""
    m = int(math.ceil(2.5 * sigma))
    a0, b0, a1, b1 = max(0, X0 - m), max(0, Y0 - m), min(c.W, X1 + m), min(c.H, Y1 + m)
    trozo = c.img[b0:b1, a0:a1]
    f = 4
    peq = cv2.resize(trozo, (max(1, (a1 - a0) // f), max(1, (b1 - b0) // f)), interpolation=cv2.INTER_AREA)
    peq = cv2.GaussianBlur(peq, (0, 0), sigma / f, borderType=cv2.BORDER_REFLECT)
    grande = cv2.resize(peq, (a1 - a0, b1 - b0), interpolation=cv2.INTER_LINEAR)
    return grande[Y0 - b0:Y1 - b0, X0 - a0:X1 - a0]


def _poner_tarjeta(c, T, x, y, esc, alfa):
    """Pone la tarjeta con su esquina de arriba a la izquierda en (x, y) (con decimales) y escalada `esc` desde su
    centro: la sombra, el cristal (lo de detrás desenfocado) y lo de encima."""
    if alfa <= 0.003:
        return
    u = c.u
    w, h, p = T.w, T.h, T.pad
    cxc, cyc = x + w / 2, y + h / 2
    X, Y = cxc - esc * w / 2, cyc - esc * h / 2               # la esquina ya escalada
    X0, Y0 = max(0, int(math.floor(X - p * esc)) - 1), max(0, int(math.floor(Y - p * esc)) - 1)
    X1, Y1 = min(c.W, int(math.ceil(X + (w + p) * esc)) + 2), min(c.H, int(math.ceil(Y + (h + p) * esc)) + 2)
    if X1 <= X0 or Y1 <= Y0:
        return
    zona = c.img[Y0:Y1, X0:X1]
    # al entrar y al salir, el cristal se empaña y se desempaña (el desenfoque crece con él) en vez de fundirse: si se
    # fundiera, lo de detrás se vería nítido a través de la tarjeta a medio aparecer
    empano = B.sale(min(1.0, alfa * 1.25))
    fondo = _vidrio(c, X0, Y0, X1, Y1, max(1.0, DESENFOQUE * u * empano))
    fondo = 1.0 - (1.0 - fondo) * np.float32(1.0 - 0.12 * empano)                 # un poco más claro, como esmerilado
    tam = (X1 - X0, Y1 - Y0)
    M = np.float32([[esc, 0, X - X0], [0, esc, Y - Y0]])
    Ms = np.float32([[esc, 0, X - p * esc - X0], [0, esc, Y - p * esc - Y0]])
    sh = cv2.warpAffine(T.sombra, Ms, tam, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    F = cv2.warpAffine(T.forma, M, tam, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    C = cv2.warpAffine(T.capa(c.t), M, tam, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                       borderValue=(0, 0, 0, 0))
    a = np.float32(alfa)
    zona *= (1.0 - sh * a)[..., None]
    Fa = (F * np.float32(min(1.0, alfa * 2.5)))[..., None]
    zona *= (1.0 - Fa)
    zona += fondo * Fa
    Ca = C[..., 3:4] * a
    zona *= (1.0 - Ca)
    zona += C[..., :3] * a


def _camara(c, s, P):
    """Acerca el cuadro entero `s` veces hacia P (con decimales: sin saltitos)."""
    if s <= 1.0 + 1e-5:
        return
    M = np.float32([[s, 0, P[0] * (1 - s)], [0, s, P[1] * (1 - s)]])
    hecho = cv2.warpAffine(c.img, M, (c.W, c.H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    np.copyto(c.img, hecho)


def dibujar(c):
    L = c.estado.get('L') or _preparar(c)
    u = c.u
    r = c.estado['r']
    P = L['P']

    # 1. la cámara: se acerca suave al empezar y vuelve al acabar (el último cuadro ya es el plano de verdad)
    z = B.suave(B.tramo(c.t, 0, CAMARA_ENTRA * r)) * B.suave(B.tramo(c.queda, 0, CAMARA_SALE * r))
    s = 1.0 + (L['zoom'] - 1.0) * z
    _camara(c, s, P)
    cara = _caja_cara(c.cara, s, P)

    # 2. las tarjetas: suben con un rebote y un fundido, flotan un poco y se van con un fundido cuando vuelve la cámara
    sale = _seno(B.tramo(c.queda - (FUNDIDO_DESDE - FUNDIDO_SALE) * r, 0, FUNDIDO_SALE * r))
    tarjetas = [(L['t1'], L['r1'], 0.0, MARGEN_CARA)]
    if L['t2'] is not None:
        tarjetas.append((L['t2'], L['r2'], SEGUNDA_DESPUES, MARGEN_BARRAS))
    techo = TECHO * u
    for T, (x0, y0, x1, y1), retraso, margen in tarjetas:
        a0 = (TARJETA_ENTRA[0] + retraso) * r
        p = B.tramo(c.t, a0, a0 + TARJETA_ENTRA[1] * r)
        if p <= 0.0:
            continue
        entra = B.rebote(p, 1.1)
        alfa = B.tramo(c.t, a0, a0 + FUNDIDO_ENTRA * r) * sale
        flota = math.sin((c.t - a0) * 2 * math.pi / 2.8) * 3.0 * u * min(1.0, p * 1.5)
        y = y0 + (1.0 - entra) * SUBE * u + flota
        esc = 0.95 + 0.05 * entra
        # si la persona se le acerca de verdad (a menos de lo que se dejó al colocarla, con holgura para que moverse un
        # poco no haga nada): la grande sube lo que pueda y, si ni así, las dos se desvanecen antes que tapar la cara
        m = margen * HOLGURA * cara[4]
        d = _distancia(cara, x0, y, x1, y + (y1 - y0))
        if d < m and retraso == 0.0 and (y + (y1 - y0) / 2) < (cara[1] + cara[3]) / 2:
            y = max(techo, y - (m - d))
            d = _distancia(cara, x0, y, x1, y + (y1 - y0))
        se_ve = 1.0 if d >= m else float(np.clip((d - 0.3 * m) / (0.7 * m), 0, 1))
        _poner_tarjeta(c, T, x0, y, esc, alfa * se_ve)
