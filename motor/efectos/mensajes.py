"""mensajes: te llegan mensajes uno detrás de otro, como las notificaciones del teléfono.

Cada mensaje es una tarjeta clara de cristal esmerilado (blanco translúcido con lo de detrás desenfocado, esquinas muy
redondas y una sombra suave), con el icono verde de la app (un bocadillo blanco, dibujado aquí), el nombre de la app en
negrita, «ahora» a la derecha y, debajo, el texto del mensaje (si no cabe en una línea, en dos). Las medidas son las del
Reel de referencia: 940 de ancho, unos 164 de alto con una línea y 18 entre una y otra.

Llegan de uno en uno (cada `intervalo`) y el último queda ABAJO, el más cerca del móvil: el nuevo aparece en el sitio de
abajo (crece un poco mientras se funde, en 0,15 s, por debajo de la de encima, que lo destapa al subir) y empuja a los de
antes un puesto hacia arriba (en 0,17 s, frenando al final y sin rebote). Así lo hace el Reel de referencia, medido
cuadro a cuadro (28 oct 2026: «salen de abajo hacia arriba, no de arriba hacia abajo» y «un poquito más pegadas al
teléfono»). Antes era al revés: el último quedaba arriba y caía desde arriba. Como mucho `maximo` a la vista: el más
viejo se apaga al salir por arriba. Al final, un fundido.

Dónde: el montón crece hacia arriba desde un sitio fijo, el borde de abajo de la tarjeta de abajo.
- `movil`: la y (a 1080 de ancho) del borde de arriba del móvil. La tarjeta de abajo queda pegada encima, a 52 px (como
  en la referencia). Manda sobre `lugar`. Vacío: con `lugar=auto` y sin persona en el plano, el móvil se busca solo (la
  mancha oscura más grande de abajo: un móvil en la mesa) y se dice dónde lo encontró; «no» = no buscarlo.
- `lugar` «auto»: sin persona, encima del móvil (si no lo encuentra, arriba); con persona, donde no le tapen la cara:
  pegadas encima de la cabeza si caben, si no debajo de la barbilla (si en ninguno de los dos caben todos, se ven menos a
  la vez).
- `lugar` «arriba» o «centro», o un número: dónde queda el montón cuando ya han llegado todos (con el número, la y a 1080
  de ancho donde empieza la tarjeta de arriba). Estos no miran la cara ni el móvil.

    .venv/bin/python efectos.py mensajes tu_video.mp4 --fotos 0.3,0.8,1.3,1.8,2.5
    .venv/bin/python efectos.py mensajes la_mesa.mp4 --op movil=1026      # el móvil empieza en la y 1026
"""
import numpy as np
from PIL import Image, ImageDraw

import base as B
from efectos import lista as Li      # la tarjeta de cristal, la sombra y los textos alineados (sin cambiar lista.py)

NOMBRE = 'mensajes'
DESCRIPCION = 'Te llegan mensajes uno detrás de otro, como notificaciones del teléfono'
OPCIONES = {
    # cada mensaje separado por «|», en el orden en que llegan (el último queda abajo, el más cerca del móvil)
    'mensajes': '¿Cómo editaste esto?|¿Qué app es esa?|Pásame los efectos|¿Me lo enseñas?',
    'app': 'Mensajes',               # el nombre de la app, en negrita
    'hora': 'ahora',                 # lo de la derecha (vacío = nada, como en la referencia)
    'primero': '0.15',               # segundos hasta que llega el primero (empieza a verse 0,05 s antes)
    'intervalo': '0.4',              # segundos entre un mensaje y el siguiente (0,4: el ritmo de la referencia)
    'maximo': '4',                   # cuántos a la vista a la vez
    'lugar': 'auto',                 # auto, arriba, centro, o la y de la tarjeta de arriba (a 1080 de ancho)
    'movil': '',                     # la y del borde de arriba del móvil (a 1080); vacío = lo busca solo; «no» = no buscarlo
    'color': '#34C759',              # el verde del icono
}
DURACION = 3.0

