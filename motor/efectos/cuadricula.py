"""Cuadrícula: te alejas y caes en el centro de tu perfil, rodeado de tus Reels con sus vistas.

Empieza con el vídeo a pantalla completa y en 0,6 s la cámara se aleja (una curva suave, sin tirón) hasta que el vídeo
queda como la casilla del centro de una cuadrícula de 3 columnas, como el perfil de Instagram: casillas 3:4 y una
separación fina de 4 px. El vídeo sigue moviéndose dentro de su casilla, que queda un poco levantada, con un borde fino y
un brillo alrededor (en el fondo claro, una sombra) para que se vea que es la tuya. Después la cuadrícula se sigue
alejando muy despacio y al final todo se va con un fundido de 0,3 s.

Las demás casillas:
  - `imagenes=<carpeta>`: las imágenes de esa carpeta (jpg, png o webp), ordenadas por nombre, recortadas a 3:4 por el
    centro sin deformarse. Las primeras van en las 8 casillas de alrededor; si hay pocas, se repiten sin que dos iguales
    queden pegadas.
  - sin carpeta: cuadros del propio vídeo (como la órbita).
  - `vistas=1M|114K|9,9K`: las vistas de cada imagen, en el mismo orden (por nombre). Abajo a la izquierda de su casilla,
    en blanco con sombra, con el icono de reproducir (o el ojo: `icono=ojo`). Vacía = sin números. Nunca se inventan.

Nada tiembla ni hace muaré: cada imagen se prepara una vez en varias copias de tamaño fijo (reducidas con filtro de área y
suavizadas); en cada cuadro se coge la que toca y se encoge un poco con decimales, sin volver a reducirla a un tamaño entero
distinto (eso hacía centellear las letras finas). Los bordes de las casillas se pintan con su parte de píxel. El primer
cuadro es el vídeo tal cual (entra sin salto) y el último vuelve a él con el fundido. revisar_video.py, 27 oct 2026: pasa
a 540 y a 1080 (solo avisos de menos de 520 píxeles, en los bordes de fuera de la cuadrícula mientras se aleja).

    .venv/bin/python efectos.py cuadricula mi-video.mp4 --desde 2 --op imagenes=mis-portadas --op "vistas=1M|114K|9,9K"
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import base as B

NOMBRE = 'cuadricula'
DESCRIPCION = 'Te alejas y caes en el centro de tu perfil, rodeado de tus Reels con sus vistas'
OPCIONES = {
    # la carpeta con las portadas de tus Reels (jpg, png o webp; por nombre). Vacío: cuadros de tu propio vídeo
    'imagenes': '',
    # las vistas de cada imagen, en el mismo orden y separadas por «|» («1M|114K|9,9K»). Vacío = sin números
    'vistas': '',
    # el fondo de la cuadrícula: oscuro, claro o un color (#101014)
    'fondo': 'oscuro',
    # el icono junto a las vistas: reproducir, ojo o nada
    'icono': 'reproducir',
    # el color del borde de tu casilla
    'color': '#FFFFFF',
    # cuánto se sigue alejando después de caer: 1 = se queda quieta; 0,88 = un 12 % más lejos al acabar
    'alejar': '0.88',
}
DURACION = 3.0

MARGEN = 60          # la zona segura (a 1080 de ancho): la cuadrícula, ya posada, va de x 60 a x 1020
HUECO = 4            # la separación entre casillas, con la cuadrícula posada (a 1080 de ancho)
CAE = 0.6            # lo que tarda en alejarse hasta su casilla
FUNDE = 0.3          # el fundido del final
LETRA = 37           # el tamaño de las vistas con la cuadrícula posada (a 1080; al acabar, ×0,88 ≈ 32 px)
LEVANTA = 0.03       # cuánto más grande queda tu casilla que las demás (parece levantada)
BORDE = 3            # el grosor del borde de tu casilla (a 1080)
BRILLO = 16          # lo que se abre el brillo (o la sombra) alrededor de tu casilla (a 1080)
SUAVIZA = 0.6        # el desenfoque (en px de la copia grande) de las imágenes antes de reducirlas: sin muaré
SUAVIZA_NIVEL = 0.8  # el de cada copia reducida (en sus px): al encogerla un poco en cada cuadro, las letras finas no
                     # centellean (con 0,45 o con interpolación más nítida, revisar_video marcaba parpadeo en las letras)
PASO_NIVEL = 1.5     # entre una copia reducida y la siguiente (las «mip»): de cada copia se encoge como mucho 1,5 veces
APAGA = 0.12         # cuánto se oscurecen las demás casillas al posarse (así la tuya resalta; las vistas se leen igual)


# ── Números y opciones ──────────────────────────────────────────────────────────────────────────────────────────────
def _num(v, defecto):
    try:
        return float(str(v).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return float(defecto)


def _fondo(op):
    """(color de fondo 0–1, ¿es oscuro?)."""
    s = str(op.get('fondo') or 'oscuro').strip().lower()
    if s in ('claro', 'blanco', 'light', 'white'):
        return np.array([1.0, 1.0, 1.0], np.float32), False
    if s.startswith('#'):
        try:
            rgb = np.array(B.color(s)[:3], np.float32) / 255.0
            return rgb, float(rgb @ np.array([0.299, 0.587, 0.114], np.float32)) < 0.5
        except ValueError:
            print(f'  Aviso (cuadrícula): «{s}» no es un color; uso el fondo oscuro.')
    return np.array([10, 10, 12], np.float32) / 255.0, True


def _erf(x):
    """La función de error (Abramowitz y Stegun 7.1.26, error < 2e-7), con numpy."""
    s = np.sign(x)
    x = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * \
        np.exp(-x * x)
    return s * y


def _cobertura(a0, a1, n0, n):
    """Qué parte de cada píxel (n0 … n0+n−1; el píxel k va de k a k+1) cae dentro de [a0, a1]: los bordes, suaves."""
    k = np.arange(n0, n0 + n, dtype=np.float64)
    return np.clip(np.minimum(a1, k + 1.0) - np.maximum(a0, k), 0.0, 1.0).astype(np.float32)


# ── Las casillas (se preparan una vez, en grande) ───────────────────────────────────────────────────────────────────
def _cubrir(im, w, h):
    """La imagen recortada por el centro para llenar w × h sin deformarse (reducida con Lanczos, que ya filtra)."""
    im = im.convert('RGB')
    k = max(w / im.width, h / im.height)
    cw, ch = w / k, h / k
    x0, y0 = (im.width - cw) / 2, (im.height - ch) / 2
    return im.resize((w, h), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))


def _icono(tipo, tam):
    """El icono blanco de las vistas (reproducir u ojo), de `tam` px de alto, dibujado a 4× y reducido (bordes limpios)."""
    k = 4
    S = max(8, int(round(tam * k)))
    capa = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    blanco = (255, 255, 255, 255)
    g = max(2, int(round(S * 0.12)))
    if tipo == 'ojo':
        # un ojo: el contorno en forma de almendra (dos arcos de círculo que se cortan en las esquinas) y la pupila
        a, s = S / 2 - g, S * 0.30                       # medio ancho y lo que sube cada arco desde la línea del centro
        R = (a * a + s * s) / (2 * s)
        th = math.degrees(math.asin(min(1.0, a / R)))
        o = S / 2 - s + R                                # el centro del círculo del arco de arriba (queda por debajo)
        d.arc([S / 2 - R, o - R, S / 2 + R, o + R], start=270 - th, end=270 + th, fill=blanco, width=g)
        o = S / 2 + s - R                                # el del arco de abajo (queda por encima)
        d.arc([S / 2 - R, o - R, S / 2 + R, o + R], start=90 - th, end=90 + th, fill=blanco, width=g)
        p = S * 0.16
        d.ellipse([S / 2 - p, S / 2 - p, S / 2 + p, S / 2 + p], fill=blanco)
    else:
        # reproducir: un triángulo con el contorno y las esquinas redondeadas
        m = g / 2 + S * 0.04
        pts = [(S * 0.16 + m, m), (S - m, S / 2), (S * 0.16 + m, S - m)]
        d.line(pts + [pts[0], pts[1]], fill=blanco, width=g, joint='curve')
    return capa.resize((max(1, int(round(tam))), max(1, int(round(tam)))), Image.LANCZOS)


def _vistas(texto, icono, tam):
    """La fila de las vistas (icono + número), blanca, con su sombra suave. Devuelve (capa, el aire que le añade la
    sombra por cada lado, la altura de la línea de base dentro de la fila sin sombra)."""
    f = B.fuente('bold', tam)
    asc, desc = f.getmetrics()
    alto_mayus = -f.getbbox('8', anchor='ls')[1]
    ic = _icono(icono, alto_mayus * 1.12) if icono in ('reproducir', 'ojo') else None
    hueco = tam * 0.26 if ic is not None else 0
    w = int(math.ceil((ic.width if ic is not None else 0) + hueco + f.getlength(texto))) + 2
    h = int(math.ceil(asc + desc))
    capa = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    linea = asc                                              # la línea de base
    if ic is not None:
        capa.alpha_composite(ic, (0, int(round(linea - alto_mayus / 2 - ic.height / 2))))
    ImageDraw.Draw(capa).text(((ic.width if ic is not None else 0) + hueco, linea), texto, font=f,
                              fill=(255, 255, 255, 255), anchor='ls')
    desenfoque = tam * 0.12
    pad = int(desenfoque * 2 + abs(tam * 0.04))
    return B.con_sombra(capa, desenfoque, tam * 0.04, 175), pad, linea


def _casilla(foto, w, h, vista, icono, escala):
    """Una casilla en grande (w × h, a `escala` veces su tamaño posada): la foto recortada a 3:4, algo suavizada para que
    al reducirla no haga muaré, y sus vistas abajo a la izquierda. Devuelve un array uint8 h × w × 3."""
    im = _cubrir(foto, w, h)
    if SUAVIZA > 0:
        im = im.filter(ImageFilter.GaussianBlur(SUAVIZA))
    if not vista:
        return np.ascontiguousarray(np.asarray(im, np.uint8))
    # una sombra muy suave abajo, para que las vistas se lean también sobre una portada clara
    arr = np.asarray(im, np.float32)
    y = (np.arange(h, dtype=np.float32) + 0.5) / h
    rampa = np.clip((y - 0.72) / 0.28, 0, 1)
    arr *= (1.0 - 0.30 * rampa * rampa)[:, None, None]
    im = Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8), 'RGB').convert('RGBA')
    fila, pad, linea = _vistas(vista, icono, LETRA * escala)
    izq, abajo = 13 * escala, 15 * escala                    # el aire hasta el borde de la casilla (posada, a 1080)
    im.alpha_composite(fila, (int(round(izq - pad)), int(round(h - abajo - linea - pad))))
    return np.ascontiguousarray(np.asarray(im.convert('RGB'), np.uint8))


def _fotos(c, n):
    """Las fotos de las casillas: las de la carpeta o, si no hay, cuadros del propio vídeo."""
    carpeta = (c.op.get('imagenes') or '').strip()
    fotos = B.imagenes_de(carpeta)
    if fotos:
        return fotos[:24]
    if carpeta:
        print(f'  Aviso (cuadrícula): no encuentro imágenes en «{carpeta}»; uso cuadros del propio vídeo.')
    sacar = c.estado.get('sacar_cuadros')
    if callable(sacar):
        fotos = sacar(n, int(min(1080, max(540, c.W))))
        if fotos:
            return fotos
    # sin motor (el efecto probado suelto): trozos del cuadro de este momento
    W, H = c.W, c.H
    tw, th = int(W * 0.5), int(W * 0.5 * 4 / 3)
    sitios = [(0.05, 0.05), (0.5, 0.1), (0.0, 0.5), (0.5, 0.55), (0.25, 0.3), (0.3, 0.8), (0.7, 0.35), (0.1, 0.2)]
    return [B.a_capa(c.img[int(fy * (H - th)):int(fy * (H - th)) + th, int(fx * (W - tw)):int(fx * (W - tw)) + tw])
            for fx, fy in sitios[:n]]


def _repartir(n, filas):
    """Qué imagen va en cada casilla {(fila, columna): índice}. Primero las 8 de alrededor (en orden de lectura), después
    las filas de más lejos. Si hay menos imágenes que casillas se repiten: la que menos se ha usado y, entre esas, la
    que tenga su copia más lejos (así dos iguales nunca quedan pegadas si se puede evitar)."""
    orden = [(r, k) for r in (-1, 0, 1) for k in (-1, 0, 1) if (r, k) != (0, 0)]
    for d in range(2, filas + 1):
        for r in (-d, d):
            orden += [(r, k) for k in (-1, 0, 1)]
    sitio, usos, sig = {}, [0] * n, 0
    donde = [[] for _ in range(n)]
    for r, k in orden:
        mejor, elegida = None, sig % n
        for j in range(n):
            cand = (sig + j) % n
            lejos = min((math.hypot(r - a, k - b) for a, b in donde[cand]), default=1e9)
            nota = (usos[cand], -lejos)
            if mejor is None or nota < mejor:
                mejor, elegida = nota, cand
        sitio[(r, k)] = elegida
        usos[elegida] += 1
        donde[elegida].append((r, k))
        sig = elegida + 1
    return sitio


def _preparar(c):
    u = c.u
    W, H = c.W, c.H
    e = {}
    e['fondo'], e['oscuro'] = _fondo(c.op)
    try:
        e['color'] = np.array(B.color(c.op.get('color') or '#FFFFFF')[:3], np.float32) / 255.0
    except ValueError:
        print(f'  Aviso (cuadrícula): «{c.op.get("color")}» no es un color; el borde va en blanco.')
        e['color'] = np.ones(3, np.float32)
    e['alejar'] = min(1.0, max(0.5, _num(c.op.get('alejar'), 0.88)))
    icono = str(c.op.get('icono') or 'reproducir').strip().lower()
    icono = {'play': 'reproducir', 'eye': 'ojo', 'ninguno': 'nada', 'no': 'nada'}.get(icono, icono)

    # la casilla posada: tres columnas dentro de la zona segura (si el vídeo no es vertical, que no sea enorme)
    g = HUECO * u
    w = min((W - 2 * MARGEN * u - 2 * g) / 3.0, 0.42 * H * 0.75)
    h = w * 4.0 / 3.0
    e.update(g=g, w=w, h=h)
    # el trozo 3:4 del vídeo que queda en tu casilla: todo el ancho, con la cara a un tercio de arriba
    cx, cy, _ = c.cara
    if W / H <= 0.75:
        cw, ch = float(W), W * 4.0 / 3.0
    else:
        cw, ch = H * 0.75, float(H)
    xc = min(max(cx - cw / 2, 0.0), W - cw)
    yc = min(max(cy - 0.34 * ch, 0.0), H - ch)
    e['recorte'] = (xc, yc, cw, ch)
    k = w / cw                                             # vídeo → cuadrícula posada
    z0 = 1.0 / k                                           # el acercamiento del principio: el vídeo a pantalla completa
    e.update(k=k, z0=z0)
    # el centro de la cuadrícula posada y el punto fijo de la cámara (el que no se mueve al alejarse): así, al empezar,
    # el vídeo queda exactamente donde estaba
    e['centro'] = np.array([W / 2.0, H / 2.0])
    cc = np.array([xc + cw / 2, yc + ch / 2])
    e['cc'] = cc
    e['fijo'] = (z0 * e['centro'] - cc) / (z0 - 1.0)

    # las casillas de alrededor: qué imagen va en cada una y cuántas filas hacen falta para llenar la pantalla
    filas = int(math.ceil(H / (2 * e['alejar'] * 0.97 * (h + g)))) + 1
    fotos = _fotos(c, 8)
    if not fotos:
        raise ValueError('no hay ninguna imagen para las casillas')
    vistas = [s.strip() for s in str(c.op.get('vistas') or '').split('|')]
    # copias de cada casilla a varios tamaños fijos (1, 1,5, 2,25… veces la posada, hasta la del principio). En cada
    # cuadro se coge la más pequeña que no sea menor que la casilla en pantalla y se encoge un poco con decimales: así el
    # filtro no cambia de un cuadro a otro (reducir cada vez a un tamaño entero distinto hacía centellear las letras)
    niveles = [1.0]
    while niveles[-1] * PASO_NIVEL < z0 / 1.2:
        niveles.append(niveles[-1] * PASO_NIVEL)
    niveles.append(z0)
    e['niveles'] = niveles
    sw, sh = int(round(z0 * w)), int(round(z0 * h))
    e['mip'] = []
    for i, f in enumerate(fotos):
        grande = _casilla(f, sw, sh, vistas[i] if i < len(vistas) else '', icono, z0 * u)
        copias = []
        for s in niveles[:-1]:
            m = cv2.resize(grande, (max(1, int(round(s * w))), max(1, int(round(s * h)))), interpolation=cv2.INTER_AREA)
            copias.append(cv2.GaussianBlur(m, (0, 0), SUAVIZA_NIVEL))
        copias.append(grande)
        e['mip'].append(copias)
    e['sitio'] = _repartir(len(fotos), filas)
    e['filas'] = filas
    # la deriva lenta: arranca suave (sin tirón) y sigue a ritmo constante hasta el final
    T = 0.35
    e['deriva'] = lambda t: (t - T * (1 - math.exp(-t / T))) / max(1e-6, c.dur - T * (1 - math.exp(-c.dur / T)))
    return e


# ── Pintar ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _nivel(niveles, z):
    """El índice de la copia más pequeña que no es menor que `z` (la casilla en pantalla, en veces la posada)."""
    for i, s in enumerate(niveles):
        if s >= z * (1 - 1e-6):
            return i
    return len(niveles) - 1


def _pegar(lienzo, src, ex, ey, ax, ay, caja, luz=1.0):
    """Pone `src` (alto × ancho × 3, float32 de 0 a 1 o uint8) en el lienzo: su esquina (continua) en (ax, ay) y cada
    píxel de `src` mide ex × ey en pantalla; solo dentro de `caja` (x0, y0, x1, y1 con decimales), con los bordes suaves.
    `luz` < 1 la oscurece."""
    x0, y0, x1, y1 = caja
    H, W = lienzo.shape[:2]
    X0, Y0 = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
    X1, Y1 = min(W, int(math.ceil(x1))), min(H, int(math.ceil(y1)))
    if X1 <= X0 or Y1 <= Y0:
        return
    M = np.array([[ex, 0.0, 0.5 * ex - 0.5 + ax - X0], [0.0, ey, 0.5 * ey - 0.5 + ay - Y0]], np.float64)
    hecha = cv2.warpAffine(src, M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if hecha.dtype == np.uint8:
        hecha = hecha.astype(np.float32) * np.float32(luz / 255.0)
    elif luz < 0.999:
        hecha *= np.float32(luz)
    cx = _cobertura(x0, x1, X0, X1 - X0)
    cy = _cobertura(y0, y1, Y0, Y1 - Y0)
    zona = lienzo[Y0:Y1, X0:X1]
    if cx.min() >= 0.9999 and cy.min() >= 0.9999:
        zona[...] = hecha
    else:
        cov = np.outer(cy, cx)[..., None]
        zona += (hecha - zona) * cov


def _reducir(src, tw, th, flotante=True):
    """`src` a tw × th con filtro de área (al reducir no hace muaré); si no hace falta, tal cual."""
    if src.shape[1] == tw and src.shape[0] == th:
        out = src
    else:
        modo = cv2.INTER_AREA if (tw < src.shape[1] and th < src.shape[0]) else cv2.INTER_LINEAR
        out = cv2.resize(src, (tw, th), interpolation=modo)
    if flotante and out.dtype == np.uint8:
        out = out.astype(np.float32) * np.float32(1.0 / 255.0)
    return out


def _halo(lienzo, caja, sigma, color, alfa, dy=0.0):
    """Un brillo (o una sombra) suave alrededor de la caja, solo por fuera de ella: el desenfoque exacto de un
    rectángulo (separable, con la función de error), sin desenfocar ninguna imagen."""
    if alfa <= 0.003 or sigma <= 0.1:
        return
    x0, y0, x1, y1 = caja
    H, W = lienzo.shape[:2]
    m = 3.2 * sigma
    X0, Y0 = max(0, int(math.floor(x0 - m))), max(0, int(math.floor(y0 + dy - m)))
    X1, Y1 = min(W, int(math.ceil(x1 + m))), min(H, int(math.ceil(y1 + dy + m)))
    if X1 <= X0 or Y1 <= Y0:
        return
    xs = np.arange(X0, X1, dtype=np.float64) + 0.5
    ys = np.arange(Y0, Y1, dtype=np.float64) + 0.5
    s = sigma * math.sqrt(2.0)
    gx = 0.5 * (_erf((xs - x0) / s) - _erf((xs - x1) / s))
    gy = 0.5 * (_erf((ys - y0 - dy) / s) - _erf((ys - y1 - dy) / s))
    dentro = np.outer(_cobertura(y0, y1, Y0, Y1 - Y0), _cobertura(x0, x1, X0, X1 - X0))
    k = (np.outer(gy, gx) * (1.0 - dentro) * alfa).astype(np.float32)[..., None]
    zona = lienzo[Y0:Y1, X0:X1]
    zona += (color - zona) * k


def _borde(lienzo, caja, grosor, color, alfa):
    """Un borde fino por dentro de la caja, con su parte de píxel en cada lado (no tiembla al moverse)."""
    if alfa <= 0.003 or grosor <= 0.05:
        return
    x0, y0, x1, y1 = caja
    H, W = lienzo.shape[:2]
    X0, Y0 = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
    X1, Y1 = min(W, int(math.ceil(x1))), min(H, int(math.ceil(y1)))
    if X1 <= X0 or Y1 <= Y0:
        return
    fuera = np.outer(_cobertura(y0, y1, Y0, Y1 - Y0), _cobertura(x0, x1, X0, X1 - X0))
    dentro = np.outer(_cobertura(y0 + grosor, y1 - grosor, Y0, Y1 - Y0),
                      _cobertura(x0 + grosor, x1 - grosor, X0, X1 - X0))
    k = ((fuera - dentro) * alfa)[..., None]
    zona = lienzo[Y0:Y1, X0:X1]
    zona += (color - zona) * k


def dibujar(c):
    if 'cuadricula' not in c.estado:
        c.estado['cuadricula'] = _preparar(c)
    e = c.estado['cuadricula']
    u, W, H = c.u, c.W, c.H
    # si el efecto dura menos de lo normal, la caída y el fundido se acortan
    cae = min(CAE, 0.4 * c.dur)
    funde = min(FUNDE, 0.15 * c.dur)
    p = B.suave(B.tramo(c.t, 0.0, cae))                     # cuánto se ha alejado (0 = pantalla completa, 1 = posada)
    # el acercamiento de la cámara: de z0 a 1 (en escala logarítmica: la misma sensación de velocidad grande o pequeña)
    # y, sumada desde el principio, la deriva lenta que sigue alejándose
    z = math.exp((1.0 - p) * math.log(e['z0']) + math.log(e['alejar']) * e['deriva'](c.t))
    levanta = 1.0 + LEVANTA * p
    fijo, centro = e['fijo'], e['centro']
    w, h, g = e['w'], e['h'], e['g']

    def a_pantalla(X, Y):
        return fijo[0] + z * (X - fijo[0]), fijo[1] + z * (Y - fijo[1])

    lienzo = e.get('lienzo')
    if lienzo is None or lienzo.shape != c.img.shape:
        lienzo = e['lienzo'] = np.empty_like(c.img)
    lienzo[...] = e['fondo']

    alfa_marca = B.suave(B.tramo(c.t, 0.35 * cae, cae))    # el borde y el brillo llegan cuando ya casi se ha posado
    luz = np.float32(1.0 - APAGA * alfa_marca)

    # 1) las casillas de alrededor: cada una, desde su copia fija del tamaño que toca, encogida con decimales
    nv = _nivel(e['niveles'], z)
    for (r, k), i in e['sitio'].items():
        X = centro[0] + k * (w + g)
        Y = centro[1] + r * (h + g)
        sx, sy = a_pantalla(X, Y)
        caja = (sx - z * w / 2, sy - z * h / 2, sx + z * w / 2, sy + z * h / 2)
        if caja[2] <= 0 or caja[0] >= W or caja[3] <= 0 or caja[1] >= H:
            continue
        m = e['mip'][i][nv]
        _pegar(lienzo, m, z * w / m.shape[1], z * h / m.shape[0], caja[0], caja[1], caja, luz)

    # 2) tu casilla: el vídeo, recortándose de 9:16 a 3:4 mientras se aleja
    xc, yc, cw, ch = e['recorte']
    wx0, wx1 = B.mezclar(0.0, xc, p), B.mezclar(float(W), xc + cw, p)
    wy0, wy1 = B.mezclar(0.0, yc, p), B.mezclar(float(H), yc + ch, p)
    zk = z * e['k'] * levanta                               # vídeo → pantalla
    cc = e['cc']

    def video_a_pantalla(vx, vy):
        return a_pantalla(centro[0] + levanta * e['k'] * (vx - cc[0]), centro[1] + levanta * e['k'] * (vy - cc[1]))

    sx0, sy0 = video_a_pantalla(wx0, wy0)
    sx1, sy1 = video_a_pantalla(wx1, wy1)
    caja = (sx0, sy0, sx1, sy1)
    if e['oscuro']:
        _halo(lienzo, caja, BRILLO * u * z, e['color'], 0.42 * alfa_marca)
    else:
        _halo(lienzo, caja, BRILLO * u * z, np.zeros(3, np.float32), 0.38 * alfa_marca, dy=7 * u * z)
    ix0, iy0 = max(0, int(math.floor(wx0))), max(0, int(math.floor(wy0)))
    ix1, iy1 = min(W, int(math.ceil(wx1))), min(H, int(math.ceil(wy1)))
    src = c.img[iy0:iy1, ix0:ix1]
    if not src.flags['C_CONTIGUOUS']:
        src = np.ascontiguousarray(src)
    # el vídeo se reduce (con filtro de área) al tamaño de la copia que toca, que ya posado no cambia de un cuadro a otro,
    # y se encoge el resto con decimales al pegarlo
    s = e['niveles'][nv] * e['k'] * levanta
    vw = min(ix1 - ix0, max(1, int(math.ceil((ix1 - ix0) * s - 1e-6))))
    vh = min(iy1 - iy0, max(1, int(math.ceil((iy1 - iy0) * s - 1e-6))))
    reducido = _reducir(src, vw, vh)
    if vw < 0.8 * (ix1 - ix0):
        reducido = cv2.GaussianBlur(reducido, (0, 0), SUAVIZA_NIVEL)
    ax, ay = video_a_pantalla(ix0, iy0)
    _pegar(lienzo, reducido, zk * (ix1 - ix0) / vw, zk * (iy1 - iy0) / vh, ax, ay, caja)
    _borde(lienzo, caja, BORDE * u * min(z, 1.6), e['color'], 0.95 * alfa_marca)

    # 3) el fundido del final: vuelve el vídeo tal cual
    a = B.tramo(c.queda, 0.0, funde)
    if a >= 0.999:
        np.copyto(c.img, lienzo)
    else:
        lienzo -= c.img
        lienzo *= np.float32(B.suave(a))
        c.img += lienzo
