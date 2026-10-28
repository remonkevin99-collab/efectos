"""interruptores: encima de la cabeza, una tarjeta de ajustes (como la del teléfono) con interruptores que se encienden
uno a uno. La parte de abajo de la tarjeta va DETRÁS de la cabeza, y la cámara empieza lejos y se acerca.

Cómo va (medido cuadro a cuadro en la referencia, 28 oct 2026: *"sale primero la cámara alejada y después se le hace
un zoom"*):
  - 0–0,37 s: la cámara empieza en el plano tal cual y se acerca deprisa, frenando al final (`zoom`; ella, un 12 % en 11
    cuadros), apoyada arriba: la persona crece y baja, y deja sitio encima de la cabeza. A la vez entra la tarjeta, pegada
    a la cabeza (baja con ella): un fundido de 0,2 s y un saltito (de 0,88 a 1,04 y vuelve a 1).
  - Después, la cámara se sigue acercando despacio hasta el final (`zoom_lento`), hacia la cara: la cabeza sube y se
    mete un poco más en la tarjeta, que sube menos (la sigue a medias, también si la persona se mueve). Es lo que se ve
    en el de ella cuando se inclina hacia la cámara: lo que se mete pasa del 5 % al 9 % del alto de la tarjeta.
  - Los interruptores se encienden uno detrás de otro (`primero`, `cada`; ella, cada 0,33 s): la bola se desliza a la
    derecha y la pista se pone verde en 0,2 s.
  - Al final, la tarjeta se va con un fundido y la cámara vuelve al plano de verdad a la vez (el último cuadro del efecto
    ya es el plano tal cual: nada salta al acabar).

La tarjeta es blanca (con un toque de la pared de detrás), con las esquinas muy redondas y una sombra suave. Cada fila
lleva su texto a la izquierda y un interruptor a la derecha: una pista gris con su bola blanca.

Dónde va: centrada con la cara y con la parte de abajo detrás de la cabeza (la cabeza va delante y la cara nunca se tapa).
Siempre dentro de la zona segura: entre x 60 y 1020 y nunca más arriba de y 210, en ningún momento del acercamiento.
Su tamaño es la referencia (filas de 132 px a 1080, el 72 % del ancho o lo que pidan los textos) si cabe encima de la
cabeza; si no, con `zoom=auto` la cámara se acerca algo más (hasta 1,25) y, si ni así, la tarjeta se hace más baja: las
filas se aprietan antes que la letra y los interruptores, para que siga pareciendo grande. Con poco aire encima de la
cabeza (la toma 1 de la gorra empieza en y 440), sale un 30 % más baja que la de ella.

    .venv/bin/python efectos.py interruptores tu_video.mp4 --desde 2 --hasta 5 --fotos 2.1,2.4,3.2,4.4
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import base as B

try:                       # OpenCV desenfoca y mueve la cámara mucho más rápido; sin él, la cámara se queda quieta
    import cv2
except ImportError:
    cv2 = None

NOMBRE = 'interruptores'
DESCRIPCION = 'Encima de tu cabeza, una tarjeta de ajustes con interruptores que se encienden uno a uno'
OPCIONES = {
    'lineas': 'Un clip|Escribo /efectos|Cero apps de edición',   # una fila por cada texto, separados por «|»
    'color': '#34C759',          # el color del interruptor encendido
    'primero': '0,5',            # cuándo se enciende el primero (segundos desde que empieza el efecto)
    'cada': '0,33',              # los segundos entre un interruptor y el siguiente (si no caben, más seguidos)
    'detras': 'si',              # «si»: lo de abajo, detrás de la cabeza; «no»: encima, delante; «auto»: delante si cabe
    'zoom': 'auto',              # lo que se acerca la cámara al empezar, en 0,37 s (1 = quieta; «auto»: de 1,12 a 1,25)
    'zoom_lento': '1,08',        # lo que se sigue acercando después, despacio, hasta el final (1 = nada; hasta 1,2)
}
DURACION = 3.0

# el tiempo (segundos desde que empieza el efecto)
CAMARA = 0.37        # la cámara se acerca deprisa en esto (ella: de 0,894 a 1 en 11 cuadros)…
CURVA_CAMARA = 1.6   # …frenando así: 1 − (1 − x)^1,6 (la curva de ella, medida cuadro a cuadro)
LENTO_DESDE = 0.26   # el acercamiento lento empieza antes de que acabe el rápido (la cámara no se para entre los dos)
APARECE = 0.07       # cuándo empieza a verse la tarjeta (ella: en el tercer cuadro de la cámara)
FUNDIDO = 0.20       # su fundido de entrada
SALTO = (0.88, 1.04, 0.17, 0.36)   # el saltito: de 0,88 a 1,04 en 0,17 s, y vuelve a 1 a los 0,36 s
SALIDA = 0.30        # el fundido del final (y la vuelta de la cámara al plano de verdad)
CAMBIO = 0.20        # lo que tarda un interruptor en encenderse (ella: la bola llega en ~5 cuadros)
PRIMERO = 0.5        # cuándo se enciende el primero, si no se dice (ella: 0,5 s después de empezar la cámara)
QUIETO = 0.55        # lo que se ven todos encendidos, como mínimo, antes de irse

# dónde va (las medidas, a 1080 de ancho)
METER = 0.055        # lo que se mete la tarjeta detrás de la cabeza, en partes de su alto (ella: 5 %; 9 % al acabar)
SIGUE = 0.7          # en el acercamiento lento, y cuando la persona se mueve arriba o abajo, la tarjeta sigue esto de
                     # lo que se mueve la cabeza (ella: ~0,6): la cabeza se mete un poco más, sin tapar nunca el texto
VISIBLE = 0.5        # el tamaño se decide con la tarjeta ya medio visible; antes, si hiciera falta, baja un poco
HUECO_CABEZA = 30    # con detras=no: el aire entre la tarjeta y la cabeza
TECHO = 212          # lo más arriba que puede estar la tarjeta (la zona segura empieza en 210)
ZOOM_ELLA = 1.12     # el acercamiento rápido de ella; con zoom=auto, nunca menos…
ZOOM_MAX = 1.25      # …ni más que esto
K_OBJETIVO = 0.67    # con zoom=auto, la cámara se acerca hasta que la tarjeta quepa a este alto (1 = el de ella). Más no
                     # compensa: con la toma 1 de la persona, de 0,67 a 0,74 pedía pasar de 1,15 a 1,25 y la imagen se ablanda
K_MIN = 0.55         # la tarjeta, como mucho, se achica a esto; si ni así cabe, baja y se mete más detrás de la cabeza

# la tarjeta a su tamaño (el de ella, a 1080: 774 × 402, filas de 132, interruptores de 140 × 84)
ANCHO = 0.717        # en partes del ancho del vídeo (si los textos piden más, más ancha, sin salir de la zona segura)
FILA = 132
PV = 4               # el aire de arriba y de abajo (las filas llenan la tarjeta, como en los ajustes del teléfono)
ABAJO = 12           # y un poco más abajo: el sitio donde se mete la cabeza, para que no llegue al texto
TAM = 54             # la letra (Poppins es más ancha que la del teléfono: a 54 ocupa lo que la de ella a 64)
PX = 52              # el aire a los lados
HUECO = 44           # entre el texto más largo y el interruptor
TW, TH = 140, 84     # el interruptor
RADIO = 44
APRIETA = 1.3        # la fila, como poco, 1,3 veces el alto del interruptor (en el teléfono, 1,4)

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
    dy = 2.2 * L['u'] * L['k'] * SS
    ImageDraw.Draw(sombra).ellipse([bx, by + dy, bx + d, by + d + dy], fill=(0, 0, 0, 70))
    capa.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(3.2 * L['u'] * L['k'] * SS)))
    ImageDraw.Draw(capa).ellipse([bx, by, bx + d, by + d], fill=(255, 255, 255, 255))
    capa = capa.resize((int(round(tw + 2 * pad)), int(round(th + 2 * pad))), Image.LANCZOS)
    arr = np.asarray(capa, np.float32) / 255.0
    hecho = (arr[..., :3] * arr[..., 3:4], arr[..., 3:4])        # premultiplicado, para pegarlo rápido
    L['interruptores'][q] = hecho
    return hecho


def _cabeza_arriba(c):
    """Lo más alto de la cabeza (la gorra o el pelo cuentan), de la silueta: desde la cara hacia arriba, mientras siga
    habiendo persona encima de ella (una mano levantada que no toca la cabeza no cuenta). La tarjeta se mete detrás de la
    cabeza contando desde aquí, así que tiene que ser lo alto de verdad: la cara sola se queda corta con una gorra."""
    cx, cy, ac = (float(v) for v in c.cara)
    por_cara = cy - 1.25 * ac
    x0, x1 = int(max(0, cx - 0.7 * ac)), int(min(c.W, cx + 0.7 * ac))
    abajo = int(min(c.H, max(0, cy)))
    if x1 - x0 < 4 or abajo < 2:
        return por_cara
    hay = (c.mascara[:abajo, x0:x1] > 0.5).sum(1) >= max(4.0, 0.08 * ac)
    if not hay[-1]:
        return por_cara
    vacias = np.where(~hay)[0]
    return float(vacias[-1] + 1) if len(vacias) else 0.0


def _salto(t):
    """El tamaño de la tarjeta al entrar: de 0,88 a 1,04 y vuelve a 1 (el saltito de ella)."""
    a0, a1, t1, t2 = SALTO
    if t <= APARECE:
        return a0
    if t < APARECE + t1:
        return a0 + (a1 - a0) * B.suave(B.tramo(t, APARECE, APARECE + t1))
    return a1 + (1.0 - a1) * B.suave(B.tramo(t, APARECE + t1, APARECE + t2))


def _alfa(t, dur):
    return B.suave(B.tramo(t, APARECE, APARECE + FUNDIDO)) * B.suave(B.tramo(dur - t, 0, SALIDA))


def _camino(z, lento, cara, dur):
    """La cámara en cada momento: (S, ax, ay, sA), con el punto (x, y) del vídeo yendo a (ax + S·x, ay + S·y).
    Primero se acerca `z` apoyada arriba y con la cara en su sitio (sA); después, `lento` hacia la cara; al final vuelve
    al plano de verdad. Nunca deja ver fuera del vídeo: S ≥ 1, ax y ay ≤ 0 y lo de abajo y la derecha, dentro."""
    cx, cy, ac = cara
    Qy = z * cy                                                        # adonde va el acercamiento lento (en la pantalla)
    if dur - SALIDA < LENTO_DESDE + 0.1:                               # un efecto muy corto: solo el acercamiento rápido
        lento = 1.0

    def en(t):
        x = B.tramo(t, 0, CAMARA)
        sA = 1.0 + (z - 1.0) * (1.0 - (1.0 - x) ** CURVA_CAMARA)
        x = B.tramo(t, LENTO_DESDE, dur - SALIDA)
        r = 1.0 + (lento - 1.0) * x * x * (2.0 - x)                     # arranca suave y llega sin frenar
        S = r * sA
        ax, ay = cx * (1.0 - S), Qy * (1.0 - r)
        q = B.suave(B.tramo(t, dur - SALIDA, dur))                    # la vuelta al plano de verdad
        if q > 0:
            S, ax, ay = S + (1.0 - S) * q, ax * (1.0 - q), ay * (1.0 - q)
        return S, ax, ay, sA
    return en


def _ancla(cam, yh, t, dur, sigue):
    """Lo alto de la cabeza que sigue la tarjeta: entera en el acercamiento rápido, `sigue` en el lento y entera otra vez
    mientras la cámara vuelve al final (la tarjeta ya se está yendo con el fundido)."""
    tf = min(t, dur - SALIDA)
    S, ax, ay, sA = cam(tf)
    rapido = sA * yh                                                   # solo con el acercamiento rápido
    out = rapido + sigue * ((ay + S * yh) - rapido)
    if t > tf:
        S2, _, ay2, _ = cam(t)
        out += (ay2 + S2 * yh) - (ay + S * yh)
    return out


def _alto_que_cabe(cam, yh, dur, sigue, meter, aire, techo):
    """El alto más grande que puede tener la tarjeta sin pasar del techo mientras se ve (en los primeros cuadros del
    fundido, cuando aún casi no se ve, `dibujar` la baja lo que haga falta: nunca pasa del techo)."""
    mejor = float('inf')
    for t in np.arange(0.0, dur, 1.0 / 60.0):
        if _alfa(t, dur) < VISIBLE:
            continue
        sc = _salto(t)
        div = 0.5 + 0.5 * sc - meter
        if div > 1e-6:
            mejor = min(mejor, (_ancla(cam, yh, t, dur, sigue) - aire - techo) / div)
    return mejor


def _preparar(c):
    u, op = c.u, c.op
    lineas = _lineas(op)
    n = len(lineas)
    cara = tuple(float(v) for v in c.cara)
    cx = cara[0]
    yh = _cabeza_arriba(c)
    izq, der = B.zona_segura(c)
    techo = TECHO * u
    dur = c.dur
    h_ideal = (2 * PV + ABAJO + n * FILA) * u

    lento = 1.0 if cv2 is None else min(1.2, max(1.0, _numero(op.get('zoom_lento'), 1.08)))
    z_op = str(op.get('zoom') or 'auto').strip().lower()
    z_fijo = None if z_op == 'auto' else min(ZOOM_MAX, max(1.0, _numero(z_op, ZOOM_ELLA)))
    if cv2 is None:
        z_fijo = 1.0

    def medir(detras):
        """(zoom, cámara, k) para ese modo: con zoom=auto, la cámara se acerca hasta que la tarjeta quepa grande."""
        meter, aire, sigue = (METER, 0.0, SIGUE) if detras else (0.0, HUECO_CABEZA * u, 1.0)
        zs = [z_fijo] if z_fijo is not None else [round(float(v), 3) for v in np.arange(ZOOM_ELLA, ZOOM_MAX + 1e-6, 0.01)]
        for z in zs:
            cam = _camino(z, lento, cara, dur)
            k = _alto_que_cabe(cam, yh, dur, sigue, meter, aire, techo) / h_ideal
            if k >= K_OBJETIVO:
                break
        return z, cam, min(1.0, k), meter, aire, sigue

    modo = str(op.get('detras') or 'si').strip().lower()
    if modo in ('no', '0', 'false'):
        detras = False
    elif modo == 'auto':                                               # delante si cabe encima (como antes)
        detras = medir(False)[2] < K_OBJETIVO
    else:
        detras = True
    z, cam, k, meter, aire, sigue = medir(detras)
    k = float(max(K_MIN, k))                                          # un float de Python (Pillow no quiere los de numpy)

    # las medidas, a su tamaño. Si la tarjeta tiene que ser más baja que la de ella, las filas se aprietan más de lo que
    # se achican la letra y los interruptores (kf = √k), como en los ajustes del teléfono: así sigue pareciendo grande
    pv, abajo = PV * u * k, ABAJO * u * k
    fila = (h_ideal * k - 2 * pv - abajo) / n
    kf = min(k ** 0.5, fila / (APRIETA * TH * u))
    tam, px, tw, th, hueco = (v * u * kf for v in (TAM, PX, TW, TH, HUECO))
    f = B.fuente('medium', tam)
    largo = max(f.getlength(s) for s in lineas)
    sitio = der - izq
    w = max(ANCHO * c.W * kf, 2 * px + largo + hueco + tw)
    if w > sitio:                                                      # textos muy largos: la letra baja hasta caber
        tam *= (sitio - 2 * px - hueco - tw) / largo
        f = B.fuente('medium', tam)
        w = sitio
    h = 2 * pv + abajo + n * fila
    w, h = int(round(w)), int(round(h))
    x = min(max(cx - w / 2, izq), der - w)
    L = {'u': u, 'k': kf, 'n': n, 'acento': B.color(op.get('color') or '#34C759'), 'interruptores': {},
         'w': w, 'h': h, 'x': int(round(x)), 'TW': tw, 'TH': th, 'TPAD': 8 * u * kf, 'r': min(RADIO * u * kf, h / 2),
         'cam': cam, 'z': z, 'lento': lento, 'yh': yh, 'meter': meter * h, 'aire': aire, 'sigue': sigue,
         'techo': techo, 'detras': detras, 'cy0': cara[1]}

    # lo que no cambia: los textos y los separadores, en una capa (premultiplicada) del tamaño de la tarjeta
    fija = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(fija)
    alto_mayus = -f.getbbox('H', anchor='ls')[1]
    grosor = max(1.0, 1.6 * u)
    L['filas'] = []
    for i, s in enumerate(lineas):
        yc = pv + fila * (i + 0.5)
        d.text((px, round(yc + alto_mayus / 2)), s, font=f, fill=TINTA, anchor='ls')
        if i < n - 1:                                                # el separador: desde el texto hasta el borde
            ys = pv + fila * (i + 1)
            sep = B.caja(w - px, grosor * 3, 0, LINEA)
            sep = sep.resize((sep.width, max(1, int(round(grosor)))), Image.LANCZOS)
            fija.alpha_composite(sep, (int(round(px)), int(round(ys - grosor / 2))))
        L['filas'].append(yc)
    arr = np.asarray(fija, np.float32) / 255.0
    L['fija'] = (arr[..., :3] * arr[..., 3:4], arr[..., 3:4])
    L['forma'] = np.asarray(B.caja(w, h, L['r'], (255, 255, 255, 255)).split()[3], np.float32) / 255.0
    L['int_x'] = int(round(w - px - tw - L['TPAD']))                  # la esquina de cada interruptor (con su aire)
    L['sombra'] = _sombra(w, h, L['r'], 30 * u * kf, 62)

    # cuándo se enciende cada uno: el primero en «primero» y después cada «cada»; si no caben en el tiempo, más seguidos
    cada = max(0.15, _numero(op.get('cada'), 0.33))
    primero = max(0.0, _numero(op.get('primero'), PRIMERO))
    ultimo = dur - SALIDA - QUIETO - CAMBIO
    primero = min(primero, max(0.0, ultimo))
    if n > 1 and primero + (n - 1) * cada > ultimo:
        cada = max(0.15, (ultimo - primero) / (n - 1))
    L['inicios'] = [primero + i * cada for i in range(n)]
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
    """Lo que hay detrás de la tarjeta, desenfocado y aclarado (blanco casi opaco)."""
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
    return fondo * 0.04 + 0.96 * 0.99                                 # blanco (la de ella: 250) y un toque de detrás


def _mover_camara(c, S, ax, ay):
    """La cámara: el cuadro entero (y el recorte de la persona, para que la tarjeta siga detrás de ella) acercado con
    decimales (sin saltitos)."""
    if cv2 is None or (S <= 1.0 + 1e-5 and abs(ax) < 1e-3 and abs(ay) < 1e-3):
        return
    M = np.float32([[S, 0, ax], [0, S, ay]])
    np.copyto(c.img, cv2.warpAffine(c.img, M, (c.W, c.H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE))
    m = cv2.warpAffine(c.mascara, M, (c.W, c.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    c.mascara = np.clip(m, 0.0, 1.0)                                  # una copia: el recorte del motor no se toca


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def dibujar(c):
    L = c.estado.get('interruptores')
    if L is None:
        L = c.estado['interruptores'] = _preparar(c)
    u, t = c.u, c.t

    # 1. la cámara
    S, ax, ay, _ = L['cam'](t)
    _mover_camara(c, S, ax, ay)

    # 2. la tarjeta: pegada a lo alto de la cabeza, con su saltito al entrar
    alfa = _alfa(t, c.dur)
    if alfa <= 0.003:
        return
    sc = _salto(t)
    w, h = L['w'], L['h']
    # pegada a lo alto de la cabeza; si la persona sube o baja (la cara, ya suavizada por el motor), la sigue a medias
    mueve = L['sigue'] * S * (float(c.cara[1]) - L['cy0'])
    Yc = _ancla(L['cam'], L['yh'], t, c.dur, L['sigue']) + mueve + L['meter'] - L['aire'] - h / 2
    arriba = Yc - sc * h / 2
    if arriba < L['techo']:                                            # nunca por encima de la zona segura
        Yc += L['techo'] - arriba
    Xc = L['x'] + w / 2

    # lo de detrás esmerilado, los textos y los separadores, y los interruptores
    tarjeta = _esmerilado(c, Xc - w / 2, Yc - h / 2, w, h)
    rgbp, a = L['fija']
    tarjeta = tarjeta * (1 - a) + rgbp
    ix = L['int_x']
    for i, yc in enumerate(L['filas']):
        k = B.sale(B.tramo(t, L['inicios'][i], L['inicios'][i] + CAMBIO))
        trgbp, ta = _interruptor(L, k)
        th, tw = ta.shape[:2]
        iy = int(round(yc - th / 2))
        zona = tarjeta[iy:iy + th, ix:ix + tw]
        zona *= (1 - ta)
        zona += trgbp
    rgba = np.dstack([tarjeta, L['forma']])
    capa = Image.fromarray((rgba * 255 + 0.5).clip(0, 255).astype(np.uint8), 'RGBA')

    B.poner(c, L['sombra'], Xc, Yc + 14 * u * L['k'] * sc, escala=sc, alfa=alfa, detras=L['detras'])
    B.poner(c, capa, Xc, Yc, escala=sc, alfa=alfa, detras=L['detras'])