# medidas a 1080 de ancho (se multiplican por c.u), sacadas de la referencia
ANCHO = 940          # la tarjeta: de x 70 a 1010, dentro de la zona segura (60–1020)
RADIO = 40           # esquinas muy redondas
PX, PD = 28, 32      # aire a la izquierda (hasta el icono) y a la derecha
ICONO = 80           # el icono de la app
ICONO_Y = 35         # del borde de arriba de la tarjeta al icono
HUECO_ICONO = 24     # del icono al texto
APP_Y = 60           # del borde de arriba a la mitad de las mayúsculas del nombre de la app
PASO = 47.5          # de esa fila a la primera del mensaje (y de una línea del mensaje a la otra, con la letra grande)
PB = 56              # de la mitad de las mayúsculas de la última línea al borde de abajo
TAM_APP, TAM_HORA = 34, 28
TAM_MSJ, TAM_MIN = 36, 27   # el texto del mensaje (y lo más pequeño que puede llegar a ser para caber en dos líneas)
SEPARA = 18          # entre tarjeta y tarjeta
TECHO = 220          # nada por encima de esta y (arriba, Instagram pone sus cosas)
SUELO = 260          # ni por debajo de H − esto (abajo, el texto y los botones de Instagram)
ARRIBA = 280         # «arriba»: donde empieza la tarjeta de arriba cuando ya están todas
MARGEN_CARA = 44     # el aire entre las tarjetas y la cabeza o la barbilla
PEGADO = 52          # del borde de abajo de la última tarjeta al borde de arriba del móvil (en la referencia, 1170 → 1222)

EMPUJA = 0.167       # lo que tardan los de antes en subir un puesto (5 cuadros, frenando al final: medido en la referencia)
ENTRA = 0.15         # el nuevo crece y se funde en su sitio, abajo
ANTES = 0.05         # empieza a aparecer un poco antes de que suba el montón, DEBAJO de la de encima: cuando esa sube y lo
                     # destapa, ya está casi entero (si no, durante un cuadro se veía la mesa: un parpadeo medido)
ESCALA0 = 0.90       # el tamaño con el que empieza a crecer
SALIDA = 0.30        # el fundido del final

TINTA = (24, 24, 28, 255)
TINTA_APP = (24, 24, 28, 255)
GRIS = (120, 120, 128, 255)
BLANCO = (255, 255, 255, 255)
SS = 4               # el icono se dibuja 4 veces más grande y se reduce: bordes suaves


# ── El icono: un cuadrado redondeado verde con un bocadillo blanco ──────────────────────────────────────────────────
def icono_mensajes(d, col):
    D = int(round(d * SS))
    claro = Li._mezcla(col, BLANCO, 0.22)
    oscuro = Li._mezcla(col, (0, 0, 0, 255), 0.10)
    im = Li._degradado(D, D, D * 0.23, claro, oscuro, diagonal=1.0)       # de arriba (más claro) a abajo
    dr = ImageDraw.Draw(im)
    bw, bh = D * 0.66, D * 0.54
    cx, cy = D * 0.5, D * 0.47
    dr.ellipse([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], fill=BLANCO)
    # la colita, abajo a la izquierda: sale del borde del bocadillo y se curva hacia fuera
    pts = []
    for k in range(25):
        s = k / 24
        # de un punto del borde (abajo a la izquierda) a la punta, y vuelta por dentro a otro punto del borde
        pts.append((cx - bw * (0.30 + 0.16 * s ** 1.4), cy + bh * (0.30 + 0.33 * s)))
    for k in range(25):
        s = 1 - k / 24
        pts.append((cx - bw * (0.07 + 0.39 * s ** 2.2), cy + bh * (0.47 + 0.16 * s)))
    dr.polygon(pts, fill=BLANCO)
    return im.resize((max(1, round(d)), max(1, round(d))), Image.LANCZOS)


