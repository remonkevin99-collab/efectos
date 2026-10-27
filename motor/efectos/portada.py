"""Portada de revista: la persona se convierte en la portada de una revista.

La cámara se acerca un poco y sube a la persona, el color se pone «de revista» (más contraste, más cálido y las esquinas
algo más oscuras), y entran por orden: el nombre de la revista enorme DETRÁS de la cabeza (la cabeza lo tapa un poco,
como en las portadas de verdad), la línea del número y la fecha, tres titulares a un lado (uno grande y dos pequeños) y un
código de barras pequeño abajo. Al final todo se va con un fundido y la cámara vuelve a su sitio.

    .venv/bin/python efectos.py portada tu_video.mp4 --fotos 0.3,0.9,1.6,3.0

"""
import datetime
import math
import random
import re

import numpy as np
from PIL import Image, ImageDraw

import base as B

try:                                   # OpenCV hace el acercamiento mucho más rápido; si no está, se usa Pillow
    import cv2
except ImportError:                    # pragma: no cover
    cv2 = None

NOMBRE = 'portada'
DESCRIPCION = 'Te convierte en la portada de una revista'
OPCIONES = {
    'titulo': 'EFECTOS',                       # el nombre de la revista (va enorme, detrás de la cabeza)
    'numero': 'Nº 1 · hoy',                    # la línea del número y la fecha («hoy» = el mes y el año de hoy)
    'lineas': 'Un clip|13 efectos|sin editor', # los tres titulares, separados por «|» (el primero va grande)
    'color': '#8B5CF6',                        # el color de acento (las rayitas de los titulares)
    'lado': 'auto',                            # dónde van los titulares: izquierda, derecha o auto (donde hay sitio)
    'zoom': '1.2',                             # cuánto se acerca la cámara (1 = nada)
}
DURACION = 4.0

BLANCO = (255, 255, 255, 255)
MESES = ('ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE',
         'DICIEMBRE')


def _con_fecha(texto):
    """«hoy» en la línea del número se cambia por el mes y el año de hoy («Nº 1 · hoy» → «Nº 1 · OCTUBRE 2026»)."""
    hoy = datetime.date.today()
    return re.sub(r'(?i)\bhoy\b', f'{MESES[hoy.month - 1]} {hoy.year}', str(texto))


# ── El acercamiento de la cámara ────────────────────────────────────────────────────────────────────────────────────
def _plan_acercamiento(c, z):
    """Se calcula una vez: el punto fijo del acercamiento, para que la persona quede centrada y con la cabeza a ~23 %
    del alto (así cabe el nombre de la revista encima). Es un punto fijo: la cámara no persigue a la persona."""
    cx, cy, ancho = c.cara
    cabeza = cy - 0.8 * ancho                          # lo alto de la cabeza
    if z <= 1.001:
        return c.W / 2, c.H / 2
    ancho_ventana, alto_ventana = c.W / z, c.H / z      # el trozo del cuadro que se ve con el acercamiento
    x0 = min(max(cx - ancho_ventana / 2, 0), c.W - ancho_ventana)
    y0 = min(max(cabeza - 0.235 * c.H / z, 0), c.H - alto_ventana)
    # un acercamiento sobre un punto fijo P deja ver la ventana que empieza en P·(1 − 1/z): de ahí sale P
    return x0 / (1 - 1 / z), y0 / (1 - 1 / z)


