"""cristal: ocho tarjetas de cristal grandes, apiñadas alrededor de la cabeza y los hombros, y varias por DETRÁS.

Las tarjetas llenan el cuadro en dos columnas pegadas a la persona, cada una de un tercio del ancho más o menos:
  - a la izquierda, arriba: la grande, con una palabra pequeña (`marca`), un número enorme que sube desde 0 (`numero`) y
    su texto (`texto_numero`);
  - a la derecha, arriba: una exportación (`exportando`) con su barra que se llena y el tanto por ciento que sube
    («4K · 60 %», con `resolucion`);
  - debajo: la ficha del creador, con su cara (sacada del propio vídeo), su nombre (`nombre`) y su @ (`usuario`);
  - DETRÁS de la cabeza, a la izquierda: un calendario (`dia`, `fecha`) con lo que toca ese día (`evento`);
  - DETRÁS de la cabeza, a la derecha: lo que se está editando (`editando_titulo`, `editando`), con la onda del sonido,
    la barrita que avanza y los controles (atrás, play, adelante);
  - DETRÁS del hombro derecho: un anillo que se llena, con la resolución y los cuadros por segundo dentro (`fps`);
  - DETRÁS del brazo izquierdo: una marca verde que se dibuja (`etiqueta`);
  - abajo, DELANTE: la pastilla (`pastilla`; la última palabra en el color de acento) con su interruptor.
Cualquier texto vacío quita su tarjeta (o su parte).

El cristal es de verdad: cada tarjeta desenfoca lo que tiene detrás (las de detrás, solo la pared: la persona no se cuela
en su cristal), lo oscurece y lleva un filo claro (más claro arriba a la izquierda), un brillo por dentro, un destello que
la cruza una vez al llegar y una sombra suave que cae en la pared, nunca en la persona. El color de acento (`color`), solo
en los detalles. En las de detrás, la persona vuelve encima con el color limpio de su borde (sin filo de la pared).

Cómo se mueven: salen como de detrás de la persona, todas en ~0,7 s, una detrás de otra y con un muelle (se pasan un
poco y se asientan); flotan despacio, cada una a su ritmo; lo de dentro se anima en los primeros 3 s (lo que se suele
ver de una escena), y se van con un fundido y encogiéndose un poco en el último tercio de segundo. Al entrar y al salir,
el cristal se empaña y se desempaña (no se funde: así nunca se ve doble lo de detrás).

Nunca tapan la cara: las de delante nunca se acercan a menos de 0,6 anchos de cara (si la cara va hacia una, la tarjeta
se aparta); las de detrás pueden acercarse a la cabeza lo que quieran, porque la persona va encima. Todo el texto queda en
la zona segura (de x 60 a x 1020 a 1080 de ancho; ni en los 180 px de arriba ni en los 380 de abajo, ni debajo de los
botones de Instagram). La silueta de la persona nunca se encoge; solo se le tapan los agujeritos sueltos que a veces
trae el recorte, para que una tarjeta de detrás no se vea a través del brazo.

La colocación está pensada para alguien sentado a media distancia, con la cara hacia la mitad del cuadro (a ~777 px de
alto a 1080 × 1920); si la cara está mucho más arriba o más abajo, todo se mueve con ella.

    .venv/bin/python efectos.py cristal tu_video.mp4 --op "nombre=TU NOMBRE" --op usuario=@tu_usuario --fotos 0.4,1.5,3.2
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

import base as B

NOMBRE = 'cristal'
DESCRIPCION = ('Ocho tarjetas de cristal grandes pegadas a ti (un contador, tu ficha, una exportación que avanza, un '
               'calendario, lo que se está editando, un anillo de calidad, una marca y «Editado por Claude»); varias '
               'pasan por detrás de tu cabeza y tus hombros, y ninguna te tapa la cara')
OPCIONES = {
    'marca': 'Claude',                    # la palabra pequeña de arriba de la tarjeta grande (vacía: solo el destello)
    'numero': '13',                       # el número enorme de la tarjeta grande (sube desde 0)
    'texto_numero': 'efectos · un clip',  # lo que va debajo del número
    'exportando': 'Exportando',           # la tarjeta de la barra que se llena (vacía: no sale)
    'resolucion': '4K',                   # va junto al tanto por ciento («4K · 60 %») y dentro del anillo
    'fps': '30',                          # dentro del anillo, debajo de la resolución («30 fps»)
    'nombre': 'TU NOMBRE',                # la ficha: tu nombre…
    'usuario': '@tu_usuario',             # …y tu @
    'dia': 'MAR',                         # el calendario: el día de la semana…
    'fecha': '27',                        # …el número del día (vacío: el calendario no sale)…
    'evento': 'Subir el Reel',            # …y lo que toca ese día
    'editando_titulo': 'AHORA EDITANDO',  # la línea pequeña de la tarjeta de edición
    'editando': 'Cortes sin pausas',      # lo que se está editando (vacío: esa tarjeta no sale)
    'etiqueta': 'sin editor',             # la marca verde que se dibuja (vacía: no sale)
    'pastilla': 'Editado por Claude',     # la pastilla de abajo; la última palabra va en el color de acento (vacía: no sale)
    'color': '#8B5CF6',                   # el color de acento
}
DURACION = 3.5

# ── El cristal ──────────────────────────────────────────────────────────────────────────────────────────────────────
DESENFOQUE = 28.0            # cuánto se desenfoca lo de detrás (a 1080)
SOMBRA_PERSONA = (0.5, 7.0)   # la sombra de la persona en las tarjetas de detrás: cuánto oscurece y lo que se abre (a 1080)
TINTE = (16, 12, 30)         # el tono oscuro del cristal (un violeta casi negro)
OPACIDAD = 0.50              # cuánto pesa ese tono sobre lo de detrás
VIVEZA = 1.18                # un poco más de color en lo desenfocado, como el cristal de un teléfono
NIEBLA = 0.025               # un velo blanco muy suave: el esmerilado

# ── El movimiento (segundos) ────────────────────────────────────────────────────────────────────────────────────────
ENTRA = 0.45                 # lo que tarda el muelle de cada tarjeta
ESCALONADO = 0.035           # cada tarjeta sale un poco después que la anterior (la última acaba a los ~0,7 s)
SALE = 0.32                  # el fundido del final (con el escalonado, los últimos ~0,4 s)
DESDE_DENTRO = 0.13          # al entrar, cada tarjeta sale de esta fracción del camino hacia la cabeza (como de detrás)
RITMO = 3.0                  # lo de dentro (el número, la barra, el anillo, las marcas) acaba en estos segundos
MARGEN_CARA = 0.6            # la distancia mínima de las de delante a la cara, en anchos de cara
AGUJERO_MAX = 64             # px² (a 1080): los agujeritos sueltos de la silueta hasta este tamaño se tapan

# La colocación, a 1080 × 1920 (se escala con el vídeo). x, y: la esquina de arriba a la izquierda; con `der`, la x es
# donde acaba por la derecha; con `centro`, dónde cae su mitad. `orden`: en qué turno entra. `detras`: pasa por detrás
# de la persona. Las de detrás se meten tras la cabeza y los hombros de alguien sentado a media distancia; su texto queda
# siempre del lado de fuera, donde la persona no llega.
SITIOS = {
    'editando': dict(x=598, y=520, orden=0, detras=True),     # tras la cabeza, a la derecha
    'calendario': dict(x=64, y=540, orden=1, detras=True),    # tras la cabeza y el hombro, a la izquierda
    'contador': dict(x=64, y=196, orden=2),
    'creador': dict(der=1010, y=372, orden=3),
    'anillo': dict(x=764, y=858, orden=4, detras=True),       # tras el hombro derecho
    'etiqueta': dict(x=64, y=878, orden=5, detras=True),      # tras el brazo izquierdo
    'exportando': dict(der=1010, y=196, orden=6),
    'pastilla': dict(centro=540, y=1372, orden=7),
}
CARA_REFERENCIA = (555, 777)  # dónde está la cara para la que está pensada la colocación (a 1080 × 1920); si está mucho
                              # más arriba o más abajo, todo se mueve con ella
SS = 4                        # los iconos dibujados a mano se hacen 4 veces más grandes y se reducen (bordes suaves)
BLANCO = (255, 255, 255, 255)


# ── Curvas ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _muelle(p):
    """Un muelle: llega, se pasa un 10 % y se asienta (0 → 1)."""
    p = min(1.0, max(0.0, p))
    return 1.0 - math.exp(-5.5 * p) * math.cos(7.5 * p) if p < 1.0 else 1.0


def _seno(x):
    """Ida y vuelta suave, más pareja que la cúbica: el fundido de salida se reparte por todo su tiempo."""
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def _paso_suave(a, b, x):
    """De 0 a 1 entre a y b, suave (para arrays)."""
    k = np.clip((x - a) / (b - a), 0.0, 1.0)
    return k * k * (3.0 - 2.0 * k)


def _ritmo(c):
    """Lo de dentro se anima en RITMO segundos; si el efecto dura menos, todo se aprieta para que dé tiempo."""
    return min(1.0, max(0.2, c.dur / RITMO))


# ── Dibujo con números (todo en float, con decimales: nada salta) ───────────────────────────────────────────────────
def _rejilla(w, h):
    """Las coordenadas del centro de cada píxel de un trozo de w × h."""
    xs = np.arange(w, dtype=np.float32) + 0.5
    ys = np.arange(h, dtype=np.float32) + 0.5
    return np.meshgrid(xs, ys)


def _sdf_caja(xx, yy, cx, cy, hw, hh, r):
    """Distancia con signo a un rectángulo redondeado (negativa dentro)."""
    r = min(r, hw, hh)
    qx = np.abs(xx - cx) - (hw - r)
    qy = np.abs(yy - cy) - (hh - r)
    fuera = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2)
    return fuera + np.minimum(np.maximum(qx, qy), 0) - r


def _cobertura(sd):
    """Cuánto de cada píxel cae dentro de una forma, con el borde suave de un píxel."""
    return np.clip(0.5 - sd, 0.0, 1.0).astype(np.float32)


def _pintar(dst, cob, rgb, alfa=1.0, x0=0, y0=0):
    """Pinta un color (o un degradado, alto × ancho × 3) con su cobertura sobre una capa premultiplicada, en (x0, y0)."""
    h, w = cob.shape
    X0, Y0 = max(0, x0), max(0, y0)
    X1, Y1 = min(dst.shape[1], x0 + w), min(dst.shape[0], y0 + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    a = cob[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0] * np.float32(alfa)
    zona = dst[Y0:Y1, X0:X1]
    zona *= (1.0 - a)[..., None]
    col = np.asarray(rgb, np.float32)
    if col.ndim == 3:
        col = col[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    zona[..., :3] += a[..., None] * col
    zona[..., 3] += a


def _sobre(dst, src, x0, y0, alfa=1.0):
    """Pone una capa premultiplicada encima de otra, con su esquina en (x0, y0) (enteros)."""
    h, w = src.shape[:2]
    X0, Y0 = max(0, x0), max(0, y0)
    X1, Y1 = min(dst.shape[1], x0 + w), min(dst.shape[0], y0 + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    s = src[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    if alfa < 0.999:
        s = s * np.float32(alfa)
    zona = dst[Y0:Y1, X0:X1]
    zona *= (1.0 - s[..., 3:4])
    zona += s


def _premult(capa):
    """De una imagen PIL RGBA a un array float32 con el color multiplicado por su transparencia."""
    a = np.asarray(capa, np.float32) * np.float32(1.0 / 255.0)
    a[..., :3] *= a[..., 3:4]
    return np.ascontiguousarray(a)


class _Barra:
    """Una barra horizontal redondeada (de x0 a x1, centrada en y) que se puede pintar llena hasta donde se quiera."""

    def __init__(self, x0, x1, y, alto):
        self.x0, self.x1, self.y, self.alto = x0, x1, y, alto
        self.ox, self.oy = int(math.floor(x0)) - 2, int(math.floor(y - alto / 2)) - 2
        w, h = int(math.ceil(x1 - x0)) + 5, int(math.ceil(alto)) + 5
        xx, yy = _rejilla(w, h)
        self.xx, self.yy = xx + self.ox, yy + self.oy

    def hasta(self, k):
        """La cobertura de la barra llena hasta la fracción k (0–1); con k pequeño, un puntito redondo."""
        largo = max((self.x1 - self.x0) * min(1.0, max(0.0, k)), self.alto * 0.999)
        return _cobertura(_sdf_caja(self.xx, self.yy, self.x0 + largo / 2, self.y, largo / 2, self.alto / 2,
                                    self.alto / 2))

    def degradado(self, a, b):
        """Del color a (izquierda) al b (derecha), del tamaño del trozo de la barra."""
        k = np.clip((self.xx - self.x0) / max(1e-3, self.x1 - self.x0), 0, 1)[..., None]
        return (a + (b - a) * k).astype(np.float32)


# ── Textos ──────────────────────────────────────────────────────────────────────────────────────────────────────────
class Rotulo:
    """Un texto listo para colocar: su capa y dónde cae la tinta dentro de ella (para alinear la letra, no la caja)."""

    def __init__(self, s, tam, peso, relleno, espacio=0.0):
        self.s = s
        self.capa = B.texto(s, tam, peso, relleno, espacio=espacio)
        f = B.fuente(peso, tam)
        asc, desc = f.getmetrics()
        self.pad = (self.capa.height - (asc + desc)) / 2
        caja_h = f.getbbox('H')
        self.medio = self.pad + (caja_h[1] + caja_h[3]) / 2          # la mitad de la altura de las mayúsculas
        self.alto_may = caja_h[3] - caja_h[1]
        if espacio:
            self.ancho = sum(f.getlength(ch) for ch in s) + espacio * tam * max(0, len(s) - 1)
        else:
            self.ancho = f.getlength(s)
        self.w, self.h = self.capa.size

    def esquina(self, x, y, alinear='izq'):
        """La esquina de la capa (enteros) para que la tinta empiece en x (o acabe, o se centre) y las mayúsculas queden
        centradas en y."""
        if alinear == 'izq':
            x0 = x - self.pad
        elif alinear == 'der':
            x0 = x - self.pad - self.ancho
        else:
            x0 = x - self.pad - self.ancho / 2
        return int(round(x0)), int(round(y - self.medio))

    def poner(self, lienzo, x, y, alinear='izq'):
        lienzo.alpha_composite(self.capa, self.esquina(x, y, alinear))


def _tam_que_cabe(s, peso, tam, ancho, espacio=0.0):
    f = B.fuente(peso, 100)
    largo = (sum(f.getlength(ch) for ch in s) + espacio * 100 * max(0, len(s) - 1)) if espacio else f.getlength(s)
    return min(tam, ancho / max(1e-3, largo / 100.0))


def _lineas(s, peso, tam, ancho, minimo):
    """El texto en una línea; si para caber tendría que quedar más pequeño que `minimo`, en dos (partido por el espacio
    que deja las dos líneas más parejas, pero sin dejar colgada al final de la primera una palabra corta como «sin», «de»
    o «por»: «Cortes / sin pausas», no «Cortes sin / pausas»). Devuelve (líneas, tamaño)."""
    s = ' '.join(s.split())
    t1 = _tam_que_cabe(s, peso, tam, ancho)
    if t1 >= minimo or ' ' not in s:
        return [s], t1
    f = B.fuente(peso, 100)
    pal = s.split(' ')

    def coste(k):
        largo = max(f.getlength(' '.join(pal[:k])), f.getlength(' '.join(pal[k:])))
        return largo * (1.35 if len(pal[k - 1]) <= 3 else 1.0)

    mejor = min((coste(k), k) for k in range(1, len(pal)))
    lin = [' '.join(pal[:mejor[1]]), ' '.join(pal[mejor[1]:])]
    return lin, min(_tam_que_cabe(x, peso, tam, ancho) for x in lin)


# ── Iconos dibujados a mano ─────────────────────────────────────────────────────────────────────────────────────────
def _destello(d, col):
    """Un destello de cuatro puntas, con otro pequeño arriba a la derecha."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)

    def estrella(cx, cy, R):
        pts = []
        for k in range(160):
            a = 2 * math.pi * k / 160
            co, si = math.cos(a), math.sin(a)
            pts.append((cx + R * math.copysign(abs(co) ** 2.6, co), cy + R * math.copysign(abs(si) ** 2.6, si)))
        dr.polygon(pts, fill=col)

    estrella(D * 0.42, D * 0.58, D * 0.41)
    estrella(D * 0.83, D * 0.17, D * 0.16)
    return im.resize((max(1, round(d)), max(1, round(d))), Image.LANCZOS)