# ── El texto del mensaje, en una o dos líneas ───────────────────────────────────────────────────────────────────────
def _partir(s, f, ancho):
    lineas, linea = [], ''
    for p in s.split():
        prueba = (linea + ' ' + p).strip()
        if not linea or f.getlength(prueba) <= ancho:
            linea = prueba
        else:
            lineas.append(linea)
            linea = p
    if linea:
        lineas.append(linea)
    return lineas or ['']


def _lineas(s, u, ancho):
    """Las líneas del mensaje y su tamaño: como mucho dos; si no caben, la letra baja hasta TAM_MIN y, si aun así no,
    lo que sobra se corta con «…»."""
    tam = TAM_MSJ * u
    while True:
        f = B.fuente('medium', tam)
        lin = _partir(s, f, ancho)
        if (len(lin) <= 2 and all(f.getlength(x) <= ancho for x in lin)) or tam <= TAM_MIN * u:
            break
        tam = max(TAM_MIN * u, tam * 0.95)
    if len(lin) > 2 or any(f.getlength(x) > ancho for x in lin):
        lin = lin[:2]
        ult = lin[-1]
        while ult and f.getlength(ult + '…') > ancho:
            ult = ult[:-1].rstrip()
        lin[-1] = ult + '…'
    return lin, tam


# ── Lo que no cambia: cada tarjeta, ya dibujada ─────────────────────────────────────────────────────────────────────
def _tarjeta(c, texto, L):
    """El contenido de una tarjeta (icono y textos) en una capa del tamaño de la tarjeta; el cristal se pone aparte, cada
    cuadro, con lo que haya detrás."""
    u = c.u
    w = L['w']
    x_txt = PX * u + L['ico'].width + HUECO_ICONO * u
    ancho_txt = w - x_txt - PD * u
    lineas, tam = _lineas(texto, u, ancho_txt)
    paso = PASO * u * tam / (TAM_MSJ * u)          # con la letra más pequeña, las líneas más juntas
    h = int(round(APP_Y * u + PASO * u + (len(lineas) - 1) * paso + PB * u))
    capa = Image.new('RGBA', (w, h), (0, 0, 0, 0))

    def pegar(rt, x, y, alinear='izq'):
        cx, cy = rt.centro(x, y, alinear)
        capa.alpha_composite(rt.capa, (int(round(cx - rt.w / 2)), int(round(cy - rt.h / 2))))

    capa.alpha_composite(L['ico'], (int(round(PX * u)), int(round(ICONO_Y * u))))
    y_app = APP_Y * u
    hora = L['hora']
    libre_app = ancho_txt - (hora.ancho + 20 * u if hora else 0)
    app = Li.Rotulo(L['app_txt'], Li.tam_que_cabe(L['app_txt'], 'bold', TAM_APP * u, libre_app), 'bold', TINTA_APP)
    pegar(app, x_txt, y_app)
    if hora:
        pegar(hora, w - PD * u, y_app, 'der')
    for k, s in enumerate(lineas):
        rt = Li.Rotulo(s, tam, 'medium', TINTA)
        pegar(rt, x_txt, APP_Y * u + PASO * u + k * paso)
    return capa


def _hay_persona(c):
    return float((c.mascara > 0.5).mean()) > 0.02


def _buscar_movil(c):
    """La y del borde de arriba del móvil (en píxeles del cuadro): la mancha oscura más grande de la parte de abajo, que
    sea ancha y llena como un móvil en la mesa (la pantalla y la funda son lo más oscuro del plano). None si no hay
    ninguna que lo parezca."""
    try:
        import cv2
    except ImportError:
        return None
    H, W = c.H, c.W
    oscuro = (c.img.mean(axis=2) < 0.22).astype(np.uint8)
    k = max(3, int(round(9 * c.u)) | 1)
    oscuro = cv2.morphologyEx(oscuro, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))      # fuera las motas sueltas
    n, _, st, _ = cv2.connectedComponentsWithStats(oscuro, connectivity=8)
    mejor = None
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in st[i])
        if not (0.02 * W * H <= area <= 0.45 * W * H):     # ni una mota ni medio cuadro
            continue
        if w < 0.30 * W or y < 0.30 * H or area < 0.30 * w * h:
            continue
        if mejor is None or area > mejor[1]:
            mejor = (y, area)
    return None if mejor is None else float(mejor[0])


