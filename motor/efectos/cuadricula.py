"""Cuadrícula: te encoges hasta el centro de tu perfil y tus Reels, con sus vistas, aparecen a tu alrededor.

Como la referencia (medido cuadro a cuadro en su vídeo, 28 oct 2026):
  1. El vídeo, a pantalla completa, se encoge en 0,34 s hasta la casilla del centro de una cuadrícula de 3 × 3. Detrás
     queda tu propio vídeo muy desenfocado (no un color plano), así que no hay ningún corte.
  2. Al posarse le sale el borde (del color de `color`) y se queda sola un momento.
  3. Las demás llegan de una en una, en el sentido del reloj: arriba, derecha, abajo, izquierda y después las esquinas
     (una cada 0,045 s; cada una entra con un fundido de 0,2 s y crece del 92 al 100 %).
  4. Ya formada, la cámara se acerca muy despacio (un 4 % hasta el final) y todo se va con un fundido de 0,3 s.
Las casillas, como en su vídeo: de la forma del Reel (9:16, la portada entera), con las esquinas redondeadas, un filo
blanco fino y aire de verdad entre ellas (20 px a 1080) y a los lados: las de los lados salen ENTERAS, dentro de la zona
segura (de x 60 a x 1020 aunque la cámara se acerque). Sus medidas: casilla del 30 % del ancho, hueco del 6 % de la
casilla, esquinas de 9 px y las vistas con las mayúsculas al 6,5 % del ancho de la casilla.

Las demás casillas:
  - `imagenes=<carpeta>`: las imágenes de esa carpeta (jpg, png o webp), ordenadas por nombre, recortadas a la forma de
    la casilla por el centro sin deformarse. Las primeras van en las 8 casillas de alrededor, en orden de lectura; si hay
    pocas, se repiten sin que dos iguales queden pegadas.
  - sin carpeta: cuadros del propio vídeo (como la órbita).
  - `vistas=1M|114K|9,9K`: las vistas de cada imagen, en el mismo orden (por nombre). Abajo a la izquierda de su casilla,
    en blanco con sombra, con el icono de reproducir (o el ojo: `icono=ojo`). Vacía = sin números. Nunca se inventan.
Lo demás se puede cambiar: el fondo (`fondo=oscuro`, `claro` o un color, en vez de tu vídeo desenfocado), el hueco, el
margen, las esquinas, la forma (`forma=3:4`, como la cuadrícula del perfil; con `filas=5` llenan la pantalla), cómo llegan
(`entrada=juntas`: ya están y la cámara las descubre al alejarse) y la cámara del final (`alejar`).

Nada tiembla ni hace muaré: cada imagen se prepara una vez en varias copias de tamaño fijo (reducidas con filtro de área y
suavizadas); en cada cuadro se coge la que toca y se encoge un poco con decimales, sin volver a reducirla a un tamaño entero
distinto (eso hacía centellear las letras finas). Los bordes, los filos y las esquinas redondeadas se pintan con su parte de
píxel (la distancia exacta al borde), así que no tiemblan mientras la cámara se mueve. El primer cuadro es el vídeo tal
cual (entra sin salto) y el último vuelve a él con el fundido. revisar_video.py, 28 oct 2026, con la toma de pasa
(parpadeo de 137 píxeles en el peor segundo, el aviso empieza en 300; solo marca, para mirarlos, el final de la caída y el
fundido del final, que son movimientos y no saltos).

    .venv/bin/python efectos.py cuadricula mi-video.mp4 --desde 2 --op imagenes=mis-portadas --op "vistas=1M|114K|9,9K"
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import base as B

NOMBRE = 'cuadricula'
DESCRIPCION = 'Te encoges hasta el centro de tu perfil y tus Reels, con sus vistas, aparecen a tu alrededor'
OPCIONES = {
    # la carpeta con las portadas de tus Reels (jpg, png o webp; por nombre). Vacío: cuadros de tu propio vídeo
    'imagenes': '',
    # las vistas de cada imagen, en el mismo orden y separadas por «|» («1M|114K|9,9K»). Vacío = sin números
    'vistas': '',
    # lo que se ve detrás de las casillas: video (tu propio vídeo muy desenfocado), oscuro, claro o un color (#101014)
    'fondo': 'video',
    # el icono junto a las vistas: reproducir, ojo o nada
    'icono': 'reproducir',
    # el color del borde de tu casilla
    'color': '#FFFFFF',
    # la cámara, ya formada la cuadrícula: 1 = quieta; 1,04 = se acerca un 4 % hasta el final; 0,88 = se aleja un 12 %
    'alejar': '1.04',
    # la separación entre casillas, en px a 1080 de ancho
    'hueco': '20',
    # el aire mínimo a cada lado de la cuadrícula, en px a 1080 (60 = la zona segura de Instagram), también al acercarse
    'margen': '60',
    # el redondeo de las esquinas de las casillas, en px a 1080 (0 = rectas)
    'esquinas': '9',
    # la forma de las casillas: 9:16 (el Reel entero) o 3:4 (como la cuadrícula del perfil)
    'forma': '9:16',
    # cuántas filas: 3 (la cuadrícula entera a la vista) o 5 (las de arriba y abajo salen cortadas; con forma=3:4 llenan)
    'filas': '3',
    # cómo llegan las demás: una (de una en una, ya posada la tuya) o juntas (ya están y la cámara las descubre)
    'entrada': 'una',
}
DURACION = 3.0

ESPERA = 0.10        # el vídeo quieto a pantalla completa antes de encogerse (la referencia: 0,1 s)
CAE = 0.34           # lo que tarda en encogerse hasta su casilla (la referencia: 0,27 s; algo más suave aquí)
SOLA = 0.12          # tu casilla sola sobre el fondo antes de que lleguen las demás (la referencia: 0,1 s)
ESCALONA = 0.045     # entre una casilla y la siguiente (la referencia: una por cuadro, de golpe; aquí, con su fundido)
APARECE = 0.2        # lo que tarda cada una en aparecer (fundido, y crece de CRECE a su tamaño)
CRECE = 0.92
DERIVA = 0.35        # lo que tarda la cámara del final en coger su ritmo (arranca suave, sin tirón)
FUNDE = 0.3          # el fundido del final
LETRA = 0.105        # el tamaño de las vistas, en proporción al ancho de la casilla (≈ 31 px a 1080)
AIRE_VISTAS = 0.05   # lo que separa las vistas del borde izquierdo y del de abajo, en proporción al ancho de la casilla
LEVANTA = 0.016      # cuánto más grande queda tu casilla que las demás (el borde queda por fuera, como la referencia)
BORDE = 3.5          # el grosor del borde de tu casilla (a 1080)
FILO = 1.5           # el filo blanco de las demás casillas (a 1080) …
FILO_ALFA = 0.8      # … y lo que se ve
BRILLO = 16          # con fondo oscuro o claro: lo que se abre el brillo (o la sombra) alrededor de tu casilla (a 1080)
SUAVIZA = 0.6        # el desenfoque (en px de la copia grande) de las imágenes antes de reducirlas: sin muaré
SUAVIZA_NIVEL = 0.8  # el de cada copia reducida (en sus px): al encogerla un poco en cada cuadro, las letras finas no
                     # centellean (con 0,45 o con interpolación más nítida, revisar_video marcaba parpadeo en las letras)
PASO_NIVEL = 1.5     # entre una copia reducida y la siguiente (las «mip»): de cada copia se encoge como mucho 1,5 veces
DESENFOQUE = 2.5     # el desenfoque del fondo de vídeo, en px de su copia pequeña (68 px de ancho): ≈ 40 px a 1080
# el orden en que llegan las 8 de alrededor (fila, columna): arriba, derecha, abajo, izquierda y las esquinas
ORDEN = [(-1, 0), (0, 1), (1, 0), (0, -1), (-1, 1), (1, 1), (1, -1), (-1, -1)]


# ── Números y opciones ──────────────────────────────────────────────────────────────────────────────────────────────
def _num(v, defecto):
    try:
        return float(str(v).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return float(defecto)


def _fondo(op):
    """(color de fondo 0–1 o None si es el propio vídeo desenfocado, ¿es oscuro?)."""
    s = str(op.get('fondo') or 'video').strip().lower()
    if s in ('video', 'vídeo', 'desenfocado', 'blur'):
        return None, False
    if s in ('claro', 'blanco', 'light', 'white'):
        return np.array([1.0, 1.0, 1.0], np.float32), False
    if s.startswith('#'):
        try:
            rgb = np.array(B.color(s)[:3], np.float32) / 255.0
            return rgb, float(rgb @ np.array([0.299, 0.587, 0.114], np.float32)) < 0.5
        except ValueError:
            print(f'  Aviso (cuadrícula): «{s}» no es un color; uso tu vídeo desenfocado.')
            return None, False
    if s not in ('oscuro', 'negro', 'dark', 'black'):
        print(f'  Aviso (cuadrícula): no conozco el fondo «{s}»; uso tu vídeo desenfocado.')
        return None, False
    return np.array([10, 10, 12], np.float32) / 255.0, True


def _forma(op):
    """El ancho entre el alto de las casillas («9:16», «3:4», «1:1»…)."""
    s = str(op.get('forma') or '9:16').strip().replace('/', ':').replace('x', ':')
    try:
        a, b = (float(v.replace(',', '.')) for v in s.split(':'))
        if a > 0 and b > 0:
            return min(1.5, max(0.4, a / b))
    except ValueError:
        pass
    print(f'  Aviso (cuadrícula): «{s}» no es una forma (9:16, 3:4); uso 9:16.')
    return 9.0 / 16.0


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


def _cobertura_caja(x0, y0, x1, y1, r, X0, Y0, nx, ny):
    """Qué parte de cada píxel de la zona (X0, Y0, nx × ny) cae dentro del rectángulo (con decimales) de esquinas
    redondeadas de radio r. Los lados, con su parte exacta de píxel; las cuatro esquinas, con la distancia al arco desde el
    centro de cada píxel. Las dos cosas cambian poco a poco con la posición: al moverse, nada tiembla."""
    cov = np.outer(_cobertura(y0, y1, Y0, ny), _cobertura(x0, x1, X0, nx))
    r = min(r, 0.5 * (x1 - x0), 0.5 * (y1 - y0))
    if r <= 0.3:
        return cov
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    hx, hy = 0.5 * (x1 - x0) - r, 0.5 * (y1 - y0) - r
    for ax, bx in ((x0, x0 + r), (x1 - r, x1)):
        i0, i1 = max(X0, int(math.floor(ax))), min(X0 + nx, int(math.ceil(bx)))
        if i1 <= i0:
            continue
        for ay, by in ((y0, y0 + r), (y1 - r, y1)):
            j0, j1 = max(Y0, int(math.floor(ay))), min(Y0 + ny, int(math.ceil(by)))
            if j1 <= j0:
                continue
            qx = np.abs(np.arange(i0, i1, dtype=np.float64) + 0.5 - cx) - hx
            qy = np.abs(np.arange(j0, j1, dtype=np.float64) + 0.5 - cy) - hy
            QX, QY = np.meshgrid(qx, qy)
            d = np.hypot(np.maximum(QX, 0.0), np.maximum(QY, 0.0)) + np.minimum(np.maximum(QX, QY), 0.0) - r
            cov[j0 - Y0:j1 - Y0, i0 - X0:i1 - X0] = np.clip(0.5 - d, 0.0, 1.0)
    return cov


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


def _casilla(foto, w, h, vista, icono):
    """Una casilla en grande (w × h px): la foto recortada a su forma, algo suavizada para que al reducirla no haga
    muaré, y sus vistas abajo a la izquierda (a su tamaño: LETRA y AIRE_VISTAS van en proporción al ancho).
    Devuelve un array uint8 h × w × 3."""
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
    fila, pad, linea = _vistas(vista, icono, LETRA * w)
    aire = AIRE_VISTAS * w
    im.alpha_composite(fila, (int(round(aire - pad)), int(round(h - aire - linea - pad))))
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


def _repartir(n, mitad):
    """Qué imagen va en cada casilla {(fila, columna): índice}, con las filas de -mitad a +mitad. Primero las 8 de
    alrededor (en orden de lectura), después las filas de más lejos. Si hay menos imágenes que casillas se repiten: la que
    menos se ha usado y, entre esas, la que tenga su copia más lejos (así dos iguales nunca quedan pegadas si se puede
    evitar)."""
    orden = [(r, k) for r in (-1, 0, 1) for k in (-1, 0, 1) if (r, k) != (0, 0)]
    for d in range(2, mitad + 1):
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
    e['alejar'] = min(1.2, max(0.5, _num(c.op.get('alejar'), 1.04)))
    icono = str(c.op.get('icono') or 'reproducir').strip().lower()
    icono = {'play': 'reproducir', 'eye': 'ojo', 'ninguno': 'nada', 'no': 'nada'}.get(icono, icono)
    entrada = str(c.op.get('entrada') or 'una').strip().lower()
    e['una'] = entrada not in ('juntas', 'todas', 'alejar')
    asp = _forma(c.op)
    filas = int(round(_num(c.op.get('filas'), 3)))
    mitad = min(3, max(1, (filas - 1) // 2))
    g = max(0.0, _num(c.op.get('hueco'), 20)) * u
    M = max(0.0, _num(c.op.get('margen'), 60)) * u
    e['radio'] = max(0.0, _num(c.op.get('esquinas'), 9)) * u

    # la casilla posada: 3 columnas con su hueco, y la cuadrícula entera (las 3 filas del centro) dentro del margen también
    # cuando la cámara del final se ha acercado del todo
    zmax = max(1.0, e['alejar'])
    w = min(((W - 2 * M) / zmax - 2 * g) / 3.0, ((H - 2 * M) / zmax - 2 * g) / 3.0 * asp)
    w = max(8.0 * u, w)
    h = w / asp
    e.update(g=g, w=w, h=h)
    # el trozo del vídeo que queda en tu casilla (de su misma forma): todo el ancho (o todo el alto), con la cara a un
    # tercio de arriba. Con 9:16 en un vídeo vertical es el vídeo entero
    cx, cy, _ = c.cara
    if W / H <= asp:
        cw, ch = float(W), W / asp
    else:
        cw, ch = H * asp, float(H)
    xc = min(max(cx - cw / 2, 0.0), W - cw)
    yc = min(max(cy - 0.34 * ch, 0.0), H - ch)
    e['recorte'] = (xc, yc, cw, ch)
    k = w / cw                                             # vídeo → cuadrícula posada
    z0 = max(1.0 / k, zmax * 1.05)                         # el acercamiento del principio: el vídeo a pantalla completa
    e.update(k=k, z0=z0)
    # el centro de la cuadrícula posada y el punto fijo de la cámara (el que no se mueve al alejarse): así, al empezar,
    # el vídeo queda exactamente donde estaba
    e['centro'] = np.array([W / 2.0, H / 2.0])
    cc = np.array([xc + cw / 2, yc + ch / 2])
    e['cc'] = cc
    e['fijo'] = (z0 * e['centro'] - cc) / (z0 - 1.0)

    # las casillas de alrededor: qué imagen va en cada una y cuándo llega
    fotos = _fotos(c, 8)
    if not fotos:
        raise ValueError('no hay ninguna imagen para las casillas')
    e['sitio'] = _repartir(len(fotos), mitad)
    orden = ORDEN + [s for s in e['sitio'] if s not in ORDEN]
    # los tiempos (si el efecto dura menos de lo normal, la entrada se aprieta para que quepa)
    entra = ESPERA + CAE + SOLA + (len(orden) - 1) * ESCALONA + APARECE if e['una'] else ESPERA + CAE
    f = min(1.0, 0.55 * c.dur / entra)
    e['cae'] = (ESPERA * f, (ESPERA + CAE) * f)
    e['aparece'] = APARECE * f
    e['llega'] = {s: (ESPERA + CAE + SOLA + i * ESCALONA) * f for i, s in enumerate(orden)}
    t0 = entra * f                                          # la cámara del final arranca con la cuadrícula ya formada
    D = max(1e-3, c.dur - t0)
    norma = D - DERIVA * (1 - math.exp(-D / DERIVA))
    e['deriva'] = lambda t: 0.0 if t <= t0 else \
        ((t - t0) - DERIVA * (1 - math.exp(-(t - t0) / DERIVA))) / max(1e-6, norma)

    vistas = [s.strip() for s in str(c.op.get('vistas') or '').split('|')]
    # copias de cada casilla a varios tamaños fijos (la del final, 1,5 veces esa…, hasta la del principio). En cada cuadro
    # se coge la más pequeña que no sea menor que la casilla en pantalla y se encoge un poco con decimales: así el filtro
    # no cambia de un cuadro a otro (reducir cada vez a un tamaño entero distinto hacía centellear las letras)
    niveles = [zmax]
    while niveles[-1] * PASO_NIVEL < z0 / 1.2:
        niveles.append(niveles[-1] * PASO_NIVEL)
    niveles.append(z0)
    e['niveles'] = niveles
    sw, sh = int(round(z0 * w)), int(round(z0 * h))
    e['mip'] = []
    for i, foto in enumerate(fotos):
        grande = _casilla(foto, sw, sh, vistas[i] if i < len(vistas) else '', icono)
        copias = []
        for s in niveles[:-1]:
            m = cv2.resize(grande, (max(1, int(round(s * w))), max(1, int(round(s * h)))), interpolation=cv2.INTER_AREA)
            copias.append(cv2.GaussianBlur(m, (0, 0), SUAVIZA_NIVEL))
        copias.append(grande)
        e['mip'].append(copias)
    return e


# ── Pintar ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _nivel(niveles, z):
    """El índice de la copia más pequeña que no es menor que `z` (la casilla en pantalla, en veces la posada)."""
    for i, s in enumerate(niveles):
        if s >= z * (1 - 1e-6):
            return i
    return len(niveles) - 1


def _desenfocado(img, destino):
    """El cuadro muy desenfocado (para el fondo), en `destino`: se reduce a 68 px de ancho, se desenfoca y se vuelve a
    agrandar. Sale igual a cualquier resolución y cuesta poco."""
    H, W = img.shape[:2]
    pw = 68
    ph = max(4, int(round(pw * H / W)))
    pequeno = cv2.resize(img, (pw, ph), interpolation=cv2.INTER_AREA)
    pequeno = cv2.GaussianBlur(pequeno, (0, 0), DESENFOQUE, borderType=cv2.BORDER_REFLECT)
    np.clip(cv2.resize(pequeno, (W, H), interpolation=cv2.INTER_CUBIC), 0.0, 1.0, out=destino)


def _pegar(lienzo, src, ex, ey, ax, ay, caja, radio=0.0, alfa=1.0):
    """Pone `src` (alto × ancho × 3, float32 de 0 a 1 o uint8) en el lienzo: su esquina (continua) en (ax, ay) y cada
    píxel de `src` mide ex × ey en pantalla; solo dentro de `caja` (x0, y0, x1, y1 con decimales), con los bordes suaves y
    las esquinas redondeadas de radio `radio`. `alfa` < 1: a medio aparecer."""
    if alfa <= 0.003:
        return
    x0, y0, x1, y1 = caja
    H, W = lienzo.shape[:2]
    X0, Y0 = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
    X1, Y1 = min(W, int(math.ceil(x1))), min(H, int(math.ceil(y1)))
    if X1 <= X0 or Y1 <= Y0:
        return
    M = np.array([[ex, 0.0, 0.5 * ex - 0.5 + ax - X0], [0.0, ey, 0.5 * ey - 0.5 + ay - Y0]], np.float64)
    hecha = cv2.warpAffine(src, M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if hecha.dtype == np.uint8:
        hecha = hecha.astype(np.float32) * np.float32(1.0 / 255.0)
    cov = _cobertura_caja(x0, y0, x1, y1, radio, X0, Y0, X1 - X0, Y1 - Y0)
    if alfa < 0.999:
        cov *= np.float32(alfa)
    zona = lienzo[Y0:Y1, X0:X1]
    if cov.min() >= 0.9999:
        zona[...] = hecha
    else:
        zona += (hecha - zona) * cov[..., None]


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


def _anillo(lienzo, caja, radio, grosor, color, alfa):
    """Un borde fino por dentro de la caja de esquinas redondeadas, con su parte de píxel en cada lado (no tiembla al
    moverse)."""
    if alfa <= 0.003 or grosor <= 0.05:
        return
    x0, y0, x1, y1 = caja
    H, W = lienzo.shape[:2]
    X0, Y0 = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
    X1, Y1 = min(W, int(math.ceil(x1))), min(H, int(math.ceil(y1)))
    if X1 <= X0 or Y1 <= Y0:
        return
    nx, ny = X1 - X0, Y1 - Y0
    fuera = _cobertura_caja(x0, y0, x1, y1, radio, X0, Y0, nx, ny)
    dentro = _cobertura_caja(x0 + grosor, y0 + grosor, x1 - grosor, y1 - grosor, max(0.0, radio - grosor), X0, Y0, nx, ny)
    k = (np.clip(fuera - dentro, 0.0, 1.0) * np.float32(alfa))[..., None]
    zona = lienzo[Y0:Y1, X0:X1]
    zona += (color - zona) * k


def dibujar(c):
    if 'cuadricula' not in c.estado:
        c.estado['cuadricula'] = _preparar(c)
    e = c.estado['cuadricula']
    u, W, H = c.u, c.W, c.H
    t = c.t
    funde = min(FUNDE, 0.15 * c.dur)
    c0, c1 = e['cae']
    p = B.suave(B.tramo(t, c0, c1))                         # cuánto se ha encogido (0 = pantalla completa, 1 = posada)
    # el acercamiento de la cámara: de z0 a 1 (en escala logarítmica: la misma sensación de velocidad grande o pequeña)
    # y, con la cuadrícula ya formada, la cámara lenta del final
    z = math.exp((1.0 - p) * math.log(e['z0']) + math.log(e['alejar']) * e['deriva'](t))
    levanta = 1.0 + LEVANTA * p
    fijo, centro = e['fijo'], e['centro']
    w, h, g = e['w'], e['h'], e['g']

    def a_pantalla(X, Y):
        return fijo[0] + z * (X - fijo[0]), fijo[1] + z * (Y - fijo[1])

    lienzo = e.get('lienzo')
    if lienzo is None or lienzo.shape != c.img.shape:
        lienzo = e['lienzo'] = np.empty_like(c.img)
    if e['fondo'] is None:
        _desenfocado(c.img, lienzo)                         # detrás, tu propio vídeo muy desenfocado
    else:
        lienzo[...] = e['fondo']

    alfa_marca = B.suave(B.tramo(t, c0 + 0.35 * (c1 - c0), c1))   # el borde llega cuando ya casi se ha posado

    # 1) las casillas de alrededor: cada una, desde su copia fija del tamaño que toca, encogida con decimales
    blanco = np.ones(3, np.float32)
    for (r, k), i in e['sitio'].items():
        a, s = 1.0, 1.0
        if e['una']:
            q = B.tramo(t, e['llega'][(r, k)], e['llega'][(r, k)] + e['aparece'])
            if q <= 0.0:
                continue
            a = B.sale(min(1.0, q * 1.4))                   # el fundido, algo antes que el tamaño
            s = CRECE + (1.0 - CRECE) * B.sale(q)
        X = centro[0] + k * (w + g)
        Y = centro[1] + r * (h + g)
        sx, sy = a_pantalla(X, Y)
        mw, mh = 0.5 * z * s * w, 0.5 * z * s * h
        caja = (sx - mw, sy - mh, sx + mw, sy + mh)
        if caja[2] <= 0 or caja[0] >= W or caja[3] <= 0 or caja[1] >= H:
            continue
        m = e['mip'][i][_nivel(e['niveles'], z * s)]
        radio = e['radio'] * z * s
        _pegar(lienzo, m, 2 * mw / m.shape[1], 2 * mh / m.shape[0], caja[0], caja[1], caja, radio, a)
        _anillo(lienzo, caja, radio, FILO * u * min(z * s, 1.6), blanco, FILO_ALFA * a)

    # 2) tu casilla: el vídeo, recortándose (si hace falta) a la forma de la casilla mientras se encoge
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
    radio = e['radio'] * z * levanta * p                    # a pantalla completa, sin redondeo (entra sin salto)
    if e['fondo'] is not None:
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
    s = e['niveles'][_nivel(e['niveles'], z)] * e['k'] * levanta
    vw = min(ix1 - ix0, max(1, int(math.ceil((ix1 - ix0) * s - 1e-6))))
    vh = min(iy1 - iy0, max(1, int(math.ceil((iy1 - iy0) * s - 1e-6))))
    reducido = _reducir(src, vw, vh)
    if vw < 0.8 * (ix1 - ix0):
        reducido = cv2.GaussianBlur(reducido, (0, 0), SUAVIZA_NIVEL)
    ax, ay = video_a_pantalla(ix0, iy0)
    _pegar(lienzo, reducido, zk * (ix1 - ix0) / vw, zk * (iy1 - iy0) / vh, ax, ay, caja, radio)
    _anillo(lienzo, caja, radio, BORDE * u * min(z, 1.6), e['color'], 0.95 * alfa_marca)

    # 3) el fundido del final: vuelve el vídeo tal cual
    a = B.tramo(c.queda, 0.0, funde)
    if a >= 0.999:
        np.copyto(c.img, lienzo)
    else:
        lienzo -= c.img
        lienzo *= np.float32(B.suave(a))
        c.img += lienzo
