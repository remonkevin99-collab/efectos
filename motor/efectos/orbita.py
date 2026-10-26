"""Órbita: de 3 a 6 tarjetas con fotos giran alrededor de la cabeza en una elipse inclinada.

Las que pasan por detrás quedan DETRÁS de la persona (más pequeñas y algo más oscuras, asomando junto a la cabeza) y las de
delante pasan por encima, a la altura del pecho, sin tapar nunca la cara. Entran creciendo (0,4 s, una detrás de otra),
giran a ritmo constante y se van encogiendo (0,3 s).

Las fotos:
  - `imagenes=<carpeta>`: las de esa carpeta (jpg, png o webp, en orden; de 3 a 6, si hay menos se repiten).
  - si no se da carpeta: cuadros del propio vídeo, que pide al motor con `c.estado['sacar_cuadros'](n)` (`cantidad`).
  - y si tampoco hay motor (al probar el efecto suelto, sin vídeo): trozos del cuadro de ese momento.

    python efectos.py orbita mi-video.mp4 --desde 2 --hasta 6 --op imagenes=mis-fotos
"""
import math

import cv2
import numpy as np
from PIL import Image

import base as B

NOMBRE = 'orbita'
DESCRIPCION = ('De 3 a 6 tarjetas con fotos giran alrededor de tu cabeza: por detrás pasan detrás de ti y por delante, '
               'a la altura del pecho, sin taparte la cara')
OPCIONES = {'imagenes': '', 'cantidad': '5', 'tamano': '300', 'velocidad': '1'}
DURACION = 4.0

INCLINACION = -9.0      # grados: la elipse sube por la derecha
VUELTA = 6.0            # segundos por vuelta con velocidad 1
ENTRA, SALE = 0.4, 0.3  # lo que tarda cada tarjeta en crecer al entrar y en encogerse al irse
ESCALONADO = 0.05       # cada tarjeta entra un poco después que la anterior
OSCURO_ATRAS = 0.34     # cuánto se oscurecen las de detrás (0–1)


def _premultiplicada(capa):
    """De una capa PIL RGBA a un array float32 (alto × ancho × 4) con el color ya multiplicado por su transparencia."""
    a = np.asarray(capa, np.float32) * (1.0 / 255.0)
    a[..., :3] *= a[..., 3:4]
    return np.ascontiguousarray(a)


def _poner(c, capa, cx, cy, escala, giro, alfa, tapa, brillo=1.0):
    """Como `B.poner` (el centro en (cx, cy) con decimales, escalada y girada; `giro` en grados, a favor del reloj), pero
    con la capa ya preparada y OpenCV, que con seis tarjetas por cuadro va varias veces más rápido. Y con dos cosas más:
    `tapa` (0 = encima de la persona, 1 = detrás de ella; en medio, a medias, para cruzar de un lado al otro sin saltar) y
    `brillo` (1 = tal cual; menos, más oscura)."""
    if alfa <= 0.003 or escala <= 0.003:
        return
    h, w = capa.shape[:2]
    th = math.radians(giro)
    co, si = math.cos(th), math.sin(th)
    bw = abs(w * escala * co) + abs(h * escala * si)
    bh = abs(w * escala * si) + abs(h * escala * co)
    X0, Y0 = max(0, int(math.floor(cx - bw / 2)) - 2), max(0, int(math.floor(cy - bh / 2)) - 2)
    X1, Y1 = min(c.W, int(math.ceil(cx + bw / 2)) + 2), min(c.H, int(math.ceil(cy + bh / 2)) + 2)
    if X1 <= X0 or Y1 <= Y0:
        return
    M = np.array([[escala * co, -escala * si, 0.0], [escala * si, escala * co, 0.0]], np.float64)
    M[0, 2] = cx - X0 - (M[0, 0] * (w - 1) / 2 + M[0, 1] * (h - 1) / 2)
    M[1, 2] = cy - Y0 - (M[1, 0] * (w - 1) / 2 + M[1, 1] * (h - 1) / 2)
    hecha = cv2.warpAffine(capa, M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                           borderValue=(0, 0, 0, 0))
    v = np.full((Y1 - Y0, X1 - X0), np.float32(alfa), np.float32)
    if tapa > 0:
        v *= 1.0 - np.float32(tapa) * c.mascara[Y0:Y1, X0:X1]
    # lo de debajo se apaga según la transparencia y se suma el color (con OpenCV y en su sitio: es lo que más tarda)
    zona = c.img[Y0:Y1, X0:X1]
    queda = 1.0 - hecha[..., 3] * v
    cv2.multiply(zona, cv2.merge([queda, queda, queda]), dst=zona)
    v *= np.float32(brillo)
    cv2.add(zona, cv2.multiply(np.ascontiguousarray(hecha[..., :3]), cv2.merge([v, v, v])), dst=zona)


def _cubrir(im, w, h, arriba=0.4):
    """La imagen recortada para llenar w × h sin deformarse (si sobra alto, se queda más con la parte de arriba)."""
    im = im.convert('RGBA')
    k = max(w / im.width, h / im.height)
    nw, nh = max(w, int(math.ceil(im.width * k))), max(h, int(math.ceil(im.height * k)))
    im = im.resize((nw, nh), Image.LANCZOS)
    x0 = (nw - w) // 2
    y0 = int(round((nh - h) * arriba))
    return im.crop((x0, y0, x0 + w, y0 + h))


def _tarjeta(foto, w, h, u):
    """Una tarjeta: la foto con las esquinas redondeadas, un filo blanco fino y una sombra suave, lista para `_poner`."""
    r = 0.085 * w
    cara = B.recortar_redondo(_cubrir(foto, w, h), r)
    filo = B.caja(w, h, r, (0, 0, 0, 0), borde=(255, 255, 255, 225), grosor=max(1.0, 2.2 * u))
    cara.alpha_composite(filo)
    return _premultiplicada(B.con_sombra(cara, 16 * u, 10 * u, 120))