def _acercar(c, z, px, py):
    """Acerca el cuadro (y la máscara) z veces alrededor del punto fijo (px, py)."""
    if z <= 1.0005:
        return
    m = np.float32([[z, 0, px - px * z], [0, z, py - py * z]])
    if cv2 is not None:
        img = cv2.warpAffine(np.ascontiguousarray(c.img), m, (c.W, c.H), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE)
        mas = cv2.warpAffine(np.ascontiguousarray(c.mascara, np.float32), m, (c.W, c.H), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE)
    else:
        inv = (1 / z, 0, px - px / z, 0, 1 / z, py - py / z)
        im = Image.fromarray((np.clip(c.img, 0, 1) * 255 + 0.5).astype(np.uint8))
        img = np.asarray(im.transform((c.W, c.H), Image.AFFINE, inv, Image.BILINEAR), np.float32) / 255.0
        mm = Image.fromarray((np.clip(c.mascara, 0, 1) * 255 + 0.5).astype(np.uint8))
        mas = np.asarray(mm.transform((c.W, c.H), Image.AFFINE, inv, Image.BILINEAR), np.float32) / 255.0
    c.img[...] = img
    try:                                # la máscara tiene que seguir a la imagen (para poner cosas detrás de la persona)
        c.mascara[...] = mas
    except ValueError:                  # si viene de solo lectura, se cambia por la nueva
        c.mascara = mas
    cx, cy, ancho = c.cara
    c.cara = (px + (cx - px) * z, py + (cy - py) * z, ancho * z)


# ── El color de revista ─────────────────────────────────────────────────────────────────────────────────────────────
def _color_fijo(c):
    """Se calcula una vez: el cambio de color completo como «cuadro × G + O» (más contraste, más cálido y las esquinas un
    poco más oscuras). Así, en cada cuadro son solo dos cuentas."""
    y, x = np.mgrid[0:c.H, 0:c.W].astype(np.float32)
    r = np.sqrt(((x - c.W / 2) / (c.W * 0.62)) ** 2 + ((y - c.H * 0.48) / (c.H * 0.62)) ** 2)
    k = np.clip((r - 0.55) / 0.65, 0, 1)
    viñeta = (1.0 - 0.32 * k * k * (3 - 2 * k)).astype(np.float32)[..., None]
    contraste = 1.16
    calido = np.array([1.07, 1.01, 0.90], np.float32)                 # más rojo, menos azul
    g = (viñeta * (contraste * calido)).astype(np.float32)
    o = (viñeta * (np.float32(0.5 * (1 - contraste)) + np.array([0.012, 0.004, -0.01], np.float32))).astype(np.float32)
    return g, o


def _color_revista(c, k, g, o):
    """Pone el color de revista con fuerza k (0–1)."""
    if k <= 0.002:
        return
    if k >= 0.998:
        np.multiply(c.img, g, out=c.img)
        np.add(c.img, o, out=c.img)
    else:                                                              # mientras entra o se va: mezcla con el original
        nuevo = c.img * g
        nuevo += o
        nuevo -= c.img
        nuevo *= np.float32(k)
        c.img += nuevo
    np.clip(c.img, 0, 1, out=c.img)


# ── Las piezas (se hacen una vez) ───────────────────────────────────────────────────────────────────────────────────
def _recortar(capa):
    """La capa recortada a lo que tiene dibujado."""
    caja = capa.getbbox()
    return capa.crop(caja) if caja else capa


def _cabecera(titulo, ancho, alto_max, u):
    """El nombre de la revista: letras gordas un poco apretadas y estiradas hacia arriba, como una cabecera."""
    titulo = titulo.strip().upper() or 'EFECTOS'
    espacio = -0.025
    f = B.fuente('extrabold', 100)
    largo = sum(f.getlength(ch) for ch in titulo) + espacio * 100 * max(0, len(titulo) - 1)
    tam = min(ancho * 100 / max(1.0, largo), 330 * u)
    capa = _recortar(B.texto(titulo, tam, 'extrabold', BLANCO, espacio=espacio))
    estirar = min(1.35, alto_max / max(1, capa.height))
    capa = capa.resize((capa.width, max(1, int(round(capa.height * estirar)))), Image.LANCZOS)
    return capa