def _sitio(c, altos, maximo, mostrar):
    """(y del borde de abajo de la tarjeta de abajo, cuántas a la vista). `altos`: lo que ocupa cada tarjeta, en el
    orden en que llegan. El montón crece hacia arriba desde esa y."""
    u, H = c.u, c.H
    sep = SEPARA * u
    techo, suelo = TECHO * u, H - SUELO * u

    def ocupa(k):
        """Lo más alto que llega a ser el montón con k a la vista (k mensajes seguidos, los que más ocupen)."""
        k = max(1, min(k, len(altos)))
        return max(sum(altos[i:i + k]) for i in range(len(altos) - k + 1)) + (k - 1) * sep

    def caben(banda):
        k = 0
        while k < len(altos) and ocupa(k + 1) <= banda:
            k += 1
        return k

    def encima_de(y):
        """Pegadas encima de y: la de abajo termina en y (sin bajar del suelo); a la vista, las que quepan bajo el techo."""
        abajo = min(y, suelo)
        return round(abajo), max(1, min(maximo, caben(abajo - techo)))

    movil = str(c.op.get('movil') or '').strip().lower()
    if movil not in ('', 'auto', 'no'):
        try:
            return encima_de(float(movil.replace(',', '.')) * u - PEGADO * u)
        except ValueError:
            print(f'  Aviso (mensajes): «{movil}» en `movil` no es un número (la y del móvil); lo busco solo.')
            movil = ''
    lugar = str(c.op.get('lugar') or 'auto').strip().lower()
    try:
        return round(float(lugar.replace(',', '.')) * u + ocupa(mostrar)), maximo
    except ValueError:
        pass
    if lugar == 'centro':
        return round((H + ocupa(mostrar)) / 2), maximo
    if lugar == 'arriba':
        return round(ARRIBA * u + ocupa(mostrar)), maximo
    if not _hay_persona(c):
        y = None if movil == 'no' else _buscar_movil(c)
        if y is not None:
            print(f'  mensajes: el móvil empieza en la y {y / u:.0f} (a 1080); las notificaciones, justo encima. '
                  f'Si no es ahí: --op movil=<y>')
            return encima_de(y - PEGADO * u)
        return round(ARRIBA * u + ocupa(mostrar)), maximo
    # con persona: pegadas encima de la cabeza si caben todas; si no, debajo de la barbilla (o donde quepan más)
    cx, cy, ac = (float(v) for v in c.cara)
    coronilla = Li.cabeza_arriba(c) - MARGEN_CARA * u
    barbilla = cy + 1.05 * ac + MARGEN_CARA * u
    k_arriba = min(mostrar, caben(coronilla - techo))
    k_abajo = min(mostrar, caben(suelo - barbilla))
    if k_arriba >= mostrar:
        return round(coronilla), maximo
    if k_abajo >= k_arriba and k_abajo >= 1:
        return round(barbilla + ocupa(k_abajo)), k_abajo
    if k_arriba >= 1:
        return round(coronilla), k_arriba
    arriba = barbilla if suelo - barbilla > coronilla - techo else techo
    return round(arriba + ocupa(1)), 1


def _numero(s, defecto, minimo):
    try:
        return max(minimo, float(str(s).replace(',', '.')))
    except (TypeError, ValueError):
        return defecto


