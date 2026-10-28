"""Muro de texto: el fondo de detrás de la persona se cambia por un muro de texto que ocupa todo el cuadro, con una
palabra (`resalta`) dentro de una caja de color. La persona queda delante, con sus colores y el borde limpio (como en
`fondo`). Hay dos maneras (`modo`):

`modo=paginas` (la de fábrica; como el «match-cut» dun Reel de referencia, medido cuadro a cuadro el 28 oct 2026):
- El muro son PÁGINAS de texto quietas que se cambian de golpe cada pocos cuadros (`cambio`, 0,2 s: 6 cuadros a 30 fps;
  las de ella duran de 4 a 9). Cada página va con otra letra y otro tamaño (`tipos`, en orden y en bucle): Poppins
  negrita, una cursiva con serifa, una de máquina de escribir, Poppins media, una con serifa y una condensada muy gruesa.
  Las palabras son las de `texto`, en minúscula y barajadas de otra forma en cada página.
- La palabra resaltada sale UNA vez por página, en la misma letra que la página, en blanco dentro de la caja, y la caja
  NO se mueve de una página a otra: siempre centrada en el mismo punto, encima de la cabeza (si no cabe por debajo de lo
  que tapa Instagram arriba, al lado). Es el «match-cut»: todo cambia menos la palabra.
- Como en el de ella, la letra es grande (de 66 a 96 px a 1080 de ancho, unas 19 líneas en el alto) y oscura alrededor de
  la palabra, y se va desenfocando y aclarando hacia abajo (y un poco hacia arriba), como un muro con poca profundidad de
  campo. El papel tiene una luz suave detrás de la persona y las esquinas algo más oscuras.
- Como el texto de cada página está quieto, no hay nada que tiemble: lo único que se mueve es el cambio de página, limpio
  y siempre al mismo ritmo. Entra con un fundido corto (`entra`; 0 = lleno desde el primer cuadro, para cuando el montaje
  ya lo funde) y se va con un fundido en los últimos 0,3 s.

    .venv/bin/python efectos.py muro tu_video.mp4 --desde 1 --hasta 4 --op resalta=Claude
    .venv/bin/python efectos.py muro tu_video.mp4 --desde 1 --hasta 4 --op tipos=condensada,cursiva --op cambio=0.25

`modo=deriva` (el de antes): una página de periódico (un papel claro, blanco roto, con una viñeta muy suave) llena de
líneas de texto gris que se deslizan muy despacio, una línea hacia un lado y la siguiente hacia el otro. La palabra sale
varias veces entre el texto, y la que queda más cerca de la cabeza entra en la caja con un pequeño golpe de escala.
- El muro entra con un barrido de arriba abajo (0,3 s, con el filo suave; la persona no cambia) y se va con un fundido en
  los últimos 0,3 s.
- Las líneas, en Poppins Regular a 42 px (a 1080 de ancho), en gris cálido sobre el papel; cada una se mueve 15 px por
  segundo. Para que no tiemble ni haga muaré, el texto se pinta una vez a 4 veces de ancho y en cada cuadro se coge un
  trozo y se reduce: se mueve de cuarto en cuarto de píxel, el mismo paso en todos los cuadros (a 4K, 1 px justo).
  Más deprisa, el revisor de parpadeos lo marca (a 30 px/s, 1.000 píxeles; a 15, 170, como el fondo).
- La caja de la palabra: al lado de la cabeza o encima (donde quede más cerca de la frente y quepa), siempre dentro de la
  zona segura (x de 60 a 1020), por debajo de lo que tapa Instagram arriba y sin pisar la silueta. Su línea se aleja de
  la cabeza, así que la caja nunca se mete detrás. Entra a los 0,35 s con un rebote corto. Es un 20 % más grande que la
  letra del muro y la palabra gris queda debajo, con sitio a los lados para que la caja no pise las vecinas.

En los dos, una sombra muy suave de la persona sobre el papel, para que no parezca pegada, y todo se coloca según dónde
está la persona al empezar y ya no la persigue: es un decorado.

    .venv/bin/python efectos.py muro tu_video.mp4 --desde 1 --hasta 4 --op modo=deriva --op color=#E5484D

Las letras nuevas (Anton, Instrument Serif y Courier Prime) son libres (licencia OFL) y van en `fuentes/` con su
licencia. Si falta alguna, esa página sale en Poppins.
"""
import math
import os
import re
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import base as B

NOMBRE = 'muro'
DESCRIPCION = ('Detrás de ti, páginas de texto que cambian de letra cada pocos cuadros, con una palabra resaltada '
               'siempre en su sitio')
