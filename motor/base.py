"""La base de los efectos: lo que comparten todos.

Cada efecto es un módulo de `efectos/` con `NOMBRE`, `DESCRIPCION`,
`OPCIONES` (los valores por defecto, en texto) y `dibujar(c)`, que recibe un `Cuadro` y cambia `c.img` en su sitio.

Reglas de la casa para que nada tiemble ni salte (las aprendimos editando los Reels de Kevin):
- Lo que se mueve se pone con `poner()`, que coloca con decimales (transformación afín). Pegar en píxeles enteros hace que
  lo que se mueve despacio vaya a saltitos.
- Todo entra y sale suave: `suave()` (ida y vuelta), `sale()` (frena al final) o `rebote()` (un rebote corto, para lo que
  aterriza). Nada aparece de golpe: como mínimo, un fundido de 0,2 s.
- Todas las medidas se multiplican por `c.u` (el ancho entre 1080): así el mismo efecto sale igual a 1080 y a 4K.
- Lo importante, dentro de la zona segura de Instagram: entre x = 60·u y x = 1020·u.
"""
import math
import os
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # la carpeta del motor
FUENTES = os.path.join(RAIZ, 'fuentes')
PESOS = {'light': 'Poppins-Light.ttf', 'regular': 'Poppins-Regular.ttf', 'medium': 'Poppins-Medium.ttf',
         'bold': 'Poppins-Bold.ttf', 'extrabold': 'Poppins-ExtraBold.ttf'}


@dataclass
class Cuadro:
    """Un cuadro del vídeo mientras dura un efecto."""
    img: np.ndarray          # alto × ancho × 3, float32 de 0 a 1: el cuadro. El efecto lo cambia en su sitio.
    mascara: np.ndarray      # alto × ancho, float32 de 0 a 1: 1 = la persona (para poner cosas detrás de ella)
    cara: tuple              # (cx, cy, ancho) de la cara en píxeles, ya suavizado entre cuadros
    t: float                 # segundos desde que empezó el efecto
    dur: float               # cuánto dura el efecto
    fps: float = 30.0
    op: dict = field(default_factory=dict)       # las opciones (en texto), con las de por defecto ya puestas
    estado: dict = field(default_factory=dict)   # lo que el efecto quiera guardar entre cuadros (cachés, imágenes)

    @property
    def H(self):
        return self.img.shape[0]

    @property
    def W(self):
        return self.img.shape[1]

    @property
    def u(self):
        """La escala: 1 a 1080 de ancho, 2 a 4K."""
        return self.W / 1080.0

    @property
    def queda(self):
        """Segundos que faltan para que acabe el efecto."""
        return self.dur - self.t


# ── Curvas de movimiento ────────────────────────────────────────────────────────────────────────────────────────────
def tramo(t, a, b):
    """De 0 a 1 mientras t va de a a b (fuera, 0 o 1)."""
    if b <= a:
        return 1.0 if t >= b else 0.0
    return min(1.0, max(0.0, (t - a) / (b - a)))


def suave(x):
    """Arranca y frena suave (ida y vuelta cúbica)."""
    x = min(1.0, max(0.0, x))
    return 4 * x * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def sale(x):
    """Sale rápido y frena al final (cúbica)."""
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def entra(x):
    """Arranca despacio y acelera (cúbica)."""
    x = min(1.0, max(0.0, x))
    return x * x * x


def rebote(x, fuerza=1.25):
    """Llega, se pasa un poco y vuelve (para lo que aterriza). fuerza 1–1,7."""
    x = min(1.0, max(0.0, x))
    c3 = fuerza + 1
    return 1 + c3 * (x - 1) ** 3 + fuerza * (x - 1) ** 2


def fundido(c, entrada=0.25, salida=0.25):
    """La opacidad general de un efecto: sube al empezar y baja antes de acabar."""
    return tramo(c.t, 0, entrada) * tramo(c.queda, 0, salida)


def mezclar(a, b, k):
    return a + (b - a) * k


