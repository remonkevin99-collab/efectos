"""mensajes: te llegan mensajes uno detrás de otro, como las notificaciones del teléfono.

Cada mensaje es una tarjeta clara de cristal esmerilado (blanco translúcido con lo de detrás desenfocado, esquinas muy
redondas y una sombra suave), con el icono verde de la app (un bocadillo blanco, dibujado aquí), el nombre de la app en
negrita pequeña, «ahora» a la derecha y, debajo, el texto del mensaje (si no cabe en una línea, en dos).

Llegan de uno en uno (cada `intervalo`), como en la pantalla bloqueada del iPhone (el último queda arriba): los de antes
bajan un puesto con un rebote corto para hacerle sitio y el nuevo cae en el hueco desde un poco más arriba, con su fundido
(así nunca asoma por encima del montón ni se monta sobre otro). Como mucho `maximo` a la vista: el más viejo se
apaga al salir por abajo. Al final, un fundido.

Dónde (`lugar`):
- «auto»: sin persona en el plano (un móvil en la mesa), en la mitad de arriba; con persona, donde no le tapen la cara:
  encima de la cabeza si caben, si no debajo de la barbilla (si en ninguno de los dos caben todos, se ven menos a la vez).
- «arriba» o «centro», o un número: la altura (a 1080 de ancho) donde empieza la tarjeta de arriba. Estos no miran la cara.

    .venv/bin/python efectos.py mensajes tu_video.mp4 --fotos 0.3,0.8,1.3,1.8,2.5
"""
from PIL import Image, ImageDraw

import base as B
from efectos import lista as Li      # la tarjeta de cristal, la sombra y los textos alineados (sin cambiar lista.py)

NOMBRE = 'mensajes'
DESCRIPCION = 'Te llegan mensajes uno detrás de otro, como notificaciones del teléfono'
OPCIONES = {
    # cada mensaje separado por «|», en el orden en que llegan (el último queda arriba)
    'mensajes': '¿Cómo editaste esto?|¿Qué app es esa?|Pásame los efectos|¿Me lo enseñas?',
    'app': 'Mensajes',               # el nombre de la app, en negrita pequeña
    'hora': 'ahora',                 # lo de la derecha (vacío = nada)
    'intervalo': '0.5',              # segundos entre un mensaje y el siguiente
    'maximo': '4',                   # cuántos a la vista a la vez
    'lugar': 'auto',                 # auto, arriba, centro, o la y de la primera tarjeta (a 1080 de ancho)
    'color': '#34C759',              # el verde del icono
}
DURACION = 3.0

# medidas a 1080 de ancho (se multiplican por c.u)
ANCHO = 920          # la tarjeta: de x 80 a 1000, dentro de la zona segura (60–1020)
RADIO = 44           # esquinas muy redondas
PX, PD = 26, 32      # aire a la izquierda (hasta el icono) y a la derecha
ICONO = 82           # el icono de la app
HUECO_ICONO = 24     # del icono al texto
PT, PB = 25, 27      # aire de arriba y de abajo
FILA_APP = 40        # la fila del nombre de la app y la hora
TAM_APP, TAM_HORA = 29, 27
TAM_MSJ, TAM_MIN = 39, 28   # el texto del mensaje (y lo más pequeño que puede llegar a ser para caber en dos líneas)
INTERLINEA = 1.30
SEPARA = 18          # entre tarjeta y tarjeta
TECHO = 220          # nada por encima de esta y (arriba, Instagram pone sus cosas)
SUELO = 260          # ni por debajo de H − esto (abajo, el texto y los botones de Instagram)
ARRIBA = 280         # «arriba»: donde empieza la primera tarjeta
MARGEN_CARA = 44     # el aire entre las tarjetas y la cabeza o la barbilla

BAJA = 0.50          # lo que tardan los de antes en bajar un puesto (arrancan suave, se pasan un poco y vuelven)
CAE = 0.45           # lo que tarda el nuevo en caer a su sitio
CAIDA = 60           # desde cuánto más arriba cae (a 1080)
RETRASO = 0.15       # el nuevo empieza a caer cuando los de antes ya le han abierto hueco
APARECE = 0.22       # su fundido de entrada
SALIDA = 0.30        # el fundido del final

TINTA = (24, 24, 28, 255)
TINTA_APP = (34, 34, 40, 255)
GRIS = (120, 120, 128, 255)
BLANCO = (255, 255, 255, 255)
SS = 4               # el icono se dibuja 4 veces más grande y se reduce: bordes suaves


def muelle(t, dur, pasa=0.05):
    """De 0 a 1 en `dur` segundos con un rebote corto: arranca desde quieto (sin tirón: el primer cuadro casi no se
    mueve), llega a 1 + `pasa` a los dos tercios, se para un instante y vuelve suave al 1."""
    if t <= 0:
        return 0.0
    if t >= dur:
        return 1.0
    k = 0.66 * dur
    if t < k:
        return (1 + pasa) * B.suave(t / k)
    return 1 + pasa * (1 - B.suave((t - k) / (dur - k)))


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
    paso = round(tam * INTERLINEA)
    h = int(round(PT * u + FILA_APP * u + len(lineas) * paso + PB * u))
    capa = Image.new('RGBA', (w, h), (0, 0, 0, 0))

    def pegar(rt, x, y, alinear='izq'):
        cx, cy = rt.centro(x, y, alinear)
        capa.alpha_composite(rt.capa, (int(round(cx - rt.w / 2)), int(round(cy - rt.h / 2))))

    capa.alpha_composite(L['ico'], (int(round(PX * u)), int(round((h - L['ico'].height) / 2))))
    y_app = PT * u + FILA_APP * u * 0.42
    hora = L['hora']
    libre_app = ancho_txt - (hora.ancho + 20 * u if hora else 0)
    app = Li.Rotulo(L['app_txt'], Li.tam_que_cabe(L['app_txt'], 'bold', TAM_APP * u, libre_app), 'bold', TINTA_APP)
    pegar(app, x_txt, y_app)
    if hora:
        pegar(hora, w - PD * u, y_app, 'der')
    for k, s in enumerate(lineas):
        rt = Li.Rotulo(s, tam, 'medium', TINTA)
        pegar(rt, x_txt, PT * u + FILA_APP * u + paso * (k + 0.5) - 1 * u)
    return capa