def _marca(d, p):
    """El círculo verde con la marca dibujada hasta `p` (0–1)."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, D - 1, D - 1], fill=(34, 197, 94, 255))
    if p > 0:
        R = D / 2
        pts = [(D / 2 + x * R, D / 2 + y * R) for x, y in ((-0.40, 0.03), (-0.12, 0.31), (0.42, -0.26))]
        g = 0.19 * R
        largos = [math.dist(pts[i], pts[i + 1]) for i in range(2)]
        queda = p * sum(largos)
        dr.ellipse([pts[0][0] - g / 2, pts[0][1] - g / 2, pts[0][0] + g / 2, pts[0][1] + g / 2], fill=BLANCO)
        for i, L in enumerate(largos):
            if queda <= 0:
                break
            k = min(1.0, queda / L)
            a, b = pts[i], pts[i + 1]
            fin = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            dr.line([a, fin], fill=BLANCO, width=int(round(g)))
            dr.ellipse([fin[0] - g / 2, fin[1] - g / 2, fin[0] + g / 2, fin[1] + g / 2], fill=BLANCO)
            queda -= L
    return im.resize((max(1, round(d)), max(1, round(d))), Image.LANCZOS)


def _control(tipo, d, col):
    """Un control de reproducción de d × d: 'atras' (barra y triángulo a la izquierda), 'play' (triángulo dentro de un
    círculo de cristal) o 'adelante'."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    if tipo == 'play':
        dr.ellipse([0, 0, D - 1, D - 1], fill=(255, 255, 255, 46))
        dr.polygon([(D * 0.40, D * 0.29), (D * 0.40, D * 0.71), (D * 0.74, D * 0.50)], fill=col)
    else:
        izq = tipo == 'atras'
        bx = (D * 0.22, D * 0.33) if izq else (D * 0.67, D * 0.78)
        dr.rounded_rectangle([bx[0], D * 0.24, bx[1], D * 0.76], radius=D * 0.05, fill=col)
        if izq:
            dr.polygon([(D * 0.80, D * 0.24), (D * 0.80, D * 0.76), (D * 0.36, D * 0.50)], fill=col)
        else:
            dr.polygon([(D * 0.20, D * 0.24), (D * 0.20, D * 0.76), (D * 0.64, D * 0.50)], fill=col)
    return im.resize((max(1, round(d)), max(1, round(d))), Image.LANCZOS)


