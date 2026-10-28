"""Muro de texto: el fondo de detrás de la persona se cambia por una página de periódico (un papel claro, blanco roto, con
una viñeta muy suave) llena de líneas de texto gris que ocupan todo el cuadro y se deslizan muy despacio, una línea hacia
un lado y la siguiente hacia el otro. Una palabra (`resalta`) sale varias veces entre el texto, y la que queda más cerca
de la cabeza entra dentro de una caja de color, con la letra blanca y un pequeño golpe de escala. La persona queda
delante, con sus colores y el borde limpio (como en `fondo`).

Lo que se ve:
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
- Una sombra muy suave de la persona sobre el papel, para que no parezca pegada.
Todo se coloca según dónde está la persona al empezar y ya no la persigue: es un decorado.

    .venv/bin/python efectos.py muro tu_video.mp4 --desde 1 --hasta 4 --op resalta=Claude --op color=#E5484D
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

import base as B

NOMBRE = 'muro'
DESCRIPCION = 'Detrás de ti, un muro de texto como una página de periódico, con una palabra resaltada'
OPCIONES = {
    'resalta': 'Claude',            # la palabra que sale varias veces y, la de al lado de la cabeza, dentro de la caja
    'color': '#E5484D',             # el color de la caja (la letra va en blanco)
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
    col = B.color(c.op.get('color') or '#E5484D')
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


def dibujar(c):
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
