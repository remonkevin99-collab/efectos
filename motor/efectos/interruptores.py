"""interruptores: encima de la cabeza, una tarjeta de ajustes (como la del teléfono) con interruptores que se encienden
uno a uno.

La tarjeta es blanca y esmerilada (se adivina un poco la pared de detrás), con las esquinas muy redondas y una sombra
suave. Cada fila lleva su texto a la izquierda y un interruptor a la derecha: una pista gris con su bola blanca. Uno detrás
de otro, la bola se desliza a la derecha y la pista se pone verde. La tarjeta sube un poco al entrar y se va con un
fundido.

Dónde va: encima de la cabeza, centrada con la cara y dentro de la zona segura. Si encima no cabe entera, se achica; y si
ni así cabe, se pone detrás de la persona (la cabeza queda delante y la cara nunca se tapa).

    .venv/bin/python efectos.py interruptores tu_video.mp4 --desde 2 --hasta 5 --fotos 2.2,2.9,3.6,4.6
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import base as B

try:                       # OpenCV desenfoca mucho más rápido; si no está, se usa Pillow
    import cv2
except ImportError:
    cv2 = None

NOMBRE = 'interruptores'
DESCRIPCION = 'Encima de tu cabeza, una tarjeta de ajustes con interruptores que se encienden uno a uno'
OPCIONES = {
    'lineas': 'Un clip|Escribo /efectos|Cero apps de edición',   # una fila por cada texto, separados por «|»
    'color': '#34C759',          # el color del interruptor encendido
    'cada': '0,45',              # los segundos entre un interruptor y el siguiente
    'detras': 'auto',            # «si»: la tarjeta va detrás de la persona; «no»: delante; «auto»: delante si cabe
}
DURACION = 3.0

ENTRADA = 0.35       # lo que tarda la tarjeta en subir y aparecer
SALIDA = 0.30        # el fundido del final
CAMBIO = 0.30        # lo que tarda un interruptor en encenderse
PRIMERO = 0.55       # cuándo empieza a encenderse el primero
QUIETO = 0.55        # lo que se ven todos encendidos, como mínimo, antes de irse

TINTA = (22, 22, 26, 255)            # el texto (casi negro, como en los ajustes del teléfono)
GRIS_PISTA = (212, 212, 218, 255)    # la pista apagada
LINEA = (60, 60, 67, 46)             # los separadores entre filas
SS = 4                               # los interruptores se dibujan 4 veces más grandes y se reducen: bordes suaves


# ── Las piezas ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _lineas(op):
    out = [x.strip() for x in str(op.get('lineas') or '').split('|') if x.strip()]
    return out or ['Listo']


def _numero(s, defecto):
    try:
        return float(str(s).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return defecto


def _mezcla(a, b, k):
    return tuple(int(round(x + (y - x) * k)) for x, y in zip(a, b))


def _interruptor(L, k):
    """El interruptor con la bola en k (0 = apagado, a la izquierda; 1 = encendido, a la derecha). Se guarda por pasos
    de 1/64 (la bola avanza menos de un píxel de uno a otro)."""
    q = round(min(1.0, max(0.0, k)) * 64) / 64
    hecho = L['interruptores'].get(q)
    if hecho is not None:
        return hecho
    tw, th, pad = L['TW'], L['TH'], L['TPAD']
    W, H = int(round((tw + 2 * pad) * SS)), int(round((th + 2 * pad) * SS))
    p, a, b = pad * SS, tw * SS, th * SS
    capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(capa).rounded_rectangle([p, p, p + a, p + b], radius=b / 2, fill=_mezcla(GRIS_PISTA, L['acento'], q))
    # la bola: blanca, con una sombra suave debajo
    margen = b * 0.068
    d = b - 2 * margen
    bx = p + margen + (a - 2 * margen - d) * q
    by = p + margen
    sombra = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dy = 2.2 * L['u'] * SS
    ImageDraw.Draw(sombra).ellipse([bx, by + dy, bx + d, by + d + dy], fill=(0, 0, 0, 70))
    capa.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(3.2 * L['u'] * SS)))
    ImageDraw.Draw(capa).ellipse([bx, by, bx + d, by + d], fill=(255, 255, 255, 255))
    capa = capa.resize((int(round(tw + 2 * pad)), int(round(th + 2 * pad))), Image.LANCZOS)
    arr = np.asarray(capa, np.float32) / 255.0
    hecho = (arr[..., :3] * arr[..., 3:4], arr[..., 3:4])        # premultiplicado, para pegarlo rápido
    L['interruptores'][q] = hecho
    return hecho


def _cabeza_arriba(c):
    """Lo más alto de la cabeza (una gorra o un peinado alto cuentan): lo que diga la cara o la silueta, lo más arriba."""
    cx, cy, ac = (float(v) for v in c.cara)
    por_cara = cy - 1.25 * ac
    x0, x1 = int(max(0, cx - 1.2 * ac)), int(min(c.W, cx + 1.2 * ac))
    if x1 - x0 < 4:
        return por_cara
    filas = np.where((c.mascara[:, x0:x1] > 0.5).mean(1) > 0.15)[0]
    return min(por_cara, float(filas[0])) if len(filas) else por_cara


def _preparar(c):
    u, op = c.u, c.op
    lineas = _lineas(op)
    n = len(lineas)
    L = {'u': u, 'n': n, 'acento': B.color(op.get('color') or '#34C759'), 'interruptores': {}}

    # medidas a tamaño natural (a 1080 de ancho)
    tam, PX, FILA, PV = 44 * u, 40 * u, 100 * u, 8 * u
    TW, TH = 96 * u, 58 * u
    HUECO = 44 * u                                                   # entre el texto más largo y el interruptor
    izq, der = B.zona_segura(c)
    w_max = der - izq
    f = B.fuente('medium', tam)
    largo = max(f.getlength(s) for s in lineas)
    sitio_txt = w_max - 2 * PX - HUECO - TW
    if largo > sitio_txt:                                            # un texto muy largo: la letra baja hasta caber
        tam *= sitio_txt / largo
        largo = sitio_txt
    w = max(600 * u, 2 * PX + largo + HUECO + TW)
    h = 2 * PV + n * FILA

    # dónde va: encima de la cabeza, centrada con la cara; si no cabe, más pequeña; si ni así, detrás de la persona
    cx, cy, ac = (float(v) for v in c.cara)
    arriba_min = 210 * u
    abajo_max = _cabeza_arriba(c) - 30 * u
    sitio = abajo_max - arriba_min
    if h > sitio:                                                    # primero, las filas un poco más juntas
        FILA = max(86 * u, (sitio - 2 * PV) / n)
        h = 2 * PV + n * FILA
    esc = 1.0 if h <= sitio else max(0.72, sitio / h)
    detras = str(op.get('detras') or 'auto').strip().lower()
    if detras in ('si', 'sí', 'yes', '1', 'true'):
        L['detras'] = True
    elif detras in ('no', '0', 'false'):
        L['detras'] = False
    else:
        L['detras'] = h * esc > sitio + 1                            # no cabe encima ni achicada: detrás de la cabeza
    if esc < 0.999:                                                   # todo un poco más pequeño
        tam, PX, FILA, PV, TW, TH, HUECO = (v * esc for v in (tam, PX, FILA, PV, TW, TH, HUECO))
        f = B.fuente('medium', tam)
        largo = max(f.getlength(s) for s in lineas)
        w = max(600 * u * esc, 2 * PX + largo + HUECO + TW)
        h = 2 * PV + n * FILA
    w, h = int(round(w)), int(round(h))
    x = min(max(cx - w / 2, izq), der - w)
    y = max(arriba_min, abajo_max - h)
    L.update(w=w, h=h, x=int(round(x)), y=int(round(y)), TW=TW, TH=TH, TPAD=8 * u, r=min(44 * u * max(esc, 0.8), h / 2))

    # lo que no cambia: los textos y los separadores, en una capa (premultiplicada) del tamaño de la tarjeta
    fija = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(fija)
    alto_mayus = -f.getbbox('H', anchor='ls')[1]
    grosor = max(1.0, 1.6 * u)
    L['filas'] = []
    for i, s in enumerate(lineas):
        yc = PV + FILA * (i + 0.5)
        d.text((PX, round(yc + alto_mayus / 2)), s, font=f, fill=TINTA, anchor='ls')
        if i < n - 1:                                                # el separador: desde el texto hasta el borde
            ys = PV + FILA * (i + 1)
            sep = B.caja(w - PX, grosor * 3, 0, LINEA)
            sep = sep.resize((sep.width, max(1, int(round(grosor)))), Image.LANCZOS)
            fija.alpha_composite(sep, (int(round(PX)), int(round(ys - grosor / 2))))
        L['filas'].append(yc)
    arr = np.asarray(fija, np.float32) / 255.0
    L['fija'] = (arr[..., :3] * arr[..., 3:4], arr[..., 3:4])
    L['forma'] = np.asarray(B.caja(w, h, L['r'], (255, 255, 255, 255)).split()[3], np.float32) / 255.0
    L['int_x'] = int(round(w - PX * 0.8 - TW - 8 * u))               # la esquina de cada interruptor (con su aire)
    L['sombra'] = _sombra(w, h, L['r'], 30 * u, 62)

    # cuándo se enciende cada uno: cada «cada» segundos; si no caben en el tiempo, más seguidos
    cada = max(0.15, _numero(op.get('cada'), 0.45))
    ultimo = c.dur - SALIDA - QUIETO - CAMBIO
    if n > 1 and PRIMERO + (n - 1) * cada > ultimo:
        cada = max(0.15, (ultimo - PRIMERO) / (n - 1))
    L['inicios'] = [PRIMERO + i * cada for i in range(n)]
    return L


def _sombra(w, h, r, desenfoque, alfa):
    """Solo la sombra de la tarjeta, con aire para el desenfoque."""
    pad = int(desenfoque * 2.5)
    a = B.caja(w, h, r, (0, 0, 0, 255)).split()[3].point(lambda v: v * alfa // 255)
    out = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    negro = Image.new('RGBA', a.size, (0, 0, 0, 255))
    negro.putalpha(a)
    out.alpha_composite(negro, (pad, pad))
    return out.filter(ImageFilter.GaussianBlur(desenfoque))


def _esmerilado(c, x, y, w, h):
    """Lo que hay detrás de la tarjeta, desenfocado y aclarado (cristal blanco casi opaco)."""
    xi, yi = int(math.floor(x)), int(math.floor(y))
    if 0 <= xi and xi + w <= c.W and 0 <= yi and yi + h <= c.H:
        trozo = c.img[yi:yi + h, xi:xi + w]
    else:                                                             # se sale del cuadro: se repite el borde
        filas = np.clip(np.arange(yi, yi + h), 0, c.H - 1)
        cols = np.clip(np.arange(xi, xi + w), 0, c.W - 1)
        trozo = c.img[filas[:, None], cols[None, :]]
    w4, h4 = max(1, w // 4), max(1, h // 4)
    if cv2 is not None:
        peq = cv2.resize(trozo, (w4, h4), interpolation=cv2.INTER_AREA)
        peq = cv2.GaussianBlur(peq, (0, 0), 30 * c.u / 4)
        fondo = cv2.resize(peq, (w, h), interpolation=cv2.INTER_LINEAR)
    else:
        im = Image.fromarray((trozo * 255 + 0.5).clip(0, 255).astype(np.uint8), 'RGB').resize((w4, h4), Image.BOX)
        fondo = np.asarray(im.filter(ImageFilter.GaussianBlur(30 * c.u / 4)).resize((w, h), Image.BILINEAR),
                           np.float32) / 255.0
    return fondo * 0.10 + 0.90 * 0.985                                # blanco al 90 %, con un poco de lo de detrás


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def dibujar(c):
    L = c.estado.get('interruptores')
    if L is None:
        L = c.estado['interruptores'] = _preparar(c)
    u, t = c.u, c.t
    alfa = B.suave(B.tramo(t, 0, ENTRADA)) * B.suave(B.tramo(c.queda, 0, SALIDA))
    if alfa <= 0.003:
        return
    sube = (1 - B.sale(B.tramo(t, 0, ENTRADA))) * 40 * u               # sube un poco al entrar
    w, h = L['w'], L['h']
    X, Y = L['x'], L['y'] + sube

    # la tarjeta: lo de detrás esmerilado, los textos y los separadores, y los interruptores
    tarjeta = _esmerilado(c, X, Y, w, h)
    rgbp, a = L['fija']
    tarjeta = tarjeta * (1 - a) + rgbp
    ix = L['int_x']
    for i, yc in enumerate(L['filas']):
        k = B.suave(B.tramo(t, L['inicios'][i], L['inicios'][i] + CAMBIO))
        trgbp, ta = _interruptor(L, k)
        th, tw = ta.shape[:2]
        iy = int(round(yc - th / 2))
        zona = tarjeta[iy:iy + th, ix:ix + tw]
        zona *= (1 - ta)
        zona += trgbp
    rgba = np.dstack([tarjeta, L['forma']])
    capa = Image.fromarray((rgba * 255 + 0.5).clip(0, 255).astype(np.uint8), 'RGBA')

    B.poner(c, L['sombra'], X + w / 2, Y + h / 2 + 14 * u, alfa=alfa, detras=L['detras'])
    B.poner(c, capa, X + w / 2, Y + h / 2, alfa=alfa, detras=L['detras'])
