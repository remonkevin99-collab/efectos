"""sobre-el-hombro: la cámara se acerca de golpe hacia una esquina de arriba y ahí aparece una tarjeta de cristal claro con
tu número subiendo y su gráfica de línea dibujándose, un poco METIDA DETRÁS DE TU CABEZA (tu cabeza o tu gorra va delante
de la parte de abajo de la tarjeta). Si le das `barras`, la cámara vuelve al plano abierto y se acerca hacia la OTRA
esquina, donde sale una segunda tarjeta, también detrás de tu cabeza, con las barras creciendo y su total.

Lo que pasa (el ritmo, copiado cuadro a cuadro de un Reel de referencia; los segundos cuentan desde `empieza`):
  - 0–0,33 s: el primer acercamiento (de 1 a `zoom`), rápido: arranca y frena suave. La cámara va hacia la esquina
    de arriba del lado de la tarjeta: tu cara se va al otro lado y hacia abajo, y tu cabeza queda justo debajo de la
    tarjeta, tapando un poco su parte de abajo. Mientras está cerca sigue entrando muy despacio (no se queda muerta).
  - 0,2 s: la tarjeta aparece en su sitio con un fundido corto y un rebote pequeño. Lleva el título pequeño en
    mayúsculas (`titulo`) arriba a la izquierda, el número grande arriba a la derecha, que cuenta de `inicio` a `final`
    escrito corto («125K», «1,2M», «9,9K»), y la gráfica de línea que se dibuja de izquierda a derecha al mismo paso que
    el número (el número es siempre el valor de la punta), con un punto brillante en la punta y debajo un degradado
    suave del color de la línea (`color`).
  - Con `barras` («40,65,52,80,120»): a los 0,9 s la cámara vuelve al plano abierto en 0,33 s (la tarjeta se va justo
    antes) y, sin llegar a pararse, se acerca igual de rápido hacia la otra esquina, donde sale la tarjeta de las
    barras: su título (`titulo_barras`), su total (la suma de las barras) y las barras creciendo una detrás de otra.
  - Con `portadas` (una carpeta con las portadas de tus Reels, en orden) la segunda tarjeta, en vez de barras, es una
    rejilla de 4 × 2 con ellas (proporción de Reel, esquinas redondeadas), cada una con sus vistas (`vistas_portadas`)
    en una pastilla; entran una detrás de otra con un fundido rápido mientras su total (`total`, o la suma) cuenta. La
    primera va con un brillo dorado y su número más grande. La rejilla va del lado de fuera y el título y el total, del
    lado de la cabeza (lo de abajo de ese lado queda detrás). La primera portada sale también, pequeña, junto al título
    de la tarjeta de la línea.
  - Los últimos 0,6 s: la cámara vuelve a como estaba, suave (el último cuadro del efecto ya es el plano original: el
    corte no se nota), y en cuanto se pone en marcha la tarjeta se va con un fundido. El cristal se empaña al entrar y se
    desempaña al salir (no se funde: así no se ve nítido lo de detrás a través de él).
  - Los números que cuentan cambian cada 3 cuadros (~10 veces por segundo): si cambiaran en cada cuadro, parpadearían.
  - `empieza`: los segundos de plano quieto antes del primer acercamiento. Sirve en un montaje donde el clip se ve primero
    pequeño (en una tarjeta de chat) y salta a la pantalla entera: el acercamiento, en el salto.
  - Si el efecto dura menos de lo que pide este ritmo, todo se aprieta; si dura más, la última tarjeta se queda más.

El cristal es claro: desenfoca lo que tiene detrás (la pared, sin la persona), lo blanquea, lleva un brillo en diagonal,
un filo fino brillante (más claro arriba) y una sombra suave. El texto va oscuro, para que se lea en el teléfono.

Nunca tapa la cara: la tarjeta va DETRÁS de la persona (el recorte la tapa, con el color de verdad del borde de la
persona, sin filo de la pared) y el acercamiento se calcula para que la tarjeta acabe por encima de la cara, solo detrás
de la cabeza; si no cabe así, la tarjeta se hace más pequeña. La cara nunca se sale de la zona segura de Instagram, y las
tarjetas tampoco (de x 60 a x 1020 a 1080 de ancho y por debajo de y 210): no se acercan con la cámara.

    .venv/bin/python efectos.py sobre-el-hombro tu_video.mp4 --desde 2 --op final=125000 --op barras=40,65,52,80 --fotos 2.5,3.5
"""
import math
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw

import base as B

NOMBRE = 'sobre-el-hombro'
DESCRIPCION = 'La cámara se acerca a un lado y aparece una gráfica de cristal detrás de tu cabeza con tu número subiendo'
OPCIONES = {
    'titulo': 'VISTAS',                 # la línea pequeña de arriba (va en mayúsculas)
    'inicio': '0',                      # de dónde empieza a contar el número
    'final': '125000',                  # dónde acaba («125000», «125.000», «125K» o «1,2M» valen)
    'color': '#22C55E',                 # el color de la línea, su punto, su degradado y las barras
    'barras': '',                       # un segundo acercamiento, al otro lado, con una tarjeta de barras: sus valores
                                        # («40,65,52,80»; su total es la suma; vacía: un solo acercamiento)
    'titulo_barras': 'ÚLTIMOS REELS',   # el título de la segunda tarjeta (barras o portadas): di qué es su total
    'portadas': '',                     # una carpeta con las portadas de tus Reels, en orden (por nombre): la segunda
                                        # tarjeta pasa a ser una rejilla de 4 × 2 con ellas y sus vistas (en vez de las
                                        # barras), y la primera lleva la primera portada junto al título
    'vistas_portadas': '',              # las vistas de cada portada, en el mismo orden y como se tienen que leer
                                        # («1M|244K|147K|9937»; separadas por |)
    'total': '',                        # el número grande de la segunda tarjeta (vacío: la suma de las barras o, si no
                                        # hay, de las vistas de las portadas). Ponle el número exacto si lo tienes
    'lado': 'auto',                     # hacia dónde va el primer acercamiento (y la línea): «auto» (el lado con más sitio;
                                        # si estás en el centro, la izquierda), «izquierda» o «derecha». Las barras, al otro
    'zoom': '1.75',                     # cuánto se acerca la cámara (1 = nada; de 1 a 2,2). Si con tanto la cara se saliera
                                        # de la pantalla o la tarjeta no le cupiera encima, se acerca menos
    'empieza': '0',                     # segundos de plano quieto antes del primer acercamiento
}
DURACION = 3.5