# ── Color y letras ──────────────────────────────────────────────────────────────────────────────────────────────────
def color(hexa, alfa=255):
    """'#7C3AED' → (124, 58, 237, alfa)."""
    h = str(hexa).strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(ch * 2 for ch in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alfa)


@lru_cache(maxsize=256)
def fuente(peso, tam):
    return ImageFont.truetype(os.path.join(FUENTES, PESOS[peso]), max(4, int(round(tam))))


def texto(s, tam, peso='bold', relleno=(255, 255, 255, 255), contorno=0, color_contorno=(0, 0, 0, 200), sombra=0,
          color_sombra=(0, 0, 0, 160), espacio=0.0):
    """Un texto en una capa RGBA justa (con aire para el contorno y la sombra). `espacio`: separación extra entre letras,
    en proporción al tamaño (0,02 = un poco más abierta)."""
    f = fuente(peso, tam)
    pad = int(math.ceil(contorno + sombra * 2.5 + tam * 0.08))
    if espacio:
        anchos = [f.getlength(ch) for ch in s]
        w = int(math.ceil(sum(anchos) + espacio * tam * max(0, len(s) - 1)))
    else:
        w = int(math.ceil(f.getlength(s)))
    asc, desc = f.getmetrics()
    h = asc + desc
    capa = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)

    def escribir(dibujo, xy, rell, trazo=0, color_trazo=None):
        if espacio:
            x = xy[0]
            for ch, a in zip(s, anchos):
                dibujo.text((x, xy[1]), ch, font=f, fill=rell, stroke_width=trazo, stroke_fill=color_trazo)
                x += a + espacio * tam
        else:
            dibujo.text(xy, s, font=f, fill=rell, stroke_width=trazo, stroke_fill=color_trazo)

    if sombra:
        sm = Image.new('RGBA', capa.size, (0, 0, 0, 0))
        escribir(ImageDraw.Draw(sm), (pad, pad + sombra * 0.6), color_sombra)
        capa = Image.alpha_composite(capa, sm.filter(ImageFilter.GaussianBlur(sombra)))
        d = ImageDraw.Draw(capa)
    escribir(d, (pad, pad), relleno, int(round(contorno)), color_contorno if contorno else None)
    return capa


def encajar(s, ancho, peso='extrabold', tam_max=400, **kw):
    """El texto al tamaño justo para ocupar `ancho` (sin pasar de `tam_max`)."""
    f = fuente(peso, 100)
    tam = min(tam_max, 100 * ancho / max(1.0, f.getlength(s)))
    return texto(s, tam, peso, **kw)


# ── Formas ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def caja(w, h, r, relleno=(20, 20, 24, 255), borde=None, grosor=0, nitidez=3):
    """Un rectángulo redondeado en RGBA, con los bordes suaves (se dibuja a `nitidez` veces y se reduce)."""
    w, h = max(1, int(round(w))), max(1, int(round(h)))
    k = nitidez
    grande = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    ImageDraw.Draw(grande).rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=int(r * k), fill=relleno,
                                            outline=borde, width=int(round(grosor * k)) if borde else 0)
    return grande.resize((w, h), Image.LANCZOS)