def _fotos(c, cantidad):
    carpeta = (c.op.get('imagenes') or '').strip()
    fotos = B.imagenes_de(carpeta)
    if fotos:
        return fotos[:6]
    if carpeta:
        print(f'  Aviso (órbita): no encuentro imágenes en «{carpeta}»; uso cuadros del propio vídeo.')
    sacar = c.estado.get('sacar_cuadros')
    if callable(sacar):
        fotos = sacar(cantidad)
        if fotos:
            return fotos
    # sin motor (el efecto probado suelto): trozos del cuadro de este momento
    W, H = c.W, c.H
    tw, th = int(W * 0.42), int(W * 0.56)
    sitios = [(0.05, 0.03), (0.52, 0.06), (0.0, 0.62), (0.55, 0.58), (0.28, 0.30), (0.3, 0.74)]
    out = []
    for fx, fy in sitios[:cantidad]:
        x0, y0 = int(fx * (W - tw)), int(fy * (H - th))
        out.append(B.a_capa(c.img[y0:y0 + th, x0:x0 + tw]))
    return out


def _preparar(c):
    u = c.u
    cantidad = int(min(6, max(3, round(float(c.op.get('cantidad') or 5)))))
    fotos = _fotos(c, cantidad)
    if not fotos:
        raise ValueError('no hay ninguna foto para las tarjetas')
    n = min(6, max(3, len(fotos)))
    fotos = [fotos[k % len(fotos)] for k in range(n)]
    w = max(40, int(round(float(c.op.get('tamano') or 300) * u)))
    h = int(round(w * 4 / 3))
    grandes = [_tarjeta(f, w, h, u) for f in fotos]
    # una copia más pequeña para las de detrás (reducir mucho al vuelo hace dientes en el filo)
    chicas = [_tarjeta(f, int(w * 0.72), int(w * 0.72 * 4 / 3), u * 0.72) for f in fotos]
    return {'n': n, 'w': w, 'h': h, 'grandes': grandes, 'chicas': chicas, 'fw': c.cara[2]}


def dibujar(c):
    if 'orbita' not in c.estado:
        c.estado['orbita'] = _preparar(c)
    e = c.estado['orbita']
    u = c.u
    n, w, h = e['n'], e['w'], e['h']
    cx, cy, _ = c.cara
    fw = e['fw']                                   # el tamaño del aro se fija al empezar: no respira con la cara

    # la elipse: centrada un poco por debajo de la cara; por detrás sube a la gorra, por delante baja al pecho
    lado = 0.80                                    # escala de una tarjeta en el lado del aro
    rx = 0.5 * fw + 0.5 * w * lado + 42 * u
    ry = 1.2 * fw + 0.16 * h
    x_min, x_max = 60 * u + rx + 0.5 * w * lado, c.W - 60 * u - rx - 0.5 * w * lado
    ex = min(max(cx, x_min), x_max) if x_min <= x_max else c.W / 2
    ey = cy + 0.55 * fw
    fi = math.radians(INCLINACION)
    cf, sf = math.cos(fi), math.sin(fi)
    vel = float(c.op.get('velocidad') or 1)
    giro_total = 2 * math.pi * vel * c.t / VUELTA

    tarjetas = []
    for k in range(n):
        th = math.radians(20) + 2 * math.pi * k / n + giro_total
        z = math.sin(th)                           # 1 = delante (abajo), -1 = detrás (arriba)
        X, Y = rx * math.cos(th), ry * z
        x = ex + X * cf - Y * sf
        y = ey + X * sf + Y * cf
        # entrar creciendo (una detrás de otra) e irse encogiendo
        ent = B.tramo(c.t, k * ESCALONADO, k * ESCALONADO + ENTRA)
        sal = B.tramo(c.queda, 0, SALE)
        crece = B.rebote(ent, 1.1) * B.suave(sal)
        alfa = min(1.0, ent * 3.0) * min(1.0, sal * 2.5)
        esc = (0.80 + 0.20 * z) * crece
        delante = B.suave(B.tramo(z, -0.3, 0.3))   # de detrás a delante, fundido (no salta al cruzar el lado)
        giro = 0.5 * INCLINACION + 5.0 * math.cos(th)
        # nunca encima de la cara: si una de delante la pisaría, baja lo justo (con lo que sube la esquina al girar)
        if delante > 0:
            sg, cg = abs(math.sin(math.radians(giro))), math.cos(math.radians(giro))
            hw = 0.5 * esc * (w * cg + h * sg)
            hh = 0.5 * esc * (h * cg + w * sg)
            solape = min(x + hw, cx + 0.65 * fw) - max(x - hw, cx - 0.65 * fw)
            if solape > 0:
                baja = max(0.0, (cy + 0.80 * fw) - (y - hh))
                y += baja * delante * min(1.0, solape / (30 * u))
        tarjetas.append((z, x, y, esc, alfa, delante, k, giro))

    for z, x, y, esc, alfa, delante, k, giro in sorted(tarjetas):
        if esc <= 0.01 or alfa <= 0.003:
            continue
        chica = esc < 0.80
        capa = (e['chicas'] if chica else e['grandes'])[k]
        rel = esc / 0.72 if chica else esc
        oscuro = (1.0 - (z + 1) / 2) ** 1.3                # 1 = la de más atrás
        _poner(c, capa, x, y, rel, giro, alfa, tapa=1.0 - delante, brillo=1.0 - OSCURO_ATRAS * oscuro)