OPCIONES = {
    'resalta': 'Claude',            # la palabra de la caja (en `deriva`, además, sale varias veces entre el texto)
    'color': '#CE2C29',             # el color de la caja, rojo de rotulador (letra en blanco; el de antes, #E5484D)
    'modo': 'paginas',              # paginas: páginas quietas que cambian de letra de golpe · deriva: el de antes
    'tipos': 'negrita,cursiva,maquina,redonda,serif,condensada',   # (paginas) la letra de cada página, en bucle
    'cambio': '0.2',                # (paginas) cada cuánto cambia de página, en segundos (se redondea a cuadros enteros)
    'entra': '0.15',                # (paginas) el fundido de la entrada, en segundos; 0 = lleno desde el primer cuadro
    'texto': ('Grabas la toma tres veces porque en la primera se te trabó una palabra. Después cortas los silencios uno '
              'por uno, subes la voz, bajas la música y buscas el momento justo para cada corte. Pones los subtítulos a '
              'mano, mueves cada texto para que no tape la cara, eliges la portada y esperas a que el vídeo termine de '
              'exportarse. Un clip de treinta segundos se come la tarde entera, y mañana toca empezar otra vez.'),
}
DURACION = 3.0

ENTRA, SALE = 0.30, 0.30      # el barrido del muro al entrar y el fundido al salir
FILO_BARRIDO = 280            # lo suave que es el borde del barrido (a 1080 de ancho)
CAJA_T0, CAJA_T1 = 0.35, 0.72   # el golpe de escala de la caja
TAM = 42                      # el tamaño de la letra (a 1080 de ancho)
CAJA_LETRA = 1.20             # la palabra de la caja, en tamaños de la letra de las líneas
INTERLINEA = 1.24             # de una línea a la siguiente, en tamaños de letra
ALTERNA = True                # una línea hacia un lado y la siguiente hacia el otro (False: todas hacia el mismo)
DERIVA = 15                   # lo que se mueve cada línea por segundo (a 1080 de ancho); a 30, el revisor ve parpadeo
PAPEL = (244, 240, 232)       # blanco roto
TINTA = (146, 141, 132)       # gris cálido
SOMBRA = 0.20                 # lo oscura que es la sombra de la persona en el papel
SUPER = 4                     # el texto se pinta a 4 veces de ancho y se mueve de cuarto en cuarto de píxel
HUECO = 34                    # el aire entre la silueta y la caja (a 1080 de ancho)
TECHO, PISO = 250, 0.70       # la caja, por debajo de lo que tapa Instagram arriba y por encima del 70 % del alto

# ── modo=paginas ──
# Cada letra: (archivo en fuentes/, tamaño a 1080 de ancho, de una línea a la siguiente en tamaños de letra). Medidas
# sacadas de las páginas de la referencia: de 88 a 112 px de una línea a otra (a 1080), la caja casi del alto de la línea.
TIPOS = {
    'negrita': ('Poppins-Bold.ttf', 66, 1.32),                 # redonda y gruesa (en la de ella, Montserrat negrita)
    'redonda': ('Poppins-Medium.ttf', 66, 1.34),               # redonda y media
    'cursiva': ('InstrumentSerif-Italic.ttf', 96, 1.16),       # cursiva con serifa, de revista
    'serif': ('InstrumentSerif-Regular.ttf', 94, 1.16),        # con serifa, recta
    'maquina': ('CourierPrime-Bold.ttf', 68, 1.36),            # de máquina de escribir
    'condensada': ('Anton-Regular.ttf', 82, 1.24),             # condensada y muy gruesa, de cartel
}
TINTA_P = (48, 45, 40)        # la letra de las páginas, casi negra (la de ella, 63·60·49 al lado de la palabra)
PAPEL_P = (238, 233, 224)     # el papel; con la viñeta, las esquinas quedan en ~215·210·200, como el de ella
LUZ_P = (255, 252, 247)       # la luz suave detrás de la persona (la de ella llega a 255·250·247 detrás de la cabeza)
LUZ_RADIO = 0.50              # el tamaño de esa luz, en anchos del cuadro
LUZ_LAVA = 0.30               # cuánto aclara la letra justo detrás de la persona
CAJA_ALTO = 0.94              # el alto de la caja, en alturas de línea de su página
CAJA_LADO = 0.24              # el aire de la caja a los lados de la palabra, en altos de caja
CAJA_RADIO = 5                # las esquinas de la caja (a 1080)
HUECO_P = 16                  # el aire entre lo alto de la cabeza (la gorra, el pelo) y la caja (a 1080)
TECHO_P = 210                 # nada importante por encima de esto (a 1080): lo tapa Instagram
FOCO = (150, 950)             # el desenfoque empieza a esta distancia de la palabra y llega al máximo a esta (a 1080)
DESENFOQUE = 7.0              # el máximo (sigma, a 1080), abajo del todo
NIVELES = (0.0, 1.2, 2.6, 4.4, 7.0)    # los desenfoques que se calculan; cada fila mezcla los dos que le tocan
DESVANECE = 0.45              # cuánto se aclara la letra lejos de la palabra (0 = nada)
SOMBRA_P = 0.12               # la sombra de la persona en el papel


