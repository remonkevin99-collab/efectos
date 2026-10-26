"""Letrero LED: el cuarto se oscurece y DETRÁS de la cabeza se escribe, letra a letra, un letrero de neón.

  - El cuarto baja la luz (la persona se queda con la suya).
  - Cada letra se enciende como un tubo de neón al arrancar: un par de destellos y se queda fija. Las letras van de una en
    una, de izquierda a derecha.
  - La luz es de verdad «luz»: se SUMA a lo que hay detrás (el centro del tubo casi blanco, un brillo del color alrededor
    y un halo más ancho), y tiñe un poco la pared alrededor del letrero.
  - Al final se apaga con un fundido y el cuarto vuelve a su luz.
Si el texto es largo (más de 13 letras), va en dos líneas. Con «|» se elige dónde partirlo: «SIN|EDITOR».

    python efectos.py letrero-led mi-video.mp4 --desde 2 --hasta 6 --op "texto=SIN EDITOR"
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import base as B

NOMBRE = 'letrero-led'
DESCRIPCION = 'El cuarto se oscurece y detrás de tu cabeza se escribe, letra a letra, un letrero de neón'
OPCIONES = {'texto': 'SIN EDITOR', 'color': '#FFA43A'}
DURACION = 4.0

OSCURO = 0.60           # cuánto baja la luz del cuarto
ENTRA, SALE = 0.40, 0.45
PRIMERA = 0.35          # cuándo se enciende la primera letra
TAPA = 0.30             # qué parte de la altura de las letras queda por debajo de lo alto de la cabeza
ANCHO = 880             # el ancho del letrero (a 1080), dentro de la zona segura y con aire para el brillo


def _arranque(tau, k):
    """La intensidad (0–1) de una letra `tau` segundos después de que empieza a encenderse: un tubo de neón al arrancar,
    un par de destellos y fija. Cada letra lo hace un poco distinto (pero siempre igual en cada pasada)."""
    if tau <= 0:
        return 0.0
    r = math.sin(k * 12.9898 + 4.1) * 43758.5453
    r = r - math.floor(r)                       # un número de 0 a 1 propio de cada letra
    pasos = [(0.00, 0.85), (0.05, 0.12 + 0.15 * r), (0.10, 1.0), (0.16, 0.30 + 0.3 * r), (0.21, 1.0)]
    if r > 0.55:                                # algunas dudan una vez más
        pasos = pasos[:-1] + [(0.21, 0.9), (0.26, 0.4), (0.31, 1.0)]
    nivel = 0.0
    for inicio, valor in pasos:
        if tau >= inicio:
            nivel = valor
    return nivel


def _mezcla(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


def _lineas(texto):
    if '|' in texto:
        return [p.strip() for p in texto.split('|') if p.strip()]
    if len(texto) > 13 and ' ' in texto:
        palabras = texto.split()
        mejor, corte = None, 1
        for i in range(1, len(palabras)):
            a, b = ' '.join(palabras[:i]), ' '.join(palabras[i:])
            dif = abs(len(a) - len(b))
            if mejor is None or dif < mejor:
                mejor, corte = dif, i
        return [' '.join(palabras[:corte]), ' '.join(palabras[corte:])]
    return [texto]


def _luz_de(mascara, u, caliente, tono):
    """La luz de una letra: el tubo (casi blanco), su brillo y su halo, ya sumados. Devuelve float32 alto × ancho × 3."""
    nucleo = np.asarray(mascara.filter(ImageFilter.GaussianBlur(0.8 * u)), np.float32) / 255.0
    brillo = np.asarray(mascara.filter(ImageFilter.GaussianBlur(7 * u)), np.float32) / 255.0
    halo = np.asarray(mascara.filter(ImageFilter.GaussianBlur(24 * u)), np.float32) / 255.0
    luz = (nucleo[..., None] * np.array(caliente, np.float32) * 1.05
           + brillo[..., None] * np.array(tono, np.float32) * 1.25
           + halo[..., None] * np.array(tono, np.float32) * 1.05)
    return luz


def _recortar(luz, x0, y0, umbral=0.003):
    """Quita el borde donde ya no hay luz (menos que sumar en cada cuadro)."""
    hay = luz.max(axis=2) > umbral
    filas, cols = np.where(hay.any(1))[0], np.where(hay.any(0))[0]
    if not len(filas):
        return None
    a, b, cc, d = filas[0], filas[-1] + 1, cols[0], cols[-1] + 1
    return luz[a:b, cc:d].copy(), x0 + cc, y0 + a


def _preparar(c):
    u = c.u
    texto = (c.op.get('texto') or 'SIN EDITOR').strip().upper()
    tono = np.array(B.color(c.op.get('color') or '#FFA43A')[:3], np.float32) / 255.0
    caliente = _mezcla(tuple(tono), (1.0, 0.97, 0.92), 0.6)
    lineas = _lineas(texto)
    f100 = B.fuente('medium', 100)
    tam = min(190 * u, min(100 * ANCHO * u / max(1.0, f100.getlength(l)) for l in lineas))
    f = B.fuente('medium', tam)
    asc, desc = f.getmetrics()
    # dónde va: centrado en el ancho y con lo alto de la cabeza tapando la parte de abajo
    cx, cy, fw = c.cara
    caja_m = f.getbbox('H')                      # la altura de una mayúscula
    alto_letra = caja_m[3] - caja_m[1]
    salto = tam * 1.18
    alto_total = alto_letra + salto * (len(lineas) - 1)
    arriba_cabeza = cy - 1.05 * fw
    abajo = arriba_cabeza + TAPA * alto_letra                     # la base de la última línea
    abajo = max(abajo, 190 * u + alto_total)                      # que no se salga por arriba
    pad = int(math.ceil(3 * 24 * u))
    letras = []
    for n_linea, linea in enumerate(lineas):
        ancho_linea = f.getlength(linea)
        x_ini = c.W / 2 - ancho_linea / 2
        base_y = abajo - salto * (len(lineas) - 1 - n_linea)      # la base de las mayúsculas de esta línea
        top_y = base_y - caja_m[3]                                # dónde se escribe (Pillow mide desde arriba)
        for i, ch in enumerate(linea):
            if ch == ' ':
                continue
            x = x_ini + f.getlength(linea[:i])
            w = int(math.ceil(f.getlength(ch))) + 2
            m = Image.new('L', (w + 2 * pad, asc + desc + 2 * pad), 0)
            ImageDraw.Draw(m).text((pad, pad), ch, font=f, fill=255)
            x0, y0 = int(round(x)) - pad, int(round(top_y)) - pad
            hecho = _recortar(_luz_de(m, u, caliente, tono), x0, y0)
            if hecho:
                letras.append(hecho)
    # la pared teñida: un halo muy ancho de todo el letrero (se calcula pequeño y se agranda: es todo suave)
    red = 4
    todo = Image.new('L', (c.W // red, c.H // red), 0)
    for luz, x0, y0 in letras:
        trozo = Image.fromarray(np.clip(luz.max(axis=2) * 255, 0, 255).astype(np.uint8))
        trozo = trozo.resize((max(1, luz.shape[1] // red), max(1, luz.shape[0] // red)), Image.BILINEAR)
        todo.paste(Image.fromarray(np.maximum(np.asarray(todo.crop((x0 // red, y0 // red, x0 // red + trozo.width,
                                                                       y0 // red + trozo.height))), np.asarray(trozo))),
                   (x0 // red, y0 // red))
    pared = np.asarray(todo.filter(ImageFilter.GaussianBlur(95 * u / red)), np.float32) / 255.0
    pared = pared / max(1e-3, pared.max())
    pared = np.asarray(Image.fromarray((pared * 255).astype(np.uint8)).resize((c.W, c.H), Image.BILINEAR),
                       np.float32) / 255.0
    filas = np.where(pared.max(1) > 0.02)[0]
    py0, py1 = (filas[0], filas[-1] + 1) if len(filas) else (0, 1)
    pared = (pared[py0:py1, :, None] * tono[None, None, :] * 0.30).astype(np.float32)
    # los tiempos: de una en una
    n = len(letras)
    paso = min(0.13, 1.4 / max(1, n))
    return {'letras': letras, 'inicios': [PRIMERA + k * paso for k in range(n)], 'pared': pared, 'pared_y': py0}


def _oscurecer(c, m, cuanto, tinte):
    """Lo mismo que `B.oscurecer(c, cuanto, salvo_persona=True, tinte)`, en menos pasadas (es lo que más tarda de este
    efecto: va sobre el cuadro entero). `m` es la máscara con el borde firme: lo que queda fuera se apaga entero, también
    el filo de pared que el recorte deja pegado a la persona."""
    if cuanto <= 0.002:
        return
    k = (1.0 - m) * np.float32(cuanto)                    # cuánto se apaga cada píxel (la persona, nada)
    queda = 1.0 - k
    cv2.multiply(c.img, cv2.merge([queda, queda, queda]), dst=c.img)
    cv2.add(c.img, cv2.merge([k * np.float32(t) for t in tinte]), dst=c.img)


def _sumar(c, m, luz, x0, y0, k):
    """Suma la luz al cuadro en (x0, y0), detrás de la persona (`m`, la máscara con el borde firme)."""
    if k <= 0.002:
        return
    h, w = luz.shape[:2]
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(c.W, x0 + w), min(c.H, y0 + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    trozo = np.ascontiguousarray(luz[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0])
    fondo = (1.0 - m[Y0:Y1, X0:X1]) * np.float32(k)                # detrás de la persona
    zona = c.img[Y0:Y1, X0:X1]
    cv2.add(zona, cv2.multiply(trozo, cv2.merge([fondo, fondo, fondo])), dst=zona)


def dibujar(c):
    if 'letrero' not in c.estado:
        c.estado['letrero'] = _preparar(c)
    e = c.estado['letrero']
    entra = B.suave(B.tramo(c.t, 0, ENTRA))
    sale = B.suave(B.tramo(c.queda, 0, SALE))
    # 0. el borde de la persona, limpio: un pelo hacia dentro y su filo con el tono de la persona (si no, al apagar el
    #    cuarto queda un halo de pared clara alrededor de los hombros y los brazos)
    cuanto = OSCURO * entra * sale
    m = B.borde_firme(c.mascara, c.u)
    if cuanto > 0.002:
        limpia = B.sin_halo(c.img, m, c.u)
        mm = m[..., None]
        c.img[:] = limpia * mm + c.img * (1.0 - mm)
    # 1. el cuarto, a oscuras (la persona no)
    _oscurecer(c, m, cuanto, (0.012, 0.008, 0.03))
    # 2. cada letra con su arranque de neón
    niveles = [_arranque(c.t - t0, k) * sale for k, t0 in enumerate(e['inicios'])]
    for (luz, x0, y0), nivel in zip(e['letras'], niveles):
        _sumar(c, m, luz, x0, y0, nivel)
    # 3. la pared, teñida según cuántas letras están encendidas
    encendido = sum(niveles) / max(1, len(niveles))
    _sumar(c, m, e['pared'], 0, e['pared_y'], encendido)
