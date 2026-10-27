"""Órbita: de 3 a 6 tarjetas con fotos giran alrededor de la cabeza en una elipse inclinada.

Las que pasan por detrás quedan DETRÁS de la persona (más pequeñas y algo más oscuras, asomando junto a la cabeza) y las de
delante pasan por encima, por el pecho, sin tapar nunca la cara. Entran creciendo (0,4 s, una detrás de otra), arrancan
pegadas a la persona y en 1,2 s se abren a una órbita más ancha (`radio_inicio` → `radio`), giran y se van encogiendo
(0,3 s). Al abrirse, por delante bajan más de lo que suben por detrás: así pasan por debajo de las manos y se ven los
gestos. Nunca se salen de la zona segura (x de 60 a 1020 a 1080 de ancho): si el radio no cabe, se quedan en lo que quepa.

Si se pide (`acelera`), en ese segundo la vuelta se acelera (`acelera_por` veces, durante `acelera_dura` s) y después
vuelve a su ritmo. Va muy bien con un gesto de la mano, como el de deslizar en el teléfono: parece que las empujas. Sin
tirones: la velocidad sube y baja suave y el ángulo es su suma exacta, así que de un cuadro al siguiente nunca salta. En
lo más rápido llevan un poco de desenfoque de movimiento (solo lo que va de más: a su ritmo normal se leen nítidas).

Detrás de la persona, su borde va con su color de verdad (`base.color_persona`): sin el filo de la pared alrededor del
pelo, la gorra o la mano cuando una tarjeta pasa por detrás.

Las fotos:
  - `imagenes=<carpeta>`: las de esa carpeta (jpg, png o webp, en orden; de 3 a 6, si hay menos se repiten).
  - si no se da carpeta: cuadros del propio vídeo, que pide al motor con `c.estado['sacar_cuadros'](n)` (`cantidad`).
  - y si tampoco hay motor (al probar el efecto suelto, sin vídeo): trozos del cuadro de ese momento.

    python efectos.py orbita mi-video.mp4 --desde 2 --hasta 6 --op imagenes=mis-fotos
    python efectos.py orbita mi-video.mp4 --desde 2 --hasta 6 --op imagenes=mis-fotos --op acelera=1.5
"""
import math

import cv2
import numpy as np
from PIL import Image

import base as B

NOMBRE = 'orbita'
DESCRIPCION = ('De 3 a 6 tarjetas con fotos giran alrededor de tu cabeza: arrancan pegadas a ti y se abren, pasan por '
               'detrás de ti y por delante sin taparte la cara, y si quieres se aceleran en el segundo que digas (con un '
               'gesto de la mano queda perfecto)')
OPCIONES = {
    # la carpeta con tus fotos (jpg, png o webp, de 3 a 6). Vacío: cuadros de tu propio vídeo
    'imagenes': '',
    # cuántas tarjetas (de 3 a 6)
    'cantidad': '5',
    # el ancho de cada tarjeta, en píxeles de un vídeo de 1080 de ancho
    'tamano': '300',
    # el ritmo de la vuelta: 1 = una vuelta cada 6 s; 2 = el doble de rápido; en negativo, giran al revés
    'velocidad': '1',
    # cuánto se separan de ti: 1 = pegadas; 1,3 = algo más abiertas; 1,6 = muy abiertas (si no caben, lo que quepa)
    'radio': '1.3',
    # de dónde arrancan: con menos que `radio`, empiezan pegadas y se abren en 1,2 s; igual que `radio`, no se abren
    'radio_inicio': '1',
    # el segundo (contado desde que empieza el efecto) en que la vuelta se acelera: ponlo cuando haces un gesto con la
    # mano. Varios, separados por «|» (por ejemplo «1,2|3,5»). Vacío = nunca
    'acelera': '',
    # cuántas veces más rápido giran en lo más rápido de la aceleración
    'acelera_por': '3',
    # cuánto dura cada aceleración, en segundos, contando lo que tarda en subir y en volver a su ritmo
    'acelera_dura': '1.2',
}
DURACION = 4.0