def _numero(texto, ancho, u):
    """La línea del número y la fecha, con dos rayitas finas a los lados."""
    t = _recortar(B.texto(texto.strip().upper(), 27 * u, 'medium', BLANCO, espacio=0.16))
    hueco = 22 * u
    raya = max(0, (ancho - t.width) / 2 - hueco)
    capa = Image.new('RGBA', (int(ancho), int(t.height + 4 * u)), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    ym = capa.height / 2
    g = max(1, int(round(2 * u)))
    if raya > 20 * u:
        d.rectangle([0, ym - g / 2, raya, ym + g / 2], fill=(255, 255, 255, 210))
        d.rectangle([ancho - raya, ym - g / 2, ancho, ym + g / 2], fill=(255, 255, 255, 210))
    capa.alpha_composite(t, (int(round((ancho - t.width) / 2)), int(round((capa.height - t.height) / 2))))
    return capa


def _en_lineas(texto, f, ancho_max):
    """El texto en una línea si cabe; si no, en dos lo más parejas posible."""
    palabras = texto.split()
    if f.getlength(texto) <= ancho_max or len(palabras) < 2:
        return [texto]
    mejor = None
    for i in range(1, len(palabras)):
        a, b = ' '.join(palabras[:i]), ' '.join(palabras[i:])
        largo = max(f.getlength(a), f.getlength(b))
        if mejor is None or largo < mejor[0]:
            mejor = (largo, [a, b])
    return mejor[1]


def _titular(texto, tam, peso, ancho_max, acento, u, a_la_derecha):
    """Un titular: una rayita del color de acento encima y el texto en blanco (con sombra suave para que se lea). Si no
    cabe, va en dos líneas; y si aun así no cabe, se achica."""
    f = B.fuente(peso, tam)
    lineas = _en_lineas(texto, f, ancho_max)
    largo = max(f.getlength(ln) for ln in lineas)
    if largo > ancho_max:
        tam *= ancho_max / largo
        f = B.fuente(peso, tam)
    alto_mayus = -f.getbbox('H', anchor='ls')[1]
    bajada = f.getmetrics()[1] * 0.75                                   # lo que baja la «p» o la «g»
    interlinea = tam * 1.04
    raya_w, raya_h = max(46 * u, tam * 0.55), max(5 * u, tam * 0.075)
    hueco = max(10 * u, tam * 0.16)
    margen = int(4 * u)
    w = int(math.ceil(max(f.getlength(ln) for ln in lineas))) + 2 * margen
    h = int(math.ceil(raya_h + hueco + alto_mayus + (len(lineas) - 1) * interlinea + bajada))
    capa = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    raya = B.caja(raya_w, raya_h, raya_h / 2, acento)
    capa.alpha_composite(raya, (int(w - margen - raya.width) if a_la_derecha else margen, 0))
    d = ImageDraw.Draw(capa)
    for n, ln in enumerate(lineas):
        x = (w - margen - f.getlength(ln)) if a_la_derecha else margen
        d.text((x, raya_h + hueco + alto_mayus + n * interlinea), ln, font=f, fill=BLANCO, anchor='ls')
    return B.con_sombra(capa, 12 * u, 4 * u, 120)


def _codigo_barras(semilla, u):
    """Un código de barras pequeño de adorno (barras al azar, siempre las mismas para el mismo título)."""
    rnd = random.Random(semilla)
    w, h = int(150 * u), int(104 * u)
    k = 3                                                           # se dibuja a 3× y se reduce (bordes limpios)
    capa = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=int(7 * u * k), fill=(255, 255, 255, 245))
    x, margen = 12 * u * k, 12 * u * k
    alto_barras = (h - 40 * u) * k
    while x < w * k - margen - 2 * u * k:
        grosor = rnd.choice([1, 1, 1, 2, 2, 3]) * 1.35 * u * k
        if rnd.random() < 0.62:
            d.rectangle([x, 10 * u * k, x + grosor, 10 * u * k + alto_barras], fill=(18, 16, 24, 255))
        x += grosor + rnd.choice([1, 1, 2]) * 1.35 * u * k
    capa = capa.resize((w, h), Image.LANCZOS)
    cifras = ''.join(str(rnd.randint(0, 9)) for _ in range(10))
    t = _recortar(B.texto(cifras, 15 * u, 'medium', (18, 16, 24, 255), espacio=0.12))
    capa.alpha_composite(t, (int((w - t.width) / 2), int(h - 9 * u - t.height)))
    return B.con_sombra(capa, 10 * u, 4 * u, 90)