# ── Piezas que se hacen una vez ─────────────────────────────────────────────────────────────────────────────────────
def _papel(c):
    """El papel con su viñeta (y la tinta con la misma viñeta): se guardan como papel y (tinta − papel), para que cada
    cuadro sea solo papel + diferencia × letras. Un grano fijo y finísimo evita escalones en la viñeta."""
    W, H = c.W, c.H
    w4, h4 = max(8, W // 4), max(8, H // 4)
    y, x = np.mgrid[0:h4, 0:w4].astype(np.float32)
    x = (x + 0.5) / w4 - 0.5
    y = (y + 0.5) / h4 - 0.5
    r = np.sqrt((x / 0.62) ** 2 + (y / 0.60) ** 2)
    k = np.clip((r - 0.45) / 0.75, 0, 1)
    vin = 1.0 - 0.11 * k * k * (3 - 2 * k)
    vin = cv2.resize(vin.astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)[..., None]
    rng = np.random.default_rng(11)
    grano = (rng.random((H, W), np.float32) - rng.random((H, W), np.float32)) * np.float32(1.0 / 255.0)
    papel = np.array(PAPEL, np.float32) / 255.0 * vin + grano[..., None]
    tinta = np.array(TINTA, np.float32) / 255.0 * vin
    return np.clip(papel, 0, 1).astype(np.float32), (tinta - papel).astype(np.float32)


def _palabras(texto, resalta, n, rng):
    """Un chorro de palabras: el texto repetido, con la palabra resaltada metida cada 32–56 palabras."""
    base = [p for p in texto.split() if p] or ['texto']
    out, i, hasta = [], 0, int(rng.integers(10, 30))
    while len(out) < n:
        out.append(base[i % len(base)])
        i += 1
        hasta -= 1
        if hasta <= 0 and resalta:
            out.append(resalta)
            hasta = int(rng.integers(32, 56))
    return out


def _corrido(m, cx):
    """El tramo de la silueta (columnas) que contiene cx, o el más cercano. None si no hay silueta."""
    cols = np.where(m)[0]
    if not len(cols):
        return None
    cx = int(min(max(0, round(cx)), len(m) - 1))
    if not m[cx]:
        cx = int(cols[np.argmin(np.abs(cols - cx))])
    a = cx
    while a > 0 and m[a - 1]:
        a -= 1
    b = cx
    while b < len(m) - 1 and m[b + 1]:
        b += 1
    return a, b


def _sitio_caja(c, bw, alto_arriba, alto_abajo, D):
    """Dónde va la caja: (línea de base, x de su borde izquierdo al empezar, hacia dónde se mueve: +1 derecha, −1
    izquierda). Prueba al lado de la cabeza (los dos lados) y encima, y se queda con la más cercana a la frente que quepa
    entera en la zona segura durante todo el efecto sin pisar la silueta."""
    u = c.u
    cx, cy, an = c.cara
    izq, der = B.zona_segura(c)
    hueco = HUECO * u
    m = c.mascara > 0.35
    arriba_cabeza = cy - 1.35 * an
    x0, x1 = int(max(0, cx - 0.8 * an)), int(min(c.W, cx + 0.8 * an))
    filas = np.where(m[:, x0:x1].any(axis=1))[0] if x1 > x0 else []
    if len(filas) and cy - 2.0 * an < filas[0] < cy - 0.5 * an:
        arriba_cabeza = float(filas[0])
    frente = (cx, cy - 0.55 * an)
    techo, piso = TECHO * u, PISO * c.H
    mejor = None
    paso = max(4.0, 6 * u)
    for yb in np.arange(arriba_cabeza - 2.5 * TAM * u, cy + 0.2 * an, paso):
        top, bot = yb - alto_arriba, yb + alto_abajo
        if top < techo or bot > piso:
            continue
        r0, r1 = int(max(0, top - 18 * u)), int(min(c.H, bot + 18 * u))     # con aire por arriba y por abajo
        fila = m[r0:r1].any(axis=0)
        tramo = _corrido(fila, cx)
        opciones = []
        if tramo is None or not fila[max(0, int(cx - 0.6 * an)):int(cx + 0.6 * an)].any():
            opciones.append((cx - bw / 2 - D / 2, 1))                            # encima de la cabeza, centrada
            opciones.append((cx - bw / 2 + D / 2, -1))
        else:
            a, b = tramo
            opciones.append((b + hueco, 1))                                     # a la derecha, alejándose
            opciones.append((a - hueco - bw, -1))                               # a la izquierda, alejándose
        for xl, sentido in opciones:
            xa, xb = (xl, xl + bw + D) if sentido > 0 else (xl - D, xl + bw)    # todo lo que barre la caja
            if xa < izq or xb > der:
                continue
            if m[int(top):int(bot), int(max(0, xa - hueco / 2)):int(min(c.W, xb + hueco / 2))].mean() > 0.002:
                continue
            d = math.hypot(xl + bw / 2 - frente[0], (top + bot) / 2 - frente[1])
            if mejor is None or d < mejor[0]:
                mejor = (d, yb, xl, sentido)
    if mejor is None:                                                           # sin sitio: encima, centrada, como sea
        yb = max(techo + alto_arriba, arriba_cabeza - 0.5 * TAM * u - alto_abajo)
        return yb, min(max(izq, cx - bw / 2 - D / 2), der - bw - D), 1
    return mejor[1], mejor[2], mejor[3]


def _reducir(arr, S):
    """Una capa RGBA (numpy, alto × ancho × 4, uint8) hecha S veces más pequeña promediando cada S × S (con el color
    premultiplicado: los bordes no se oscurecen)."""
    a = arr.astype(np.float32)
    a[..., :3] *= a[..., 3:4] / 255.0
    h, w = a.shape[0] // S, a.shape[1] // S
    a = a[:h * S, :w * S].reshape(h, S, w, S, 4).mean(axis=(1, 3))
    a[..., :3] /= np.maximum(a[..., 3:4], 1e-3) / 255.0
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8), 'RGBA')


