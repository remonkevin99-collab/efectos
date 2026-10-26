"""Tier list: una tabla de clasificación de la S a la F en la mitad de abajo, y lo tuyo entra volando hasta la S.

Una tarjeta de cristal sube desde abajo con un título y seis filas (cada letra con su color). Lo que ya está clasificado
cae en su fila, una cosa detrás de otra, y el elemento principal entra volando en un arco desde un lado hasta su fila,
aterriza con un rebote y suelta un pequeño destello. La tabla nunca tapa la cara: se pone debajo de la barbilla (o encima
de la cabeza si abajo no cabe). Al final se va con un fundido.

    .venv/bin/python efectos.py tier-list tu_video.mp4 --duracion 4.5 --fotos 0.3,1.0,1.9,2.4,3.5

"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import base as B

try:                                   # OpenCV hace el desenfoque del cristal mucho más rápido; si no está, Pillow
    import cv2
except ImportError:                    # pragma: no cover
    cv2 = None

NOMBRE = 'tier-list'
DESCRIPCION = 'Una tabla de la S a la F y lo tuyo entra volando hasta arriba'
OPCIONES = {
    'titulo': '¿La mejor forma de editar un Reel?',
    'filas': 'S:|A:|B:Plantillas|C:Líneas de tiempo|D:Apps|F:A mano',   # «letra:cosa, otra cosa|…»
    'elemento': 'Claude',                                              # lo que entra volando
    'fila': 'S',                                                       # la fila donde aterriza
    'color': '#8B5CF6',                                                # el color del elemento y del destello
}
DURACION = 4.5

# la paleta de las letras (propia): de lo mejor (cálido) a lo peor (frío), todas claras para que la letra oscura se lea
PALETA = {'S': '#FF6B7A', 'A': '#FFA45B', 'B': '#FFD45C', 'C': '#7DDB8C', 'D': '#62C3F5', 'E': '#8F9BFF', 'F': '#C59BFF'}
ORDEN = ['#FF6B7A', '#FFA45B', '#FFD45C', '#7DDB8C', '#62C3F5', '#8F9BFF', '#C59BFF']
TINTA = (28, 21, 55, 255)              # el texto oscuro (#1C1537)
BLANCO = (255, 255, 255, 255)


# ── Leer las opciones ───────────────────────────────────────────────────────────────────────────────────────────────
def _filas(texto):
    """'S:|B:Plantillas,Apps' → [('S', []), ('B', ['Plantillas', 'Apps'])]."""
    filas = []
    for trozo in str(texto).split('|'):
        trozo = trozo.strip()
        if not trozo:
            continue
        letra, _, cosas = trozo.partition(':')
        filas.append((letra.strip()[:3] or '?', [s.strip() for s in cosas.split(',') if s.strip()]))
    return filas or [('S', [])]


# ── Piezas que no cambian ───────────────────────────────────────────────────────────────────────────────────────────
def _escribir(capa, s, tam, peso, x, y_centro, col, centrado=False):
    """Escribe con las mayúsculas centradas en y_centro."""
    f = B.fuente(peso, tam)
    alto_mayus = -f.getbbox('H', anchor='ls')[1]
    ImageDraw.Draw(capa).text((x, y_centro + alto_mayus / 2), s, font=f, fill=col, anchor='ms' if centrado else 'ls')


def _ficha(texto, alto, tam, fondo, tinta, u, peso='bold'):
    """Una ficha (lo que va dentro de una fila): una pastilla con su texto."""
    f = B.fuente(peso, tam)
    w = f.getlength(texto) + 2 * 22 * u
    capa = B.caja(w, alto, 14 * u, fondo)
    _escribir(capa, texto, tam, peso, capa.width / 2, capa.height / 2, tinta, centrado=True)
    return capa


def _titulo(texto, ancho, u):
    """El título en una o dos líneas, lo más grande que quepa (como mucho 52)."""
    f = B.fuente('bold', 100)
    tam = min(52 * u, 100 * ancho / max(1.0, f.getlength(texto)))
    if tam >= 40 * u:
        return [texto], tam
    palabras = texto.split()                                           # en dos líneas, lo más parejas posible
    mejor = None
    for i in range(1, len(palabras)):
        a, b = ' '.join(palabras[:i]), ' '.join(palabras[i:])
        largo = max(f.getlength(a), f.getlength(b))
        if mejor is None or largo < mejor[0]:
            mejor = (largo, [a, b])
    if mejor is None:
        return [texto], tam
    return mejor[1], min(48 * u, 100 * ancho / max(1.0, mejor[0]))


def _preparar(c):
    u = c.u
    e = c.estado
    cx, cy, ancho = c.cara
    izq, der = B.zona_segura(c)
    filas = _filas(c.op.get('filas', OPCIONES['filas']))
    n = len(filas)
    lineas, tam_t = _titulo(str(c.op.get('titulo', '')).strip(), (der - izq) - 2 * 34 * u, u)
    pad, gap = 22 * u, 8 * u
    alto_tit = (len(lineas) * tam_t * 1.22 + 26 * u) if lineas and lineas[0] else 0

    # dónde cabe: debajo de la barbilla (lo normal) o encima de la cabeza
    barbilla = cy + 1.05 * ancho
    cabeza = cy - 0.85 * ancho
    abajo = (c.H - 150 * u) - (barbilla + 40 * u)
    arriba = (cabeza - 40 * u) - 150 * u
    fijo = 2 * pad + alto_tit + (n - 1) * gap
    debajo = abajo >= fijo + n * 62 * u or abajo >= arriba
    sitio = abajo if debajo else arriba
    rh = max(54 * u, min(92 * u, (sitio - fijo) / n))
    alto = fijo + n * rh
    x0 = int(round(izq))
    w = int(round(der - izq))
    h = int(round(alto))
    if debajo:                                                         # lo más abajo que se pueda, sin pasar del margen
        y0 = int(round(max(barbilla + 40 * u, c.H - 150 * u - h)))
    else:
        y0 = int(round(cabeza - 40 * u - h))
    e['caja'] = (x0, y0, w, h)
    e['debajo'] = debajo

    # la tarjeta: el contenido fijo (título, letras y carriles), en una capa del tamaño de la tarjeta
    contenido = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    y = pad
    for ln in lineas if lineas and lineas[0] else []:
        _escribir(contenido, ln, tam_t, 'bold', w / 2, y + tam_t * 0.61, BLANCO, centrado=True)
        y += tam_t * 1.22
    if alto_tit:
        y += 26 * u
    filas_geo = []
    lado_letra = rh
    carril_x = pad + lado_letra + 10 * u
    carril_w = w - carril_x - pad
    for i, (letra, cosas) in enumerate(filas):
        col = B.color(PALETA.get(letra.upper(), ORDEN[i % len(ORDEN)]))
        etiqueta = B.caja(lado_letra, rh, 14 * u, col)
        _escribir(etiqueta, letra, rh * (0.5 if len(letra) == 1 else 0.36), 'extrabold', etiqueta.width / 2,
                  etiqueta.height / 2, TINTA, centrado=True)
        contenido.alpha_composite(etiqueta, (int(round(pad)), int(round(y))))
        contenido.alpha_composite(B.caja(carril_w, rh, 14 * u, (255, 255, 255, 20)), (int(round(carril_x)), int(round(y))))
        filas_geo.append(dict(letra=letra, cosas=cosas, y=y + rh / 2, col=col))
        y += rh + gap
    e['filas'] = filas_geo
    e['rh'] = rh

    # el cristal: su forma (esquinas redondeadas) y su filo, una vez
    forma = np.asarray(B.caja(w, h, 30 * u, BLANCO).split()[3], np.float32) / 255.0
    e['forma'] = forma[..., None]
    filo = B.caja(w, h, 30 * u, (0, 0, 0, 0), borde=(255, 255, 255, 40), grosor=max(1, 1.5 * u))
    contenido_con_filo = filo.copy()
    contenido_con_filo.alpha_composite(contenido)
    arr = np.asarray(contenido_con_filo, np.float32) / 255.0             # el contenido, ya listo para mezclar
    e['cont_a'] = np.ascontiguousarray(arr[..., 3:4])
    e['cont_rgb'] = np.ascontiguousarray(arr[..., :3] * arr[..., 3:4])

    # las fichas de lo que ya está clasificado (caen en su sitio)
    alto_ficha = rh * 0.68
    tam_ficha = rh * 0.35
    fichas = []
    hueco_ficha = 10 * u
    for i, fg in enumerate(filas_geo):
        x = x0 + carril_x + 12 * u
        for cosa in fg['cosas']:
            f = _ficha(cosa, alto_ficha, tam_ficha, (255, 255, 255, 240), TINTA, u)
            fichas.append(dict(capa=f, x=x + f.width / 2, y=y0 + fg['y'], fila=i))
            x += f.width + hueco_ficha
        fg['libre'] = x                                                 # dónde empieza el sitio libre de la fila
    e['fichas'] = fichas

    # el elemento principal: una ficha más grande, del color de acento, con sombra
    acento = B.color(c.op.get('color', '#8B5CF6'))
    e['acento'] = acento
    el = _ficha(str(c.op.get('elemento', 'Claude')).strip() or 'Claude', rh * 0.8, rh * 0.42, acento, BLANCO, u,
                'extrabold')
    filo_el = B.caja(el.width, el.height, 14 * u, (0, 0, 0, 0), borde=(255, 255, 255, 120), grosor=2 * u)
    el.alpha_composite(filo_el)
    e['elemento'] = B.con_sombra(el, 14 * u, 8 * u, 120)
    e['el_w'], e['el_h'] = el.width, el.height
    meta = str(c.op.get('fila', 'S')).strip().upper()
    destino = next((fg for fg in filas_geo if fg['letra'].upper() == meta), filas_geo[0])
    ex = min(destino['libre'] + el.width / 2, x0 + w - pad - el.width / 2)
    e['destino'] = (ex, y0 + destino['y'])
    e['fila_meta'] = destino

    # el arco del vuelo: entra por el lado de fuera de la pantalla y nunca pasa por encima de la cara
    sale_x = c.W + el.width * 0.7 if ex < c.W / 2 or cx < c.W / 2 else -el.width * 0.7
    if debajo:
        p0 = (sale_x, e['destino'][1] + 430 * u)
        p1 = (c.W * 0.62 if sale_x > 0 else c.W * 0.38, e['destino'][1] - 210 * u)
        limite = barbilla + 24 * u + el.height / 2                       # lo más alto que puede subir el centro
        for _ in range(8):
            ys = [(1 - s) ** 2 * p0[1] + 2 * (1 - s) * s * p1[1] + s * s * e['destino'][1] for s in np.linspace(0, 1, 41)]
            if min(ys) >= limite:
                break
            p1 = (p1[0], p1[1] + 2 * (limite - min(ys)) + 2 * u)
    else:
        p0 = (sale_x, e['destino'][1] - 430 * u)
        p1 = (c.W * 0.62 if sale_x > 0 else c.W * 0.38, e['destino'][1] + 210 * u)
        limite = cabeza - 24 * u - el.height / 2
        for _ in range(8):
            ys = [(1 - s) ** 2 * p0[1] + 2 * (1 - s) * s * p1[1] + s * s * e['destino'][1] for s in np.linspace(0, 1, 41)]
            if max(ys) <= limite:
                break
            p1 = (p1[0], p1[1] - 2 * (max(ys) - limite) - 2 * u)
    e['arco'] = (p0, p1)
    e['giro0'] = -22 if sale_x > 0 else 22
    # el brillo de la fila cuando aterriza (una mancha suave de su color)
    br = B.caja(w - 2 * 16 * u, rh + 14 * u, 20 * u, destino['col'][:3] + (255,))
    e['brillo'] = br.filter(ImageFilter.GaussianBlur(7 * u))
    e['rayas'] = [B.caja(34 * u, 9 * u, 4.5 * u, BLANCO),
                  B.caja(34 * u, 9 * u, 4.5 * u, tuple(int(B.mezclar(v, 255, 0.4)) for v in acento[:3]) + (255,))]
    e['listo'] = True


# ── El cristal (cambia cada cuadro, porque lo de detrás se mueve) ───────────────────────────────────────────────────
def _vidrio(c, x0, y0, w, h):
    """Lo que hay detrás de la tarjeta, muy desenfocado y oscurecido. Para que sea rápido, se desenfoca en pequeño."""
    u = c.u
    ya, yb = max(0, y0), min(c.H, y0 + h)
    xa, xb = max(0, x0), min(c.W, x0 + w)
    trozo = np.empty((h, w, 3), np.float32)
    trozo[:] = 0.06
    if yb > ya and xb > xa:
        trozo[ya - y0:yb - y0, xa - x0:xb - x0] = c.img[ya:yb, xa:xb]
    peq_w, peq_h = max(2, w // 8), max(2, h // 8)
    if cv2 is not None:
        peq = cv2.resize(trozo, (peq_w, peq_h), interpolation=cv2.INTER_AREA)
        peq = cv2.GaussianBlur(peq, (0, 0), 3.2 * u)
        borroso = cv2.resize(peq, (w, h), interpolation=cv2.INTER_LINEAR)
    else:
        im = B.a_capa(trozo).convert('RGB').resize((peq_w, peq_h), Image.BOX).filter(ImageFilter.GaussianBlur(3.2 * u))
        borroso = np.asarray(im.resize((w, h), Image.BILINEAR), np.float32) / 255.0
    tinte = np.array([14, 12, 24], np.float32) / 255.0
    return borroso * 0.30 + tinte * 0.70


def _tarjeta(c, x0, y, alfa):
    """Pone la tarjeta (el cristal con su contenido encima) con su borde de arriba en y, con decimales: se mueve solo en
    vertical, así que el medio píxel se reparte entre dos filas (no va a saltitos y es muy rápido)."""
    e = c.estado
    _, _, w, h = e['caja']
    if alfa <= 0.003:
        return
    yi = int(math.floor(y))
    fr = np.float32(y - yi)
    forma, ca, crgb = e['forma'], e['cont_a'], e['cont_rgb']
    vid = _vidrio(c, x0, yi, w, h)
    pm = vid * (forma * (1.0 - ca))                                    # el cristal donde no hay contenido…
    pm += crgb                                                         # …y el contenido encima (ya multiplicado por su alfa)
    a = ca + forma * (1.0 - ca)
    if fr > 0.002:                                                     # el trozo de píxel: una fila más, repartida
        pm2 = np.zeros((h + 1, w, 3), np.float32)
        a2 = np.zeros((h + 1, w, 1), np.float32)
        pm2[:h] = pm * (1 - fr)
        pm2[1:] += pm * fr
        a2[:h] = a * (1 - fr)
        a2[1:] += a * fr
        pm, a = pm2, a2
    hh = pm.shape[0]
    ya, yb = max(0, yi), min(c.H, yi + hh)
    xa, xb = max(0, x0), min(c.W, x0 + w)
    if yb <= ya or xb <= xa:
        return
    pm = pm[ya - yi:yb - yi, xa - x0:xb - x0]
    a = a[ya - yi:yb - yi, xa - x0:xb - x0] * np.float32(alfa)
    zona = c.img[ya:yb, xa:xb]
    zona *= (1.0 - a)
    zona += pm * np.float32(alfa)


# ── Poner lo que ya no se mueve, sin repetir trabajo ────────────────────────────────────────────────────────────────
def _poner(c, clave, capa, cx, cy, k, alfa, **mov):
    """Mientras se mueve (k < 1) se pone con B.poner, que mueve con decimales. Cuando ya está quieta, colocarla se hace
    una sola vez y se guarda: en los cuadros siguientes solo se mezcla con el cuadro."""
    if alfa <= 0.003:
        return
    if k < 1:
        B.poner(c, capa, cx, cy, alfa=alfa, **mov)
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
    zona = c.img[Y0:Y1, X0:X1]
    zona *= (1.0 - al)
    zona += rgb * al


# ── El destello del aterrizaje ──────────────────────────────────────────────────────────────────────────────────────
def _destello(c, cx, cy, w, h, k):
    """Rayitas que salen de la ficha hacia fuera y se apagan (k de 0 a 1)."""
    if k <= 0 or k >= 1:
        return
    u = c.u
    e = c.estado
    dist = (14 + 44 * B.sale(k)) * u
    alfa = (1 - B.entra(k)) * min(1.0, k * 7)
    sitios = []
    for ang in (-60, -20, 20, 60):                                     # por los dos lados
        th = math.radians(ang)
        sitios.append((w / 2 + dist * math.cos(th) + 4 * u, (h / 2) * math.sin(th) + dist * math.sin(th) * 0.6, th))
        sitios.append((-w / 2 - dist * math.cos(th) - 4 * u, (h / 2) * math.sin(th) + dist * math.sin(th) * 0.6,
                       math.pi - th))
    for fx in (-0.25, 0.25):                                           # por arriba
        th = math.atan2(-1, fx * 1.6)
        sitios.append((fx * w, -h / 2 - dist * 0.8, th))
    for n, (x, y, th) in enumerate(sitios):
        B.poner(c, e['rayas'][n % 2], cx + x, cy + y, escala=1 - 0.55 * k, giro=math.degrees(th), alfa=alfa)


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def dibujar(c):
    e = c.estado
    if not e.get('listo'):
        _preparar(c)
    u = c.u
    t = c.t / min(1.0, c.dur / DURACION)               # si el efecto dura menos de lo normal, todo entra más deprisa
    x0, y0, w, h = e['caja']
    signo = 1 if e['debajo'] else -1                                   # hacia dónde queda «lejos de la cara»
    fuera = B.suave(B.tramo(c.queda, 0, 0.4))                          # el fundido del final
    baja = signo * (1 - fuera) * 24 * u                                 # y al irse se aleja un poco de la cara

    # 1) la tarjeta sube desde abajo (o baja desde arriba, si va encima de la cabeza)
    k = B.sale(B.tramo(t, 0, 0.6))
    alfa = B.tramo(t, 0, 0.3) * fuera
    _tarjeta(c, x0, y0 + signo * (1 - k) * 110 * u + baja, alfa)

    # 2) lo que ya está clasificado cae en su fila, uno detrás de otro
    for i, f in enumerate(e['fichas']):
        a = 0.55 + 0.13 * i
        k = B.tramo(t, a, a + 0.42)
        if k <= 0:
            continue
        caida = (1 - B.rebote(k, 1.4)) * 64 * u
        quieta = 1 if (k >= 1 and abs(baja) <= 0.01) else 0
        _poner(c, f'ficha{i}', f['capa'], f['x'], f['y'] - caida + baja, quieta, min(1.0, k * 3) * fuera)

    # 3) el elemento vuela en arco hasta su fila y aterriza con un rebote
    sale_en = 0.75 + 0.13 * len(e['fichas']) + 0.25
    vuelo = 0.85
    llega = sale_en + vuelo
    k = B.tramo(t, sale_en, llega)
    if k <= 0:
        return
    (p0, p1), (dx, dy) = e['arco'], e['destino']
    kd = B.tramo(t, llega - 0.02, llega + 0.6)                         # el destello
    if 0 < kd < 1:                                                     # la fila de destino se ilumina un momento
        fg = e['fila_meta']
        B.poner(c, e['brillo'], x0 + w / 2, y0 + fg['y'] + baja, alfa=0.42 * (1 - B.sale(kd)) * min(1, kd * 6) * fuera)
    s = B.suave(k) * 0.35 + B.sale(k) * 0.65                             # arranca con fuerza y frena al llegar
    x = (1 - s) ** 2 * p0[0] + 2 * (1 - s) * s * p1[0] + s * s * dx
    y = (1 - s) ** 2 * p0[1] + 2 * (1 - s) * s * p1[1] + s * s * dy
    giro = e['giro0'] * (1 - B.sale(k))
    escala = 1.18 - 0.18 * B.sale(k)
    kt = B.tramo(t, llega, llega + 0.45)                               # al aterrizar: se aplasta, se pasa y vuelve
    if kt > 0:
        escala *= 1 - 0.09 * math.sin(kt * math.pi * 2) * (1 - kt) ** 1.4
    quieta = 1 if (kt >= 1 and abs(baja) <= 0.01) else 0
    _poner(c, 'elemento', e['elemento'], x, y + baja, quieta, min(1.0, k * 5) * fuera, escala=escala, giro=giro)
    _destello(c, dx, dy + baja, e['el_w'], e['el_h'], kd)