# ── El ritmo (segundos desde `empieza`; medido cuadro a cuadro en la referencia, que va a 30 fps) ──────────────────────
ACERCA = 0.33               # cada acercamiento (10 cuadros: arranca y frena suave, deprisa en medio; con menos, el
                            # primer y el último cuadro dan un tirón)
DERIVA = 0.04               # mientras está cerca, sigue entrando muy despacio: un 4 % por segundo
ENTRA = 0.20                # la tarjeta empieza a aparecer esto después de empezar su acercamiento…
FUNDIDO_ENTRA = 0.20        # …con un fundido de esto (nada aparece de golpe)…
REBOTE = 0.36               # …y sube a su sitio con un rebote corto en esto
SUBE = 30                   # desde cuántos px (a 1080) más abajo sube
LINEA = (0.26, 0.64)        # la línea se dibuja (y el número cuenta) en este tramo
VUELVE = 0.90               # con barras: aquí la cámara empieza a volver al plano abierto…
ALEJA = 0.33                # …en esto (arranca y frena suave)…
FUNDIDO_SALE = 0.24         # …y la tarjeta de la línea se va con un fundido de esto (arranca y acaba suave)…
DESFASE = -0.10             # …que empieza esto antes de que la cámara se mueva: así ya no está cuando, al alejarse, la
                            # cabeza destapa su esquina (se veía un cuadro suelto), y no arranca en el mismo cuadro que la
                            # cámara (sumadas, daban un tirón)
CRUCE = 0.10                # el segundo acercamiento arranca esto antes de que acabe la vuelta (las dos cosas a la vez,
                            # como en la referencia: la cámara no llega a pararse; parada del todo, el arranque se notaba)
BARRAS = (0.22, 0.50)       # las barras crecen (y su total cuenta) en este tramo, desde que empieza el segundo acercamiento
LEER = 0.30                 # lo mínimo para leer el último número antes de que la cámara vuelva
VUELTA = 0.60               # al acabar, la cámara vuelve al plano de verdad en esto (y frena más suave todavía: después
                            # el plano se queda quieto, y un frenazo ahí se nota)

# ── La colocación (a 1080 × 1920; se escala con el vídeo) ───────────────────────────────────────────────────────────
BORDE = 66                  # de la tarjeta al borde de su lado (la zona segura empieza en 60)
ARRIBA = 232                # dónde empieza la tarjeta por arriba (lo de Instagram acaba en 210)
ANCHO, ALTO = 860, 480      # las dos tarjetas, a tamaño completo (en la referencia, ~0,8 del ancho y ~0,27 del alto)
MENOR = 0.62                # lo más pequeñas que se hacen si no caben encima de la cara (en proporción)
SOLAPE = 0.27               # cuánto de la tarjeta (de su alto) queda detrás de la cabeza: la coronilla va ahí (en la
                            # referencia, ~1/3 por donde la cabeza es más alta)
CARA_X = 0.70               # dónde queda el centro de la cara con la cámara cerca (en proporción del ancho, desde el
                            # lado de la tarjeta): la cara se va al otro lado, como en la referencia
MARGEN_CARA = 0.25          # de la tarjeta a la frente, como poco (en anchos de cara): la tarjeta solo va detrás de la cabeza
DESENFOQUE = 44             # cuánto se desenfoca lo de detrás (a 1080): mucho, para que un cuadro oscuro detrás no manche
BLANCO = 0.6                # cuánto blanquea el cristal arriba (abajo, un poco menos)
SS = 4                      # la línea se dibuja 4 veces más grande y se reduce (bordes suaves)

TINTA = (20, 17, 34)        # el texto oscuro
TINTA_SUAVE = (74, 70, 96)  # el título


# ── Números ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _leer_numero(v, defecto):
    """«125000», «125.000», «125 000», «125K», «1,2M», «9,9 mil» → número. Si no se entiende, `defecto`."""
    s = str(v or '').strip().lower().replace(' ', '').replace(' ', '')
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


def _acerca(x):
    """La curva de los acercamientos y de la vuelta al plano abierto: arranca y frena suave, muy deprisa en medio. Medido
    cuadro a cuadro en la referencia (cuánto cambia la imagen de un cuadro al siguiente): sube en 3–4 cuadros, cada uno
    como mucho ~2,4 veces el anterior, y baja igual. Si arrancara a toda velocidad (o con una curva seno, en una toma
    tranquila), el primer cuadro sería un tirón: por eso es casi toda cúbica."""
    return 0.75 * B.suave(x) + 0.25 * _seno(x)


def _frena(x):
    """La vuelta del final: como `_acerca`, pero frena todavía más suave (después viene el plano quieto)."""
    x = min(1.0, max(0.0, x))
    return x * x * x * (10.0 - 15.0 * x + 6.0 * x * x)


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
        self.derecha = self.pad + f.getbbox(s)[2] if s else self.pad      # dónde acaba la tinta
        self.arr = _premult(capa)

    def poner(self, dst, x, y):
        """La tinta empieza en x y las mayúsculas quedan centradas en y."""
        _sobre(dst, self.arr, int(round(x - self.pad)), int(round(y - self.medio)))

    def poner_derecha(self, dst, x, y):
        """La tinta acaba en x (alineado a la derecha) y las mayúsculas quedan centradas en y."""
        _sobre(dst, self.arr, int(round(x - self.derecha)), int(round(y - self.medio)))