def _preparar(c):
    e = c.estado
    u = c.u
    W, H = c.W, c.H
    S = SUPER
    tam = TAM * u
    f4 = B.fuente('regular', tam * S)                          # todo el texto se pinta a S veces
    resalta = (c.op.get('resalta') or '').strip()
    texto = (c.op.get('texto') or OPCIONES['texto']).strip()
    rng = np.random.default_rng(5)

    # el paso: un número entero de cuartos de píxel por cuadro, siempre el mismo (a 1080 y 30 cuadros, 1 píxel justo)
    e['paso'] = max(1, int(round(DERIVA * u / max(1.0, c.fps) * S)))
    cuadros = int(math.ceil(c.dur * c.fps)) + 2
    D = int(math.ceil(cuadros * e['paso'] / S))               # lo que se mueve en todo el efecto (en píxeles)
    M = D + int(8 * u) + 2
    e['M'] = M
    LW = W + 2 * M

    # la caja: cuánto mide (se mide a S veces) y dónde va
    col = B.color(c.op.get('color') or OPCIONES['color'])
    tc4 = CAJA_LETRA * tam * S                                 # la palabra de la caja, algo más grande que la línea
    fm4 = B.fuente('medium', tc4)
    ww4 = f4.getlength(resalta) if resalta else 0.0
    wm4 = fm4.getlength(resalta) if resalta else 0.0
    bw = int(math.ceil((max(ww4, wm4) + 2 * 0.30 * tc4) / S))
    bh = int(round(1.16 * CAJA_LETRA * tam))
    # centrada en la tinta de la palabra de la línea
    _, ya, _, yz = f4.getbbox(resalta or 'x', anchor='ls')
    alto_arriba = int(round(-(ya + yz) / 2 / S + bh / 2))
    alto_abajo = bh - alto_arriba
    if resalta:
        yb, xl, sentido = _sitio_caja(c, bw, alto_arriba, alto_abajo, D)
    else:
        yb, xl, sentido = c.cara[1] - 1.5 * c.cara[2], 0, 1
    yb, xl = int(round(yb)), int(round(xl))
    e['sentido'], e['x_caja'] = sentido, xl

    # las líneas: la de la caja manda dónde caen todas. Se apuntan por sentido y se pintan después, una capa cada vez
    LH = INTERLINEA * tam
    k0 = -int(math.ceil((yb + tam) / LH))
    k1 = int(math.ceil((H - yb + tam) / LH))
    palabras = _palabras(texto, resalta, 8000, rng)
    esp4 = f4.getlength(' ')
    fin4 = (LW + 2 * tam) * S
    ordenes = {1: [], -1: []}                                  # (x, y, texto, ancla), a S veces
    p = int(rng.integers(0, 40))
    for k in range(k0, k1 + 1):
        base4 = (yb + k * LH) * S
        o = ordenes[sentido if (k % 2 == 0 or not ALTERNA) else -sentido]
        if k == 0 and resalta:
            # la línea de la caja: la palabra justo debajo de la caja (centrada en ella), con sitio a los lados para
            # que la caja no pise las vecinas, y texto a los dos lados
            X4 = (M + xl) * S + (bw * S - ww4) / 2
            hueco4 = max(esp4, (bw * S - ww4) / 2 + 0.5 * esp4)
            antes, j = [], p
            while f4.getlength(' '.join(antes)) < X4 + 2 * tam * S:
                j -= 1
                antes.insert(0, palabras[j % len(palabras)])
            o.append((X4 - hueco4, base4, ' '.join(antes), 'rs'))
            o.append((X4, base4, resalta, 'ls'))
            despues = []
            while X4 + ww4 + hueco4 + f4.getlength(' '.join(despues)) < fin4:
                despues.append(palabras[p % len(palabras)])
                p += 1
            o.append((X4 + ww4 + hueco4, base4, ' '.join(despues), 'ls'))
            continue
        x4 = -float(rng.uniform(0, 6 * tam)) * S
        linea = []
        while x4 + f4.getlength(' '.join(linea)) < fin4:
            linea.append(palabras[p % len(palabras)])
            p += 1
        o.append((x4, base4, ' '.join(linea), 'ls'))
    e['capas'] = {}
    for sentido_capa, lista in ordenes.items():
        grande = Image.new('L', (LW * S, H * S), 0)
        d = ImageDraw.Draw(grande)
        for x, y, t, ancla in lista:
            d.text((x, y), t, font=f4, fill=255, anchor=ancla)
        e['capas'][sentido_capa] = np.asarray(grande.reduce((1, S)), np.uint8)     # alto normal, ancho a S veces
        del grande, d

    # la caja con la palabra en blanco, en S versiones (una por cada cuarto de píxel), para que vaya con su línea sin
    # remuestrear: siempre nítida
    if resalta:
        grande = B.caja(bw * S, bh * S, 6 * u * S, col, nitidez=1)
        _, ya, _, yz = fm4.getbbox(resalta, anchor='ls')
        ImageDraw.Draw(grande).text(((bw * S - wm4) / 2, bh * S / 2 - (ya + yz) / 2), resalta, font=fm4,
                                    fill=(255, 255, 255, 255), anchor='ls')
        g = np.asarray(grande, np.uint8)
        fases = []
        for fase in range(S):
            lienzo = np.zeros((bh * S, (bw + 1) * S, 4), np.uint8)
            lienzo[:, fase:fase + bw * S] = g
            fases.append(B.con_sombra(_reducir(lienzo, S), 9 * u, 4 * u, 70))
        e['fases'] = fases
        e['y_caja'] = yb - alto_arriba + bh / 2                # su centro (la esquina queda en un píxel entero)
        e['bw'] = bw

    e['papel'], e['dif'] = _papel(c)
    e['listo'] = True


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _cuadro_n(c):
    return int(math.floor(c.t * c.fps + 0.5))