def _preparar(c):
    u, op = c.u, c.op
    textos = [x.strip() for x in str(op.get('mensajes') or '').split('|') if x.strip()] or ['Hola']
    n = len(textos)
    L = {'n': n, 'w': int(round(ANCHO * u)), 'r': RADIO * u, 'sep': int(round(SEPARA * u))}
    L['ico'] = icono_mensajes(ICONO * u, B.color(op.get('color') or '#34C759'))
    L['app_txt'] = str(op.get('app') or '').strip() or 'Mensajes'
    hora = str(op.get('hora') or '').strip()
    L['hora'] = Li.Rotulo(hora, TAM_HORA * u, 'regular', GRIS) if hora else None
    L['capas'] = [_tarjeta(c, s, L) for s in textos]
    L['altos'] = [cp.height for cp in L['capas']]
    L['sombra'] = {h: Li.sombra_de(L['w'], h, L['r'], 26 * u, 64) for h in set(L['altos'])}
    L['x'] = (c.W - L['w']) / 2

    # cuándo llega cada uno: cada `intervalo`, y el último con tiempo de verse quieto antes del fundido
    maximo = int(_numero(op.get('maximo'), 4, 1))
    intervalo = _numero(op.get('intervalo'), 0.4, 0.05)
    primero = _numero(op.get('primero'), 0.15, ANTES)
    ultimo = c.dur - SALIDA - max(EMPUJA, ENTRA) - 0.30
    primero = min(primero, max(ANTES, ultimo))
    if n > 1:
        intervalo = min(intervalo, max(0.12, (ultimo - primero) / (n - 1)))
    L['llegan'] = [primero + i * intervalo for i in range(n)]
    L['abajo'], L['maximo'] = _sitio(c, L['altos'], maximo, min(maximo, n))
    return L


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def dibujar(c):
    L = c.estado.get('mensajes')
    if L is None:
        L = c.estado['mensajes'] = _preparar(c)
    u, t = c.u, c.t
    total = B.suave(B.tramo(c.queda, 0, SALIDA))
    if total <= 0.003:
        return
    n, sep, abajo, x, w, r = L['n'], L['sep'], L['abajo'], L['x'], L['w'], L['r']
    llegan, altos = L['llegan'], L['altos']
    # sube[j]: cuánto ha subido el montón para hacerle sitio abajo al mensaje j (de 0 a 1, frenando al final)
    sube = [B.sale(B.tramo(t, a, a + EMPUJA)) for a in llegan]

    tarjetas = []
    for i in range(n):
        if t < llegan[i] - ANTES:
            break
        empuje = sum(sube[j] * (altos[j] + sep) for j in range(i + 1, n))
        y = abajo - altos[i] - empuje                                   # su esquina de arriba
        e = B.sale(B.tramo(t, llegan[i] - ANTES, llegan[i] - ANTES + ENTRA))      # el nuevo, creciendo en su sitio
        escala = ESCALA0 + (1 - ESCALA0) * e
        puesto = sum(sube[j] for j in range(i + 1, n))                  # 0 = abajo del todo
        alfa = e * (1 - B.suave(B.tramo(puesto, L['maximo'] - 1, L['maximo'] - 0.4)))  # el más viejo se va por arriba
        alfa *= total
        if alfa > 0.003:
            tarjetas.append((i, y, escala, alfa))

    # primero todas las sombras, para que la sombra de una no ensucie la de al lado
    for i, y, escala, alfa in tarjetas:
        h = altos[i]
        Li.colocar(c, L['sombra'][h], x + w / 2, y + h / 2 + 12 * u * escala, alfa=alfa, escala=escala,
                   solo_sombra=True)
    # después cada tarjeta, de la nueva a la más vieja: la nueva queda DEBAJO mientras crece y la de encima la destapa al
    # subir (encima, sus letras se mezclaban con las de la otra durante dos cuadros)
    for i, y, escala, alfa in reversed(tarjetas):
        h = altos[i]
        ws, hs = w * escala, h * escala
        xs, ys = x + (w - ws) / 2, y + (h - hs) / 2
        rgbp, a_vid = Li.vidrio(c, xs, ys, ws, hs, r * escala, tinte=(255, 255, 255), opacidad=0.80, desenfoque=36,
                                brillo=0.55)
        Li._pegar(c, rgbp, a_vid, xs, ys, alfa)
        Li.colocar(c, L['capas'][i], x + w / 2, y + h / 2, alfa=alfa, escala=escala)