def _punto_que_late(capa, cx, cy, u, t, col, rejilla):
    """Un punto de color con un aro que se abre y se apaga, una vez por segundo."""
    ox, oy, pxx, pyy = rejilla
    pr = np.sqrt((pxx + ox - cx) ** 2 + (pyy + oy - cy) ** 2)
    ciclo = (t % 1.1) / 1.1
    r_halo = 6.5 * u + 10 * u * B.sale(ciclo)
    halo = np.clip(1.6 * u - np.abs(pr - r_halo) + 0.5, 0, 1).astype(np.float32)
    _pintar(capa, halo, col, 0.55 * (1 - ciclo), ox, oy)
    _pintar(capa, np.clip(6.5 * u - pr + 0.5, 0, 1).astype(np.float32), col, 1.0, ox, oy)


def _rejilla_punto(cx, cy, u):
    lado = int(math.ceil(44 * u))
    ox, oy = int(round(cx - lado / 2)), int(round(cy - lado / 2))
    xx, yy = _rejilla(lado, lado)
    return ox, oy, xx, yy


# ── Una tarjeta ─────────────────────────────────────────────────────────────────────────────────────────────────────
class Tarjeta:
    """Una tarjeta de cristal: su forma, su brillo y lo que lleva quieto (`base`), su sombra y, si tiene, lo que se
    mueve por dentro (`animar(capa, t)`)."""

    def __init__(self, clave, w, h, r, u, detras=False):
        self.clave = clave
        self.w, self.h = int(round(w)), int(round(h))
        self.r = r
        self.u = u
        self.detras = detras
        self.animar = None
        xx, yy = _rejilla(self.w, self.h)
        self.xx, self.yy = xx, yy
        sd = _sdf_caja(xx, yy, self.w / 2, self.h / 2, self.w / 2, self.h / 2, r)
        self.forma = _cobertura(sd)
        # 0 arriba a la izquierda → 1 abajo a la derecha: de aquí salen el brillo y el filo
        self.diag = np.clip(xx / self.w * 0.55 + yy / self.h * 0.45, 0, 1).astype(np.float32)
        brillo = 0.085 * (1.0 - self.diag) ** 2 * self.forma                         # el brillo en diagonal
        canto = 0.065 * np.clip(1.0 + sd / (10.0 * u), 0, 1) * self.forma           # el canto, un poco más claro
        bw = max(1.0, 1.5 * u)
        filo = (_cobertura(sd) - _cobertura(sd + bw)) * (0.55 - 0.42 * self.diag)  # el filo fino, más claro arriba
        a = 1.0 - (1.0 - brillo) * (1.0 - canto) * (1.0 - filo)
        # el volumen: el cristal un poco más oscuro abajo, como si la luz le llegara de arriba
        oscuro = (0.11 * np.clip(yy / self.h, 0, 1) ** 1.4 * self.forma).astype(np.float32)
        self.base = np.dstack([a, a, a, a]).astype(np.float32)
        self.base *= (1.0 - oscuro)[..., None]
        self.base[..., 3] += oscuro
        self.contenido = Image.new('RGBA', (self.w, self.h), (0, 0, 0, 0))       # lo quieto, en PIL, hasta cerrar()
        # la sombra: una amplia y suave y otra corta pegada, como la de un objeto de verdad
        self.pad_sombra = int(math.ceil(3 * 22 * u + 18 * u))
        p = self.pad_sombra
        lienzo = np.zeros((self.h + 2 * p, self.w + 2 * p), np.float32)
        s1 = lienzo.copy()
        d1 = int(round(16 * u))
        s1[p + d1:p + d1 + self.h, p:p + self.w] = self.forma
        s1 = cv2.GaussianBlur(s1, (0, 0), 22 * u) * 0.34
        s2 = lienzo.copy()
        d2 = int(round(4 * u))
        s2[p + d2:p + d2 + self.h, p:p + self.w] = self.forma
        s2 = cv2.GaussianBlur(s2, (0, 0), 5 * u) * 0.16
        self.sombra = (1.0 - (1.0 - s1) * (1.0 - s2)).astype(np.float32)
        # el destello que cruza la tarjeta una vez al llegar
        self.cruce = (xx * 0.78 + yy * 0.22) / (self.w * 0.78 + self.h * 0.22)
        self.t_cruce = None

    def cerrar(self):
        """Junta lo quieto (PIL) con el brillo del cristal."""
        _sobre(self.base, _premult(self.contenido), 0, 0)
        self.contenido = None

    def capa(self, t):
        """Lo que se pone encima del cristal en el instante t (premultiplicado, alto × ancho × 4)."""
        destello = 0.0
        if self.t_cruce is not None:
            destello = B.tramo(t, self.t_cruce, self.t_cruce + 0.75)
            destello = 0.0 if destello >= 1.0 else destello
        if self.animar is None and destello <= 0.0:
            return self.base
        capa = self.base.copy()
        if self.animar is not None:
            self.animar(capa, t)
        if destello > 0.0:
            pos = -0.35 + 1.7 * B.suave(destello)
            banda = 0.13 * np.exp(-((self.cruce - pos) / 0.085) ** 2) * self.forma
            _pintar(capa, banda.astype(np.float32), (1.0, 1.0, 1.0))
        return capa


