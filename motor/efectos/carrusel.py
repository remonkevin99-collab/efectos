"""Carrusel: tus Reels salen de la pantalla del móvil y giran en un anillo que flota encima de él.

En el plano hay un móvil (en la mano o de pie en la mesa, con la pantalla hacia la cámara). De su pantalla salen de 5 a 10
tarjetas (8 por defecto): nacen pequeñas en la parte de arriba de la pantalla y en ~0,3 s se abren en un anillo que flota
JUSTO ENCIMA del móvil, con el eje en el móvil. Las de delante bajan un poco por delante del borde de arriba de la
pantalla; las de atrás quedan detrás de las de delante, algo más altas y más pequeñas. El móvil se sigue viendo debajo
(28 oct 2026: antes las fotos salían por encima del móvil, sin rodearlo).

El anillo arranca girando rápido (~65 px por cuadro delante, como la referencia) y a los ~0,6 s empieza a frenar. La
tarjeta que se pida con `destaca` sale por delante, da una vuelta entera y vuelve a quedar delante, en el centro, justo
cuando el anillo se queda casi quieto: a los 2,2 s (o justo antes del final); después gira muy despacio. Las tarjetas
van de verdad pegadas al anillo (tangentes): en los lados se ven de canto, como en un carrusel 3D. Van nítidas, como las
de ella: solo llevan un desenfoque de movimiento muy ligero en el arranque rápido. Al final se apagan con un fundido de
0,3 s (encogiéndose un poco).

Con persona en el plano: las de la parte de atrás del anillo pasan DETRÁS de ella (y del móvil, cuando el recorte lo
incluye: el del Mac lo incluye si está en la mano), con su máscara y el color de verdad de su borde, como la órbita. Si
hay una cara de verdad justo encima del móvil, las de delante nunca se la tapan: el anillo baja lo justo (o se hace más
pequeño). Sin persona (un plano del móvil solo), todas van por encima.

Cada tarjeta lleva abajo una pastilla con un ojo y sus vistas (`vistas`), y la que se pida con `destaca` lleva ese número
grande con un brillo dorado DETRÁS de la letra (la letra, nítida encima).

Las fotos:
  - `imagenes=<carpeta>`: las de esa carpeta (jpg, png o webp), ordenadas por nombre; si hay menos que `cantidad`, se
    repiten.
  - si no se da carpeta: cuadros del propio vídeo (`c.estado['sacar_cuadros']`), como la órbita.
  - y si tampoco hay motor: trozos del cuadro de ese momento.

    python efectos.py carrusel mi-video.mp4 --desde 2 --hasta 5 --op imagenes=mis-reels --op movil=540,1350
    python efectos.py carrusel mi-video.mp4 --desde 2 --hasta 5 --op imagenes=mis-reels --op "vistas=1M|120K|8K"
        --op destaca=1M --op ancho_movil=380
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import base as B

NOMBRE = 'carrusel'
DESCRIPCION = 'Tus Reels salen de tu móvil y giran en un carrusel encima de él'
OPCIONES = {
    # la carpeta con las portadas de tus Reels (jpg, png o webp; van ordenadas por nombre). Vacío: cuadros de tu vídeo
    'imagenes': '',
    # las vistas de cada tarjeta, en el mismo orden que las imágenes, separadas por «|» (por ejemplo «1M|120K|8K»).
    # Vacío = sin pastillas. Un hueco vacío («1M||8K») deja esa tarjeta sin pastilla
    'vistas': '',
    # un número que sale GRANDE, con un brillo dorado detrás, en la tarjeta que pasa por delante (por ejemplo «1M»). Si
    # coincide con unas `vistas`, va en esa tarjeta. Vacío = ninguno
    'destaca': '',
    # dónde está la pantalla del móvil, en píxeles de un vídeo de 1080 × 1920 («x,y»: su centro)
    'movil': '540,1350',
    # el ancho del móvil en el vídeo (en píxeles de 1080 de ancho)
    'ancho_movil': '240',
    # el alto del móvil en el vídeo (en píxeles de 1080 de ancho). Marca su borde de arriba: el anillo flota justo encima.
    # Vacío = 2 veces el ancho (un móvil de frente). Si el móvil está muy inclinado hacia atrás, se ve más bajo: ponlo
    'alto_movil': '',
    # cuántas tarjetas (de 5 a 10)
    'cantidad': '8',
    # el ancho de la tarjeta de delante, en píxeles de 1080 de ancho (si el carrusel no cabe, se hace más pequeño)
    'tamano': '260',
    # la forma de las tarjetas: «9:16» (como un Reel) o «3:4» (como en la cuadrícula del perfil)
    'proporcion': '9:16',
    # el giro lento del final: 1 = una vuelta cada 30 s; 2 = el doble de rápido; 0 = se para; en negativo, gira al revés.
    # El arranque rápido es siempre una vuelta entera que frena (la destacada vuelve delante)
    'velocidad': '1',
}
DURACION = 3.0

VUELTA = 30.0           # segundos por vuelta del giro lento del final, con velocidad 1 (casi quieto, pero vivo)
FRENTE = 2.2            # a qué segundo termina la vuelta entera y la destacada queda delante (si el efecto es corto,
                        # antes: justo antes del fundido, que es cuando se corta). Medido en la referencia: 2,2 s
LLENO = 0.27            # la parte de ese tiempo que gira a toda velocidad; después frena en línea recta (la referencia:
                        # ~65 px por cuadro hasta los 0,6 s y frenando hasta pararse a los 2,2 s)
SALIDA = 0.35           # lo que tarda el anillo en abrirse desde la pantalla (frena al final: casi todo en 0,15 s)
APARECE = 0.2           # el fundido de entrada
FUNDIDO = 0.3           # el fundido del final
INICIO = 0.18           # el tamaño con el que nacen las tarjetas en la pantalla (veces el suyo)
INICIO_R = 0.1          # y el del anillo
NACE = 0.28             # dónde nacen: a esta parte del alto del móvil, desde su borde de arriba
SOLAPE = 0.16           # cuánto bajan las de delante por delante del móvil (veces el ancho del móvil)
RADIO = 1.65            # el radio del anillo (veces el ancho de la tarjeta), como la referencia
INCLINA = math.radians(8)    # la cámara mira el anillo un poco desde arriba: las de atrás quedan algo más altas
LEJOS = 5.9             # la distancia de la cámara (veces el radio): la de atrás sale al ~70 % de la de delante
OSCURO_ATRAS = 0.3      # cuánto se oscurece la de más atrás
DETRAS = -0.5           # de qué profundidad (1 = delante, −1 = atrás) para atrás van detrás de la persona
CRUCE = 0.12            # cuánto antes y después de esa profundidad se desvanece la que cruza por encima de la persona
OBTURADOR = 0.15        # un desenfoque de movimiento muy ligero: lo que recorre en 0,15 de cuadro (a ~65 px por cuadro,
                        # 10 px). Con 0,5 (una cámara a 180°) las tarjetas se emborronan y no se parece al de la referencia, que
                        # va nítido; sin nada, el contenido de las tarjetas «salta» en el arranque rápido
PASO_BORRON = 3         # una copia de la tarjeta cada tantos px de ese recorrido (a 1080 de ancho): sin escalones
BORRON_MAX = 6          # y como mucho tantas copias
MARGEN = 60             # la zona segura (a 1080 de ancho)
ARRIBA = 210            # y lo más alto que puede llegar el anillo (a 1920 de alto)
NIVELES = [1.0, 0.707, 0.5, 0.354, 0.25, 0.177, 0.125]   # las copias de cada tarjeta, de grande a pequeña


# ── Opciones ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _num(v, defecto):
    """Un número de una opción, con coma o con punto («1,3» = «1.3»). Si no es un número, el de por defecto."""
    try:
        return float(str(v).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return float(defecto)


def _punto(v, defecto):
    """«540,1350» (o «540;1350», «540 1350», «540x1350») → (540.0, 1350.0)."""
    s = str(v or '').strip().lower()
    for sep in (';', 'x', ' '):
        s = s.replace(sep, ',')
    trozos = [p for p in s.split(',') if p.strip()]
    if len(trozos) == 2:
        try:
            return float(trozos[0]), float(trozos[1])
        except ValueError:
            pass
    if s:
        print(f'  Aviso (carrusel): «{v}» en `movil` no es «x,y»; uso {defecto[0]:g},{defecto[1]:g}.')
    return defecto


def _proporcion(v):
    """«9:16» → 16/9 (alto entre ancho). También «3:4», «9/16» o «1,78»."""
    s = str(v or '').strip().replace('/', ':').replace(',', '.')
    try:
        if ':' in s:
            a, b = (float(x) for x in s.split(':', 1))
            return max(0.5, min(3.0, b / a))
        return max(0.5, min(3.0, float(s)))
    except (ValueError, ZeroDivisionError):
        if s:
            print(f'  Aviso (carrusel): «{v}» en `proporcion` no es «9:16» ni «3:4»; uso 9:16.')
        return 16 / 9


def _vistas(v):
    s = str(v or '').strip()
    return [p.strip() for p in s.split('|')] if s else []


def _igual(a, b):
    return a.replace(' ', '').replace('.', ',').lower() == b.replace(' ', '').replace('.', ',').lower()


# ── Las tarjetas ────────────────────────────────────────────────────────────────────────────────────────────────────
def _premultiplicada(capa):
    a = np.asarray(capa, np.float32) * (1.0 / 255.0)
    a[..., :3] *= a[..., 3:4]
    return np.ascontiguousarray(a)


def _cubrir(im, w, h, arriba=0.35):
    """La imagen recortada para llenar w × h sin deformarse (si sobra alto, se queda más con la parte de arriba)."""
    im = im.convert('RGBA')
    k = max(w / im.width, h / im.height)
    nw, nh = max(w, int(math.ceil(im.width * k))), max(h, int(math.ceil(im.height * k)))
    im = im.resize((nw, nh), Image.LANCZOS)
    x0 = (nw - w) // 2
    y0 = int(round((nh - h) * arriba))
    return im.crop((x0, y0, x0 + w, y0 + h))


def _justo(capa):
    """La capa recortada a lo que tiene dibujado (para centrar el texto por su letra, no por su caja)."""
    caja = capa.split()[3].getbbox()
    return capa.crop(caja) if caja else capa


def _ojo(alto, color=(255, 255, 255, 255)):
    """Un ojo (almendra con la pupila), dibujado a 4 veces y reducido para que el borde salga suave."""
    k = 4
    W, H = max(4, int(round(alto * 1.6 * k))), max(4, int(round(alto * k)))
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    g = 0.12 * H
    xs = np.linspace(-1.0, 1.0, 48)
    arriba = [(W / 2 + x * (W / 2 - g), H / 2 - (H / 2 - g) * (1 - x * x)) for x in xs]
    abajo = [(W / 2 + x * (W / 2 - g), H / 2 + (H / 2 - g) * (1 - x * x)) for x in xs[::-1]]
    d.line(arriba + abajo[1:] + [arriba[0]], fill=color, width=max(1, int(round(g))), joint='curve')
    r = 0.25 * H
    d.ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=color)
    return im.resize((W // k, H // k), Image.LANCZOS)


def _pastilla(vista, cw):
    """La pastilla de las vistas: fondo oscuro translúcido, un ojo y el número, en blanco."""
    tam = 0.118 * cw
    txt = _justo(B.texto(vista, tam, 'bold'))
    ojo = _ojo(0.62 * tam)
    alto = int(round(tam * 1.5))
    hueco = 0.42 * tam
    ancho = int(round(0.55 * tam + ojo.width + hueco + txt.width + 0.62 * tam))
    p = B.caja(ancho, alto, alto / 2, (10, 10, 14, 165))
    x = 0.55 * tam
    p.alpha_composite(ojo, (int(round(x)), int(round((alto - ojo.height) / 2))))
    x += ojo.width + hueco
    p.alpha_composite(txt, (int(round(x)), int(round((alto - txt.height) / 2))))
    return p


def _brillo_dorado(w, h, cx, cy, rx, ry, fuerza=0.9):
    """Un brillo dorado redondo con rayos de luz que salen del centro (en float, sin escalones), como capa RGBA w × h."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = (xs - cx) / rx, (ys - cy) / ry
    d2 = dx ** 2 + dy ** 2
    a = fuerza * np.exp(-1.6 * d2)
    # los rayos (como el número grande de la referencia): finos, de largo distinto, y se apagan hacia fuera
    ang = np.arctan2(dy, dx)
    rayos = np.clip(np.cos(12 * ang), 0, 1) ** 6 * (0.55 + 0.45 * np.cos(5 * ang + 0.7) ** 2)
    a = a + 0.85 * rayos * np.exp(-0.55 * d2) * np.clip(np.sqrt(d2) / 0.35, 0, 1)
    a = np.clip(a, 0, 1)
    rgb = np.empty((h, w, 3), np.float32)
    # del centro, casi blanco cálido, hacia el borde, oro
    k = np.exp(-3.5 * d2)[..., None]
    rgb[:] = np.array([255, 178, 36], np.float32) * (1 - k) + np.array([255, 236, 170], np.float32) * k
    out = np.dstack([rgb, a * 255]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def _numero(cara, numero, cw, ch):
    """El número grande con su brillo dorado detrás (sobre la foto de la tarjeta, ya recortada)."""
    tam = 0.40 * cw
    txt = _justo(B.texto(numero, tam, 'extrabold', relleno=(255, 250, 236, 255)))
    if txt.width > 0.86 * cw:                              # un número largo: más pequeño, que quepa
        k = 0.86 * cw / txt.width
        txt = _justo(B.texto(numero, tam * k, 'extrabold', relleno=(255, 250, 236, 255)))
    cx, cy = cw / 2, 0.58 * ch                            # por debajo del título de la portada
    # 1) el brillo redondo, con sus rayos, detrás
    cara.alpha_composite(_brillo_dorado(cw, ch, cx, cy, 0.62 * cw, 0.42 * cw, 0.92))
    # 2) un resplandor con la forma del número, también detrás
    pad = int(0.12 * cw)
    sombra = Image.new('RGBA', (txt.width + 2 * pad, txt.height + 2 * pad), (0, 0, 0, 0))
    a = txt.split()[3]
    oro = Image.new('RGBA', txt.size, (255, 170, 20, 255))
    oro.putalpha(a)
    sombra.alpha_composite(oro, (pad, pad))
    sombra = sombra.filter(ImageFilter.GaussianBlur(0.045 * cw))
    x0, y0 = int(round(cx - sombra.width / 2)), int(round(cy - sombra.height / 2))
    cara.alpha_composite(sombra, (x0, y0))
    cara.alpha_composite(sombra, (x0, y0))
    # 3) un filo oscuro muy fino pegado a la letra (que se recorte nítida sobre el oro) y la letra encima
    filo = Image.new('RGBA', (txt.width + 8, txt.height + 8), (0, 0, 0, 0))
    osc = Image.new('RGBA', txt.size, (92, 52, 0, 255))
    osc.putalpha(a.point(lambda v: v * 150 // 255))
    filo.alpha_composite(osc, (4, 4 + max(1, int(0.006 * cw))))
    filo = filo.filter(ImageFilter.GaussianBlur(max(0.8, 0.006 * cw)))
    cara.alpha_composite(filo, (int(round(cx - txt.width / 2)) - 4, int(round(cy - txt.height / 2)) - 4))
    cara.alpha_composite(txt, (int(round(cx - txt.width / 2)), int(round(cy - txt.height / 2))))


def _tarjeta(foto, cw, ch, u, vista='', numero=''):
    """Una tarjeta: la foto con las esquinas redondeadas, el número grande (si lo lleva), la pastilla de las vistas, un
    filo blanco fino y una sombra suave. Devuelve (capa premultiplicada, margen de la sombra)."""
    r = 0.075 * cw
    cara = _cubrir(foto, cw, ch)
    if numero:
        _numero(cara, numero, cw, ch)
    if vista:
        p = _pastilla(vista, cw)
        cara.alpha_composite(p, (int(round((cw - p.width) / 2)), int(round(ch - 0.055 * ch - p.height))))
    cara = B.recortar_redondo(cara, r)
    cara.alpha_composite(B.caja(cw, ch, r, (0, 0, 0, 0), borde=(255, 255, 255, 170), grosor=max(1.0, 2.0 * u)))
    capa = B.con_sombra(cara, 16 * u, 10 * u, 115)
    return _premultiplicada(capa), (capa.width - cw) // 2


def _fotos(c, cantidad):
    carpeta = (c.op.get('imagenes') or '').strip()
    fotos = B.imagenes_de(carpeta)
    if fotos:
        return fotos
    if carpeta:
        print(f'  Aviso (carrusel): no encuentro imágenes en «{carpeta}»; uso cuadros del propio vídeo.')
    sacar = c.estado.get('sacar_cuadros')
    if callable(sacar):
        fotos = sacar(cantidad)
        if fotos:
            return fotos
    W, H = c.W, c.H
    tw, th = int(W * 0.42), int(W * 0.56)
    sitios = [(0.05, 0.03), (0.52, 0.06), (0.0, 0.62), (0.55, 0.58), (0.28, 0.30), (0.3, 0.74), (0.6, 0.35),
              (0.15, 0.45), (0.45, 0.15), (0.7, 0.7)]
    out = []
    for fx, fy in sitios[:cantidad]:
        x0, y0 = int(fx * (W - tw)), int(fy * (H - th))
        out.append(B.a_capa(c.img[y0:y0 + th, x0:x0 + tw]))
    return out


# ── La geometría ────────────────────────────────────────────────────────────────────────────────────────────────────
def _esquinas(e, phi, g=None):
    """Las 4 esquinas en pantalla (arriba izq., arriba der., abajo der., abajo izq.) de la tarjeta en el ángulo `phi` del
    anillo (0 = delante), y su profundidad (1 = delante, −1 = atrás). `g`: el anillo en ese momento (radio, tamaño de la
    tarjeta y centro; mientras se abre es más pequeño). La tarjeta va tangente al anillo: en los lados se ve de canto.
    Cuando se ve por su cara de dentro, se da la vuelta para que la foto se lea bien (en ese cambio está de canto: no
    salta). Devuelve (None, z) si está tan de canto que no se ve."""
    g = g or e
    R, w, h = g['R'], g['w'], g['h']
    X, Z = R * math.sin(phi), -R * math.cos(phi)               # Z: hacia el fondo
    rx, rz = math.cos(phi), math.sin(phi)                     # tangente al anillo
    ct, st = math.cos(INCLINA), math.sin(INCLINA)
    D, f = e['D'], e['f']
    out = np.empty((4, 2), np.float64)
    for j, (a, b) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        x = X + a * rx * w / 2
        y = b * h / 2
        z = Z + a * rz * w / 2
        yy = y * ct - z * st                                 # la cámara, un poco desde arriba
        zz = y * st + z * ct
        p = f / (D + zz)
        out[j] = (g['Cx'] + x * p, g['Cy'] + yy * p)
    x_, y_ = out[:, 0], out[:, 1]
    area = 0.5 * float(np.dot(x_, np.roll(y_, -1)) - np.dot(np.roll(x_, -1), y_))
    alto = 0.5 * (abs(out[3, 1] - out[0, 1]) + abs(out[2, 1] - out[1, 1]))
    if abs(area) < 0.8 * max(1.0, alto) * e['u']:           # de canto: menos de ~1 px de ancho
        return None, math.cos(phi)
    if area < 0:                                             # se ve por dentro: la foto, al derecho
        out = out[[1, 0, 3, 2]]
    return out, math.cos(phi)


def _giro(t, e):
    """El ángulo girado hasta `t` (solo depende de `t`: da igual el orden de los cuadros). Gira a toda velocidad hasta
    `e['lleno']` s, frena en línea recta (sin saltos de velocidad) y a los `e['frente']` s ha dado justo una vuelta y va
    al giro lento."""
    t1, L = e['lleno'], e['frente'] - e['lleno']
    if t <= t1:
        g = t
    elif t <= e['frente']:
        g = t - (t - t1) ** 2 / (2 * L)
    else:
        g = t1 + L / 2
    return e['w0'] * t + e['empuje'] * g


def _abre(t):
    """Cuánto se ha abierto el anillo (0 = en la pantalla, 1 = en su sitio)."""
    return B.sale(B.tramo(t, 0.0, SALIDA))


def _anillo(e, k):
    """El anillo cuando se ha abierto `k`: sale de la pantalla pequeño y crece mientras sube a su sitio."""
    s = INICIO + (1.0 - INICIO) * k
    return {'R': e['R'] * (INICIO_R + (1.0 - INICIO_R) * k), 'w': e['w'] * s, 'h': e['h'] * s,
            'Cx': e['mx'] + (e['Cx'] - e['mx']) * k, 'Cy': e['Cy0'] + (e['Cy'] - e['Cy0']) * k}


def _profundidad(e, k, t):
    """La profundidad de la tarjeta k en el segundo t (1 = delante, −1 = atrás), contando que al salir nace delante."""
    z = math.cos(e['phi0'] + 2 * math.pi * k / e['n'] + _giro(t, e))
    return 1.0 + (z - 1.0) * _abre(t)


def _alcance(e):
    """(izquierda, derecha, arriba, abajo de la de delante) de todo el anillo en una vuelta, respecto a su centro."""
    iz = de = 0.0
    arriba = math.inf
    for phi in np.linspace(0, 2 * math.pi, 73):
        q, _ = _esquinas(e, phi)
        if q is None:
            continue
        iz, de = max(iz, e['Cx'] - q[:, 0].min()), max(de, q[:, 0].max() - e['Cx'])
        arriba = min(arriba, q[:, 1].min())
    q, _ = _esquinas(e, 0.0)
    return iz, de, arriba, q[:, 1].max()


def _choca_cara(e, cara):
    """Cuánto habría que bajar el anillo para que ninguna tarjeta que va por encima de la persona le pise la cara."""
    fx, fb, fa = cara
    peor = 0.0
    for phi in np.linspace(0, 2 * math.pi, 73):
        q, z = _esquinas(e, phi)
        if q is None or z < DETRAS:
            continue
        if q[:, 0].max() < fx - fa or q[:, 0].min() > fx + fa:
            continue
        peor = max(peor, fb - q[:, 1].min())
    return peor


def _preparar(c):
    u = c.u
    W, H = c.W, c.H
    cantidad = int(min(10, max(5, round(_num(c.op.get('cantidad'), 8)))))
    fotos = _fotos(c, cantidad)
    if not fotos:
        raise ValueError('no hay ninguna imagen para las tarjetas')
    # tantas tarjetas como fotos (hasta `cantidad`): con 5 fotos, 5 tarjetas, sin repetir ninguna; con menos de 5, se
    # repiten hasta llegar a 5
    n = max(5, min(cantidad, len(fotos)))
    vistas = _vistas(c.op.get('vistas'))
    destaca = str(c.op.get('destaca') or '').strip()
    # la tarjeta k lleva la foto k (las fotos se repiten si hay menos) y las vistas de esa foto
    idx = [k % len(fotos) for k in range(n)]
    vista_de = [vistas[i] if i < len(vistas) else '' for i in idx]
    hk = 0
    if destaca:
        for k in range(n):
            if vista_de[k] and _igual(vista_de[k], destaca):
                hk = k
                break
    mx, my = _punto(c.op.get('movil'), (540.0, 1350.0))
    mx, my = mx * W / 1080.0, my * H / 1920.0
    am = max(40.0, _num(c.op.get('ancho_movil'), 240)) * u
    hm = _num(c.op.get('alto_movil'), 0) * u
    hm = hm if hm > am * 0.5 else 2.0 * am
    techo = my - hm / 2                                        # el borde de arriba del móvil
    prop = _proporcion(c.op.get('proporcion'))

    w = max(60.0, _num(c.op.get('tamano'), 260)) * u
    e = {'n': n, 'mx': mx, 'my': my, 'am': am, 'hk': hk, 'u': u, 'techo': techo}

    def medidas(w, baja=0.0):
        h = w * prop
        R = max(0.6 * w / math.sin(math.pi / n), RADIO * w)   # abierto, y que las de delante no se pisen
        D = LEJOS * R
        e.update(w=w, h=h, R=R, D=D, f=D - R * math.cos(INCLINA), Cx=e.get('Cx', mx), Cy=0.0)
        # la de delante, con su borde de abajo un poco por delante del borde de arriba del móvil
        q, _ = _esquinas(e, 0.0)
        e['Cy'] = techo + SOLAPE * am + baja - q[:, 1].max()

    e['Cx'] = mx
    medidas(w)
    # que quepa en la zona segura, de lado: todo es proporcional al tamaño, así que se encoge entero
    util = W - 2 * MARGEN * u
    iz, de, _, _ = _alcance(e)
    if iz + de > util:
        medidas(e['w'] * util / (iz + de) * 0.995)
    # y por arriba: si sube más de la cuenta, más pequeño (con el borde de abajo en su sitio)
    for _ in range(4):
        iz, de, arriba, abajo = _alcance(e)
        if arriba >= ARRIBA * H / 1920.0:
            break
        medidas(e['w'] * max(0.3, (abajo - ARRIBA * H / 1920.0) / max(1.0, abajo - arriba)) * 0.995)
    iz, de, _, _ = _alcance(e)
    e['Cx'] = min(max(mx, MARGEN * u + iz), W - MARGEN * u - de)

    # con una cara de verdad justo encima del móvil: que las de delante no se la pisen. Si el motor no encuentra cara, da
    # una aproximada (que puede caer en el árbol de detrás o en una foto de la pantalla): solo vale si es persona (su
    # máscara) y está por encima del móvil
    hay = float(c.mascara[::8, ::8].max()) > 0.5
    cx, cy, fw = c.cara
    x0, x1 = int(max(0, cx - fw / 2)), int(min(W, cx + fw / 2))
    y0, y1 = int(max(0, cy - fw / 2)), int(min(H, cy + fw / 2))
    es_persona = x1 > x0 and y1 > y0 and float(c.mascara[y0:y1, x0:x1].mean()) > 0.5
    e['cara'] = hay and es_persona and (cy + 0.85 * fw < techo)
    if e['cara']:
        baja = 0.0
        for _ in range(6):
            mas = _choca_cara(e, (cx, cy + 0.85 * fw + 12 * u, 0.75 * fw))
            if mas <= 0:
                break
            hueco = max(0.0, (my - techo) - SOLAPE * am - baja)   # puede bajar hasta la mitad de la pantalla
            if mas <= hueco:
                baja += mas
                medidas(e['w'], baja)
                break
            baja += hueco
            medidas(e['w'] * 0.9, baja)                        # no cabe bajando: más pequeño
            iz, de, _, _ = _alcance(e)
            e['Cx'] = min(max(mx, MARGEN * u + iz), W - MARGEN * u - de)

    # dónde nace: en la parte de arriba de la pantalla
    e['Cy0'] = techo + NACE * hm - INICIO_R * e['R'] * math.sin(INCLINA)

    # el giro: la destacada (o la primera) sale delante, da una vuelta entera frenando y vuelve delante a los `frente` s
    vel = _num(c.op.get('velocidad'), 1)
    signo = -1.0 if vel < 0 else 1.0
    e['w0'] = 2 * math.pi * vel / VUELTA
    e['frente'] = min(FRENTE, max(0.9, 0.98 * (c.dur - FUNDIDO)))
    e['lleno'] = LLENO * e['frente']
    e['empuje'] = (signo * 2 * math.pi - e['w0'] * e['frente']) / (e['lleno'] + (e['frente'] - e['lleno']) / 2)
    e['phi0'] = -2 * math.pi * hk / n

    # las tarjetas, en copias de varios tamaños (reducir mucho al vuelo hace dientes); la destacada, con su número
    e['capas'] = []
    for k in range(n):
        foto = fotos[idx[k]]
        lleva_num = bool(destaca) and k == hk
        vista = '' if (lleva_num and vista_de[k] and _igual(vista_de[k], destaca)) else vista_de[k]
        copias = []
        for L in NIVELES:
            cw, ch = max(8, int(round(e['w'] * L))), max(8, int(round(e['h'] * L)))
            copias.append(_tarjeta(foto, cw, ch, u * L, vista, destaca if lleva_num else '') + (cw, ch))
        e['capas'].append(copias)
    return e


# ── Pintar ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _deformar(nivel, quad, W, H):
    """La copia de la tarjeta llevada a las 4 esquinas `quad` (perspectiva) → (capa, X0, Y0) o None. Si sale mucho más
    estrecha que la copia (de canto), antes se estrecha la copia con un filtro de área: si no, la foto hace dientes."""
    capa, pad, cw, ch = nivel
    lh, lw = capa.shape[:2]
    ancho = max(np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[2] - quad[3]))
    kx = 1.0
    if ancho < 0.7 * cw:
        nw = max(4, int(round(lw * ancho / cw / 0.7)))
        if nw < lw:
            capa = cv2.resize(capa, (nw, lh), interpolation=cv2.INTER_AREA)
            kx = nw / lw
            lw = nw
    src = np.float32([[pad * kx - 0.5, pad - 0.5], [(pad + cw) * kx - 0.5, pad - 0.5],
                      [(pad + cw) * kx - 0.5, pad + ch - 0.5], [pad * kx - 0.5, pad + ch - 0.5]])
    dst = np.float32(quad - 0.5)
    M = cv2.getPerspectiveTransform(src, dst)
    borde = np.float32([[[-0.5, -0.5]], [[lw - 0.5, -0.5]], [[lw - 0.5, lh - 0.5]], [[-0.5, lh - 0.5]]])
    fuera = cv2.perspectiveTransform(borde, M).reshape(4, 2)
    if not np.all(np.isfinite(fuera)):
        return None
    X0, Y0 = max(0, int(math.floor(fuera[:, 0].min())) - 1), max(0, int(math.floor(fuera[:, 1].min())) - 1)
    X1, Y1 = min(W, int(math.ceil(fuera[:, 0].max())) + 2), min(H, int(math.ceil(fuera[:, 1].max())) + 2)
    if X1 <= X0 or Y1 <= Y0:
        return None
    T = np.array([[1, 0, -X0], [0, 1, -Y0], [0, 0, 1]], np.float64)
    hecha = cv2.warpPerspective(capa, T @ M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return hecha, X0, Y0


def _tarjeta_en(e, k, quad, W, H):
    """La tarjeta k en su sitio, mezclando las dos copias de tamaño más cercanas (sin saltos de nitidez al crecer). La
    copia se escoge por el alto (de canto, el ancho lo arregla `_deformar`)."""
    lados = np.linalg.norm(np.roll(quad, -1, axis=0) - quad, axis=1)
    s = max(lados[1], lados[3]) / e['h']
    if s >= NIVELES[0]:
        partes = [(0, 1.0)]
    elif s <= NIVELES[-1]:
        partes = [(len(NIVELES) - 1, 1.0)]
    else:
        i = max(j for j in range(len(NIVELES)) if NIVELES[j] >= s)
        k_ = math.log(NIVELES[i] / s) / math.log(NIVELES[i] / NIVELES[i + 1])
        partes = [(i, 1.0)] if k_ < 0.01 else [(i, 1.0 - k_), (i + 1, k_)]
    copias = e['capas'][k]
    return _juntar([(_deformar(copias[i], quad, W, H), p) for i, p in partes])


def _juntar(partes):
    """Suma capas ya deformadas [((capa, X0, Y0), peso), …] en una sola (las que son None no suman nada)."""
    partes = [(h, p) for h, p in partes if h is not None]
    if not partes:
        return None
    if len(partes) == 1 and abs(partes[0][1] - 1.0) < 1e-6:
        return partes[0][0]
    X0 = min(h[1] for h, _ in partes)
    Y0 = min(h[2] for h, _ in partes)
    X1 = max(h[1] + h[0].shape[1] for h, _ in partes)
    Y1 = max(h[2] + h[0].shape[0] for h, _ in partes)
    out = np.zeros((Y1 - Y0, X1 - X0, 4), np.float32)
    for (a, ax, ay), p in partes:
        out[ay - Y0:ay - Y0 + a.shape[0], ax - X0:ax - X0 + a.shape[1]] += a * np.float32(p)
    return out, X0, Y0


def _componer(c, hecha, alfa, tapa, brillo, persona):
    """Pone una tarjeta ya deformada (premultiplicada). `tapa`: 0 = encima de la persona, 1 = detrás (con el color de
    verdad de su borde, `persona`, como la órbita). `brillo`: menos de 1, más oscura."""
    capa, X0, Y0 = hecha
    X1, Y1 = X0 + capa.shape[1], Y0 + capa.shape[0]
    r_, g_, b_, a_ = cv2.split(capa)
    rgb = cv2.merge([r_, g_, b_])
    cubre = a_ * np.float32(alfa)
    zona = c.img[Y0:Y1, X0:X1]
    m = c.mascara[Y0:Y1, X0:X1] if tapa > 0.003 else None
    if m is not None and float(m.max()) > 0.004:
        encima = np.float32(tapa) * m
        peso = (1.0 - encima) * np.float32(alfa * brillo)
        F = zona.copy()
        for Fb, bx0, by0, bx1, by1 in persona or ():
            ix0, iy0, ix1, iy1 = max(X0, bx0), max(Y0, by0), min(X1, bx1), min(Y1, by1)
            if ix1 > ix0 and iy1 > iy0:
                F[iy0 - Y0:iy1 - Y0, ix0 - X0:ix1 - X0] = Fb[iy0 - by0:iy1 - by0, ix0 - bx0:ix1 - bx0]
        tapada = cubre * encima
        nuevo = cv2.add(cv2.multiply(rgb, cv2.merge([peso, peso, peso])), cv2.multiply(F, cv2.merge([tapada] * 3)))
    else:
        nuevo = rgb * np.float32(alfa * brillo)
    queda = 1.0 - cubre
    cv2.multiply(zona, cv2.merge([queda, queda, queda]), dst=zona)
    cv2.add(zona, nuevo, dst=zona)


def _quad_en(e, c, k, ts):
    """Las esquinas de la tarjeta k en el segundo `ts` (con el anillo abriéndose, el encogerse del final y sin pisar la
    cara) y su profundidad ahora (al salir de la pantalla, delante). (None, profundidad) si está de canto."""
    abre = _abre(ts)
    phi = e['phi0'] + 2 * math.pi * k / e['n'] + _giro(ts, e)
    quad, z = _esquinas(e, phi, _anillo(e, abre))
    zc = 1.0 + (z - 1.0) * abre
    if quad is None:
        return None, zc
    # al final, se encoge un poco mientras se apaga
    fin = B.suave(B.tramo(c.dur - ts, 0.0, FUNDIDO))
    cq = quad.mean(axis=0)
    quad = cq + (quad - cq) * (0.88 + 0.12 * fin)
    # nunca encima de la cara: si una de las de encima la pisaría, baja lo justo
    tapa = 1.0 - B.suave(B.tramo(zc, DETRAS - 0.02, DETRAS + 0.02))
    if e['cara'] and tapa < 0.999:
        cx, cy, fw = c.cara
        x0, x1 = quad[:, 0].min(), quad[:, 0].max()
        solape = min(x1, cx + 0.75 * fw) - max(x0, cx - 0.75 * fw)
        if solape > 0:
            baja = max(0.0, (cy + 0.85 * fw + 8 * c.u) - quad[:, 1].min())
            quad = quad + np.array([0.0, baja * (1.0 - tapa) * min(1.0, solape / (30 * c.u))])
    return quad, zc


def dibujar(c):
    if 'carrusel' not in c.estado:
        c.estado['carrusel'] = _preparar(c)
    e = c.estado['carrusel']
    u, t = c.u, c.t
    n = e['n']

    fin = B.suave(B.tramo(c.queda, 0.0, FUNDIDO))
    entra = B.suave(B.tramo(t, 0.0, APARECE))
    dt = OBTURADOR / (2.0 * max(1.0, c.fps))                  # medio obturador a cada lado del cuadro
    tarjetas = []
    for k in range(n):
        alfa = entra * fin
        if alfa <= 0.003:
            continue
        quad, zc = _quad_en(e, c, k, t)
        # el desenfoque de movimiento: lo que recorre la tarjeta mientras el obturador está abierto. En el arranque rápido
        # se pinta en varias posiciones seguidas, sumadas (una cada PASO_BORRON px); despacio, una sola
        qa, _ = _quad_en(e, c, k, t - dt)
        qb, _ = _quad_en(e, c, k, t + dt)
        mov = 0.0
        for p, q, x in ((qa, quad, 2.0), (quad, qb, 2.0), (qa, qb, 1.0)):
            if p is not None and q is not None:
                mov = max(mov, x * float(np.linalg.norm(q - p, axis=1).max()))
        veces = 1 if mov < PASO_BORRON * u else min(BORRON_MAX, 1 + int(math.ceil(mov / (PASO_BORRON * u))))
        if veces == 1:
            if quad is None:
                continue
            hecha = _tarjeta_en(e, k, quad, c.W, c.H)
        else:
            partes = []
            for j in range(veces):
                q, _ = _quad_en(e, c, k, t - dt + 2 * dt * j / (veces - 1))
                partes.append((_tarjeta_en(e, k, q, c.W, c.H) if q is not None else None, 1.0 / veces))
            hecha = _juntar(partes)
        if hecha is None:
            continue
        tapa = 1.0 - B.suave(B.tramo(zc, DETRAS - 0.02, DETRAS + 0.02))
        brillo = 1.0 - OSCURO_ATRAS * ((1.0 - zc) / 2.0) ** 1.2
        # al pasar de delante a detrás (o al revés) ENCIMA de la persona, la tarjeta se desvanece y vuelve a aparecer: así
        # no desaparece de golpe detrás del pecho (o del móvil). Si en ese momento va a su lado (sin tocarla), no cambia
        # nada (el margen es de profundidad en el giro lento, y de tiempo al salir, que cruzan en un cuadro: ±0,1 s)
        rapidez = abs(_profundidad(e, k, t + 0.04) - _profundidad(e, k, t - 0.04)) / 0.08
        cerca = 1.0 - B.suave(B.tramo(abs(zc - DETRAS), 0.01, max(CRUCE, 0.1 * rapidez)))
        if cerca > 0.003:
            capa, X0, Y0 = hecha
            a = capa[::4, ::4, 3]
            m = c.mascara[Y0:Y0 + capa.shape[0]:4, X0:X0 + capa.shape[1]:4]
            sobre = float((a * m).sum() / max(1e-6, float(a.sum())))
            alfa *= 1.0 - cerca * min(1.0, sobre / 0.25)
        tarjetas.append((zc, k, hecha, alfa, tapa, brillo))

    # el color de verdad de la persona en su borde, donde pasa alguna tarjeta por detrás (como la órbita)
    persona = []
    franja, aire = int(math.ceil(4 * u)), int(math.ceil(64 * u))
    for _, _, (capa, X0, Y0), _, tapa, _ in tarjetas:
        if tapa <= 0.003:
            continue
        X1, Y1 = X0 + capa.shape[1], Y0 + capa.shape[0]
        m = c.mascara[Y0:Y1, X0:X1]
        borde = (m > 0.004) & (m < 0.996)
        if not borde.any():
            continue
        filas, cols = np.flatnonzero(borde.any(axis=1)), np.flatnonzero(borde.any(axis=0))
        bx0, bx1 = max(0, X0 + int(cols[0]) - franja), min(c.W, X0 + int(cols[-1]) + 1 + franja)
        by0, by1 = max(0, Y0 + int(filas[0]) - franja), min(c.H, Y0 + int(filas[-1]) + 1 + franja)
        if any(bx0 >= p[1] and by0 >= p[2] and bx1 <= p[3] and by1 <= p[4] for p in persona):
            continue
        ax0, ay0, ax1, ay1 = max(0, bx0 - aire), max(0, by0 - aire), min(c.W, bx1 + aire), min(c.H, by1 + aire)
        F, _ = B.color_persona(c.img[ay0:ay1, ax0:ax1].copy(), c.mascara[ay0:ay1, ax0:ax1], u)
        persona.append((F[by0 - ay0:by1 - ay0, bx0 - ax0:bx1 - ax0], bx0, by0, bx1, by1))

    for zc, k, hecha, alfa, tapa, brillo in sorted(tarjetas, key=lambda x: (x[0], x[1])):
        _componer(c, hecha, alfa, tapa, brillo, persona)