INCLINACION = -9.0      # grados: la elipse sube por la derecha
VUELTA = 6.0            # segundos por vuelta con velocidad 1
ENTRA, SALE = 0.4, 0.3  # lo que tarda cada tarjeta en crecer al entrar y en encogerse al irse
ESCALONADO = 0.05       # cada tarjeta entra un poco después que la anterior
OSCURO_ATRAS = 0.34     # cuánto se oscurecen las de detrás (0–1)
ABRE = 1.2              # lo que tardan en abrirse de `radio_inicio` a `radio` (desde que empieza el efecto)
SUBE, BAJA = 0.3, 0.45  # de cada aceleración: la parte que tarda en subir y la que tarda en volver (del total)
ESTELA = 0.6            # el desenfoque en lo rápido: qué parte del recorrido de más de un cuadro se emborrona
MARGEN = 60             # la zona segura (a 1080 de ancho)
ABAJO = 1.3             # al abrirse, cuánto más bajan por delante que lo que suben por detrás (deja ver las manos)


# ── Números de las opciones ─────────────────────────────────────────────────────────────────────────────────────────
def _num(v, defecto):
    """Un número de una opción, con coma o con punto («1,3» = «1.3»). Si no es un número, el de por defecto."""
    try:
        return float(str(v).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return float(defecto)


def _momentos(v):
    """Los segundos de `acelera` («1,2|3,5» → [1.2, 3.5]). Vacío, «no» o «nunca» → []."""
    s = str(v or '').strip().lower()
    if s in ('', 'no', 'nunca', 'ninguno', 'none'):
        return []
    out = []
    for trozo in s.replace(';', '|').replace(' ', '').split('|'):
        if trozo:
            try:
                out.append(float(trozo.replace(',', '.')))
            except ValueError:
                print(f'  Aviso (órbita): «{trozo}» en `acelera` no es un segundo; no lo uso.')
    return sorted(out)


# ── La aceleración ──────────────────────────────────────────────────────────────────────────────────────────────────
def _empuje(x, d):
    """Cuánto de la aceleración hay `x` segundos después de empezar (de 0 a 1 y vuelta a 0, en `d` segundos): sube con
    media onda de coseno, se queda arriba y baja igual de suave. Al empezar y al acabar cada tramo la curva va plana, así
    que la velocidad cambia sin saltos y su cambio tampoco salta."""
    s, b = SUBE * d, BAJA * d
    if x <= 0 or x >= d:
        return 0.0
    if x < s:
        return 0.5 - 0.5 * math.cos(math.pi * x / s)
    if x < d - b:
        return 1.0
    return 0.5 + 0.5 * math.cos(math.pi * (x - (d - b)) / b)


def _empuje_sumado(x, d):
    """La suma exacta (la integral) de `_empuje` de 0 a `x`: los segundos «de más» que lleva girados."""
    s, b = SUBE * d, BAJA * d
    h = d - s - b
    if x <= 0:
        return 0.0
    if x < s:
        return 0.5 * x - s / (2 * math.pi) * math.sin(math.pi * x / s)
    total = 0.5 * s
    if x < s + h:
        return total + (x - s)
    total += h
    if x < d:
        y = x - s - h
        return total + 0.5 * y + b / (2 * math.pi) * math.sin(math.pi * y / b)
    return total + 0.5 * b


def _vuelta(t, e):
    """(ángulo girado hasta `t`, en radianes; su rapidez en ese momento y lo que va de más por la aceleración, los dos en
    radianes por segundo). El ángulo es una función de `t` y nada más: da igual en qué orden se pinten los cuadros (con
    --fotos se saltan)."""
    w0 = 2 * math.pi * e['vel'] / VUELTA
    extra, empuje = 0.0, 0.0
    for a in e['acelera']:
        extra += _empuje_sumado(t - a, e['dura'])
        empuje += _empuje(t - a, e['dura'])
    k = e['por'] - 1.0
    return w0 * (t + k * extra), abs(w0) * (1.0 + k * empuje), abs(w0) * max(0.0, k * empuje)


# ── Pintar ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _premultiplicada(capa):
    """De una capa PIL RGBA a un array float32 (alto × ancho × 4) con el color ya multiplicado por su transparencia."""
    a = np.asarray(capa, np.float32) * (1.0 / 255.0)
    a[..., :3] *= a[..., 3:4]
    return np.ascontiguousarray(a)


def _caja(muestras, W, H):
    """La caja (X0, Y0, X1, Y1) en píxeles enteros que cubre todas las muestras de una tarjeta, recortada con el cuadro.
    Cada muestra: (capa, cx, cy, escala, giro)."""
    x0 = y0 = math.inf
    x1 = y1 = -math.inf
    for capa, cx, cy, escala, giro in muestras:
        h, w = capa.shape[:2]
        th = math.radians(giro)
        co, si = abs(math.cos(th)), abs(math.sin(th))
        bw, bh = w * escala * co + h * escala * si, w * escala * si + h * escala * co
        x0, x1 = min(x0, cx - bw / 2), max(x1, cx + bw / 2)
        y0, y1 = min(y0, cy - bh / 2), max(y1, cy + bh / 2)
    X0, Y0 = max(0, int(math.floor(x0)) - 2), max(0, int(math.floor(y0)) - 2)
    X1, Y1 = min(W, int(math.ceil(x1)) + 2), min(H, int(math.ceil(y1)) + 2)
    if X1 <= X0 or Y1 <= Y0:
        return None
    return X0, Y0, X1, Y1


def _poner(c, muestras, caja, alfa, tapa, brillo=1.0, persona=None):
    """Pone una tarjeta: el centro en (cx, cy) con decimales, escalada y girada (`giro` en grados, a favor del reloj), con
    la capa ya preparada y OpenCV, que con seis tarjetas por cuadro va varias veces más rápido que `B.poner`.
    - Varias `muestras` (la misma tarjeta en puntos seguidos de su vuelta) se promedian: es el desenfoque de movimiento.
    - `tapa`: 0 = encima de la persona, 1 = detrás de ella; en medio, a medias, para cruzar de un lado al otro sin saltar.
    - `persona`: [(F, x0, y0, x1, y1)], el color de verdad de la persona (`B.color_persona`) en los trozos de su borde.
      Donde la persona va encima de la tarjeta, su borde se pinta con ese color y no con el píxel tal cual: el píxel del
      borde trae algo de la pared de detrás, y sobre la tarjeta saldría como un filo de color alrededor de la persona.
      Dentro de la persona (y fuera de esos trozos) el color de verdad es el del propio cuadro.
    - `brillo`: 1 = tal cual; menos, más oscura."""
    if alfa <= 0.003 or not muestras or caja is None:
        return
    X0, Y0, X1, Y1 = caja
    suma = None
    for capa, cx, cy, escala, giro in muestras:
        h, w = capa.shape[:2]
        th = math.radians(giro)
        co, si = math.cos(th), math.sin(th)
        M = np.array([[escala * co, -escala * si, 0.0], [escala * si, escala * co, 0.0]], np.float64)
        M[0, 2] = cx - X0 - (M[0, 0] * (w - 1) / 2 + M[0, 1] * (h - 1) / 2)
        M[1, 2] = cy - Y0 - (M[1, 0] * (w - 1) / 2 + M[1, 1] * (h - 1) / 2)
        hecha = cv2.warpAffine(capa, M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                               borderValue=(0, 0, 0, 0))
        if suma is None:
            suma = hecha
        else:
            cv2.add(suma, hecha, dst=suma)
    if len(muestras) > 1:
        suma *= np.float32(1.0 / len(muestras))
    # con OpenCV y canal a canal: con numpy y `[..., None]` es varias veces más lento (es lo que más tarda)
    r_, g_, b_, a_ = cv2.split(suma)
    rgb = cv2.merge([r_, g_, b_])                            # el color de la tarjeta (ya multiplicado por su alfa)
    cubre = a_ * np.float32(alfa)                            # cuánto tapa la tarjeta lo de debajo
    zona = c.img[Y0:Y1, X0:X1]
    m = c.mascara[Y0:Y1, X0:X1] if tapa > 0.003 else None
    if m is not None and float(m.max()) > 0.004:
        encima = np.float32(tapa) * m                        # cuánto va la persona encima de la tarjeta
        peso = (1.0 - encima) * np.float32(alfa * brillo)
        # la persona encima, con su color de verdad: el del cuadro dentro de ella y el de `persona` en su borde
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


# ── Las tarjetas ────────────────────────────────────────────────────────────────────────────────────────────────────
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


# ── La forma de la órbita ───────────────────────────────────────────────────────────────────────────────────────────
LADO = 0.80                                          # escala de una tarjeta en el lado del aro
_TH = np.linspace(0.0, 2 * math.pi, 181)             # la vuelta, para medir hasta dónde llegan las tarjetas


def _alto(z, ry, abajo):
    """La altura en el aro (sin inclinar) de una tarjeta con profundidad `z`: `ry` arriba y abajo, y por delante `abajo`
    más (sin esquinas: la forma es un huevo suave, más largo por delante)."""
    return ry * z + abajo * (z + z * z) / 2


def _alcance(rx, ry, abajo, w, h):
    """Hasta dónde llegan las tarjetas (con su tamaño y su giro), a izquierda y derecha del centro del aro, en una vuelta
    entera: (izquierda, derecha), los dos en positivo."""
    fi = math.radians(INCLINACION)
    z = np.sin(_TH)
    X, Y = rx * np.cos(_TH), _alto(z, ry, abajo)
    x = X * math.cos(fi) - Y * math.sin(fi)
    esc = 0.80 + 0.20 * z
    g = np.radians(0.5 * INCLINACION + 5.0 * np.cos(_TH))
    hw = 0.5 * esc * (w * np.abs(np.cos(g)) + h * np.abs(np.sin(g)))
    return float(np.max(hw - x)), float(np.max(x + hw))


def _radio_que_cabe(rx, ry, abajo, w, h, ancho_util):
    """El radio horizontal más grande (hasta `rx`) con el que el aro entero cabe en `ancho_util`."""
    iz, de = _alcance(rx, ry, abajo, w, h)
    if iz + de <= ancho_util:
        return rx
    lo, hi = 0.0, rx
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        iz, de = _alcance(mid, ry, abajo, w, h)
        lo, hi = (mid, hi) if iz + de <= ancho_util else (lo, mid)
    return lo


def _preparar(c):
    u = c.u
    cantidad = int(min(6, max(3, round(_num(c.op.get('cantidad'), 5)))))
    fotos = _fotos(c, cantidad)
    if not fotos:
        raise ValueError('no hay ninguna foto para las tarjetas')
    n = min(6, max(3, len(fotos)))
    fotos = [fotos[k % len(fotos)] for k in range(n)]
    w = max(40, int(round(_num(c.op.get('tamano'), 300) * u)))
    h = int(round(w * 4 / 3))
    grandes = [_tarjeta(f, w, h, u) for f in fotos]
    # una copia más pequeña para las de detrás (reducir mucho al vuelo hace dientes en el filo)
    chicas = [_tarjeta(f, int(w * 0.72), int(w * 0.72 * 4 / 3), u * 0.72) for f in fotos]
    radio = min(2.5, max(0.6, _num(c.op.get('radio'), 1.3)))
    inicio = c.op.get('radio_inicio')
    radio_inicio = radio if str(inicio or '').strip() == '' else min(2.5, max(0.6, _num(inicio, radio)))
    return {'n': n, 'w': w, 'h': h, 'grandes': grandes, 'chicas': chicas, 'fw': c.cara[2],
            'radio': radio, 'radio_inicio': radio_inicio,
            'vel': _num(c.op.get('velocidad'), 1),
            'acelera': _momentos(c.op.get('acelera')),
            'por': min(12.0, max(0.0, _num(c.op.get('acelera_por'), 3))),
            'dura': max(0.2, _num(c.op.get('acelera_dura'), 1.2))}


def dibujar(c):
    if 'orbita' not in c.estado:
        c.estado['orbita'] = _preparar(c)
    e = c.estado['orbita']
    u = c.u
    n, w, h = e['n'], e['w'], e['h']
    cx, cy, _ = c.cara
    fw = e['fw']                                   # el tamaño del aro se fija al empezar: no respira con la cara

    # la elipse: centrada un poco por debajo de la cara; por detrás sube a la gorra, por delante baja al pecho. Arranca con
    # `radio_inicio` y se abre hasta `radio` (los dos, veces el aro pegado de siempre). Al abrirse, por delante bajan más
    # de lo que suben por detrás: pasan por debajo de las manos y dejan ver los gestos (a los lados, como siempre)
    abre = B.suave(B.tramo(c.t, 0.0, ABRE))
    r = e['radio_inicio'] + (e['radio'] - e['radio_inicio']) * abre
    ry0 = 1.2 * fw + 0.16 * h
    ey = cy + 0.55 * fw
    ry = min(r * ry0, max(0.0, ey - 0.5 * 0.6 * h - 40 * u))                # que la de arriba no se salga por arriba
    abajo = max(0.0, ABAJO * (r - 1.0) * ry0)
    abajo = min(abajo, max(0.0, c.H - 40 * u - ey - 0.5 * h - ry))          # ni la de abajo por abajo
    ry = min(ry, max(0.0, c.H - 40 * u - ey - 0.5 * h - abajo))
    rx = r * (0.5 * fw + 0.5 * w * LADO + 42 * u)
    rx = _radio_que_cabe(rx, ry, abajo, w, h, c.W - 2 * MARGEN * u)          # dentro de la zona segura, con su giro
    iz, de = _alcance(rx, ry, abajo, w, h)
    x_min, x_max = MARGEN * u + iz, c.W - MARGEN * u - de
    ex = min(max(cx, x_min), x_max) if x_min <= x_max else 0.5 * (x_min + x_max)
    fi = math.radians(INCLINACION)
    cf, sf = math.cos(fi), math.sin(fi)

    girado, rapidez, de_mas = _vuelta(c.t, e)
    # al cruzar por un lado, la tarjeta pasa de delante a detrás de golpe, como algo que se mete detrás de una mano: con un
    # fundido, si en ese momento pasa por encima de la persona, se ve a la persona a medias encima de la tarjeta (una mano
    # transparente, 26 oct 2026). `cruce` es solo el margen para que el cambio caiga en un cuadro
    cruce = 0.02
    # el desenfoque: lo que la tarjeta recorre de más en un cuadro (en ángulo), repartido en muestras de ~1,5 px (más
    # separadas se ven los bordes repetidos, como en escalera). Solo durante la aceleración: el resto, nítidas
    barrido = ESTELA * de_mas / max(1.0, c.fps)
    largo = barrido * (max(rx, ry) + 0.5 * abajo)
    muestras = 1 if largo < 1.5 * u else int(min(24, math.ceil(largo / (1.5 * u)) + 1))

    def sitio(th, crece):
        """Dónde va una tarjeta en el ángulo `th` de su vuelta: (z, x, y, escala, delante, giro)."""
        z = math.sin(th)                           # 1 = delante (abajo), -1 = detrás (arriba)
        X, Y = rx * math.cos(th), _alto(z, ry, abajo)
        x = ex + X * cf - Y * sf
        y = ey + X * sf + Y * cf
        esc = (0.80 + 0.20 * z) * crece
        delante = B.suave(B.tramo(z, -cruce, cruce))   # de detrás a delante, fundido (no salta al cruzar el lado)
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
        return z, x, y, esc, delante, giro

    def capa_de(k, esc):
        chica = esc < 0.80
        return (e['chicas'] if chica else e['grandes'])[k], (esc / 0.72 if chica else esc)

    tarjetas = []
    for k in range(n):
        th = math.radians(20) + 2 * math.pi * k / n + girado
        # entrar creciendo (una detrás de otra) e irse encogiendo
        ent = B.tramo(c.t, k * ESCALONADO, k * ESCALONADO + ENTRA)
        sal = B.tramo(c.queda, 0, SALE)
        crece = B.rebote(ent, 1.1) * B.suave(sal)
        alfa = min(1.0, ent * 3.0) * min(1.0, sal * 2.5)
        z, x, y, esc, delante, giro = sitio(th, crece)
        if esc <= 0.01 or alfa <= 0.003:
            continue
        lista = []
        pasos = [0.0] if muestras == 1 else [barrido * (j / (muestras - 1) - 0.5) for j in range(muestras)]
        for d in pasos:
            _, xj, yj, ej, _, gj = sitio(th + d, crece) if d else (z, x, y, esc, delante, giro)
            capa, rel = capa_de(k, ej)
            lista.append((capa, xj, yj, rel, gj))
        tarjetas.append((z, k, lista, _caja(lista, c.W, c.H), alfa, delante))

    # el color de verdad de la persona en su borde, donde pasa alguna tarjeta por detrás de ella. Se calcula con el cuadro
    # de antes de ponerles ninguna y solo en los trozos de borde (lo caro es la fusión: en toda la zona de las tarjetas
    # costaría varias veces más), con aire alrededor (la fusión mira hasta ~50 px a 1080)
    persona = []
    franja, aire = int(math.ceil(4 * u)), int(math.ceil(64 * u))
    for _, _, _, caja, _, delante in tarjetas:
        if caja is None or delante >= 0.997:
            continue
        X0, Y0, X1, Y1 = caja
        m = c.mascara[Y0:Y1, X0:X1]
        borde = (m > 0.004) & (m < 0.996)
        if not borde.any():
            continue
        filas, cols = np.flatnonzero(borde.any(axis=1)), np.flatnonzero(borde.any(axis=0))
        bx0, bx1 = max(0, X0 + int(cols[0]) - franja), min(c.W, X0 + int(cols[-1]) + 1 + franja)
        by0, by1 = max(0, Y0 + int(filas[0]) - franja), min(c.H, Y0 + int(filas[-1]) + 1 + franja)
        if any(bx0 >= p[1] and by0 >= p[2] and bx1 <= p[3] and by1 <= p[4] for p in persona):
            continue                                       # ya está dentro de un trozo hecho
        ax0, ay0, ax1, ay1 = max(0, bx0 - aire), max(0, by0 - aire), min(c.W, bx1 + aire), min(c.H, by1 + aire)
        F, _ = B.color_persona(c.img[ay0:ay1, ax0:ax1].copy(), c.mascara[ay0:ay1, ax0:ax1], u)
        persona.append((F[by0 - ay0:by1 - ay0, bx0 - ax0:bx1 - ax0], bx0, by0, bx1, by1))

    for z, k, lista, caja, alfa, delante in sorted(tarjetas, key=lambda t: (t[0], t[1])):
        oscuro = (1.0 - (z + 1) / 2) ** 1.3                # 1 = la de más atrás
        _poner(c, lista, caja, alfa, tapa=1.0 - delante, brillo=1.0 - OSCURO_ATRAS * oscuro, persona=persona)