# ── Las ocho tarjetas ───────────────────────────────────────────────────────────────────────────────────────────────
def _contador(c, E):
    """La grande: la palabra pequeña con su destello, el número enorme que sube desde 0 y su texto."""
    u, R = c.u, _ritmo(c)
    try:
        n = abs(int(round(float(str(c.op.get('numero') or '0').replace(',', '.')))))
    except ValueError:
        n = 0
    n = min(n, 9999)
    T = Tarjeta('contador', 388 * u, 320 * u, 44 * u, u)
    pad = 32 * u
    T.contenido.alpha_composite(_destello(26 * u, E['acento8']), (int(round(pad)), int(round(30 * u))))
    marca = str(c.op.get('marca') or '').strip()
    if marca:
        tam = _tam_que_cabe(marca, 'medium', 28 * u, T.w - 2 * pad - 38 * u)
        Rotulo(marca, tam, 'medium', (255, 255, 255, 225)).poner(T.contenido, pad + 38 * u, 43 * u)
    texto = str(c.op.get('texto_numero') or '').strip()
    if texto:
        tam = _tam_que_cabe(texto, 'medium', 30 * u, T.w - 2 * pad)
        Rotulo(texto, tam, 'medium', (255, 255, 255, 190)).poner(T.contenido, pad, 282 * u)
    tam_num = _tam_que_cabe(str(n), 'extrabold', 188 * u, T.w - 2 * pad)
    y_num = 168 * u
    t0, t1 = 0.15 * R, 1.00 * R
    # cuándo pasa por cada número: sube rápido y frena al llegar (el 0 está desde el principio). Solo se dibujan los
    # números por los que pasa de verdad (a 30 cuadros/s, como mucho uno por cuadro), y se guardan al usarlos.
    pasos = sorted({0, n} | {int(round(n * (1.0 - (1.0 - j / 40.0) ** 3))) for j in range(41)}) if n > 0 else [0]
    cruces = [t0]
    for k in pasos[1:]:
        y = (k - 0.5) / n
        cruces.append(t0 + (1.0 - (1.0 - y) ** (1.0 / 3.0)) * (t1 - t0))
    capas = {}
    rueda = 0.10                                      # lo que tarda cada número nuevo en asentarse

    def numero(k):
        if k not in capas:
            r = Rotulo(str(k), tam_num, 'extrabold', BLANCO)
            capas[k] = (r, _premult(r.capa))
        return capas[k]

    def animar(capa, t):
        # siempre un solo número (nunca dos encima ni trozos): el nuevo llega subiendo un poco y se enciende
        i = 0
        while i < len(pasos) - 1 and t >= cruces[i + 1]:
            i += 1
        hueco = (cruces[i + 1] - cruces[i]) if i < len(pasos) - 1 else rueda
        q = B.sale(B.tramo(t, cruces[i], cruces[i] + min(rueda, max(hueco, 1e-3)))) if i > 0 else 1.0
        r, arr = numero(pasos[i])
        x0, y0 = r.esquina(pad - 4 * u, y_num)
        _sobre(capa, arr, x0, int(round(y0 + (1.0 - q) * 0.12 * r.alto_may)), 0.55 + 0.45 * q)

    T.animar = animar
    return T


def _exportando(c, E):
    """La exportación: «● Exportando», la barra que se llena y «4K · 60 %» que sube hasta el 100 %."""
    u, R = c.u, _ritmo(c)
    texto = str(c.op.get('exportando') or '').strip()
    if not texto:
        return None
    T = Tarjeta('exportando', 420 * u, 150 * u, 36 * u, u)
    pad = 32 * u
    y1 = 46 * u
    Rotulo(texto, _tam_que_cabe(texto, 'bold', 29 * u, T.w - 2 * pad - 26 * u), 'bold', BLANCO).poner(
        T.contenido, pad + 24 * u, y1)
    barra = _Barra(pad, T.w - pad, 90 * u, 10 * u)
    _pintar(T.base, barra.hasta(1.0), (1.0, 1.0, 1.0), 0.14, barra.ox, barra.oy)
    color_barra = barra.degradado(E['acento'], E['claro'])
    res = str(c.op.get('resolucion') or '').strip()
    tam_pc = 23 * u
    y_pc = 124 * u
    rotulos = {}

    def tanto(k):
        if k not in rotulos:
            s = f'{res} · {k} %' if res else f'{k} %'
            r = Rotulo(s, tam_pc, 'medium', (255, 255, 255, 178))
            rotulos[k] = (r.esquina(pad, y_pc), _premult(r.capa))
        return rotulos[k]

    punto = _rejilla_punto(pad + 7 * u, y1, u)
    verde = np.array([34, 197, 94], np.float32) / 255.0
    ta, tb = 0.30 * R, 2.90 * R

    def animar(capa, t):
        p = B.tramo(t, ta, tb)
        p = 0.6 * p + 0.4 * B.suave(p)                    # arranca, corre y frena un poco al final
        k = int(math.floor(p * 100 + 1e-6))
        listo = k >= 100
        _punto_que_late(capa, pad + 7 * u, y1, u, t, verde if listo else E['acento'], punto)
        if p > 0:
            _pintar(capa, barra.hasta(p), color_barra, min(1.0, p / 0.02), barra.ox, barra.oy)
        (x0, y0), arr = tanto(k)
        _sobre(capa, arr, x0, y0)

    T.animar = animar
    return T