def _preparar(c):
    u = c.u
    e = c.estado
    try:
        z = float(str(c.op.get('zoom', '1.2')).replace(',', '.'))
    except ValueError:
        z = 1.2
    z = max(1.0, min(1.6, z))                          # entre nada y 1,6 veces
    e['z'] = z
    e['punto'] = _plan_acercamiento(c, z)
    px, py = e['punto']
    cx, cy, ancho = c.cara
    # la cara tal como queda con el acercamiento completo
    fcx, fcy, fan = px + (cx - px) * z, py + (cy - py) * z, ancho * z
    cabeza = fcy - 0.8 * fan
    barbilla = fcy + 1.05 * fan
    izq, der = B.zona_segura(c)
    ancho_util = der - izq
    # 1) el nombre de la revista: su borde de abajo entra en la cabeza (la gorra o el pelo lo tapan)
    base = cabeza + 0.42 * fan
    alto_max = max(120 * u, min(250 * u, base - 190 * u))
    cab = _cabecera(c.op.get('titulo', 'EFECTOS'), ancho_util, alto_max, u)
    num = _numero(_con_fecha(c.op.get('numero', '')), cab.width, u)
    # si la cabeza está muy arriba, el nombre baja (va detrás de la persona: puede bajar sin taparle la cara) para que
    # la línea del número no se salga por arriba
    base = max(base, 70 * u + num.height + 26 * u + cab.height)
    e['cabecera'] = B.con_sombra(cab, 16 * u, 6 * u, 70)
    e['cab_xy'] = (c.W / 2, base - cab.height / 2)
    # 2) la línea del número, encima del nombre
    e['numero'] = B.con_sombra(num, 8 * u, 2 * u, 110)
    e['num_xy'] = (c.W / 2, base - cab.height - 26 * u - num.height / 2)
    # 3) los titulares: debajo de la barbilla, del lado con más sitio
    lado = (c.op.get('lado', 'auto') or 'auto').strip().lower()
    if lado not in ('izquierda', 'derecha'):
        lado = 'izquierda' if fcx >= c.W / 2 else 'derecha'
    a_la_derecha = lado == 'derecha'
    acento = B.color(c.op.get('color', '#8B5CF6'))
    lineas = [s.strip() for s in str(c.op.get('lineas', '')).split('|') if s.strip()][:3]
    col_w = 0.47 * ancho_util
    pad = int(12 * u * 2 + 4 * u)                      # el aire que añade la sombra a cada lado (ver con_sombra)
    y = max(barbilla + 70 * u, c.H * 0.56)
    tope = c.H - 370 * u                               # no bajan hasta el código de barras
    factor = 1.0
    for _ in range(4):                                 # si no caben (cara muy grande), se achican
        piezas = [_titular(s, (118 if i == 0 else 56) * u * factor, 'extrabold' if i == 0 else 'bold', col_w, acento, u,
                           a_la_derecha) for i, s in enumerate(lineas)]
        total = sum(p.height - 2 * pad for p in piezas) + (36 + 30 * max(0, len(piezas) - 2)) * u * factor
        if y + total <= tope or factor <= 0.5:
            break
        factor = max(0.5, factor * (tope - y) / total)
    e['titulares'] = []
    for i, p in enumerate(piezas):
        w_real = p.width - 2 * pad
        x = (der - 4 * u - w_real / 2) if a_la_derecha else (izq + 4 * u + w_real / 2)
        alto_real = p.height - 2 * pad
        e['titulares'].append((p, x, y + alto_real / 2))
        y += alto_real + (36 * u if i == 0 else 30 * u) * factor
    # 4) el código de barras, en la esquina de abajo del otro lado
    cod = _codigo_barras(c.op.get('titulo', 'EFECTOS'), u)
    x = (izq + 75 * u) if a_la_derecha else (der - 75 * u)
    e['codigo'] = (cod, x, c.H - 300 * u)
    e['color'] = _color_fijo(c)
    e['listo'] = True