def con_sombra(capa, desenfoque=18, dy=10, alfa=120):
    """La capa con una sombra suave debajo (la capa crece para que quepa)."""
    pad = int(desenfoque * 2 + abs(dy))
    w, h = capa.size
    out = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    a = capa.split()[3].point(lambda v: v * alfa // 255)
    sm = Image.new('RGBA', capa.size, (0, 0, 0, 255))
    sm.putalpha(a)
    out.alpha_composite(sm, (pad, pad + int(dy)))
    out = out.filter(ImageFilter.GaussianBlur(desenfoque))
    out.alpha_composite(capa, (pad, pad))
    return out


def recortar_redondo(im, r):
    """Una imagen con las esquinas redondeadas."""
    im = im.convert('RGBA')
    m = caja(im.width, im.height, r, (255, 255, 255, 255)).split()[3]
    a = Image.fromarray(np.minimum(np.asarray(im.split()[3]), np.asarray(m)))
    im.putalpha(a)
    return im


def a_capa(arr):
    """De un trozo del cuadro (alto × ancho × 3, 0–1) a una imagen RGBA."""
    return Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB').convert('RGBA')


def cristal(c, x, y, w, h, r, tinte=(14, 14, 18), opacidad=0.62, desenfoque=26, brillo=0.16):
    """Una tarjeta de cristal esmerilado hecha con el trozo del cuadro que queda detrás (x, y = su esquina de arriba a la
    izquierda). Devuelve una capa RGBA para ponerla con `poner()` en ese mismo sitio."""
    x0, y0 = int(max(0, math.floor(x))), int(max(0, math.floor(y)))
    x1, y1 = int(min(c.W, math.ceil(x + w))), int(min(c.H, math.ceil(y + h)))
    w, h = int(round(w)), int(round(h))
    fondo = np.zeros((h, w, 3), np.float32)
    if x1 > x0 and y1 > y0:
        fondo[y0 - int(math.floor(y)):y0 - int(math.floor(y)) + (y1 - y0),
              x0 - int(math.floor(x)):x0 - int(math.floor(x)) + (x1 - x0)] = c.img[y0:y1, x0:x1]
    capa = a_capa(fondo).filter(ImageFilter.GaussianBlur(desenfoque * c.u))
    tono = Image.new('RGBA', capa.size, tinte + (int(255 * opacidad),))
    capa = Image.alpha_composite(capa, tono)
    capa = recortar_redondo(capa, r)
    filo = caja(w, h, r, (0, 0, 0, 0), borde=(255, 255, 255, int(255 * brillo)), grosor=max(1, 1.5 * c.u))
    return Image.alpha_composite(capa, filo)


# ── Poner capas en el cuadro ────────────────────────────────────────────────────────────────────────────────────────
def poner(c, capa, cx, cy, escala=1.0, giro=0.0, alfa=1.0, detras=False):
    """Pone la capa RGBA con su CENTRO en (cx, cy), con decimales (sin saltitos), escalada y girada (`giro` en grados,
    positivo = a favor del reloj). `detras=True`: queda detrás de la persona (la máscara la tapa)."""
    if alfa <= 0.003 or escala <= 0.003:
        return
    w, h = capa.size
    th = math.radians(giro)
    co, si = math.cos(th), math.sin(th)
    bw = abs(w * escala * co) + abs(h * escala * si)
    bh = abs(w * escala * si) + abs(h * escala * co)
    x0, y0 = int(math.floor(cx - bw / 2)) - 2, int(math.floor(cy - bh / 2)) - 2
    x1, y1 = int(math.ceil(cx + bw / 2)) + 2, int(math.ceil(cy + bh / 2)) + 2
    # recorte con el cuadro
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(c.W, x1), min(c.H, y1)
    if X1 <= X0 or Y1 <= Y0:
        return
    s = escala
    a, b = co / s, si / s
    d, e = -si / s, co / s
    ox, oy = X0 - cx, Y0 - cy
    cc = a * ox + b * oy + w / 2
    f = d * ox + e * oy + h / 2
    hecha = capa.convert('RGBa').transform((X1 - X0, Y1 - Y0), Image.AFFINE, (a, b, cc, d, e, f),
                                           resample=Image.BICUBIC).convert('RGBA')
    arr = np.asarray(hecha, dtype=np.float32) / 255.0
    al = arr[..., 3:4] * float(alfa)
    if detras:
        al = al * (1.0 - c.mascara[Y0:Y1, X0:X1, None])
    zona = c.img[Y0:Y1, X0:X1]
    zona *= (1.0 - al)
    zona += arr[..., :3] * al


def oscurecer(c, cuanto, salvo_persona=True, tinte=(0.0, 0.0, 0.0)):
    """Baja la luz del cuarto (la persona se queda igual si `salvo_persona`). cuanto 0–1."""
    if cuanto <= 0:
        return
    k = cuanto * ((1.0 - c.mascara) if salvo_persona else np.ones_like(c.mascara))
    k = k[..., None]
    c.img *= (1.0 - k)
    c.img += np.array(tinte, np.float32) * k


def colorear(c, matriz=None, mas=(0.0, 0.0, 0.0), cuanto=1.0):
    """Un cambio de color de todo el cuadro: img·matriz + mas, mezclado `cuanto` con el original."""
    if cuanto <= 0:
        return
    m = np.eye(3, dtype=np.float32) if matriz is None else np.asarray(matriz, np.float32)
    nuevo = np.clip(c.img @ m.T + np.asarray(mas, np.float32), 0, 1)
    c.img += (nuevo - c.img) * cuanto


def zona_segura(c):
    """Los límites de lo importante (x de 60 a 1020 a 1080 de ancho)."""
    return 60 * c.u, c.W - 60 * c.u


def imagenes_de(carpeta):
    """Las imágenes (jpg, png, webp) de una carpeta, en orden. Vacía si no hay."""
    if not carpeta or not os.path.isdir(carpeta):
        return []
    out = []
    for n in sorted(os.listdir(carpeta)):
        if n.lower().rsplit('.', 1)[-1] in ('jpg', 'jpeg', 'png', 'webp'):
            out.append(Image.open(os.path.join(carpeta, n)).convert('RGBA'))
    return out


# ── El borde de la persona, limpio ──────────────────────────────────────────────────────────────────────────────────
# Para los efectos que cambian lo que hay alrededor de la persona (el fondo nuevo, apagar la luz del cuarto): el recorte
# trae en su filo un poco del fondo de verdad, y al cambiar lo de alrededor ese filo se ve como un halo claro (la pared
# alrededor de la oreja, del brazo). Se arregla en dos pasos: el borde, un poco hacia dentro y suave (`borde_firme`), y
# los píxeles del filo con el color de la persona de justo al lado (`sin_halo`).

def borde_firme(m, u, desde=0.5, hasta=0.9, suavizado=2.6):
    """La máscara con el contorno alisado y un pelo hacia dentro: se desenfoca y se vuelve a cortar por encima de la
    mitad (de `desde` a `hasta`). Quita los dientes del borde y deja fuera el filo del fondo de verdad. float32 0–1."""
    import cv2
    mb = cv2.GaussianBlur(m.astype(np.float32, copy=False), (0, 0), suavizado * u)
    mb -= np.float32(desde)
    mb *= np.float32(1.0 / (hasta - desde))
    np.clip(mb, 0, 1, out=mb)
    return mb * mb * (np.float32(3.0) - np.float32(2.0) * mb)


def sin_halo(p, m, u, cierre=2.5, alcance=3.0, ancho=2.0):
    """Los píxeles del filo de la persona toman el tono de la persona de justo al lado, no el suyo (que lleva mezclado
    el fondo de verdad). `p` es la imagen (gris o color, float32), `m` la máscara. El núcleo se mete `cierre` px hacia
    dentro para no coger nada del fondo. Fuera de la persona el resultado no vale: se mezcla siempre con la máscara."""
    import cv2
    nucleo = (m > 0.985).astype(np.uint8)
    r = max(1, int(round(cierre * u)))
    nucleo = cv2.erode(nucleo, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))).astype(np.float32)
    s = alcance * u
    peso = np.maximum(cv2.GaussianBlur(nucleo, (0, 0), s), np.float32(1e-3))
    if p.ndim == 3:
        vecino = cv2.GaussianBlur(p * nucleo[..., None], (0, 0), s) / peso[..., None]
        dentro = cv2.GaussianBlur(nucleo, (0, 0), ancho * u)[..., None]
    else:
        vecino = cv2.GaussianBlur(p * nucleo, (0, 0), s) / peso
        dentro = cv2.GaussianBlur(nucleo, (0, 0), ancho * u)
    return vecino + (p - vecino) * dentro