def _creador(c, E):
    """La ficha: la cara del propio vídeo en un círculo con su aro, el nombre y el @."""
    u = c.u
    h = 124 * u
    d_foto, hueco_aro, g_aro = 90 * u, 3.5 * u, 3 * u
    d_total = d_foto + 2 * (hueco_aro + g_aro)
    izq = 14 * u
    fx = izq + d_total / 2
    nombre = str(c.op.get('nombre') or '').strip()
    usuario = str(c.op.get('usuario') or '').strip()
    x_txt = izq + d_total + 18 * u
    ancho_max = 540 * u - x_txt - 34 * u       # como mucho 540: no llega a la columna de la izquierda
    rn = Rotulo(nombre, _tam_que_cabe(nombre, 'bold', 31 * u, ancho_max), 'bold', BLANCO) if nombre else None
    ru = Rotulo(usuario, _tam_que_cabe(usuario, 'regular', 24 * u, ancho_max), 'regular', (255, 255, 255, 172)) \
        if usuario else None
    ancho_txt = max(rn.ancho if rn else 0, ru.ancho if ru else 0)
    w = min(max(x_txt + ancho_txt + 36 * u, 420 * u), 540 * u)
    T = Tarjeta('creador', w, h, h / 2, u)
    if rn and ru:
        rn.poner(T.contenido, x_txt, 48 * u)
        ru.poner(T.contenido, x_txt, 83 * u)
    elif rn or ru:
        (rn or ru).poner(T.contenido, x_txt, T.h / 2)
    # la foto: la cara del propio vídeo, en un círculo con un aro del color de acento
    cx, cy, fw = (float(v) for v in c.cara)
    lado = 1.9 * fw
    x0, y0 = cx - lado / 2, cy - 0.18 * fw - lado / 2
    n = int(math.ceil(d_foto))
    # se toma del cuadro con un reescalado de área (sin dientes): primero se recorta y después se reduce
    X0, Y0 = int(max(0, math.floor(x0))), int(max(0, math.floor(y0)))
    X1, Y1 = int(min(c.W, math.ceil(x0 + lado))), int(min(c.H, math.ceil(y0 + lado)))
    trozo = np.ascontiguousarray(c.img[Y0:Y1, X0:X1])
    k = n / lado
    peq = cv2.resize(trozo, (max(1, int(round((X1 - X0) * k))), max(1, int(round((Y1 - Y0) * k)))),
                     interpolation=cv2.INTER_AREA)
    M = np.array([[1.0, 0, (X0 - x0) * k], [0, 1.0, (Y0 - y0) * k]], np.float64)
    foto = cv2.warpAffine(peq, M, (n, n), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    lado_l = int(math.ceil(d_total)) + 2
    ox, oy = int(round(fx - lado_l / 2)), int(round(T.h / 2 - lado_l / 2))
    xx, yy = _rejilla(lado_l, lado_l)
    dx, dy = xx + ox - fx, yy + oy - T.h / 2
    radio = np.sqrt(dx * dx + dy * dy)
    disco = np.clip(d_foto / 2 - radio + 0.5, 0, 1).astype(np.float32)
    lienzo = np.zeros((lado_l, lado_l, 3), np.float32)
    fo_x = int(round(fx - n / 2)) - ox
    fo_y = int(round(T.h / 2 - n / 2)) - oy
    lienzo[fo_y:fo_y + n, fo_x:fo_x + n] = foto[:lado_l - fo_y, :lado_l - fo_x]
    _pintar(T.base, disco, lienzo, 1.0, ox, oy)
    r_aro = d_foto / 2 + hueco_aro + g_aro / 2
    aro = np.clip(g_aro / 2 - np.abs(radio - r_aro) + 0.5, 0, 1).astype(np.float32)
    giro = np.clip((dx - dy) / (2 * r_aro) * 0.5 + 0.5, 0, 1)[..., None]
    _pintar(T.base, aro, E['claro'] + (E['acento'] - E['claro']) * giro, 1.0, ox, oy)
    return T


def _calendario(c, E):
    """El calendario: el día de la semana en el color de acento, el número grande y lo que toca, que entra de lado."""
    u, R = c.u, _ritmo(c)
    fecha = str(c.op.get('fecha') or '').strip()
    if not fecha:
        return None
    T = Tarjeta('calendario', 436 * u, 304 * u, 40 * u, u, detras=True)
    pad = 32 * u
    util = 300 * u - pad                          # el texto, solo en la parte de fuera (la de dentro va tras la cabeza)
    dia = str(c.op.get('dia') or '').strip().upper()
    if dia:
        Rotulo(dia, _tam_que_cabe(dia, 'bold', 28 * u, util, 0.12), 'bold', E['claro8'], espacio=0.12).poner(
            T.contenido, pad, 48 * u)
    Rotulo(fecha, _tam_que_cabe(fecha, 'extrabold', 128 * u, util), 'extrabold', BLANCO).poner(
        T.contenido, pad - 3 * u, 140 * u)
    evento = str(c.op.get('evento') or '').strip()
    if not evento:
        return T
    # lo que toca: una pastilla del color de acento, que entra de izquierda a derecha
    ph = 54 * u
    tam = _tam_que_cabe(evento, 'bold', 25 * u, util - 44 * u)
    re = Rotulo(evento, tam, 'bold', BLANCO)
    pw = re.ancho + 44 * u
    px0, py0 = int(math.floor(pad)), int(math.floor(244 * u - ph / 2))
    lw, lh = int(math.ceil(pw)) + 3, int(math.ceil(ph)) + 3
    xx, yy = _rejilla(lw, lh)
    forma = _cobertura(_sdf_caja(xx, yy, (pad - px0) + pw / 2, (244 * u - py0), pw / 2, ph / 2, ph / 2))
    pastilla = np.zeros((lh, lw, 4), np.float32)
    _pintar(pastilla, forma, E['acento'], 0.92)
    letras = Image.new('RGBA', (lw, lh), (0, 0, 0, 0))
    re.poner(letras, (pad - px0) + 22 * u, 244 * u - py0)
    _sobre(pastilla, _premult(letras), 0, 0)
    xs = (np.arange(lw, dtype=np.float32) + 0.5)[None, :, None]
    borde = 18 * u
    ta, tb = 0.50 * R, 0.85 * R

    def animar(capa, t):
        k = B.tramo(t, ta, tb)
        if k <= 0:
            return
        frente = -borde + (lw + 2 * borde) * B.sale(k)
        m = np.clip((frente - xs) / borde, 0, 1)
        _sobre(capa, pastilla * m, px0, py0, min(1.0, k / 0.15))

    T.animar = animar
    return T


def _editando(c, E):
    """Lo que se está editando: la línea pequeña, el título, la onda del sonido que corre, la barrita con su cabezal y
    los controles. Todo va a la derecha: la parte de la izquierda (cristal liso) se mete detrás de la cabeza. Nada que se
    mueva puede quedar bajo el borde de la persona: en ese borde suave, unas barras claras que cambian cada cuadro se
    transparentan y salen como una línea de puntitos que parpadea pegada a la sien."""
    u = c.u
    titulo = str(c.op.get('editando') or '').strip()
    if not titulo:
        return None
    T = Tarjeta('editando', 414 * u, 312 * u, 40 * u, u, detras=True)
    x0, der = 140 * u, 28 * u
    ancho_txt = T.w - x0 - der
    pequeno = str(c.op.get('editando_titulo') or '').strip().upper()
    if pequeno:
        Rotulo(pequeno, _tam_que_cabe(pequeno, 'medium', 19 * u, ancho_txt, 0.14), 'medium', (255, 255, 255, 160),
               espacio=0.14).poner(T.contenido, x0, 44 * u)
    lineas, tam = _lineas(titulo, 'bold', 34 * u, ancho_txt, 29 * u)
    y = 84 * u if len(lineas) > 1 else 96 * u
    for linea in lineas:
        Rotulo(linea, tam, 'bold', BLANCO).poner(T.contenido, x0, y)
        y += tam * 1.13
    # los controles: atrás, play y adelante, centrados en la parte de fuera
    cxc, cyc = (x0 + T.w - der) / 2, 270 * u
    for tipo, dx, d, a in (('atras', -66, 30, 205), ('play', 0, 52, 255), ('adelante', 66, 30, 205)):
        ic = _control(tipo, d * u, (255, 255, 255, a))
        T.contenido.alpha_composite(ic, (int(round(cxc + dx * u - ic.width / 2)), int(round(cyc - ic.height / 2))))
    # la barrita con su cabezal
    xi = x0 - 6 * u                                 # donde empieza lo que se mueve: fuera del alcance de la cabeza
    barra = _Barra(xi, T.w - der, 230 * u, 6 * u)
    _pintar(T.base, barra.hasta(1.0), (1.0, 1.0, 1.0), 0.16, barra.ox, barra.oy)
    color_barra = barra.degradado(E['acento'], E['claro'])
    lado_c = int(math.ceil(24 * u))
    cxx, cyy = _rejilla(lado_c, lado_c)
    # la onda: barras que corren hacia la izquierda y cambian de alto, como el sonido al editar
    oy0, oh = int(round(158 * u)), int(round(44 * u))
    ox0, ow = int(round(xi)), int(round(T.w - der - xi))
    wx, wy = _rejilla(ow, oh)
    paso, ancho_barra = 10 * u, 5 * u
    azar = np.random.default_rng(7)
    frec = azar.uniform(1.3, 2.9, 4096).astype(np.float32)
    fase = azar.uniform(0, 2 * math.pi, 4096).astype(np.float32)
    fuerza = azar.uniform(0.45, 1.0, 4096).astype(np.float32)
    borde = np.minimum(_paso_suave(0, 18 * u, wx[0]), _paso_suave(ow, ow - 18 * u, wx[0])).astype(np.float32)
    degradado = (E['acento'] + (E['claro'] - E['acento']) * (wx[0] / ow)[:, None]).astype(np.float32)
    degradado = np.broadcast_to(degradado[None], (oh, ow, 3))

    def animar(capa, t):
        # la onda
        xsft = wx[0] + t * 34 * u
        j = np.floor(xsft / paso).astype(np.int64)
        local = xsft - (j + 0.5) * paso
        jj = np.mod(j, 4096)
        altura = oh / 2 * (0.16 + 0.84 * fuerza[jj] * (0.5 + 0.5 * np.sin(2 * math.pi * frec[jj] * t + fase[jj])))
        rb = ancho_barra / 2
        largo = np.maximum(altura - rb, 0)[None, :]
        d = np.sqrt(local[None, :] ** 2 + np.maximum(np.abs(wy - oh / 2) - largo, 0) ** 2) - rb
        _pintar(capa, _cobertura(d) * borde[None, :], degradado, 0.95, ox0, oy0)
        # la barrita avanza todo el rato, despacio, como un vídeo que se reproduce
        p = 0.10 + 0.80 * min(1.0, t / max(c.dur, 1e-3))
        _pintar(capa, barra.hasta(p), color_barra, 1.0, barra.ox, barra.oy)
        hx = barra.x0 + (barra.x1 - barra.x0) * p
        qx0, qy0 = int(round(hx - lado_c / 2)), int(round(barra.y - lado_c / 2))
        dd = np.sqrt((cxx + qx0 - hx) ** 2 + (cyy + qy0 - barra.y - 1.2 * u) ** 2)
        _pintar(capa, np.clip((9 * u - dd) / (3 * u), 0, 1).astype(np.float32) ** 2, (0.0, 0.0, 0.0), 0.30, qx0, qy0)
        dd = np.sqrt((cxx + qx0 - hx) ** 2 + (cyy + qy0 - barra.y) ** 2)
        _pintar(capa, np.clip(7 * u - dd + 0.5, 0, 1).astype(np.float32), (1.0, 1.0, 1.0), 1.0, qx0, qy0)

    T.animar = animar
    return T


def _anillo(c, E):
    """El anillo que se llena, con la resolución grande dentro y los cuadros por segundo debajo."""
    u, R = c.u, _ritmo(c)
    T = Tarjeta('anillo', 246 * u, 190 * u, 40 * u, u, detras=True)
    Ra, g = 70 * u, 12 * u                         # el radio (al centro del trazo) y el grosor
    cx, cy = T.w / 2 + 14 * u, T.h / 2           # un poco a la derecha: el borde del hombro no llega al aro
    lado = int(math.ceil(2 * (Ra + g + 14 * u)))
    ox, oy = int(round(cx - lado / 2)), int(round(cy - lado / 2))
    xx, yy = _rejilla(lado, lado)
    dx, dy = xx + ox - cx, yy + oy - cy
    radio = np.sqrt(dx * dx + dy * dy)
    ang = np.mod(np.arctan2(dx, -dy), 2 * math.pi).astype(np.float32)      # 0 arriba, a favor del reloj
    d_aro = np.abs(radio - Ra)
    pista = np.clip(g / 2 - d_aro + 0.5, 0, 1).astype(np.float32)
    dentro = 2 * (Ra - g / 2) - 26 * u
    texto = str(c.op.get('resolucion') or '').strip()
    fps = str(c.op.get('fps') or '').strip()
    if fps:
        fps = fps if not fps.replace('.', '').replace(',', '').isdigit() else f'{fps} fps'
    if texto:
        Rotulo(texto, _tam_que_cabe(texto, 'extrabold', 46 * u, dentro), 'extrabold', BLANCO).poner(
            T.contenido, cx, cy - (12 * u if fps else 0), 'centro')
    if fps:
        Rotulo(fps, _tam_que_cabe(fps, 'medium', 21 * u, dentro - 10 * u), 'medium', (255, 255, 255, 185)).poner(
            T.contenido, cx, cy + (30 * u if texto else 0), 'centro')
    _pintar(T.base, pista, (1.0, 1.0, 1.0), 0.13, ox, oy)
    acento, claro = E['acento'], E['claro']
    t0, t1 = 0.25 * R, 1.40 * R

    def animar(capa, t):
        p = B.suave(B.tramo(t, t0, t1))
        if p <= 0.0:
            return
        A = p * 2 * math.pi
        if p >= 0.9995:
            d = d_aro
            pos = ang / (2 * math.pi)
        else:
            sa, ca = math.sin(A), math.cos(A)
            d0 = np.sqrt(dx * dx + (dy + Ra) ** 2)                       # la punta del principio
            d1 = np.sqrt((dx - Ra * sa) ** 2 + (dy + Ra * ca) ** 2)      # la punta que avanza
            en = ang <= A
            d = np.where(en, d_aro, np.minimum(d0, d1))
            pos = np.where(en, ang / max(A, 1e-4), np.where(d1 < d0, 1.0, 0.0))
        cob = np.clip(g / 2 - d + 0.5, 0, 1).astype(np.float32) * min(1.0, p / 0.03)
        # el brillo de debajo del trazo, que sube un poco al completarse
        lleno = B.tramo(t, t1, t1 + 0.35)
        brillo = 0.42 + 0.30 * math.sin(math.pi * lleno)
        _pintar(capa, cv2.GaussianBlur(cob, (0, 0), 6 * u), acento, brillo, ox, oy)
        _pintar(capa, cob, acento + (claro - acento) * pos[..., None], 1.0, ox, oy)

    T.animar = animar
    return T


def _etiqueta(c, E):
    """La marca: un círculo verde grande donde se dibuja la palomita, y el texto debajo."""
    u, R = c.u, _ritmo(c)
    texto = str(c.op.get('etiqueta') or '').strip()
    if not texto:
        return None
    T = Tarjeta('etiqueta', 296 * u, 212 * u, 40 * u, u, detras=True)
    pad = 30 * u
    rt = Rotulo(texto, _tam_que_cabe(texto, 'bold', 32 * u, 168 * u), 'bold', BLANCO)
    rt.poner(T.contenido, pad, 162 * u)
    d = 76 * u
    cx, cy = pad + d / 2, 30 * u + d / 2
    lado = int(math.ceil(d * 1.25)) + 4
    ox, oy = int(round(cx - lado / 2)), int(round(cy - lado / 2))
    xx, yy = _rejilla(lado, lado)
    radio = np.sqrt((xx + ox - cx) ** 2 + (yy + oy - cy) ** 2)
    aro = np.clip(1.6 * u - np.abs(radio - (d / 2 - 1.6 * u)) + 0.5, 0, 1).astype(np.float32)
    t_marca = 0.75 * R
    cache = {}

    def animar(capa, t):
        dt = t - t_marca
        if dt < 0.12:
            _pintar(capa, aro, (1.0, 1.0, 1.0), 0.42 * (1 - B.tramo(dt, 0.0, 0.12)), ox, oy)
        if dt <= 0:
            return
        q = round(B.sale(B.tramo(dt, 0.10, 0.40)) * 30) / 30          # la marca se dibuja (guardada por trozos)
        dd = d * (0.4 + 0.6 * B.rebote(B.tramo(dt, 0, 0.30), 1.6))
        clave = (q, round(dd * 4) / 4)
        icono = cache.get(clave)
        if icono is None:
            if len(cache) > 120:
                cache.clear()
            icono = cache[clave] = _premult(_marca(dd, q))
        _sobre(capa, icono, int(round(cx - icono.shape[1] / 2)), int(round(cy - icono.shape[0] / 2)),
               B.tramo(dt, 0, 0.08))

    T.animar = animar
    return T


def _pastilla(c, E):
    """La pastilla de abajo: el texto (la última palabra en el color de acento) y un interruptor que se enciende."""
    u, R = c.u, _ritmo(c)
    texto = str(c.op.get('pastilla') or '').strip()
    if not texto:
        return None
    antes, _, ultima = texto.rpartition(' ')
    h = 96 * u
    pista_w, pista_h = 80 * u, 46 * u
    izq, hueco, der = 34 * u, 22 * u, 25 * u
    tam = 31 * u
    for _ in range(2):                                 # si es muy larga, más pequeña (cabe en 700 px)
        r1 = Rotulo(antes + ' ', tam, 'medium', (255, 255, 255, 228)) if antes else None
        r2 = Rotulo(ultima, tam, 'bold', E['claro8'])
        ancho_txt = (r1.ancho if r1 else 0) + r2.ancho
        sobra = izq + ancho_txt + hueco + pista_w + der - 700 * u
        if sobra <= 0:
            break
        tam *= (ancho_txt - sobra) / ancho_txt
    w = izq + ancho_txt + hueco + pista_w + der
    T = Tarjeta('pastilla', w, h, h / 2, u)
    x = izq
    if r1:
        r1.poner(T.contenido, x, T.h / 2)
        x += r1.ancho
    r2.poner(T.contenido, x, T.h / 2)
    # el interruptor
    px0 = T.w - der - pista_w
    py0 = (T.h - pista_h) / 2
    ox, oy = int(math.floor(px0)) - 2, int(math.floor(py0)) - 4
    lw, lh = int(math.ceil(pista_w)) + 5, int(math.ceil(pista_h)) + 9
    xx, yy = _rejilla(lw, lh)
    xx, yy = xx + ox, yy + oy
    pista = _cobertura(_sdf_caja(xx, yy, px0 + pista_w / 2, py0 + pista_h / 2, pista_w / 2, pista_h / 2, pista_h / 2))
    rb = pista_h / 2 - 4 * u                                          # el radio de la bola
    xa, xb = px0 + pista_h / 2, px0 + pista_w - pista_h / 2
    yb = py0 + pista_h / 2
    acento = E['acento']
    t_on, d_on = 0.85 * R, 0.30 * R

    def animar(capa, t):
        q = _muelle(B.tramo(t, t_on, t_on + d_on * 1.6))                # la bola llega con un muelle corto
        k = B.suave(B.tramo(t, t_on, t_on + d_on))                      # el color de la pista
        col = np.array([1.0, 1.0, 1.0], np.float32) * (1 - k) + acento * k
        _pintar(capa, pista, col, 0.20 + 0.80 * k, ox, oy)
        bx = xa + (xb - xa) * q
        d = np.sqrt((xx - bx) ** 2 + (yy - yb - 1.5 * u) ** 2)
        sombra = np.clip((rb + 2.5 * u - d) / (4.0 * u), 0, 1).astype(np.float32)
        _pintar(capa, sombra * sombra, (0.0, 0.0, 0.0), 0.28, ox, oy)
        d = np.sqrt((xx - bx) ** 2 + (yy - yb) ** 2)
        _pintar(capa, np.clip(rb - d + 0.5, 0, 1).astype(np.float32), (1.0, 1.0, 1.0), 1.0, ox, oy)

    T.animar = animar
    return T


# ── Preparar ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _preparar(c):
    u = c.u
    r, g, b, _ = B.color(c.op.get('color') or '#8B5CF6')
    acento = np.array([r, g, b], np.float32) / 255.0
    claro = acento + (1.0 - acento) * 0.45
    E = {'acento': acento, 'claro': claro, 'acento8': (r, g, b, 255),
         'claro8': tuple(int(round(v * 255)) for v in claro) + (255,)}
    hechas = [_editando(c, E), _calendario(c, E), _contador(c, E), _creador(c, E), _anillo(c, E), _etiqueta(c, E),
              _exportando(c, E), _pastilla(c, E)]
    # dónde va cada una: la colocación de referencia, movida con la cara si está muy arriba o muy abajo
    cy0 = float(c.cara[1])
    desvio = cy0 - CARA_REFERENCIA[1] * u
    mover = math.copysign(max(0.0, abs(desvio) - 40 * u), desvio)
    mover = min(max(mover, -240 * u), 160 * u)
    tarjetas = []
    azar = np.random.default_rng(11)
    ultimo = max(s['orden'] for s in SITIOS.values())
    for T in hechas:
        if T is None:
            continue
        T.cerrar()
        s = SITIOS[T.clave]
        if 'der' in s:
            x = s['der'] * u - T.w
        elif 'centro' in s:
            x = s['centro'] * u - T.w / 2
        else:
            x = s['x'] * u
        y = s['y'] * u + mover
        T.cx0, T.cy0 = x + T.w / 2, y + T.h / 2
        T.t0 = s['orden'] * ESCALONADO
        T.orden = s['orden']
        T.sale_antes = (ultimo - s['orden']) * 0.010            # se van en el orden en que llegaron
        T.detras = bool(s.get('detras'))
        T.t_cruce = T.t0 + 0.30
        # cada una flota a su manera (las de detrás, menos: están más lejos)
        k = 0.6 if T.detras else 1.0
        T.flota = (k * azar.uniform(3.0, 4.0) * u, azar.uniform(3.8, 5.6), azar.uniform(0, 2 * math.pi),
                   k * azar.uniform(4.5, 6.5) * u, azar.uniform(3.2, 4.6), azar.uniform(0, 2 * math.pi))
        tarjetas.append(T)
    E['tarjetas'] = tarjetas
    E['centro'] = (CARA_REFERENCIA[0] * u, CARA_REFERENCIA[1] * u + mover)
    c.estado['cristal'] = E
    return E


# ── El cristal de cada tarjeta ──────────────────────────────────────────────────────────────────────────────────────
def _vidrio(c, X0, Y0, X1, Y1, sin_persona, k=1.0):
    """Lo de detrás de una tarjeta (el trozo X0..X1 × Y0..Y1 del cuadro), desenfocado, con un poco más de color y
    oscurecido con el tono del cristal. Se hace a un cuarto de tamaño (rápido y sin parpadeos). Con `sin_persona`, la
    persona no cuenta: el cristal de una tarjeta que va detrás solo ve la pared.
    `k` (0–1) es cuánto cristal hay: al entrar y al salir, el desenfoque y el tono crecen desde nada (el cristal se
    empaña), en vez de fundir una imagen nítida con una borrosa (eso se vería doble)."""
    k = min(1.0, max(0.0, k))
    sig = DESENFOQUE * c.u * max(k, 0.08)
    pad = int(math.ceil(2.6 * sig)) + 4
    a0, b0 = max(0, X0 - pad), max(0, Y0 - pad)
    a1, b1 = min(c.W, X1 + pad), min(c.H, Y1 + pad)
    trozo = c.img[b0:b1, a0:a1]
    w4, h4 = max(1, (a1 - a0) // 4), max(1, (b1 - b0) // 4)
    peq = cv2.resize(trozo, (w4, h4), interpolation=cv2.INTER_AREA)
    s4 = sig / 4
    if sin_persona:
        peso = 1.0 - cv2.resize(c.mascara[b0:b1, a0:a1], (w4, h4), interpolation=cv2.INTER_AREA)
        peq = cv2.GaussianBlur(peq * peso[..., None], (0, 0), s4)
        peso = cv2.GaussianBlur(peso, (0, 0), s4)
        peq = peq / np.maximum(peso, 1e-3)[..., None]
    else:
        peq = cv2.GaussianBlur(peq, (0, 0), s4)
    gris = peq.mean(axis=2, keepdims=True)
    peq = gris + (peq - gris) * (1.0 + (VIVEZA - 1.0) * k)
    op = OPACIDAD * k
    peq = peq * (1.0 - op) + np.asarray(TINTE, np.float32) / 255.0 * op + NIEBLA * k
    # de vuelta al tamaño de verdad, solo el trozo de la tarjeta
    kx, ky = w4 / (a1 - a0), h4 / (b1 - b0)
    M = np.array([[kx, 0, (X0 - a0 + 0.5) * kx - 0.5], [0, ky, (Y0 - b0 + 0.5) * ky - 0.5]], np.float64)
    vid = cv2.warpAffine(np.clip(peq, 0, 1), M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                         borderMode=cv2.BORDER_REPLICATE)
    if k < 0.35:                    # al empezar, de lo nítido a lo empañado (el cuarto de tamaño ya empaña un poco)
        q = np.float32(B.suave(k / 0.35))
        nitido = c.img[Y0:Y1, X0:X1]
        vid = nitido + (vid - nitido) * q
    return vid


def _matriz(izq, arriba, esc, X0, Y0):
    """La transformación que lleva un píxel de la tarjeta (su esquina en izq, arriba; escalada) al trozo del cuadro."""
    return np.array([[esc, 0, izq + 0.5 * esc - 0.5 - X0], [0, esc, arriba + 0.5 * esc - 0.5 - Y0]], np.float64)


def _caja_cara(c):
    cx, cy, fw = (float(v) for v in c.cara)
    return cx - 0.5 * fw, cy - 0.62 * fw, cx + 0.5 * fw, cy + 0.58 * fw, fw


def _distancia(caja, x0, y0, x1, y1):
    fx0, fy0, fx1, fy1, _ = caja
    dx = max(fx0 - x1, x0 - fx1, 0.0)
    dy = max(fy0 - y1, y0 - fy1, 0.0)
    return math.hypot(dx, dy), dx, dy


def _apartar(c, caja, cx, cy, w, h, detras):
    """Una de delante que quedaría a menos de 0,6 anchos de cara se aparta lo justo (hacia su lado, o hacia arriba si
    está encima). Depende de la cara, que ya viene suavizada: se aparta sin tirones. Las de detrás no se apartan: la
    persona va encima. Todas se quedan en la zona segura. Devuelve (cx, cy, cuánto se ve)."""
    zx0, zx1 = B.zona_segura(c)
    if detras:
        return min(max(cx, zx0 + w / 2), zx1 - w / 2), cy, 1.0
    fx0, fy0, fx1, fy1, fw = caja
    m = MARGEN_CARA * fw
    d, dx, dy = _distancia(caja, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    if d < m:
        if cx < fx0 or cx > fx1:                       # a un lado: se aparta hacia fuera
            falta = math.sqrt(max(0.0, m * m - dy * dy)) - dx
            cx += -falta if cx < fx0 else falta
        else:                                          # encima o debajo: se aparta hacia arriba o hacia abajo
            falta = math.sqrt(max(0.0, m * m - dx * dx)) - dy
            cy += -falta if cy < (fy0 + fy1) / 2 else falta
    cx = min(max(cx, zx0 + w / 2), zx1 - w / 2)
    d, _, _ = _distancia(caja, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    # si ni así cabe (la cara se fue hacia el borde), se desvanece antes que taparla
    se_ve = 1.0 if d >= m else float(np.clip((d - 0.3 * m) / (0.7 * m), 0, 1))
    return cx, cy, se_ve


def _silueta(c, X0, Y0, X1, Y1):
    """La silueta de la persona en el trozo X0..X1 × Y0..Y1, para lo que va DETRÁS de ella (las tarjetas de detrás y las
    sombras), con los agujeritos sueltos tapados: un recorte imperfecto trae a veces un cuadradito vacío en mitad del
    brazo, y por ahí se vería la tarjeta. Solo se tapan los huecos pequeños y cerrados (rodeados de persona); los de
    verdad (el hueco entre el brazo y el cuerpo) son más grandes y se quedan. La silueta nunca se encoge: solo puede
    crecer dentro de esos agujeritos. Se mira un poco más allá del trozo, para ver si cada hueco está cerrado."""
    m = c.mascara[Y0:Y1, X0:X1]
    if m.size == 0 or float(m.max()) < 0.5:          # sin persona en el trozo: nada que tapar
        return m
    mg = int(math.ceil(24 * c.u))
    a0, b0 = max(0, X0 - mg), max(0, Y0 - mg)
    a1, b1 = min(c.W, X1 + mg), min(c.H, Y1 + mg)
    grande = c.mascara[b0:b1, a0:a1]
    fondo = (grande < 0.5).view(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(fondo, connectivity=4)
    x, y, w, h, area = st[:, 0], st[:, 1], st[:, 2], st[:, 3], st[:, 4]
    # cerrado = no toca el borde de lo que se mira (si lo toca, es fondo de verdad o no se sabe: se deja)
    tapar = (area <= AGUJERO_MAX * c.u * c.u) & (x > 0) & (y > 0) & (x + w < a1 - a0) & (y + h < b1 - b0)
    tapar[0] = False
    if not tapar.any():
        return m
    hueco = tapar.astype(np.float32)[lab]
    r = max(1, int(round(3.5 * c.u)))                 # también el borde suave del agujerito
    hueco = cv2.dilate(hueco, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    hueco = cv2.GaussianBlur(hueco, (0, 0), 0.7 * c.u)
    return np.maximum(m, hueco[Y0 - b0:Y1 - b0, X0 - a0:X1 - a0])


def _sin_motas(F, sil, u, cuadro):
    """Quita del filo de la persona lo claro y muy fino que no es suyo. `B.color_persona` ya quita la luz de la pared,
    pero no lo que es más fino que su desenfoque: las letras blancas de un monitor pegado a la cabeza se quedaban en el
    filo y, sobre el cristal oscuro, salían como una columna de puntitos claros junto a la gorra. Una apertura (el mínimo
    y después el máximo en un cuadradito de ~3 px) borra lo claro más fino que eso y deja igual lo que cambia suave, que
    es lo que da el borde nítido. Solo en el filo (donde la silueta no es ni 0 ni 1): la silueta no cambia (no se encoge
    nada) y dentro de la persona no se toca nada. Fuera de la persona, `color_persona` deja el color medio de la persona
    (oscuro): para la apertura, ahí va el cuadro tal cual (la pared), y así el filo pasa suave de oscuro a claro y la
    apertura no lo oscurece (si no, la gorra salía con un borde oscuro borroso).
    (Pintar todo el filo con el color de dentro también quitaba los puntitos, pero dejaba la gorra con un borde oscuro
    borroso: el filo perdía la nitidez que trae el cuadro de verdad.)"""
    banda = (sil > 0.002) & (sil < 0.97)
    if not banda.any():
        return F
    r = max(1, int(round(1.5 * u)))
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (2 * r + 1, 2 * r + 1))
    fuera = (sil <= 0.002)[..., None]
    abierto = cv2.morphologyEx(np.where(fuera, cuadro, F).astype(np.float32), cv2.MORPH_OPEN, k)
    out = F.copy()
    out[banda] = abierto[banda]
    return out


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def dibujar(c):
    E = c.estado.get('cristal') or _preparar(c)
    u, t = c.u, c.t
    caja = _caja_cara(c)
    hx, hy = E['centro']
    vivas = []
    for T in E['tarjetas']:
        e = B.tramo(t, T.t0, T.t0 + ENTRA)
        if e <= 0.0:
            continue
        sal = B.tramo(c.queda - T.sale_antes, 0, SALE)
        if sal <= 0.0:
            continue
        m = _muelle(e)
        va = _seno(sal)                                                   # 1 → 0 al irse
        alfa = B.suave(B.tramo(t, T.t0, T.t0 + 0.22)) * va                # el filo, lo de dentro y la sombra
        empano = B.suave(B.tramo(t, T.t0, T.t0 + 0.28)) * va              # cuánto cristal hay
        esc = (0.78 + 0.22 * m) * (0.93 + 0.07 * va)
        ax, px, fx, ay, py, fy = T.flota
        # al entrar, sale de un poco más cerca de la cabeza (como de detrás de la persona) y llega con el muelle
        cx = T.cx0 + ax * math.sin(2 * math.pi * t / px + fx) + (hx - T.cx0) * DESDE_DENTRO * (1.0 - m)
        cy = T.cy0 + ay * math.sin(2 * math.pi * t / py + fy) + (hy - T.cy0) * DESDE_DENTRO * (1.0 - m)
        cx, cy, se_ve = _apartar(c, caja, cx, cy, T.w * esc, T.h * esc, T.detras)
        alfa *= se_ve
        if alfa <= 0.003 and empano <= 0.003:
            continue
        izq, arriba = cx - T.w * esc / 2, cy - T.h * esc / 2
        X0, Y0 = max(0, int(math.floor(izq)) - 1), max(0, int(math.floor(arriba)) - 1)
        X1, Y1 = min(c.W, int(math.ceil(izq + T.w * esc)) + 2), min(c.H, int(math.ceil(arriba + T.h * esc)) + 2)
        if X1 <= X0 or Y1 <= Y0:
            continue
        vivas.append([T, izq, arriba, esc, alfa, X0, Y0, X1, Y1, None, empano, se_ve])
    # dónde quedó cada tarjeta en este cuadro (para comprobarlo desde fuera: la cara, la zona segura)
    E['ultimo'] = [(v[0].clave, v[1], v[2], v[1] + v[0].w * v[3], v[2] + v[0].h * v[3], v[4]) for v in vivas]
    # primero el cristal de todas, con el cuadro tal cual (así una tarjeta no sale en el cristal de otra)
    for v in vivas:
        T, X0, Y0, X1, Y1 = v[0], v[5], v[6], v[7], v[8]
        v[9] = _vidrio(c, X0, Y0, X1, Y1, T.detras, v[10])
    # las de detrás primero; después las de delante
    for v in sorted(vivas, key=lambda v: (not v[0].detras, v[0].orden)):
        T, izq, arriba, esc, alfa, X0, Y0, X1, Y1, vid, empano, se_ve = v
        p = T.pad_sombra
        # la sombra
        sx0, sy0 = izq - p * esc, arriba - p * esc
        S0, T0 = max(0, int(math.floor(sx0))), max(0, int(math.floor(sy0)))
        S1 = min(c.W, int(math.ceil(sx0 + T.sombra.shape[1] * esc)) + 1)
        T1 = min(c.H, int(math.ceil(sy0 + T.sombra.shape[0] * esc)) + 1)
        if S1 > S0 and T1 > T0 and alfa > 0.003:
            sm = cv2.warpAffine(T.sombra, _matriz(sx0, sy0, esc, S0, T0), (S1 - S0, T1 - T0), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            # la sombra cae en la pared: nunca oscurece a la persona
            sm *= np.float32(alfa)
            sil = _silueta(c, S0, T0, S1, T1)
            if sil.size and float(sil.max()) > 0.0:
                sm *= 1.0 - sil
            np.subtract(np.float32(1.0), sm, out=sm)
            c.img[T0:T1, S0:S1] *= sm[..., None]
        # el cristal: entero desde el principio (lo que crece es lo empañado, ya dentro de `vid`)
        M = _matriz(izq, arriba, esc, X0, Y0)
        a = cv2.warpAffine(T.forma, M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                           borderValue=0)
        if se_ve < 1.0:
            a *= np.float32(se_ve)
        zona = c.img[Y0:Y1, X0:X1]
        antes = zona.copy() if T.detras else None
        vid -= zona                                    # zona + (cristal − zona) · forma
        vid *= a[..., None]
        zona += vid
        cubre = a
        if alfa > 0.003:
            # lo de encima del cristal (brillo, filo y lo de dentro), con un reescalado bicúbico: más nítido
            capa = cv2.warpAffine(T.capa(t), M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            np.maximum(capa, 0.0, out=capa)            # el bicúbico se pasa un pelo en los bordes: se recorta
            np.minimum(capa[..., 3], 1.0, out=capa[..., 3])
            if alfa < 0.999:
                capa *= np.float32(alfa)
            zona *= 1.0 - capa[..., 3:4]
            zona += capa[..., :3]
            cubre = np.maximum(a, capa[..., 3])
        if antes is not None:
            # la de detrás: la persona vuelve encima con el color limpio de su borde. Con el color tal cual, el borde
            # trae la luz de la pared, y sobre el cristal oscuro sale como un filo de color alrededor de la cabeza. Y lo
            # muy fino y claro que queda en el filo (las letras de un monitor), fuera (`_sin_motas`).
            sil = _silueta(c, X0, Y0, X1, Y1)
            if float(sil.max()) > 0.004:
                F, _ = B.color_persona(antes, sil, c.u)
                F = _sin_motas(F, sil, c.u, antes)
                m3 = sil[..., None]
                w = np.clip(cubre, 0.0, 1.0)[..., None]
                # la sombra de la persona sobre la tarjeta: sin ella, una oreja en penumbra (azulada por la luz de la
                # pared) se funde con el cristal oscuro y parece que no está (Kevin, 26 oct: «la oreja se me pierde por
                # detrás del fondo de la cápsula»). Suave, solo fuera de la persona y solo encima de la tarjeta
                sombra = np.clip(cv2.GaussianBlur(sil, (0, 0), SOMBRA_PERSONA[1] * c.u) * 1.6, 0.0, 1.0) * (1.0 - sil)
                zona *= 1.0 - SOMBRA_PERSONA[0] * sombra[..., None] * w
                limpio = F * m3 + zona * (1.0 - m3)
                zona[:] = antes + (limpio - antes) * w
