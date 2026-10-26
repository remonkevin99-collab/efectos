"""Fondo nuevo: el fondo de verdad desaparece y entra uno diseñado; la persona queda recortada encima (en blanco y negro,
con un poco más de contraste) y un puntero pulsa un botón de «Seguir» grande.

Lo que se ve:
- El fondo: un degradado oscuro con un brillo del color de acento detrás de la cabeza, un aro grande del color de acento
  (con su resplandor) centrado en la cabeza y unas letras gigantes muy tenues. Todo queda detrás de la persona.
- El titular: tres líneas cortas en Poppins ExtraBold, una blanca y otra del color de acento, en el lado con más sitio
  (encima de la cabeza si al lado no cabe grande).
- La franja del nombre: una banda del color de acento con el nombre en blanco y, debajo, el usuario más pequeño, sobre
  la parte de abajo a la izquierda del cuerpo (nunca sobre la cara).
- El botón de seguir, grande (un tercio del ancho): entra un puntero, lo pulsa, destella y pasa a «Siguiendo».

Entra en 0,3 s con un círculo que se abre desde la cabeza (con un filo de luz del color de acento); el blanco y negro
entra con él. En los últimos 0,3 s todo se funde con el cuadro de verdad.

    .venv/bin/python efectos.py fondo tu_video.mp4 --desde 1 --hasta 4.5 --op "nombre=TU NOMBRE" --op usuario=@tu_usuario
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw

import base as B
from efectos import boton_seguir as bs

NOMBRE = 'fondo'
DESCRIPCION = 'Cambia el fondo entero: tú recortado en blanco y negro, un titular, tu nombre y un botón de seguir que se pulsa'
OPCIONES = {
    'lineas': 'UN CLIP.|12 EFECTOS.|SIN EDITOR.',  # el titular: líneas cortas separadas por «|» (blanca, de color, blanca…)
    'nombre': 'TU NOMBRE',                         # el nombre de la franja
    'usuario': '@tu_usuario',                      # la cuenta, debajo del nombre
    'color': '#8B5CF6',                            # el color de acento (el brillo, el aro, la franja y el botón)
    'boton': 'si',                                 # si o no: el botón de seguir con su puntero
    'texto': 'Seguir',                             # el texto del botón antes de pulsarlo
    'texto_hecho': 'Siguiendo',                    # el texto después de pulsarlo
    'momento': 'mitad',                            # el segundo de la pulsación, desde que empieza el efecto
    'lado': 'auto',                                # el lado del botón: izquierda, derecha o auto (donde hay más sitio)
    'color_persona': 'no',                         # no = la persona en blanco y negro; si = con sus colores
    'letras': '',                                  # las letras gigantes del fondo (vacío = una palabra del nombre; no = sin)
}
DURACION = 3.5

ENTRA = 0.30          # lo que tarda el círculo en abrirse
SALE = 0.30           # lo que tarda en volver el cuadro de verdad
QUIETO = 0.75         # desde aquí el aro y el titular ya no se mueven: el fondo se guarda hecho
BLANCO = (255, 255, 255, 255)
OSCURO = (28, 21, 55, 255)          # el texto del botón ya pulsado
CONTRASTE = 1.22                    # el blanco y negro, con un poco más de contraste
PIVOTE = 0.40


def _si(v):
    return str(v).strip().lower() in ('si', 'sí', 'yes', 'true', '1')


def _claro(col, k):
    """El color mezclado con blanco (k de 0 a 1)."""
    return tuple(int(round(B.mezclar(v, 255, k))) for v in col[:3]) + (255,)


# ── Piezas que se hacen una vez ─────────────────────────────────────────────────────────────────────────────────────
def _tinta(s, tam, peso, col, margen=2):
    """Un texto en una capa justa a la tinta (sin el aire de arriba de la letra): así se alinea por lo que se ve."""
    f = B.fuente(peso, tam)
    x0, y0, x1, y1 = f.getbbox(s, anchor='ls')
    w, h = int(math.ceil(x1 - x0 + 2 * margen)), int(math.ceil(y1 - y0 + 2 * margen))
    capa = Image.new('RGBA', (max(1, w), max(1, h)), (0, 0, 0, 0))
    ImageDraw.Draw(capa).text((margen - x0, margen - y0), s, font=f, fill=col, anchor='ls')
    return capa


def _degradado(c, cx, cy, acento):
    """El fondo quieto: un degradado radial oscuro con el brillo detrás de la cabeza y un poco de color en la esquina de
    abajo. Se calcula en decimales (a un cuarto del tamaño, que es suave) y se le pone un grano finísimo y fijo para que
    no salgan escalones."""
    W, H = c.W, c.H
    w4, h4 = max(8, W // 4), max(8, H // 4)
    y, x = np.mgrid[0:h4, 0:w4].astype(np.float32)
    x = (x + 0.5) * (W / w4)
    y = (y + 0.5) * (H / h4)
    ac = np.array(acento[:3], np.float32) / 255.0
    negro = np.array([0.028, 0.018, 0.058], np.float32)          # casi negro, hacia el morado
    profundo = np.array([0.105, 0.055, 0.215], np.float32)       # morado profundo
    d = np.sqrt(((x - cx) / W) ** 2 + ((y - cy) / W) ** 2)
    ancho = np.exp(-(d / 0.62) ** 2)[..., None]                   # el morado, amplio
    brillo = np.exp(-(d / 0.30) ** 2)[..., None]                  # el acento, detrás de la cabeza
    esquina = np.exp(-(((x / W) ** 2 + ((y - H) / W) ** 2) / 0.55 ** 2))[..., None]
    col = negro + (profundo - negro) * ancho + ac * 0.30 * brillo + ac * 0.07 * esquina
    # las esquinas, algo más oscuras
    r = np.sqrt(((x - W / 2) / (W * 0.70)) ** 2 + ((y - H / 2) / (H * 0.62)) ** 2)
    k = np.clip((r - 0.6) / 0.6, 0, 1)
    col *= (1.0 - 0.45 * k * k * (3 - 2 * k))[..., None]
    col = cv2.resize(col.astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    rng = np.random.default_rng(7)
    grano = (rng.random((H, W), np.float32) - rng.random((H, W), np.float32)) * np.float32(1.2 / 255.0)
    col += grano[..., None]
    return np.clip(col, 0, 1).astype(np.float32)


def _aro(R, grosor, halo, acento):
    """El aro: un círculo de trazo fino con su resplandor, calculado con distancias (los bordes salen limpios)."""
    pad = halo * 3.2
    n = int(math.ceil(2 * (R + pad)))
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    o = (n - 1) / 2.0
    dist = np.abs(np.hypot(xx - o, yy - o) - R)
    linea = np.clip(grosor / 2 - dist + 0.5, 0, 1)
    luz = np.exp(-(dist / halo) ** 2) * 0.55 + np.exp(-(dist / (halo * 2.6)) ** 2) * 0.22
    col_linea = np.array(_claro(acento, 0.35)[:3], np.float32) / 255.0
    col_luz = np.array(acento[:3], np.float32) / 255.0
    a = np.clip(linea + luz * (1 - linea), 0, 1)
    rgb = (col_linea * linea[..., None] + col_luz * (luz * (1 - linea))[..., None]) / np.maximum(a, 1e-4)[..., None]
    arr = np.dstack([np.clip(rgb, 0, 1) * 255, a * 255]) + 0.5
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')


def _letras_gigantes(c, palabra, acento):
    """La palabra enorme y muy tenue del fondo: solo el contorno del color de acento y un relleno casi invisible."""
    u = c.u
    f100 = B.fuente('extrabold', 100)
    tam = min(620 * u, 100 * c.W * 1.10 / max(1.0, f100.getlength(palabra)))
    f = B.fuente('extrabold', tam)
    trazo = max(2, int(round(3 * u)))
    x0, y0, x1, y1 = f.getbbox(palabra, anchor='ls')
    m = trazo + 4
    w, h = int(math.ceil(x1 - x0 + 2 * m)), int(math.ceil(y1 - y0 + 2 * m))
    lleno = Image.new('L', (w, h), 0)
    con_trazo = Image.new('L', (w, h), 0)
    ImageDraw.Draw(lleno).text((m - x0, m - y0), palabra, font=f, fill=255, anchor='ls')
    ImageDraw.Draw(con_trazo).text((m - x0, m - y0), palabra, font=f, fill=255, anchor='ls', stroke_width=trazo,
                                   stroke_fill=255)
    contorno = ImageChops.subtract(con_trazo, lleno)
    capa = Image.new('RGBA', (w, h), _claro(acento, 0.2)[:3] + (0,))
    capa.putalpha(contorno.point(lambda v: int(v * 0.36)))
    relleno = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    relleno.putalpha(lleno.point(lambda v: int(v * 0.035)))
    return Image.alpha_composite(relleno, capa)


def _linea_titular(s, tam, col, u):
    """Una línea del titular con una sombra oscura y ancha alrededor de las letras (apaga el aro y el brillo que pasan
    por detrás, para que se lea). Devuelve la capa, el ancho de la tinta y dónde quedan, dentro de la capa, el borde
    izquierdo de la tinta y la línea de base."""
    f = B.fuente('extrabold', tam)
    x0, y0, x1, y1 = f.getbbox(s, anchor='ls')
    halo = 12 * u
    M = int(math.ceil(halo * 3 + 4))
    w, h = int(math.ceil(x1 - x0 + 2 * M)), int(math.ceil(y1 - y0 + 2 * M))
    letras = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(letras).text((M - x0, M - y0), s, font=f, fill=col, anchor='ls')
    a = np.asarray(letras.split()[3], np.float32) / 255.0
    a = cv2.dilate(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    a = cv2.GaussianBlur(a, (0, 0), halo)
    sombra = np.zeros((h, w, 4), np.uint8)
    sombra[..., 0], sombra[..., 1], sombra[..., 2] = 10, 5, 22
    sombra[..., 3] = np.clip(a * 0.85 * 255 + 0.5, 0, 255).astype(np.uint8)
    capa = Image.alpha_composite(Image.fromarray(sombra, 'RGBA'), letras)
    return capa, x1 - x0, M, M - y0


def _titular(c, lineas, acento, lado, cx, cy, an, arriba_cabeza):
    """Las líneas del titular y dónde va el centro de cada una. Prueba encima de la cabeza y a su lado, y se queda con
    el sitio donde sale más grande. Alineadas a la izquierda, colocadas por su línea de base."""
    u = c.u
    izq, der = B.zona_segura(c)
    f100 = B.fuente('extrabold', 100)
    largo = max(f100.getlength(s) for s in lineas) / 100.0          # el ancho de la línea más larga, por punto de letra
    n = len(lineas)
    MAYUS, AIRE = 0.71, 0.25                                         # la altura de las mayúsculas y el aire entre líneas
    alto_por_punto = n * MAYUS + (n - 1) * AIRE
    techo = 210 * u                                                  # lo de arriba lo tapa Instagram
    # encima de la cabeza: hasta tres cuartos de la zona segura de ancho, y el alto hasta la cabeza
    tam_encima = min(124 * u, 0.76 * (der - izq) / largo, (arriba_cabeza - 36 * u - techo) / alto_por_punto)
    # al lado: el sitio entre la cabeza y el borde
    if lado == 'derecha':
        sitio = der - (cx + 0.85 * an + 30 * u)
    else:
        sitio = (cx - 0.85 * an - 30 * u) - izq
    tam_lado = min(124 * u, sitio / largo)
    al_lado = tam_lado > tam_encima
    tam = max(34 * u, tam_lado if al_lado else tam_encima)
    hechas = []
    for i, s in enumerate(lineas):
        col = BLANCO if i % 2 == 0 else _claro(acento, 0.12)
        hechas.append(_linea_titular(s, tam, col, u))
    ancho_bloque = max(h[1] for h in hechas)
    alto_bloque = alto_por_punto * tam
    x_tinta = der - ancho_bloque if lado == 'derecha' else izq
    if al_lado:
        y0 = max(techo, arriba_cabeza - 0.15 * alto_bloque)
    else:
        y0 = max(techo, arriba_cabeza - 36 * u - alto_bloque)
    capas, sitios = [], []
    base = y0
    for capa, _, izq_tinta, linea_base in hechas:
        base += MAYUS * tam
        capas.append(capa)
        sitios.append((x_tinta - izq_tinta + capa.width / 2, base - linea_base + capa.height / 2))
        base += AIRE * tam
    return capas, sitios


def _franja(c, nombre, usuario, acento):
    """La franja del nombre (banda del color de acento) y la del usuario (banda oscura), las dos saliendo del borde
    izquierdo. El texto empieza en la zona segura."""
    u = c.u
    izq, _ = B.zona_segura(c)
    t_nombre = _tinta(nombre, 60 * u, 'extrabold', BLANCO, margen=2)
    t_usuario = _tinta(usuario, 39 * u, 'medium', BLANCO, margen=2) if usuario else None
    alto_n = int(round(0.72 * 60 * u + 2 * 24 * u))
    ancho_n = int(round(izq + 6 * u + t_nombre.width + 40 * u))
    banda = B.caja(ancho_n + 40 * u, alto_n, 10 * u, acento)
    banda = banda.crop((int(40 * u), 0, banda.width, banda.height))             # sin las esquinas de la izquierda
    banda.alpha_composite(t_nombre, (int(round(izq + 6 * u)), int(round((alto_n - t_nombre.height) / 2))))
    sub = None
    if t_usuario is not None:
        alto_u = int(round(t_usuario.height + 2 * 15 * u))
        ancho_u = int(round(izq + 6 * u + t_usuario.width + 30 * u))
        sub = B.caja(ancho_u + 40 * u, alto_u, 8 * u, (36, 25, 68, 240))
        sub = sub.crop((int(40 * u), 0, sub.width, sub.height))
        sub.alpha_composite(t_usuario, (int(round(izq + 6 * u)), int(round((alto_u - t_usuario.height) / 2))))
    return banda, sub


def _medidas_boton(c):
    """Las medidas del botón: las del botón de seguir, agrandadas hasta que «Seguir» ocupe un tercio del ancho."""
    md = bs._medidas(c)
    k = min(1.7, max(1.0, 0.33 * c.W / md['w1']))
    return {clave: v * k for clave, v in md.items()}


def _pastilla(c, w, fondo, k_viejo, k_nuevo, k_marca):
    """El botón con ancho w: antes, «+» y el texto en blanco; después, la marca del color de acento y el texto oscuro."""
    e = c.estado
    md = e['md']
    h = md['alto']
    capa = B.caja(w, h, h / 2, fondo)
    yc = capa.height / 2
    for k, icono, s, col in ((k_viejo, e['mas'], c.op.get('texto') or 'Seguir', BLANCO),
                             (k_nuevo, e['marca'], c.op.get('texto_hecho') or 'Siguiendo', OSCURO)):
        if k <= 0.01:
            continue
        contenido = Image.new('RGBA', capa.size, (0, 0, 0, 0))
        x = md['lado']
        ic = icono
        if icono is e['marca'] and k_marca < 0.999:                          # la marca entra creciendo
            lado_ic = max(1, int(round(icono.width * (0.4 + 0.6 * k_marca))))
            ic = icono.resize((lado_ic, lado_ic), Image.LANCZOS)
        contenido.alpha_composite(ic, (int(round(x + (md['icono'] - ic.width) / 2)), int(round(yc - ic.height / 2))))
        bs._escribir(contenido, s, md['tam'], 'bold', x + md['icono'] + md['hueco'], yc, col)
        if k < 0.999:
            contenido.putalpha(contenido.split()[3].point(lambda v, k=k: int(v * k)))
        capa.alpha_composite(contenido)
    return capa


def _preparar(c):
    e = c.estado
    u = c.u
    cx, cy, an = c.cara
    izq, der = B.zona_segura(c)
    acento = B.color(c.op.get('color') or '#8B5CF6')
    e['acento'] = acento
    e['color_persona'] = _si(c.op.get('color_persona', 'no'))
    e['con_boton'] = _si(c.op.get('boton', 'si'))

    # los lados: el botón donde dicen (o donde hay más sitio) y el titular donde hay más sitio (si da igual, enfrente
    # del botón, para que no se amontone todo en un lado)
    sitio_der, sitio_izq = der - cx, cx - izq
    lado = (c.op.get('lado') or 'auto').strip().lower()
    if lado not in ('izquierda', 'derecha'):
        lado = 'derecha' if sitio_der >= sitio_izq else 'izquierda'
    e['lado'] = lado
    if abs(sitio_der - sitio_izq) < 0.1 * (der - izq):
        lado_tit = ('derecha' if lado == 'izquierda' else 'izquierda') if e['con_boton'] else 'derecha'
    else:
        lado_tit = 'derecha' if sitio_der > sitio_izq else 'izquierda'

    # el fondo quieto con las letras gigantes ya puestas (no se mueven: se pintan una vez), y el aro. Todo se coloca
    # según dónde está la cabeza al empezar y ya no la persigue: es un decorado
    e['fondo'] = _degradado(c, cx, cy - 0.3 * an, acento)
    palabra = (c.op.get('letras') or '').strip()
    if not palabra:
        palabras = [p for p in (c.op.get('nombre') or '').split() if p]
        palabra = max(palabras, key=len) if palabras else ''
    if palabra and palabra.lower() != 'no':
        lienzo = B.Cuadro(img=e['fondo'], mascara=c.mascara, cara=c.cara, t=0.0, dur=c.dur, fps=c.fps)
        B.poner(lienzo, _letras_gigantes(c, palabra.upper(), acento), c.W / 2 + 20 * u, max(cy + 2.0 * an, 0.56 * c.H))
    R = min(430 * u, max(220 * u, 1.75 * an))
    e['anillo'] = _aro(R, max(2.0, 6 * u), 16 * u, acento)

    # el titular (lo alto de la cabeza sale de la silueta; si no hay, se calcula por la cara)
    arriba_cabeza = cy - 1.35 * an
    x0, x1 = int(max(0, cx - 0.8 * an)), int(min(c.W, cx + 0.8 * an))
    filas = np.where(c.mascara[:, x0:x1].max(axis=1) > 0.5)[0] if x1 > x0 else []
    if len(filas) and cy - 2.0 * an < filas[0] < cy - 0.5 * an:
        arriba_cabeza = float(filas[0])
    lineas = [s.strip() for s in (c.op.get('lineas') or '').split('|') if s.strip()][:4]
    e['titular'] = _titular(c, lineas, acento, lado_tit, cx, cy, an, arriba_cabeza) if lineas else ([], [])

    # la franja del nombre: abajo a la izquierda, sobre el cuerpo y siempre por debajo de la cara
    nombre = (c.op.get('nombre') or '').strip()
    usuario = (c.op.get('usuario') or '').strip()
    e['franja'] = _franja(c, nombre, usuario, acento) if nombre else (None, None)
    banda, sub = e['franja']
    alto_franja = (banda.height if banda else 0) + (sub.height if sub else 0)
    e['franja_y'] = max(0.70 * c.H, cy + 1.2 * an)
    if e['franja_y'] + alto_franja > 0.80 * c.H:                     # que no baje a lo que tapa Instagram
        e['franja_y'] = max(cy + 1.0 * an, 0.80 * c.H - alto_franja)

    # el botón: grande, pegado al borde de la zona segura de su lado, a la altura del pecho
    if e['con_boton']:
        md = _medidas_boton(c)
        e['md'] = md
        e['mas'] = bs._mas(md['icono'] * 0.86, 7 * u * md['alto'] / (112 * u), BLANCO)
        e['marca'] = bs._marca(md['icono'], 7 * u * md['alto'] / (112 * u), acento)
        y = cy + 1.95 * an
        if lado == 'izquierda' and banda is not None:                # encima de la franja, con aire
            y = min(y, e['franja_y'] - 46 * u - md['alto'] / 2)
        y = max(y, cy + 0.9 * an + md['alto'] / 2 + 20 * u)           # nunca sobre la cara
        e['boton_y'] = y
        e['puntero'], e['punta'] = bs._puntero(100 * u, u)
        e['sombra'] = (18 * u, 10 * u)

    e['centro'] = (cx, cy - 0.2 * an)                                # el centro del aro y del círculo de la entrada
    e['listo'] = True


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _borde(m, u):
    """La máscara con el contorno alisado, un pelo hacia dentro y con el filo suave (`base.borde_firme`): así desaparecen
    los dientes del borde (donde detrás había una pantalla o una mesa) y no queda el filo claro del fondo de verdad
    alrededor del pelo, la oreja y los hombros."""
    return B.borde_firme(m, u)


def _sin_halo(p, m, u):
    """Los últimos píxeles del borde toman el tono de la persona de justo al lado (`base.sin_halo`)."""
    return B.sin_halo(p, m, u)


def _persona(c, m):
    """La persona: en blanco y negro con más contraste (o con sus colores, algo más contrastados)."""
    if c.estado['color_persona']:
        p = c.img * np.float32(1.08) - np.float32(0.08 * PIVOTE)
        np.clip(p, 0, 1, out=p)
        return _sin_halo(p, m, c.u)
    g = cv2.cvtColor(c.img, cv2.COLOR_RGB2GRAY)
    g *= np.float32(CONTRASTE)
    g -= np.float32(PIVOTE * (CONTRASTE - 1))
    np.clip(g, 0, 1, out=g)
    return cv2.cvtColor(_sin_halo(g, m, c.u), cv2.COLOR_GRAY2RGB)


def _fondo_nuevo(c):
    """El fondo de este cuadro: el degradado con las letras, el aro y el titular (todo lo que va detrás). Mientras el aro
    y el titular entran, se pinta cada cuadro; cuando ya están quietos, se guarda hecho y se usa tal cual."""
    e = c.estado
    if 'fondo_hecho' in e:
        return e['fondo_hecho']
    u, t = c.u, c.t
    fondo = e['fondo'].copy()
    lienzo = B.Cuadro(img=fondo, mascara=c.mascara, cara=c.cara, t=t, dur=c.dur, fps=c.fps)
    ax, ay = e['centro']
    k_aro = B.sale(B.tramo(t, 0.08, 0.6))
    B.poner(lienzo, e['anillo'], ax, ay, escala=0.82 + 0.18 * k_aro, alfa=B.tramo(t, 0.08, 0.3))
    capas, sitios = e['titular']
    for i, (capa, (x, y)) in enumerate(zip(capas, sitios)):
        k = B.sale(B.tramo(t, 0.16 + 0.09 * i, 0.54 + 0.09 * i))
        B.poner(lienzo, capa, x, y + (1 - k) * 36 * u, alfa=k)
    if t >= QUIETO:
        e['fondo_hecho'] = fondo
        del e['fondo']
    return fondo


def _entrada(c, nuevo, k):
    """El círculo que se abre desde la cabeza: dentro, lo nuevo; fuera, el cuadro de verdad (que ya está en c.img); en
    el filo, una línea de luz del color de acento. Solo se calcula en el cuadrado que ocupa el círculo."""
    e = c.estado
    u = c.u
    cx, cy = e['centro']
    if 'dist_max' not in e:
        e['dist_max'] = max(math.hypot(x - cx, y - cy) for x in (0, c.W) for y in (0, c.H))
    R = k * (e['dist_max'] + 40 * u)
    ancho_filo = 7 * u
    borde = R + 4 * ancho_filo
    x0, x1 = int(max(0, math.floor(cx - borde))), int(min(c.W, math.ceil(cx + borde)))
    y0, y1 = int(max(0, math.floor(cy - borde))), int(min(c.H, math.ceil(cy + borde)))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.ogrid[y0:y1, x0:x1]
    d = np.sqrt((xx.astype(np.float32) - np.float32(cx)) ** 2 + (yy.astype(np.float32) - np.float32(cy)) ** 2)
    r = np.clip((np.float32(R) - d) * np.float32(1.0 / (22 * u)) + np.float32(0.5), 0, 1)
    caja = c.img[y0:y1, x0:x1]
    mezcla = cv2.blendLinear(np.ascontiguousarray(caja), np.ascontiguousarray(nuevo[y0:y1, x0:x1]), 1.0 - r, r)
    filo = np.exp(-((d - np.float32(R)) / np.float32(ancho_filo)) ** 2) * np.float32(0.9 * (1 - k) ** 0.5)
    luz = np.array(_claro(e['acento'], 0.4)[:3], np.float32) / 255.0
    mezcla += filo[..., None] * luz
    caja[...] = mezcla


def _boton_y_puntero(c, vis):
    e = c.estado
    u, t = c.u, c.t
    md = e['md']
    izq, der = B.zona_segura(c)
    m = bs._momento(c)
    signo = 1 if e['lado'] == 'derecha' else -1
    acento = e['acento']

    # el cambio de «Seguir» a «Siguiendo» (0,2 s desde la pulsación): se estira y se vuelve blanco
    k_cambio = B.suave(B.tramo(t, m, m + 0.2))
    w = B.mezclar(md['w1'], md['w2'], k_cambio)
    fondo = tuple(int(round(B.mezclar(a, b, k_cambio))) for a, b in zip(acento, BLANCO))
    k_viejo = 1 - B.tramo(t, m + 0.04, m + 0.14)
    k_nuevo = B.tramo(k_cambio, 0.72, 1.0)
    k_marca = B.rebote(B.tramo(t, m + 0.12, m + 0.4), 1.6)
    sd, sy = e['sombra']
    if k_cambio <= 0:
        if 'boton_antes' not in e:
            e['boton_antes'] = B.con_sombra(_pastilla(c, md['w1'], acento, 1, 0, 0), sd, sy, 130)
        capa = e['boton_antes']
    elif k_cambio >= 1 and k_marca >= 0.999 and t > m + 0.5:
        if 'boton_despues' not in e:
            e['boton_despues'] = B.con_sombra(_pastilla(c, md['w2'], BLANCO, 0, 1, 1), sd, sy, 130)
        capa = e['boton_despues']
    else:
        capa = B.con_sombra(_pastilla(c, w, fondo, k_viejo, k_nuevo, k_marca), sd, sy, 130)

    k_pulsa = B.tramo(t, m - 0.07, m + 0.05) * (1 - B.suave(B.tramo(t, m + 0.05, m + 0.3)))
    hundir = 1 - 0.06 * B.suave(k_pulsa)
    k_entra = B.rebote(B.tramo(t, 0.36, 0.86), 1.5)
    escala = (0.35 + 0.65 * k_entra) * hundir
    alfa = B.tramo(t, 0.36, 0.52) * vis
    bx = izq + w / 2 if signo < 0 else der - w / 2                   # pegado al borde de su lado; crece hacia dentro
    by = e['boton_y'] + 3 * u * B.suave(k_pulsa)
    B.poner(c, capa, bx, by, escala=escala, alfa=alfa)

    # el destello alrededor del botón ya pulsado
    if vis > 0.5:
        bs._destello(c, bx, by, md['w2'], md['alto'], B.tramo(t, m + 0.16, m + 0.8), acento, signo)

    # el puntero: sube desde abajo, pulsa y se va
    k_va = B.sale(B.tramo(t, m - 0.85, m - 0.06))
    k_vuelve = B.suave(B.tramo(t, m + 0.4, m + 0.95))
    alfa_p = B.tramo(t, m - 0.85, m - 0.6) * (1 - B.tramo(t, m + 0.6, m + 0.95)) * vis
    if alfa_p <= 0:
        return
    x_texto = (izq + md['w1'] * 0.62) if signo < 0 else (der - md['w1'] * 0.38)
    destino = (x_texto, e['boton_y'] + md['alto'] * 0.14)
    inicio = (destino[0] - signo * 60 * u, destino[1] + 420 * u)
    control = (destino[0] - signo * 200 * u, destino[1] + 120 * u)
    s = k_va
    px = (1 - s) ** 2 * inicio[0] + 2 * (1 - s) * s * control[0] + s * s * destino[0]
    py = (1 - s) ** 2 * inicio[1] + 2 * (1 - s) * s * control[1] + s * s * destino[1]
    px -= signo * 110 * u * k_vuelve                                 # al irse, baja hacia el cuerpo
    py += 220 * u * k_vuelve
    esc_p = 1 - 0.14 * B.suave(k_pulsa)
    cap = e['puntero']
    tx, ty = e['punta']
    k_aro = B.tramo(t, m - 0.04, m + 0.36)                            # el aro del clic, en la punta
    if 0 < k_aro < 1:
        r = (14 + 46 * B.sale(k_aro)) * u
        aro = Image.new('RGBA', (int(r * 2 + 10 * u) * 3,) * 2, (0, 0, 0, 0))
        o = aro.width / 2
        ImageDraw.Draw(aro).ellipse([o - r * 3, o - r * 3, o + r * 3, o + r * 3], outline=BLANCO, width=int(6 * u * 3))
        aro = aro.resize((aro.width // 3, aro.height // 3), Image.LANCZOS)
        B.poner(c, aro, px, py, alfa=0.85 * (1 - k_aro) * alfa_p)
    B.poner(c, cap, px + (cap.width / 2 - tx) * esc_p, py + (cap.height / 2 - ty) * esc_p, escala=esc_p, alfa=alfa_p)


def dibujar(c):
    e = c.estado
    if not e.get('listo'):
        _preparar(c)
    u, t = c.u, c.t
    k_in = B.sale(B.tramo(t, 0, ENTRA))
    vis = B.suave(B.tramo(c.queda, 0, SALE))                         # 1 = lo nuevo; 0 = el cuadro de verdad
    if k_in <= 0 or vis <= 0:
        return

    m = _borde(c.mascara, u)
    persona = _persona(c, m)
    fondo = _fondo_nuevo(c)
    fuera = 1.0 - m
    if k_in >= 1 and vis >= 1:                                       # lo normal: se pinta directo en el cuadro
        cv2.blendLinear(fondo, persona, fuera, m, dst=c.img)
    else:                                                            # entrando o saliendo: hace falta el cuadro de verdad
        nuevo = cv2.blendLinear(fondo, persona, fuera, m)
        real = c.img.copy() if (k_in < 1 and vis < 1) else None      # (solo si el efecto es tan corto que se pisan)
        if k_in < 1:
            _entrada(c, nuevo, k_in)
            if vis < 1:
                cv2.addWeighted(c.img, vis, real, 1.0 - vis, 0.0, dst=c.img)
        else:
            cv2.addWeighted(nuevo, vis, c.img, 1.0 - vis, 0.0, dst=c.img)

    # delante de la persona: la franja del nombre y el botón
    banda, sub = e['franja']
    if banda is not None:
        y = e['franja_y']
        for capa, t0, yy in ((banda, 0.28, y), (sub, 0.36, y + banda.height)):
            if capa is None:
                continue
            k = B.sale(B.tramo(t, t0, t0 + 0.34))
            ancho = int(math.ceil(capa.width * k))
            if ancho < 2:
                continue
            trozo = capa if ancho >= capa.width else capa.crop((0, 0, ancho, capa.height))
            B.poner(c, trozo, trozo.width / 2, yy + capa.height / 2, alfa=vis)
    if e['con_boton']:
        _boton_y_puntero(c, vis)