# ── Poner lo que ya no se mueve, sin repetir trabajo ────────────────────────────────────────────────────────────────
def _poner(c, clave, capa, cx, cy, k, alfa, detras=False, **mov):
    """Mientras entra (k < 1) se pone con B.poner, que mueve con decimales. Cuando ya está quieta, el trabajo de colocarla
    (la transformación) se hace una sola vez y se guarda: en los cuadros siguientes solo se mezcla con el cuadro."""
    if alfa <= 0.003:
        return
    if k < 1:
        B.poner(c, capa, cx, cy, alfa=alfa, detras=detras, **mov)
        return
    guardadas = c.estado.setdefault('_quietas', {})
    llave = (clave, round(cx, 2), round(cy, 2))
    if llave not in guardadas:
        w, h = capa.size
        X0, Y0 = max(0, int(math.floor(cx - w / 2)) - 2), max(0, int(math.floor(cy - h / 2)) - 2)
        X1, Y1 = min(c.W, int(math.ceil(cx + w / 2)) + 2), min(c.H, int(math.ceil(cy + h / 2)) + 2)
        if X1 <= X0 or Y1 <= Y0:
            guardadas[llave] = None
        else:
            hecha = capa.convert('RGBa').transform((X1 - X0, Y1 - Y0), Image.AFFINE,
                                                   (1, 0, X0 - cx + w / 2, 0, 1, Y0 - cy + h / 2),
                                                   resample=Image.BICUBIC).convert('RGBA')
            arr = np.asarray(hecha, np.float32) / 255.0
            guardadas[llave] = (X0, Y0, X1, Y1, np.ascontiguousarray(arr[..., :3]), np.ascontiguousarray(arr[..., 3:4]))
    g = guardadas[llave]
    if g is None:
        return
    X0, Y0, X1, Y1, rgb, a = g
    al = a * np.float32(alfa)
    if detras:
        al = al * (1.0 - c.mascara[Y0:Y1, X0:X1, None])
    zona = c.img[Y0:Y1, X0:X1]
    zona *= (1.0 - al)
    zona += rgb * al


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def dibujar(c):
    e = c.estado
    if not e.get('listo'):
        _preparar(c)
    u = c.u
    q = c.queda
    t = c.t / min(1.0, c.dur / DURACION)              # si el efecto dura menos de lo normal, todo entra más deprisa
    # la cámara: se acerca al empezar (0,7 s) y vuelve al final (0,6 s)
    k_cam = B.suave(B.tramo(t, 0, 0.7)) * B.suave(B.tramo(q, 0, 0.6))
    z = 1 + (e['z'] - 1) * k_cam
    _acercar(c, z, *e['punto'])
    _color_revista(c, B.suave(B.tramo(t, 0.05, 0.6)) * B.suave(B.tramo(q, 0, 0.5)), *e['color'])
    fuera = B.suave(B.tramo(q, 0, 0.45))              # el fundido de salida de las letras

    # el nombre de la revista baja un poco mientras aparece, detrás de la persona
    k = B.sale(B.tramo(t, 0.3, 0.95))
    x, y = e['cab_xy']
    _poner(c, 'cabecera', e['cabecera'], x, y - (1 - k) * 36 * u, k, k * fuera, detras=True, escala=1.04 - 0.04 * k)
    # la línea del número
    k = B.sale(B.tramo(t, 0.6, 1.05))
    x, y = e['num_xy']
    _poner(c, 'numero', e['numero'], x, y + (1 - k) * 14 * u, k, k * fuera)
    # los titulares, uno detrás de otro, entrando desde su lado
    lado = -1 if e['titulares'] and e['titulares'][0][1] < c.W / 2 else 1
    for i, (p, x, y) in enumerate(e['titulares']):
        k = B.sale(B.tramo(t, 0.85 + 0.17 * i, 1.35 + 0.17 * i))
        _poner(c, f'titular{i}', p, x + lado * (1 - k) * 46 * u, y, k, k * fuera)
    # el código de barras
    k = B.sale(B.tramo(t, 1.4, 1.85))
    p, x, y = e['codigo']
    _poner(c, 'codigo', p, x, y + (1 - k) * 18 * u, k, k * fuera)