def _desplazado(c):
    """Cuánto se ha movido el muro en este cuadro, en cuartos de píxel (entero, y lo mismo en cada cuadro)."""
    e = c.estado
    return min(e['M'] * SUPER - 1, _cuadro_n(c) * e['paso'])


def _fondo(c, m):
    e = c.estado
    W, H, S = c.W, c.H, SUPER
    M4 = e['M'] * S
    q = _desplazado(c)
    der = e['capas'][1][:, M4 - q:M4 - q + W * S]           # las líneas que van a la derecha
    izq = e['capas'][-1][:, M4 + q:M4 + q + W * S]          # las que van a la izquierda
    letras = np.maximum(der, izq).reshape(H, W, S).sum(axis=2, dtype=np.uint16).astype(np.float32)
    letras *= np.float32(1.0 / (255.0 * S))
    fondo = e['dif'] * letras[..., None]
    fondo += e['papel']

    # la sombra de la persona en el papel (calculada a un cuarto: es muy suave)
    h4, w4 = max(8, H // 4), max(8, W // 4)
    m4 = cv2.resize(m, (w4, h4), interpolation=cv2.INTER_AREA)
    m4 = cv2.GaussianBlur(m4, (0, 0), 7.0 * c.u)
    m4 = np.roll(m4, max(1, int(round(3 * c.u))), axis=0)
    sombra = cv2.resize(m4, (W, H), interpolation=cv2.INTER_LINEAR)
    fondo *= (1.0 - np.float32(SOMBRA) * sombra)[..., None]

    # la caja, que va con su línea (en su versión de este cuarto de píxel)
    if 'fases' in e:
        k = B.tramo(c.t, CAJA_T0, CAJA_T1)
        if k > 0:
            esc = 0.62 + 0.38 * B.rebote(k, 1.7)
            alfa = B.tramo(c.t, CAJA_T0, CAJA_T0 + 0.08)
            pos4 = e['x_caja'] * S + e['sentido'] * q
            izq_caja, fase = pos4 // S, pos4 % S
            capa = e['fases'][fase]
            margen = (capa.width - (e['bw'] + 1)) // 2
            cx = izq_caja - margen + capa.width / 2
            lienzo = B.Cuadro(img=fondo, mascara=m, cara=c.cara, t=c.t, dur=c.dur, fps=c.fps)
            B.poner(lienzo, capa, cx, e['y_caja'], escala=esc, alfa=alfa)
    return fondo


def _curva(x):
    """El avance del barrido: arranca y frena suave (así el primer cuadro no cambia de golpe), con el tramo de en medio
    a ritmo constante."""
    return 0.5 * x + 0.5 * B.suave(x)


# ── modo=paginas: páginas quietas que cambian de letra ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=64)
def _letra(archivo, tam):
    ruta = os.path.join(B.FUENTES, archivo)
    if not os.path.exists(ruta):                              # si falta una letra nueva, la página sale en Poppins
        ruta = os.path.join(B.FUENTES, 'Poppins-Bold.ttf')
    return ImageFont.truetype(ruta, max(4, int(round(tam))))


def _vocabulario(texto, resalta):
    """Las palabras del texto, en minúscula y sin signos (como un muro de palabras sueltas), sin la palabra resaltada:
    esa sale una sola vez por página, en la caja."""
    fuera = resalta.lower()
    out = [w for w in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", texto.lower()) if w != fuera]
    return out or ['texto', 'muro', 'palabras']


def _medidas(c, tipo, escala):
    """Cómo es la página de una letra: (fuente, tamaño, alto de línea, ancho de la palabra, su tinta arriba y abajo
    respecto de la línea de base, ancho y alto de la caja). Todo a la escala del cuadro."""
    archivo, tam, inter = TIPOS[tipo]
    tam = tam * c.u * escala
    f = _letra(archivo, tam)
    alto = inter * tam
    resalta = (c.op.get('resalta') or '').strip()
    w = f.getlength(resalta) if resalta else 0.0
    _, ya, _, yz = f.getbbox(resalta or 'x', anchor='ls')
    bh = int(round(CAJA_ALTO * alto))
    bw = int(math.ceil(w + 2 * CAJA_LADO * bh))
    return f, tam, alto, w, ya, yz, bw, bh


def _sitio_paginas(c, bw, bh):
    """El centro de la caja: encima de la cabeza y centrada con ella (como la de la referencia), dentro de la zona segura. Si
    encima no cabe por debajo de lo que tapa Instagram, al lado de la cabeza (la búsqueda de `deriva`, sin moverse)."""
    u = c.u
    cx, cy, an = c.cara
    izq, der = B.zona_segura(c)
    m = c.mascara > 0.35
    x0, x1 = int(max(0, cx - 0.8 * an)), int(min(c.W, cx + 0.8 * an))
    filas = np.where(m[:, x0:x1].any(axis=1))[0] if x1 > x0 else []
    arriba = float(filas[0]) if len(filas) and filas[0] < cy else cy - 1.35 * an
    by = arriba - HUECO_P * u - bh / 2
    bx = min(max(cx, izq + bw / 2), der - bw / 2)
    if by - bh / 2 >= TECHO_P * u:
        return bx, by
    yb, xl, _ = _sitio_caja(c, bw, bh // 2, bh - bh // 2, 0)
    return xl + bw / 2, yb - bh // 2 + bh / 2


def _papel_paginas(c):
    """El papel (con su viñeta y la luz de detrás de la persona) y (tinta − papel), como en `_papel`; y lo que la luz
    aclara la letra en cada píxel."""
    W, H = c.W, c.H
    cx, cy, an = c.cara
    w4, h4 = max(8, W // 4), max(8, H // 4)
    y, x = np.mgrid[0:h4, 0:w4].astype(np.float32)
    xn, yn = (x + 0.5) / w4 - 0.5, (y + 0.5) / h4 - 0.5
    r = np.sqrt((xn / 0.62) ** 2 + (yn / 0.60) ** 2)
    k = np.clip((r - 0.40) / 0.75, 0, 1)
    vin = 1.0 - 0.11 * k * k * (3 - 2 * k)
    lx, ly = cx / W * w4, (cy + 0.6 * an) / H * h4          # la luz, algo por debajo de la cara: detrás de la persona
    d = np.sqrt((x + 0.5 - lx) ** 2 + ((y + 0.5 - ly) * 0.85) ** 2) / (LUZ_RADIO * w4)
    luz = np.exp(-d * d * 2.2)
    vin = cv2.resize(vin.astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)[..., None]
    luz = cv2.resize(luz.astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    rng = np.random.default_rng(11)
    grano = (rng.random((H, W), np.float32) - rng.random((H, W), np.float32)) * np.float32(1.0 / 255.0)
    base = np.array(PAPEL_P, np.float32) / 255.0 * vin
    claro = np.array(LUZ_P, np.float32) / 255.0
    papel = base + (claro - base) * (0.85 * luz)[..., None] + grano[..., None]
    tinta = np.array(TINTA_P, np.float32) / 255.0 * vin
    lava = (1.0 - LUZ_LAVA * luz).astype(np.float32)
    return np.clip(papel, 0, 1).astype(np.float32), (tinta - papel).astype(np.float32), lava


def _preparar_paginas(c):
    e = c.estado
    u = c.u
    resalta = (c.op.get('resalta') or '').strip()
    tipos = [t.strip().lower() for t in str(c.op.get('tipos') or OPCIONES['tipos']).split(',')]
    tipos = [t for t in tipos if t in TIPOS] or OPCIONES['tipos'].split(',')
    e['tipos'] = tipos
    try:
        cambio = float(c.op.get('cambio') or OPCIONES['cambio'])
    except ValueError:
        cambio = float(OPCIONES['cambio'])
    e['cada'] = max(1, int(round(cambio * c.fps)))             # cuadros por página, siempre los mismos
    e['vocab'] = _vocabulario(c.op.get('texto') or OPCIONES['texto'], resalta)

    # la caja más grande de todas las letras manda dónde va (así cabe en todas); si no cabe en la zona segura, todo
    # se hace más pequeño
    izq, der = B.zona_segura(c)
    escala = 1.0
    for _ in range(3):
        med = [_medidas(c, t, escala) for t in set(tipos)]
        bw = max(m[6] for m in med)
        if bw <= (der - izq) * 0.9:
            break
        escala *= (der - izq) * 0.9 / bw
    e['escala'] = escala
    bh = max(m[7] for m in med)
    e['bx'], e['by'] = _sitio_paginas(c, bw, bh)
    e['color'] = B.color(c.op.get('color') or OPCIONES['color'])
    e['papel'], e['dif'], e['lava'] = _papel_paginas(c)

    # el desenfoque de cada fila (crece al alejarse de la palabra) y lo que se aclara
    filas = np.abs(np.arange(c.H, dtype=np.float32) - np.float32(e['by']))
    k = np.clip((filas - FOCO[0] * u) / ((FOCO[1] - FOCO[0]) * u), 0, 1)
    k = k * k * (3 - 2 * k)
    e['sigma'] = k * DESENFOQUE
    e['desvanece'] = (1.0 - DESVANECE * k).astype(np.float32)
    e['paginas'] = {}
    e['listo'] = True


def _pagina(c, j):
    """La página j: la capa de letras (alto × ancho, uint8, ya desenfocada y aclarada) y la caja con la palabra (RGBA,
    0–1) con su esquina. Se hace la primera vez que se necesita y se guarda (solo la de ahora y la anterior)."""
    e = c.estado
    if j in e['paginas']:
        return e['paginas'][j]
    for viejo in [k for k in e['paginas'] if k < j - 1]:
        del e['paginas'][viejo]
    W, H, u = c.W, c.H, c.u
    tipo = e['tipos'][j % len(e['tipos'])]
    f, tam, alto, w, ya, yz, bw, bh = _medidas(c, tipo, e['escala'])
    resalta = (c.op.get('resalta') or '').strip()
    bx, by = e['bx'], e['by']
    rng = np.random.default_rng(1009 + 31 * j)
    vocab = e['vocab']
    ultima = ['']

    def palabra():
        w_ = vocab[int(rng.integers(len(vocab)))]
        if w_ == ultima[0] and len(vocab) > 1:
            w_ = vocab[int(rng.integers(len(vocab)))]
        ultima[0] = w_
        return w_

    capa = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(capa)
    base0 = by - (ya + yz) / 2                                # la palabra, centrada de alto en su caja
    hueco = 0.40 * tam                                        # el aire entre la caja y las palabras de su línea
    k0 = -int(math.ceil((base0 + tam) / alto))
    k1 = int(math.ceil((H - base0 + tam) / alto))
    for k in range(k0, k1 + 1):
        yb = base0 + k * alto
        if k == 0 and resalta:
            fin = bx - bw / 2 - hueco
            antes = []
            while f.getlength(' '.join(antes)) < fin + tam:
                antes.insert(0, palabra())
            d.text((fin, yb), ' '.join(antes), font=f, fill=255, anchor='rs')
            x0 = bx + bw / 2 + hueco
            despues = []
            while x0 + f.getlength(' '.join(despues)) < W + tam:
                despues.append(palabra())
            d.text((x0, yb), ' '.join(despues), font=f, fill=255, anchor='ls')
            continue
        x0 = -float(rng.uniform(0.3, 5.0)) * tam               # cada línea empieza cortada por otro sitio
        linea = []
        while x0 + f.getlength(' '.join(linea)) < W + tam:
            linea.append(palabra())
        d.text((x0, yb), ' '.join(linea), font=f, fill=255, anchor='ls')

    # el desenfoque por filas: cada fila mezcla los dos niveles que le tocan (nítida junto a la palabra)
    a = np.asarray(capa, np.float32) * np.float32(1.0 / 255.0)
    sig = e['sigma']
    niveles = np.asarray(NIVELES, np.float32)
    idx = np.interp(sig, niveles, np.arange(len(niveles), dtype=np.float32))
    out = np.zeros_like(a)
    for n, s in enumerate(niveles):
        peso = np.clip(1.0 - np.abs(idx - n), 0, 1).astype(np.float32)
        filas = np.where(peso > 0)[0]
        if not len(filas):
            continue
        r0, r1 = int(filas[0]), int(filas[-1]) + 1
        pad = int(math.ceil(3 * s * u)) + 1
        q0, q1 = max(0, r0 - pad), min(H, r1 + pad)
        trozo = a[q0:q1] if s <= 0 else cv2.GaussianBlur(a[q0:q1], (0, 0), float(s * u))
        out[r0:r1] += trozo[r0 - q0:r1 - q0] * peso[r0:r1, None]
    out *= e['desvanece'][:, None]
    out *= e['lava']
    letras = (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)

    # la caja con la palabra en blanco, en la letra de la página (quieta: en un píxel entero)
    caja = None
    if resalta:
        img = B.caja(bw, bh, CAJA_RADIO * u, e['color'], nitidez=3)
        xl, yt = int(round(bx - bw / 2)), int(round(by - bh / 2))
        ImageDraw.Draw(img).text(((bw - w) / 2, (by - yt) - (ya + yz) / 2), resalta, font=f,
                                 fill=(255, 255, 255, 255), anchor='ls')
        arr = np.asarray(img, np.float32) * np.float32(1.0 / 255.0)
        caja = (arr[..., :3] * arr[..., 3:4], arr[..., 3:4], xl, yt)
    e['paginas'][j] = (letras, caja)
    return e['paginas'][j]


def _fondo_paginas(c, m, j):
    e = c.estado
    W, H = c.W, c.H
    letras, caja = _pagina(c, j)
    fondo = e['dif'] * (letras.astype(np.float32) * np.float32(1.0 / 255.0))[..., None]
    fondo += e['papel']
    # la sombra de la persona en el papel (calculada a un cuarto: es muy suave)
    h4, w4 = max(8, H // 4), max(8, W // 4)
    m4 = cv2.resize(m, (w4, h4), interpolation=cv2.INTER_AREA)
    m4 = cv2.GaussianBlur(m4, (0, 0), 7.0 * c.u)
    m4 = np.roll(m4, max(1, int(round(3 * c.u))), axis=0)
    sombra = cv2.resize(m4, (W, H), interpolation=cv2.INTER_LINEAR)
    fondo *= (1.0 - np.float32(SOMBRA_P) * sombra)[..., None]
    if caja is not None:                                      # la caja va en el muro: la persona la tapa si sube
        rgb, al, xl, yt = caja
        h, w = al.shape[:2]
        X0, Y0, X1, Y1 = max(0, xl), max(0, yt), min(W, xl + w), min(H, yt + h)
        if X1 > X0 and Y1 > Y0:
            zona = fondo[Y0:Y1, X0:X1]
            sl = (slice(Y0 - yt, Y1 - yt), slice(X0 - xl, X1 - xl))
            zona *= (1.0 - al[sl])
            zona += rgb[sl]
    return fondo


def _dibujar_paginas(c):
    e = c.estado
    if not e.get('listo'):
        _preparar_paginas(c)
    try:
        entra = max(0.0, float(c.op.get('entra') if c.op.get('entra') not in (None, '') else OPCIONES['entra']))
    except ValueError:
        entra = float(OPCIONES['entra'])
    vis = (B.suave(B.tramo(c.t, 0, entra)) if entra > 0 else 1.0) * B.suave(B.tramo(c.queda, 0, SALE))
    if vis <= 0:
        return
    m = np.clip(c.mascara, 0, 1).astype(np.float32, copy=False)
    persona, _ = B.color_persona(c.img, m, c.u)
    j = _cuadro_n(c) // e['cada']                              # la página de este cuadro
    nuevo = cv2.blendLinear(_fondo_paginas(c, m, j), persona, 1.0 - m, m)
    if vis >= 1:
        c.img[...] = nuevo
        return
    nuevo -= c.img
    nuevo *= np.float32(vis)
    c.img += nuevo


def dibujar(c):
    if str(c.op.get('modo') or 'paginas').strip().lower() not in ('deriva', 'periodico', 'periódico'):
        _dibujar_paginas(c)
        return
    e = c.estado
    if not e.get('listo'):
        _preparar(c)
    x = B.tramo(c.t, 0, ENTRA)                         # el barrido de la entrada, de arriba abajo
    vis = B.suave(B.tramo(c.queda, 0, SALE))           # el fundido de la salida
    if x <= 0 or vis <= 0:
        return
    m = np.clip(c.mascara, 0, 1).astype(np.float32, copy=False)    # el recorte tal cual: sin encogerlo
    persona, _ = B.color_persona(c.img, m, c.u)        # el color de la persona también en el filo: sin halo
    fondo = _fondo(c, m)
    nuevo = cv2.blendLinear(fondo, persona, 1.0 - m, m)
    if x >= 1 and vis >= 1:
        c.img[...] = nuevo
        return
    if x < 1:                                          # entra de arriba abajo con un filo suave, a ritmo constante
        filo = FILO_BARRIDO * c.u
        borde = _curva(x) * (c.H + filo)
        k = np.clip((borde - np.arange(c.H, dtype=np.float32)) / np.float32(filo), 0, 1)
        k = (k * k * (3 - 2 * k) * np.float32(vis))[:, None, None]
    else:
        k = np.float32(vis)
    nuevo -= c.img
    nuevo *= k
    c.img += nuevo