def _hay_persona(c):
    return float((c.mascara > 0.5).mean()) > 0.02


def _sitio(c, altos, maximo, mostrar):
    """(y de la primera tarjeta, cuántas a la vista). `altos`: lo que ocupa cada tarjeta, en el orden en que llegan."""
    u, H = c.u, c.H
    sep = SEPARA * u

    def ocupa(k):
        """Lo más alto que llega a ser el montón con k a la vista (k mensajes seguidos, los que más ocupen)."""
        k = max(1, min(k, len(altos)))
        return max(sum(altos[i:i + k]) for i in range(len(altos) - k + 1)) + (k - 1) * sep

    def caben(banda):
        k = 0
        while k < len(altos) and ocupa(k + 1) <= banda:
            k += 1
        return k

    lugar = str(c.op.get('lugar') or 'auto').strip().lower()
    try:
        return round(float(lugar.replace(',', '.')) * u), maximo
    except ValueError:
        pass
    if lugar == 'centro':
        return round((H - ocupa(mostrar)) / 2), maximo
    if lugar == 'arriba' or not _hay_persona(c):
        return round(ARRIBA * u), maximo
    # con persona: encima de la cabeza si caben todas; si no, debajo de la barbilla (o donde quepan más)
    cx, cy, ac = (float(v) for v in c.cara)
    techo, suelo = TECHO * u, H - SUELO * u
    coronilla = Li.cabeza_arriba(c) - MARGEN_CARA * u
    barbilla = cy + 1.05 * ac + MARGEN_CARA * u
    k_arriba = min(mostrar, caben(coronilla - techo))
    k_abajo = min(mostrar, caben(suelo - barbilla))
    if k_arriba >= mostrar:
        return round(max(techo, min(ARRIBA * u, coronilla - ocupa(mostrar)))), maximo
    if k_abajo >= k_arriba and k_abajo >= 1:
        return round(barbilla), k_abajo
    if k_arriba >= 1:
        return round(max(techo, coronilla - ocupa(k_arriba))), k_arriba
    return round(barbilla if suelo - barbilla > coronilla - techo else techo), 1


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
    L['sombras'] = {h: Li.sombra_de(L['w'], h, L['r'], 26 * u, 64) for h in set(L['altos'])}
    L['x'] = int(round((c.W - L['w']) / 2))

    # cuándo llega cada uno: cada `intervalo`, y el último con tiempo de verse quieto antes del fundido
    maximo = int(_numero(op.get('maximo'), 4, 1))
    intervalo = _numero(op.get('intervalo'), 0.5, 0.05)
    primero = 0.10
    ultimo = c.dur - SALIDA - RETRASO - CAE - 0.30
    if n > 1:
        intervalo = min(intervalo, max(0.12, (ultimo - primero) / (n - 1)))
    L['llegan'] = [primero + i * intervalo for i in range(n)]
    L['y0'], L['maximo'] = _sitio(c, L['altos'], maximo, min(maximo, n))
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
    n, sep, y0, x, w = L['n'], L['sep'], L['y0'], L['x'], L['w']
    llegan, altos = L['llegan'], L['altos']
    # p[i]: cuánto han bajado los de antes para hacerle sitio al mensaje i; q[i]: cuánto ha caído él
    p = [muelle(t - a, BAJA, 0.05) if t >= a else None for a in llegan]
    retraso = [0.0] + [RETRASO] * (n - 1)              # el primero no tiene a nadie que apartar: cae enseguida
    caida = CAIDA * u

    tarjetas = []
    for i in range(n):
        if p[i] is None:
            break
        empuje = sum(p[j] * (altos[j] + sep) for j in range(i + 1, n) if p[j] is not None)
        q = muelle(t - llegan[i] - retraso[i], CAE, 0.12)
        y = y0 - (1 - q) * caida + empuje
        puesto = sum(min(1.0, p[j]) for j in range(i + 1, n) if p[j] is not None)    # 0 = arriba del todo
        a0 = llegan[i] + retraso[i] * 0.8
        alfa = B.suave(B.tramo(t, a0, a0 + APARECE))
        alfa *= 1 - B.suave(B.tramo(puesto, L['maximo'] - 1, L['maximo'] - 0.4))       # el más viejo se va por abajo
        alfa *= total
        if alfa > 0.003:
            tarjetas.append((i, y, alfa))

    # primero todas las sombras, para que la sombra de una no ensucie la de debajo
    for i, y, alfa in tarjetas:
        h = altos[i]
        Li.colocar(c, L['sombras'][h], x + w / 2, y + h / 2 + 12 * u, alfa=alfa, solo_sombra=True)
    for i, y, alfa in tarjetas:
        h = altos[i]
        rgbp, a_vid = Li.vidrio(c, x, y, w, h, L['r'], tinte=(255, 255, 255), opacidad=0.80, desenfoque=36, brillo=0.55)
        Li._pegar(c, rgbp, a_vid, x, y, alfa)
        Li.colocar(c, L['capas'][i], x + w / 2, y + h / 2, alfa=alfa)