def _tam_que_cabe(s, peso, tam, ancho, espacio=0.0):
    f = B.fuente(peso, 100)
    largo = (sum(f.getlength(ch) for ch in s) + espacio * 100 * max(0, len(s) - 1)) if espacio else f.getlength(s)
    return min(tam, ancho / max(1e-3, largo / 100.0))


def _ancho_numeros(inicio, final, tam):
    """Lo más ancho que se pone el número mientras cuenta (para que el título no lo pise)."""
    f = B.fuente('extrabold', tam)
    return max(f.getlength(corto(v)) for v in np.linspace(inicio, final, 240))


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


def _cabecera(T, k, titulo, tam_titulo, col, ancho_numero, pad, x0=None):
    """Arriba a la izquierda (desde `x0`), el punto del color y el título pequeño, sin llegar al número (que va a la
    derecha)."""
    x0 = pad if x0 is None else x0
    yt = 52 * k
    quieto = Image.new('RGBA', (T.w * SS, T.h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(quieto)
    d.ellipse([x0 * SS, (yt - 7 * k) * SS, (x0 + 14 * k) * SS, (yt + 7 * k) * SS], fill=tuple(col) + (255,))
    _sobre(T.base, _premult(quieto.resize((T.w, T.h), Image.LANCZOS)), 0, 0)
    titulo = ' '.join(str(titulo or '').split()).upper()
    if titulo:
        libre = T.w - pad - x0 - 24 * k - ancho_numero - 28 * k
        tam = _tam_que_cabe(titulo, 'medium', tam_titulo * k, max(40 * k, libre), 0.12)
        _Rotulo(titulo, tam, 'medium', TINTA_SUAVE, espacio=0.12).poner(T.base, x0 + 24 * k, yt)


def _miniatura(im, w, h, r):
    """Una portada recortada a w × h (sin deformarla: se recorta lo que sobra, centrado) y con las esquinas redondeadas,
    como capa premultiplicada."""
    w, h = max(2, int(round(w))), max(2, int(round(h)))
    iw, ih = im.size
    e = max(w / iw, h / ih)
    cw, ch = w / e, h / e
    x0, y0 = (iw - cw) / 2, (ih - ch) / 2
    hecha = im.convert('RGBA').resize((w, h), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))
    return _premult(B.recortar_redondo(hecha, r))


def _rayas(T, k, pad, ys):
    """Las rayas muy suaves de la gráfica (la de abajo, un poco más marcada)."""
    quieto = Image.new('RGBA', (T.w * SS, T.h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(quieto)
    for i, y in enumerate(ys):
        d.line([(pad * SS, y * SS), ((T.w - pad) * SS, y * SS)], fill=TINTA + (38 if i == len(ys) - 1 else 22,),
               width=max(1, round(1.3 * k * SS)))
    _sobre(T.base, _premult(quieto.resize((T.w, T.h), Image.LANCZOS)), 0, 0)


def _curva(n=900):
    """La forma de la gráfica: sube cada vez más rápido, con tramos más y menos empinados (como unas vistas de verdad),
    pero sin bajar nunca, para que el número que va con la punta no retroceda. De 0 a 1 en x y en y."""
    x = np.linspace(0.0, 1.0, n)
    pendiente = np.exp(2.5 * x) * (1.0 + 0.55 * np.sin(2 * math.pi * 2.35 * x + 0.9)
                                   + 0.22 * np.sin(2 * math.pi * 5.1 * x + 2.3))
    pendiente = np.maximum(pendiente, 0.05)
    y = np.concatenate([[0.0], np.cumsum((pendiente[1:] + pendiente[:-1]) / 2)])
    return x, y / y[-1]


def _principal(c, k, col, a0):
    """La tarjeta de la línea: título, número que cuenta (arriba a la derecha) y la gráfica de línea. `a0`: cuándo empieza
    su acercamiento (los tiempos de dentro cuentan desde ahí)."""
    op = c.op
    r = c.estado['r']
    T = _Tarjeta(ANCHO * k, ALTO * k, 40 * k, k)
    w, h = T.w, T.h
    pad = 40 * k
    colf = np.float32(col) / 255.0
    inicio = _leer_numero(op.get('inicio'), 0.0)
    final = _leer_numero(op.get('final'), 125000.0)
    tam_num = 100 * k
    portadas = c.estado.get('portadas') or []
    x_titulo = pad
    if portadas:                                      # la primera portada, pequeña, a la izquierda del título
        mw, mh = 54 * k, 96 * k
        _sobre(T.base, _miniatura(portadas[0], mw, mh, 9 * k), int(round(pad)), int(round(22 * k)))
        x_titulo = pad + mw + 16 * k
    _cabecera(T, k, op.get('titulo'), 26, col, _ancho_numeros(inicio, final, tam_num), pad, x_titulo)
    gx0, gx1 = pad, w - pad
    gy0, gy1 = 156 * k, h - 40 * k
    _rayas(T, k, pad, (gy0, (gy0 + gy1) / 2, gy1))

    # la curva en píxeles de la tarjeta: de abajo a la izquierda a la raya de arriba a la derecha
    cx_, cy_ = _curva()
    arriba, abajo = gy0, gy1 - 8 * k
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
    grosor = 8 * k * SS
    dg.line(puntos, fill=255, width=int(round(grosor)), joint='curve')
    for (a, b) in (puntos[0], puntos[-1]):
        dg.ellipse([a - grosor / 2, b - grosor / 2, a + grosor / 2, b + grosor / 2], fill=255)
    linea = np.asarray(grande.resize((w, h), Image.LANCZOS), np.float32) / 255.0
    resplandor = cv2.GaussianBlur(linea, (0, 0), 7 * k) * 0.55
    _pintar(g, np.clip(resplandor, 0, 1).astype(np.float32), colf)
    _pintar(g, np.clip(linea, 0, 1).astype(np.float32), colf)
    columnas = xx[0]

    # el número (sus capas se guardan por texto: cambian muchas veces y se repiten)
    rotulos = {}

    def numero(s):
        if s not in rotulos:
            rotulos[s] = _Rotulo(s, tam_num, 'extrabold', TINTA)
        return rotulos[s]

    # el punto de la punta: una cobertura en un trocito, con decimales
    lado = int(math.ceil(64 * k))
    pxx, pyy = _rejilla(lado, lado)
    blanco = np.float32([1.0, 1.0, 1.0])
    l0, l1 = a0 + LINEA[0] * r, a0 + LINEA[1] * r

    def animar(capa, t):
        q = _seno(B.tramo(t, l0, l1))
        xt = gx0 + (gx1 - gx0) * q
        yt_ = float(np.interp(xt, px, py))
        # destapa la línea y el degradado hasta la punta (borde suave de un píxel)
        cols = np.clip(xt - columnas + 0.5, 0, 1).astype(np.float32)
        hasta = min(w, int(math.ceil(xt + 2 * k + 2)))
        _sobre(capa, g[:, :hasta] * cols[None, :hasta, None], 0, 0)
        # el número: el valor de la gráfica en la punta (al acabar, justo el final)
        qn = _seno(B.tramo(_a_saltos(t, l0, c.fps), l0, l1))
        v = inicio + (final - inicio) * float(np.interp(qn, cx_, cy_))
        numero(corto(final if q >= 1.0 else v)).poner_derecha(capa, w - pad, 84 * k)
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


def _barras(c, k, col, valores, a0):
    """La tarjeta de las barras: su título, el total que cuenta (arriba a la derecha) y las barras que crecen una detrás
    de otra. La más alta, del color entero; las demás, más claras. `a0`: cuándo empieza su acercamiento."""
    r = c.estado['r']
    T = _Tarjeta(ANCHO * k, ALTO * k, 40 * k, k)
    w, h = T.w, T.h
    pad = 40 * k
    colf = np.float32(col) / 255.0
    claro = colf + (1.0 - colf) * 0.4
    total = sum(valores)
    tam_num = 100 * k
    _cabecera(T, k, c.op.get('titulo_barras'), 26, col, _ancho_numeros(0.0, total, tam_num), pad)
    n = len(valores)
    gx0, gx1 = pad, w - pad
    gy0, gy1 = 156 * k, h - 40 * k
    _rayas(T, k, pad, (gy0, (gy0 + gy1) / 2, gy1))
    rotulos = {}

    def numero(s):
        if s not in rotulos:
            rotulos[s] = _Rotulo(s, tam_num, 'extrabold', TINTA)
        return rotulos[s]

    paso = (gx1 - gx0) / n
    bw = paso * 0.66
    mayor = max(valores) if max(valores) > 0 else 1.0
    ox, oy = int(math.floor(gx0)), int(math.floor(gy0)) - 2
    zw, zh = int(math.ceil(gx1 - gx0)) + 2, int(math.ceil(gy1 - gy0)) + 4
    xx, yy = _rejilla(zw, zh)
    xx, yy = xx + ox, yy + oy
    b0, b1 = a0 + BARRAS[0] * r, a0 + BARRAS[1] * r
    imax = int(np.argmax(valores))

    def animar(capa, t):
        dur = b1 - b0
        cada = dur / (1.0 + 0.35 * (n - 1))
        # el total cuenta parejo de 0 a la suma mientras crecen las barras (si sumara lo que llevan las barras, con la
        # más alta la primera saltaría de 0 a casi todo de una vez)
        lleno = total * _seno(B.tramo(_a_saltos(t, b0, c.fps), b0, b1))
        for i, v in enumerate(valores):
            a = b0 + i * cada * 0.35
            p = B.rebote(B.tramo(t, a, a + cada), 1.0) if t > a else 0.0
            if p <= 0:
                continue
            alto = max(bw * 0.3, (gy1 - gy0) * (v / mayor) * p)
            cxb = gx0 + paso * (i + 0.5)
            sd = _sdf_caja(xx, yy, cxb, gy1 - alto / 2, bw / 2, alto / 2, min(bw / 2, 9 * k))
            _pintar(capa, _cob(sd), colf if i == imax else claro, min(1.0, p * 3), ox, oy)
        acabado = t >= b1 + 0.05
        numero(corto(total if acabado else lleno)).poner_derecha(capa, w - pad, 84 * k)

    T.animar = animar
    return T


ORO = (250, 204, 21)        # el brillo y la pastilla de la primera portada (la de más vistas)
ENTRA_PORTADA = 0.14        # cada portada entra con un fundido de esto…
CADA_PORTADA = 0.035        # …una detrás de otra, con este escalonado


def _rejilla_portadas(c, k, col, etiquetas, total, a0, derecha):
    """La segunda tarjeta con portadas: a un lado, el título (en dos líneas si hace falta) y el total que cuenta, con
    «VISTAS EN TOTAL» debajo; al otro, las portadas en una rejilla de 4 × 2, con proporción de Reel y esquinas
    redondeadas, cada una con sus vistas en una pastilla. La primera, con un brillo dorado y su número más grande. La
    rejilla va del lado de fuera (el de la tarjeta que no tapa la cabeza) y el texto arriba del lado de dentro: lo de
    abajo de ese lado queda detrás de la cabeza. Entran una detrás de otra con un fundido rápido mientras el total
    cuenta. `derecha`: la tarjeta va a la derecha."""
    r = c.estado['r']
    imgs = c.estado['portadas']
    n = len(imgs)
    T = _Tarjeta(ANCHO * k, ALTO * k, 40 * k, k)
    w, h = T.w, T.h
    pad = 28 * k
    gap = 12 * k
    filas = 2 if n > 4 else 1
    cols = 4 if n > 4 else n
    th = (h - 2 * pad - gap * (filas - 1)) / filas
    tw = th * 9 / 16
    gw = cols * tw + (cols - 1) * gap
    gx = w - pad - gw if derecha else pad
    tx0 = pad + 6 * k if derecha else gx + gw + 30 * k               # la columna del texto
    tx1 = gx - 30 * k if derecha else w - pad
    ancho_txt = max(60 * k, tx1 - tx0)
    # el título, en las líneas que hagan falta, con el punto del color delante
    titulo = ' '.join(str(c.op.get('titulo_barras') or '').split()).upper()
    tam_t = 24 * k
    palabras = titulo.split()
    if not palabras or _tam_que_cabe(titulo, 'medium', tam_t, ancho_txt - 24 * k, 0.12) >= tam_t * 0.999:
        lineas = [titulo] if titulo else []
    else:                                       # en dos líneas, partido donde quedan más parejas
        f = B.fuente('medium', 100)
        corte = min(range(1, len(palabras)) or [1], key=lambda i: max(f.getlength(' '.join(palabras[:i])),
                                                                     f.getlength(' '.join(palabras[i:]))))
        lineas = [' '.join(palabras[:corte]), ' '.join(palabras[corte:])]
    quieto = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(quieto)
    yt = 52 * k
    d.ellipse([tx0 * SS, (yt - 7 * k) * SS, (tx0 + 14 * k) * SS, (yt + 7 * k) * SS], fill=tuple(col) + (255,))
    _sobre(T.base, _premult(quieto.resize((w, h), Image.LANCZOS)), 0, 0)
    for i, ln in enumerate(lineas):
        tam = _tam_que_cabe(ln, 'medium', tam_t, ancho_txt - 24 * k, 0.12)
        _Rotulo(ln, tam, 'medium', TINTA_SUAVE, espacio=0.12).poner(T.base, tx0 + 24 * k, yt + i * 34 * k)
    y_num = yt + len(lineas) * 34 * k + 52 * k
    tam_num = min(100 * k, _tam_que_cabe(corto(total), 'extrabold', 100 * k, ancho_txt))
    _Rotulo('VISTAS EN TOTAL', 20 * k, 'medium', TINTA_SUAVE, espacio=0.12).poner(T.base, tx0, y_num + 62 * k)
    rotulos = {}

    def numero(s):
        if s not in rotulos:
            rotulos[s] = _Rotulo(s, tam_num, 'extrabold', TINTA)
        return rotulos[s]

    # cada portada, hecha una vez: su brillo (la primera), la portada, su filo y su pastilla
    m = int(math.ceil(26 * k))
    fichas = []
    for i, im in enumerate(imgs):
        W2, H2 = int(math.ceil(tw)) + 2 * m, int(math.ceil(th)) + 2 * m
        f = np.zeros((H2, W2, 4), np.float32)
        rr = 12 * k
        xx, yy = _rejilla(W2, H2)
        sd = _sdf_caja(xx, yy, W2 / 2, H2 / 2, tw / 2, th / 2, rr)
        if i == 0:                                                   # el brillo dorado de la de más vistas
            brillo = cv2.GaussianBlur(_cob(sd - 3 * k), (0, 0), 9 * k) * 0.95
            _pintar(f, np.clip(brillo, 0, 1).astype(np.float32), np.float32(ORO) / 255.0)
        _sobre(f, _miniatura(im, tw, th, rr), m, m)
        if i == 0:
            _pintar(f, (_cob(sd) - _cob(sd + 3.2 * k)).astype(np.float32), np.float32(ORO) / 255.0)
        else:
            _pintar(f, (_cob(sd) - _cob(sd + 1.4 * k)).astype(np.float32), np.float32([1, 1, 1]), 0.55)
        txt = etiquetas[i] if i < len(etiquetas) else ''
        if txt:
            grande = i == 0
            tam = (25 if grande else 19) * k
            rot = _Rotulo(txt, tam, 'extrabold' if grande else 'bold', TINTA if grande else (255, 255, 255))
            ancho = B.fuente('extrabold' if grande else 'bold', tam).getlength(txt)
            pw, ph = min(tw - 8 * k, ancho + 20 * k), (40 if grande else 32) * k
            pcx, pcy = W2 / 2, m + th - 10 * k - ph / 2
            psd = _sdf_caja(xx, yy, pcx, pcy, pw / 2, ph / 2, ph / 2)
            if grande:
                _pintar(f, _cob(psd), np.float32(ORO) / 255.0)
            else:
                _pintar(f, _cob(psd), np.float32([15, 12, 30]) / 255.0, 0.74)
            rot.poner(f, pcx - ancho / 2, pcy)
        col_i, fila_i = i % cols, i // cols
        x = gx + col_i * (tw + gap) - m
        y = pad + fila_i * (th + gap) - m
        fichas.append((f, x, y))
    b0 = a0 + BARRAS[0] * r
    b1 = b0 + ((n - 1) * CADA_PORTADA + ENTRA_PORTADA) * r

    def animar(capa, t):
        for i, (f, x, y) in enumerate(fichas):
            a = b0 + i * CADA_PORTADA * r
            p = B.tramo(t, a, a + ENTRA_PORTADA * r)
            if p <= 0:
                continue
            alfa = _seno(p)
            e = 0.9 + 0.1 * B.rebote(p, 1.0)
            hh, ww = f.shape[:2]
            X0, Y0 = int(math.floor(x)), int(math.floor(y))
            # escalada desde su centro y subiendo un poco, con decimales
            M = np.float32([[e, 0, (1 - e) * ww / 2 + (x - X0)], [0, e, (1 - e) * hh / 2 + (y - Y0) + (1 - alfa) * 10 * k]])
            hecha = cv2.warpAffine(f, M, (ww, hh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                   borderValue=(0, 0, 0, 0))
            _sobre(capa, hecha * np.float32(alfa), X0, Y0)
        v = total * _seno(B.tramo(_a_saltos(t, b0, c.fps), b0, b1))
        numero(corto(total if t >= b1 + 0.05 else v)).poner(capa, tx0 - 2 * k, y_num)

    T.animar = animar
    return T


# ── La colocación ───────────────────────────────────────────────────────────────────────────────────────────────────
def _cam(s, P):
    """La cámara acercada `s` veces hacia el punto P, como (s, tx, ty): cada punto x del cuadro va a s·x + t."""
    return (s, P[0] * (1.0 - s), P[1] * (1.0 - s))


def _caja_cara(cara, cam):
    """La caja de la cara (x0, y0, x1, y1, ancho) con la cámara `cam`."""
    s, tx, ty = cam
    cx, cy, fw = (float(v) for v in cara)
    cx, cy, fw = s * cx + tx, s * cy + ty, fw * s
    return cx - 0.5 * fw, cy - 0.62 * fw, cx + 0.5 * fw, cy + 0.58 * fw, fw


def _coronilla(c, cx, cy, fw):
    """Dónde empieza la cabeza por arriba (la coronilla, o lo alto de la gorra), en el cuadro sin acercar: la primera fila,
    encima de la cara, donde la silueta ocupa algo en la franja de la cabeza. Sin silueta, un ancho de cara por encima."""
    m = c.mascara
    if m is None or m.size == 0:
        return cy - 1.0 * fw
    x0, x1 = int(max(0, cx - 0.55 * fw)), int(min(c.W, cx + 0.55 * fw))
    y1 = int(min(c.H, max(1, cy)))
    if x1 - x0 < 4:
        return cy - 1.0 * fw
    filas = (m[:y1, x0:x1] > 0.5).mean(axis=1)
    hay = np.nonzero(filas > 0.04)[0]
    return float(hay[0]) if hay.size else cy - 1.0 * fw


def _plan(c, izq, zoom):
    """Un acercamiento: hacia dónde va la cámara (P), cuánto (s) y dónde queda su tarjeta (rect y tamaño k), con la cara
    que hay en este cuadro. La tarjeta va arriba, pegada al borde de su lado; la cámara se acerca para que la coronilla
    quede SOLAPE por encima del borde de abajo de la tarjeta y la cara al otro lado (CARA_X), sin salirse de la zona
    segura y con la frente por debajo de la tarjeta. Si con `zoom` no se puede, se acerca menos; y si ni sin acercarse
    cabe la tarjeta encima de la cara, la tarjeta se hace más pequeña."""
    u, W, H = c.u, c.W, c.H
    cx, cy, fw = (float(v) for v in c.cara)
    corona = min(_coronilla(c, cx, cy, fw), cy - 0.62 * fw)
    frente = cy - 0.62 * fw
    y0 = ARRIBA * u
    seguro0, seguro1 = 62 * u, W - 62 * u
    mejor = None
    for s in np.arange(zoom, 1.0 - 1e-6, -0.05):
        s = float(s)
        for k in np.arange(1.0, MENOR - 1e-6, -0.04):
            k = float(k)
            h = ALTO * u * k
            # la cara: al otro lado de la tarjeta, dentro de la zona segura
            medio = 0.5 * fw * s
            xt = W * (CARA_X if izq else 1.0 - CARA_X)
            xt = min(max(xt, seguro0 + medio), seguro1 - medio)
            # la coronilla, SOLAPE por encima del borde de abajo de la tarjeta; y la frente, por debajo, con margen
            yt = y0 + h * (1.0 - SOLAPE)
            yt = max(yt, y0 + h + MARGEN_CARA * fw * s - s * (frente - corona))
            if s > 1.0 + 1e-3:
                P = ((xt - s * cx) / (1.0 - s), (yt - s * corona) / (1.0 - s))
                P = (min(max(P[0], 0.0), W), min(max(P[1], 0.0), H))       # dentro del cuadro: la imagen lo llena
            else:
                P = (W / 2, H / 2)
            caja = _caja_cara((cx, cy, fw), _cam(s, P))
            bien = (caja[0] >= seguro0 - 1 and caja[2] <= seguro1 + 1 and caja[3] <= H
                    and caja[1] >= y0 + h + MARGEN_CARA * caja[4] - 1)
            if bien:
                mejor = (s, P, k)
                break
        if mejor:
            break
    if mejor is None:                                     # ni sin acercarse: la tarjeta, lo más pequeña, y sin cámara
        mejor = (1.0, (W / 2, H / 2), MENOR)
    s, P, k = mejor
    w, h = ANCHO * u * k, ALTO * u * k
    x0 = BORDE * u if izq else W - BORDE * u - w
    return {'s': s, 'P': P, 'k': k, 'rect': (x0, y0, x0 + w, y0 + h)}


def _preparar(c):
    op = c.op
    L = {}
    vals = _lista(op.get('barras'))
    L['valores'] = vals if vals and max(vals) > 0 else []
    carpeta = str(op.get('portadas') or '').strip()
    portadas = B.imagenes_de(carpeta)[:8] if carpeta else []
    c.estado['portadas'] = portadas
    texto = str(op.get('vistas_portadas') or '')
    etiquetas = [x.strip() for x in (texto.split('|') if '|' in texto else texto.split(';'))] if texto.strip() else []
    L['etiquetas'] = (etiquetas + [''] * len(portadas))[:len(portadas)]
    total = _leer_numero(op.get('total'), None)
    if total is None:
        total = sum(L['valores']) if L['valores'] else sum(_leer_numero(x, 0.0) for x in L['etiquetas'])
    L['total'] = total
    dos = bool(L['valores']) or bool(portadas)
    L['dos'] = dos
    # lo que pide el ritmo (sin contar `empieza`): con barras, los dos acercamientos; sin ellas, uno
    necesita = (VUELVE + ALEJA - CRUCE + BARRAS[1] if dos else LINEA[1]) + LEER + VUELTA
    empieza = max(0.0, _leer_numero(op.get('empieza'), 0.0))
    empieza = min(empieza, max(0.0, c.dur - 0.6 * necesita))
    r = min(1.0, (c.dur - empieza) / necesita)
    c.estado['r'] = r
    L['a1'] = empieza
    L['v'] = empieza + VUELVE * r                              # la cámara vuelve al plano abierto (con barras)
    L['a2'] = L['v'] + (ALEJA - CRUCE) * r                     # el segundo acercamiento
    L['f'] = c.dur - VUELTA * r                                # la vuelta del final
    L['col'] = B.color(op.get('color') or '#22C55E')[:3]
    L['zoom'] = min(2.2, max(1.0, _leer_numero(op.get('zoom'), 1.75)))
    cx = float(c.cara[0])
    lado = str(op.get('lado') or 'auto').strip().lower()
    if lado.startswith('izq'):
        izq = True
    elif lado.startswith('der'):
        izq = False
    else:                                                      # auto: el lado con más sitio; en el centro, la izquierda
        izq = cx >= c.W * 0.44
    L['izq'] = izq
    L['p1'] = L['p2'] = None
    c.estado['L'] = L
    return L


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _matriz(cam):
    s, tx, ty = cam
    return np.float32([[s, 0, tx], [0, s, ty]])


def _camara(c, cam):
    """Acerca el cuadro entero (con decimales: sin saltitos)."""
    if cam[0] <= 1.0 + 1e-5:
        return
    hecho = cv2.warpAffine(c.img, _matriz(cam), (c.W, c.H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    np.copyto(c.img, hecho)


def _mascara_zona(c, cam, a0, b0, a1, b1):
    """La silueta de la persona en un trozo del cuadro YA acercado (la del motor es la del cuadro sin acercar)."""
    if c.mascara is None:
        return None
    if cam[0] <= 1.0 + 1e-5:
        return np.ascontiguousarray(c.mascara[b0:b1, a0:a1], dtype=np.float32)
    M = _matriz(cam)
    M[0, 2] -= a0
    M[1, 2] -= b0
    return cv2.warpAffine(c.mascara.astype(np.float32, copy=False), M, (a1 - a0, b1 - b0), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


def _vidrio(c, X0, Y0, X1, Y1, sigma, cam):
    """Lo que hay detrás de un trozo del cuadro, muy desenfocado y SIN la persona (la tarjeta está detrás de ella: el
    cristal desenfoca la pared, no la gorra). Se desenfoca pequeño y se agranda: es suave."""
    m = int(math.ceil(2.5 * sigma))
    a0, b0, a1, b1 = max(0, X0 - m), max(0, Y0 - m), min(c.W, X1 + m), min(c.H, Y1 + m)
    trozo = c.img[b0:b1, a0:a1]
    f = 4
    tam = (max(1, (a1 - a0) // f), max(1, (b1 - b0) // f))
    peq = cv2.resize(trozo, tam, interpolation=cv2.INTER_AREA)
    sg = sigma / f
    plano = cv2.GaussianBlur(peq, (0, 0), sg, borderType=cv2.BORDER_REFLECT)
    msk = _mascara_zona(c, cam, a0, b0, a1, b1)
    if msk is not None and msk.max() > 0.004:
        # la media de la pared de alrededor (convolución normalizada): donde hay persona, se rellena con la pared
        pared = 1.0 - np.clip(cv2.resize(msk, tam, interpolation=cv2.INTER_AREA), 0, 1)
        num = cv2.GaussianBlur(peq * pared[..., None], (0, 0), sg, borderType=cv2.BORDER_REFLECT)
        den = cv2.GaussianBlur(pared, (0, 0), sg, borderType=cv2.BORDER_REFLECT)
        sin = num / np.maximum(den, 1e-4)[..., None]
        w = np.clip(den / 0.12, 0, 1)[..., None]
        plano = sin * w + plano * (1.0 - w)
    grande = cv2.resize(plano, (a1 - a0, b1 - b0), interpolation=cv2.INTER_LINEAR)
    return grande[Y0 - b0:Y1 - b0, X0 - a0:X1 - a0]


def _poner_tarjeta(c, T, x, y, esc, alfa, cam):
    """Pone la tarjeta DETRÁS de la persona, con su esquina de arriba a la izquierda en (x, y) (con decimales) y
    escalada `esc` desde su centro: la sombra, el cristal (lo de detrás desenfocado) y lo de encima; y después la persona
    otra vez delante, con el color de verdad de su borde (sin el filo de la pared de detrás)."""
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
    antes = zona.copy()
    # al entrar y al salir, el cristal se empaña y se desempaña (el desenfoque crece con él) en vez de fundirse: si se
    # fundiera, lo de detrás se vería nítido a través de la tarjeta a medio aparecer
    empano = B.sale(min(1.0, alfa * 1.25))
    fondo = _vidrio(c, X0, Y0, X1, Y1, max(1.0, DESENFOQUE * u * empano), cam)
    fondo = 1.0 - (1.0 - fondo) * np.float32(1.0 - 0.12 * empano)                 # un poco más claro, como esmerilado
    tam = (X1 - X0, Y1 - Y0)
    M = np.float32([[esc, 0, X - X0], [0, esc, Y - Y0]])
    Ms = np.float32([[esc, 0, X - p * esc - X0], [0, esc, Y - p * esc - Y0]])
    sh = cv2.warpAffine(T.sombra, Ms, tam, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    F = cv2.warpAffine(T.forma, M, tam, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    C = cv2.warpAffine(T.capa(c.t), M, tam, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                       borderValue=(0, 0, 0, 0))
    a = np.float32(alfa)
    Sa = sh * a
    Fa = F * np.float32(min(1.0, alfa * 2.5))
    Ca = C[..., 3] * a
    zona *= (1.0 - Sa)[..., None]
    zona *= (1.0 - Fa)[..., None]
    zona += fondo * Fa[..., None]
    zona *= (1.0 - Ca)[..., None]
    zona += C[..., :3] * a
    # la persona, delante. Con la tarjeta (de color Cc y cobertura A) entre la pared (Bp) y la persona (Fp, silueta m):
    # nuevo = m·Fp + (1 − m)·(A·Cc + (1 − A)·Bp) = antes + (1 − m)·[(tarjeta encima − antes) + m·A·(Fp − Bp)]
    m = _mascara_zona(c, cam, X0, Y0, X1, Y1)
    if m is not None and m.max() > 0.004:
        # el borde, un poco más firme: con la cámara cerca, la silueta (que se hizo para el cuadro sin acercar) se
        # agranda y su borde se ablanda, y sobre el cristal claro se veía como un halo oscuro alrededor de la gorra. Se
        # aprieta alrededor de la mitad (el borde no se mueve: no se come la cabeza), más cuanto más cerca está
        m = np.clip((m - 0.5) * (1.0 + 0.8 * (cam[0] - 1.0)) + 0.5, 0.0, 1.0)
        A = 1.0 - (1.0 - Sa) * (1.0 - Fa) * (1.0 - Ca)
        Fp, Bp = B.color_persona(antes, m, u)
        m3 = m[..., None]
        zona[:] = antes + (1.0 - m3) * ((zona - antes) + m3 * A[..., None] * (Fp - Bp))


def _escala_en(L, t, dur):
    """La cámara en t, como (s, tx, ty)."""
    r = L['r']
    a1, v, a2, f = L['a1'], L['v'], L['a2'], L['f']
    A = ACERCA * r

    def cerca(plan, a, t):
        if plan is None or t < a:
            return (1.0, 0.0, 0.0)
        q = _acerca(B.tramo(t, a, a + A))
        return _cam(math.exp(math.log(plan['s']) * q) * (1.0 + DERIVA * max(0.0, t - a - A)), plan['P'])

    def base(t):
        if not L['dos'] or t < v:
            return cerca(L['p1'], a1, t)
        # vuelve al plano abierto…
        sv = cerca(L['p1'], a1, v)[0]
        c1 = _cam(math.exp(math.log(sv) * (1.0 - _acerca(B.tramo(t, v, v + ALEJA * r)))), L['p1']['P'])
        if t < a2 or L['p2'] is None:
            return c1
        # …y antes de que acabe, ya arranca el segundo acercamiento: las dos cosas a la vez (primero una y luego la otra)
        c2 = cerca(L['p2'], a2, t)
        return (c1[0] * c2[0], c2[0] * c1[1] + c2[1], c2[0] * c1[2] + c2[2])

    if t < f:
        return base(t)
    sf, tx, ty = base(f)                                             # la vuelta del final (el último cuadro, ya original)
    if sf <= 1.0 + 1e-6:
        return (1.0, 0.0, 0.0)
    fin = dur - 1.0 / 30.0
    return _cam(math.exp(math.log(sf) * (1.0 - _frena(B.tramo(t, f, fin)))), (tx / (1.0 - sf), ty / (1.0 - sf)))


def dibujar(c):
    L = c.estado.get('L') or _preparar(c)
    L['r'] = r = c.estado['r']
    t = c.t
    if t < L['a1']:
        return
    # cada acercamiento se planea al empezar, con la cara de ese momento
    if L['p1'] is None:
        L['p1'] = _plan(c, L['izq'], L['zoom'])
        L['t1'] = _principal(c, L['p1']['k'] * c.u, L['col'], L['a1'])
    if L['dos'] and t >= L['a2'] and L['p2'] is None:
        L['p2'] = _plan(c, not L['izq'], L['zoom'])
        if c.estado.get('portadas'):
            L['t2'] = _rejilla_portadas(c, L['p2']['k'] * c.u, L['col'], L['etiquetas'], L['total'], L['a2'],
                                        L['izq'])                       # la segunda va al otro lado
        else:
            L['t2'] = _barras(c, L['p2']['k'] * c.u, L['col'], L['valores'], L['a2'])
    u = c.u

    # 1. la cámara
    cam = _escala_en(L, t, c.dur)
    _camara(c, cam)
    cara = _caja_cara(c.cara, cam)

    # 2. las tarjetas: aparecen con un fundido y un rebote corto, flotan un poco y se van con un fundido cuando la cámara
    # empieza a volver
    tarjetas = []
    if L['dos']:
        tarjetas.append((L['t1'], L['p1'], L['a1'], L['v']))
        if L['p2'] is not None:
            tarjetas.append((L['t2'], L['p2'], L['a2'], L['f']))
    else:
        tarjetas.append((L['t1'], L['p1'], L['a1'], L['f']))
    for T, pl, a0, sale_en in tarjetas:
        e = a0 + ENTRA * r
        sale_en += DESFASE * r
        if t < e or t >= sale_en + FUNDIDO_SALE * r:
            continue
        x0, y0, x1, y1 = pl['rect']
        p = B.tramo(t, e, e + REBOTE * r)
        entra = B.rebote(p, 1.1)
        alfa = B.tramo(t, e, e + FUNDIDO_ENTRA * r) * (1.0 - B.suave(B.tramo(t, sale_en, sale_en + FUNDIDO_SALE * r)))
        flota = math.sin((t - e) * 2 * math.pi / 2.8) * 3.0 * u * min(1.0, p * 1.5)
        y = y0 + (1.0 - entra) * SUBE * u + flota
        esc = 0.96 + 0.04 * entra
        # por si la persona se levanta mucho: si la frente se mete en la tarjeta, la tarjeta se desvanece (va detrás de
        # la persona, pero así un fallo del recorte nunca la deja encima de la cara)
        dentro = (y + (y1 - y0)) - cara[1]
        se_ve = float(np.clip(1.0 - (dentro - 0.1 * cara[4]) / (0.25 * cara[4]), 0, 1))
        _poner_tarjeta(c, T, x0, y, esc, alfa * se_ve, cam)
