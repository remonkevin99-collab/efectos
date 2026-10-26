"""lista: una tarjeta de cristal esmerilado bajo la barbilla con los pasos de una tarea que se van marcando uno a uno.

Arriba, un destello, el título y un contador («2 de 5») con una barra de progreso fina. Debajo, los pasos: el que toca
lleva un círculo que gira y una franja clara detrás; al terminar, sale un círculo verde con una marca que se dibuja y un
rebote corto; los que faltan, apagados. La tarjeta entra subiendo y se va con un fundido.

    .venv/bin/python efectos.py lista tu_video.mp4 --duracion 6 --fotos 0.2,1.0,2.0,3.5,5.5
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import base as B

try:                       # OpenCV hace el desenfoque y el color mucho más rápido; si no está, se usa numpy y Pillow
    import cv2
except ImportError:
    cv2 = None

NOMBRE = 'lista'
DESCRIPCION = 'Una tarjeta de cristal con los pasos de una tarea que se van marcando uno a uno'
OPCIONES = {
    'titulo': 'Claude está editando tu clip',
    # cada paso separado por «|»; lo que va tras «::» es el dato pequeño de la derecha (en gris)
    'pasos': 'Encontró tu cara::cada cuadro|Te recortó del fondo::IA|Puso el texto detrás::profundidad|'
             'Corrigió el color::cálido|Lo dejó en 4K::2160p',
    # los segundos en que queda HECHO cada paso, separados por «|» (por ejemplo «1,2|2|3,1|4|4,8»).
    # Vacío: se reparten solos por la duración.
    'marcas': '',
    'color': '#8B5CF6',
}
DURACION = 6.0

VERDE = (34, 197, 94, 255)
ENTRADA = 0.35       # lo que tarda la tarjeta en subir
SALIDA = 0.40        # el fundido del final
POP = 0.45           # lo que tarda la marca verde en salir entera
SS = 4               # los iconos se dibujan 4 veces más grandes y se reducen: bordes suaves


# ── Ayudantes ───────────────────────────────────────────────────────────────────────────────────────────────────────
class Rotulo:
    """Un texto listo para colocar: su capa y dónde cae la tinta dentro de ella (para alinear de verdad, no la caja)."""

    def __init__(self, s, tam, peso, relleno):
        self.capa = B.texto(s, tam, peso, relleno)
        f = B.fuente(peso, tam)
        asc, desc = f.getmetrics()
        self.pad = (self.capa.height - (asc + desc)) / 2          # texto() deja el mismo aire por los cuatro lados
        caja_h = f.getbbox('H')
        self.medio = self.pad + (caja_h[1] + caja_h[3]) / 2        # la mitad de la altura de las mayúsculas
        self.ancho = f.getlength(s)                                 # lo que ocupa la tinta a lo ancho
        self.w, self.h = self.capa.size

    def centro(self, x, y, alinear='izq'):
        """El centro de la capa para que la tinta empiece en x (o acabe, o se centre) y las mayúsculas queden centradas
        en y. Redondea la esquina para que, quieto, el texto caiga justo en los píxeles (nítido)."""
        if alinear == 'izq':
            x0 = x - self.pad
        elif alinear == 'der':
            x0 = x - self.pad - self.ancho
        else:
            x0 = x - self.pad - self.ancho / 2
        return round(x0) + self.w / 2, round(y - self.medio) + self.h / 2


def tam_que_cabe(s, peso, tam, ancho):
    """El tamaño de letra (como mucho `tam`) para que `s` quepa en `ancho`."""
    largo = B.fuente(peso, 100).getlength(s) / 100.0
    return min(tam, ancho / max(1e-3, largo))


_PREMULT = {}


def _premult(capa):
    """La capa en números (color ya multiplicado por su transparencia), guardada para no convertirla cada cuadro."""
    clave = id(capa)
    hecho = _PREMULT.get(clave)
    if hecho is None or hecho[0] is not capa:
        arr = np.asarray(capa, np.float32) / 255.0
        a = arr[..., 3:4]
        hecho = (capa, arr[..., :3] * a, a)
        if len(_PREMULT) > 400:
            _PREMULT.clear()
        _PREMULT[clave] = hecho
    return hecho[1], hecho[2]


def _desplazar(arr, f, eje):
    """Mueve una capa una fracción de píxel (0 ≤ f < 1) a lo largo de un eje, repartiendo entre dos píxeles vecinos.
    La capa crece un píxel en ese eje."""
    forma = list(arr.shape)
    forma[eje] += 1
    out = np.zeros(forma, np.float32)
    if eje == 0:
        out[:-1] += arr * (1 - f)
        out[1:] += arr * f
    else:
        out[:, :-1] += arr * (1 - f)
        out[:, 1:] += arr * f
    return out


def _pegar(c, rgbp, a, x0, y0, alfa=1.0):
    """Pega con su esquina en (x0, y0) un color premultiplicado con su transparencia. Si (x0, y0) lleva decimales, la
    capa se reparte entre los píxeles vecinos (sin saltitos). Recorta con el cuadro. `rgbp=None`: solo oscurece (sombra)."""
    xi, yi = int(math.floor(x0)), int(math.floor(y0))
    fx, fy = x0 - xi, y0 - yi
    if fy > 1e-3:
        a = _desplazar(a, fy, 0)
        rgbp = None if rgbp is None else _desplazar(rgbp, fy, 0)
    if fx > 1e-3:
        a = _desplazar(a, fx, 1)
        rgbp = None if rgbp is None else _desplazar(rgbp, fx, 1)
    h, w = a.shape[:2]
    X0, Y0, X1, Y1 = max(0, xi), max(0, yi), min(c.W, xi + w), min(c.H, yi + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    sx, sy = X0 - xi, Y0 - yi
    al = a[sy:sy + Y1 - Y0, sx:sx + X1 - X0]
    zona = c.img[Y0:Y1, X0:X1]
    zona *= (1.0 - al * alfa) if alfa < 0.999 else (1.0 - al)
    if rgbp is not None:
        col = rgbp[sy:sy + Y1 - Y0, sx:sx + X1 - X0]
        zona += col * alfa if alfa < 0.999 else col


def colocar(c, capa, cx, cy, alfa=1.0, escala=1.0, giro=0.0, solo_sombra=False):
    """Como base.poner (centro en cx, cy, con decimales), pero si la capa no se escala ni se gira la pega directa con
    numpy, que es mucho más rápido. Con escala o giro usa poner."""
    if alfa <= 0.003:
        return
    if abs(escala - 1) < 1e-6 and abs(giro) < 1e-6:
        rgbp, a = _premult(capa)
        _pegar(c, None if solo_sombra else rgbp, a, cx - capa.width / 2, cy - capa.height / 2, alfa)
    else:
        B.poner(c, capa, cx, cy, escala=escala, giro=giro, alfa=alfa)


def vidrio(c, x, y, w, h, r, tinte=(18, 14, 30), opacidad=0.60, desenfoque=30, brillo=0.20):
    """Cristal esmerilado con lo que hay detrás (como base.cristal, pero más rápido): desenfoca a un cuarto de tamaño y
    guarda la forma redondeada y el filo para no rehacerlos cada cuadro. Devuelve (color premultiplicado, transparencia)
    de la tarjeta con su esquina en (x, y)."""
    w, h = int(round(w)), int(round(h))
    clave = ('vidrio', w, h)
    forma = c.estado.get(clave)
    if forma is None:
        mascara = np.asarray(B.caja(w, h, r, (255, 255, 255, 255)).split()[3], np.float32)[..., None] / 255.0
        filo = np.asarray(B.caja(w, h, r, (0, 0, 0, 0), borde=(255, 255, 255, 255), grosor=max(1.0, 1.5 * c.u)
                                 ).split()[3], np.float32)[..., None] / 255.0 * brillo
        forma = (mascara, filo, np.asarray(tinte, np.float32) / 255.0 * opacidad)
        c.estado[clave] = forma
    mascara, filo, tono = forma
    # lo de detrás, reducido a un cuarto (la media de cada 4 × 4: rápido y sin parpadeos), desenfocado y agrandado
    xi, yi = int(math.floor(x)), int(math.floor(y))
    w4, h4 = max(1, w // 4), max(1, h // 4)
    filas = np.clip(np.arange(yi, yi + h4 * 4), 0, c.H - 1)
    cols = np.clip(np.arange(xi, xi + w4 * 4), 0, c.W - 1)
    if filas[0] == yi and filas[-1] == yi + h4 * 4 - 1 and cols[0] == xi and cols[-1] == xi + w4 * 4 - 1:
        trozo = c.img[yi:yi + h4 * 4, xi:xi + w4 * 4]
    else:
        trozo = c.img[filas[:, None], cols[None, :]]
    if cv2 is not None:
        peq = cv2.resize(trozo, (w4, h4), interpolation=cv2.INTER_AREA)
        peq = cv2.GaussianBlur(peq, (0, 0), desenfoque * c.u / 4)
        fondo = cv2.resize(peq, (w, h), interpolation=cv2.INTER_LINEAR) * (1 - opacidad) + tono
    else:
        peq = trozo.reshape(h4, 4, w4, 4, 3).mean(axis=(1, 3))
        peq = Image.fromarray((peq * 255 + 0.5).clip(0, 255).astype(np.uint8), 'RGB')
        peq = peq.filter(ImageFilter.GaussianBlur(desenfoque * c.u / 4)).resize((w, h), Image.BILINEAR)
        fondo = np.asarray(peq, np.float32) * ((1 - opacidad) / 255.0) + tono
    fondo = fondo * (1 - filo) + filo                       # el filo claro del borde
    return fondo * mascara, mascara


def sombra_de(w, h, r, desenfoque, alfa):
    """Solo la sombra de una tarjeta (sin la tarjeta), con aire para el desenfoque."""
    pad = int(desenfoque * 2.5)
    a = B.caja(w, h, r, (0, 0, 0, 255)).split()[3].point(lambda v: v * alfa // 255)
    out = Image.new('RGBA', (int(round(w)) + 2 * pad, int(round(h)) + 2 * pad), (0, 0, 0, 0))
    negro = Image.new('RGBA', a.size, (0, 0, 0, 255))
    negro.putalpha(a)
    out.alpha_composite(negro, (pad, pad))
    return out.filter(ImageFilter.GaussianBlur(desenfoque))


def _bajar(im, d):
    return im.resize((max(1, round(d)), max(1, round(d))), Image.LANCZOS)


# ── Iconos (dibujados aquí, a mano) ─────────────────────────────────────────────────────────────────────────────────
def icono_destello(d, col):
    """Un destello: una estrella grande de cuatro puntas y otra pequeña arriba a la derecha."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)

    def estrella(cx, cy, R):
        pts = []
        for k in range(200):
            a = 2 * math.pi * k / 200
            co, si = math.cos(a), math.sin(a)
            pts.append((cx + R * math.copysign(abs(co) ** 2.6, co), cy + R * math.copysign(abs(si) ** 2.6, si)))
        dr.polygon(pts, fill=col)

    estrella(D * 0.42, D * 0.58, D * 0.41)
    estrella(D * 0.82, D * 0.18, D * 0.16)
    return _bajar(im, d)


def icono_giro(d, u, col):
    """El círculo que gira mientras un paso se está haciendo: un aro tenue y un trozo de arco en el color de acento."""
    D = int(round(d * SS))
    g = 3.4 * u * SS
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, D - 1, D - 1], outline=(255, 255, 255, 60), width=int(round(g)))
    dr.arc([0, 0, D - 1, D - 1], start=-90, end=40, fill=col, width=int(round(g)))
    rr = (D - g) / 2
    for ang in (-90, 40):                                   # las puntas del arco, redondas
        a = math.radians(ang)
        x, y = D / 2 + rr * math.cos(a), D / 2 + rr * math.sin(a)
        dr.ellipse([x - g / 2, y - g / 2, x + g / 2, y + g / 2], fill=col)
    return _bajar(im, d)


def icono_aro(d, u):
    """El paso que falta: un aro apagado."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([0, 0, D - 1, D - 1], outline=(255, 255, 255, 85), width=int(round(2.6 * u * SS)))
    return _bajar(im, d)


def icono_marca(d, p):
    """El círculo verde con la marca dibujada hasta `p` (0–1)."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, D - 1, D - 1], fill=VERDE)
    if p > 0:
        R = D / 2
        pts = [(D / 2 + x * R, D / 2 + y * R) for x, y in ((-0.40, 0.02), (-0.12, 0.30), (0.42, -0.27))]
        g = 0.19 * R
        largos = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        queda = p * sum(largos)
        dr.ellipse([pts[0][0] - g / 2, pts[0][1] - g / 2, pts[0][0] + g / 2, pts[0][1] + g / 2], fill=(255, 255, 255, 255))
        for i, L in enumerate(largos):
            if queda <= 0:
                break
            k = min(1.0, queda / L)
            a, b = pts[i], pts[i + 1]
            fin = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            dr.line([a, fin], fill=(255, 255, 255, 255), width=int(round(g)))
            dr.ellipse([fin[0] - g / 2, fin[1] - g / 2, fin[0] + g / 2, fin[1] + g / 2], fill=(255, 255, 255, 255))
            queda -= L
    return _bajar(im, d)


def cabeza_arriba(c):
    """Lo más alto de la cabeza: lo que diga la cara (con margen para el pelo) o lo que diga la silueta, lo que quede más
    arriba (una gorra o un peinado alto cuentan). Se mira en la franja de la cara."""
    cx, cy, ac = (float(v) for v in c.cara)
    por_cara = cy - 1.25 * ac
    x0, x1 = int(max(0, cx - 1.2 * ac)), int(min(c.W, cx + 1.2 * ac))
    if x1 - x0 < 4:
        return por_cara
    filas = np.where((c.mascara[:, x0:x1] > 0.5).mean(1) > 0.15)[0]
    return min(por_cara, float(filas[0])) if len(filas) else por_cara


# ── Lo que no cambia ────────────────────────────────────────────────────────────────────────────────────────────────
def _pasos(op):
    out = []
    for trozo in str(op.get('pasos') or '').split('|'):
        trozo = trozo.strip()
        if not trozo:
            continue
        nombre, _, dato = trozo.partition('::')
        out.append((nombre.strip(), dato.strip()))
    return out or [('Listo', '')]


def _numeros(s):
    out = []
    for x in str(s or '').split('|'):
        x = x.strip().replace(',', '.')
        try:
            out.append(float(x))
        except ValueError:
            pass
    return out


def _tiempos(dur, n, marcas):
    """Cuándo empieza y cuándo queda hecho cada paso."""
    inicio = ENTRADA + 0.10
    fin = max(inicio + 0.35 * n, dur - SALIDA - 0.55)          # la última marca tiene que verse antes de irse
    fines = [marcas[i] if i < len(marcas) else inicio + (i + 1) * (fin - inicio) / n for i in range(n)]
    for i in range(n):                                          # en orden y con un poco de aire entre uno y otro
        fines[i] = max(fines[i], (fines[i - 1] if i else inicio) + 0.25)
    return [inicio] + fines[:-1], fines


def _preparar(c):
    u, op = c.u, c.op
    acento = B.color(op.get('color') or '#8B5CF6')
    pasos = _pasos(op)
    n = len(pasos)
    L = {'n': n}

    # medidas de la tarjeta (todo por u: sale igual a 1080 y a 4K)
    w = int(round(900 * u))
    PX, PT, PB = 40 * u, 32 * u, 26 * u
    CAB, FILA, ICO = 50 * u, 72 * u, 34 * u
    cab_y = PT + CAB / 2
    barra_y = PT + CAB + 16 * u
    filas_y = barra_y + 6 * u + 16 * u
    h = int(round(filas_y + n * FILA + PB))
    r = 34 * u
    L.update(w=w, h=h, r=r, PX=PX, FILA=FILA, ICO=ICO, cab_y=cab_y, barra_y=barra_y, filas_y=filas_y)

    # dónde va: por debajo de la barbilla; si abajo no cabe, por encima de la cabeza
    cx, cy, ac = (float(v) for v in c.cara)
    barbilla = cy + 1.05 * ac
    coronilla = cabeza_arriba(c)
    abajo_max = c.H - 230 * u
    y = barbilla + 40 * u
    if y + h > abajo_max:
        arriba = coronilla - 40 * u - h
        y = arriba if arriba >= 150 * u else max(barbilla + 16 * u, abajo_max - h)
    L['x'] = int(round((c.W - w) / 2))
    L['y'] = int(round(y))

    # cabecera: destello, título y contador
    L['destello'] = icono_destello(ICO * 1.05, acento)
    contador_tam = 27 * u
    gris = (255, 255, 255, 150)
    L['de_n'] = Rotulo(f' de {n}', contador_tam, 'medium', gris)
    L['nums'] = [Rotulo(str(k), contador_tam, 'medium', (255, 255, 255, 235)) for k in range(1, n + 1)]
    titulo = str(op.get('titulo') or '')
    libre = w - 2 * PX - ICO - 14 * u - L['de_n'].ancho - L['nums'][-1].ancho - 26 * u
    L['titulo'] = Rotulo(titulo, tam_que_cabe(titulo, 'bold', 35 * u, libre), 'bold', (255, 255, 255, 255))
    L['titulo_c'] = L['titulo'].centro(PX + ICO + 14 * u, cab_y)
    L['de_n_c'] = L['de_n'].centro(w - PX, cab_y, 'der')
    x_num = w - PX - L['de_n'].ancho
    L['nums_c'] = [rt.centro(x_num, cab_y, 'der') for rt in L['nums']]

    # barra de progreso
    L['barra_w'] = w - 2 * PX
    L['barra_fondo'] = B.caja(L['barra_w'], 6 * u, 3 * u, (255, 255, 255, 38))
    L['acento'] = acento

    # filas
    L['giro'] = icono_giro(ICO, u, acento)
    L['aro'] = icono_aro(ICO, u)
    L['marca_llena'] = icono_marca(ICO, 1.0)
    L['marcas_cache'] = {}
    L['resalte'] = B.caja(w - 2 * PX + 28 * u, FILA - 10 * u, 18 * u, (255, 255, 255, 22))
    filas = []
    for i, (nombre, dato) in enumerate(pasos):
        yc = filas_y + FILA * (i + 0.5)
        rd = Rotulo(dato, 24 * u, 'regular', (255, 255, 255, 140)) if dato else None
        libre = w - 2 * PX - ICO - 18 * u - (rd.ancho + 20 * u if rd else 0)
        rn = Rotulo(nombre, tam_que_cabe(nombre, 'medium', 31 * u, libre), 'medium', (255, 255, 255, 255))
        filas.append({'y': yc, 'nombre': rn, 'nombre_c': rn.centro(PX + ICO + 18 * u, yc),
                      'dato': rd, 'dato_c': rd.centro(w - PX, yc, 'der') if rd else None})
    L['filas'] = filas
    L['ico_x'] = PX + ICO / 2
    L['inicios'], L['fines'] = _tiempos(c.dur, n, _numeros(op.get('marcas')))
    L['sombra'] = sombra_de(w, h, r, 26 * u, 80)
    c.estado['lista'] = L
    return L


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def dibujar(c):
    L = c.estado.get('lista') or _preparar(c)
    u, t = c.u, c.t
    alfa = B.suave(B.tramo(t, 0, ENTRADA * 0.9)) * B.suave(B.tramo(c.queda, 0, SALIDA))
    if alfa <= 0.003:
        return
    sube = (1 - B.suave(B.tramo(t, 0, ENTRADA))) * 70 * u      # entra subiendo
    X, Y = L['x'], L['y'] + sube
    w, h, n = L['w'], L['h'], L['n']
    inicios, fines = L['inicios'], L['fines']

    def en(capa, rx, ry, a=1.0, **kw):
        colocar(c, capa, X + rx, Y + ry, alfa=alfa * a, **kw)

    # la tarjeta: primero se toma lo de detrás, después la sombra y el cristal
    rgbp, a_vid = vidrio(c, X, Y, w, h, L['r'])
    sm = L['sombra']
    colocar(c, sm, X + w / 2, Y + h / 2 + round(12 * u), alfa=alfa, solo_sombra=True)
    _pegar(c, rgbp, a_vid, X, Y, alfa)

    todo_hecho = B.tramo(t, fines[-1], fines[-1] + 0.5)

    # cabecera: el destello late suave mientras trabaja y se queda quieto al acabar
    late = 1 + 0.07 * math.sin(t * 2 * math.pi * 0.9) * (1 - todo_hecho)
    en(L['destello'], L['ico_x'], L['cab_y'], escala=late, giro=math.sin(t * 1.7) * 7 * (1 - todo_hecho))
    en(L['titulo'].capa, *L['titulo_c'])
    en(L['de_n'].capa, *L['de_n_c'])

    # contador: el número sube al cambiar (el viejo se va hacia arriba y después entra el nuevo desde abajo; uno
    # detrás del otro, para que no se monten)
    pasados = [i for i in range(n - 1) if t >= fines[i]]
    k = len(pasados)                                            # índice del paso que toca
    if pasados:
        t0 = fines[k - 1]
        va = B.suave(B.tramo(t, t0, t0 + 0.16))
        viene = B.suave(B.tramo(t, t0 + 0.08, t0 + 0.32))
        viejo, nuevo = L['nums'][k - 1], L['nums'][k]
        vx, vy = L['nums_c'][k - 1]
        nx, ny = L['nums_c'][k]
        if va < 1:
            en(viejo.capa, vx, vy - va * 12 * u, 1 - va)
        en(nuevo.capa, nx, ny + (1 - viene) * 12 * u, viene)
    else:
        en(L['nums'][0].capa, *L['nums_c'][0])

    # barra de progreso (se llena seguida: lo hecho más lo que va del paso actual)
    prog = 0.0
    for i in range(n):
        prog += B.tramo(t, inicios[i], fines[i])
    prog /= n
    bw = L['barra_w']
    en(L['barra_fondo'], L['PX'] + bw / 2, L['barra_y'] + 3 * u)
    fw = bw * prog
    if fw >= 2 * u:
        fill = B.caja(fw, 6 * u, 3 * u, L['acento'])
        en(fill, L['PX'] + fill.width / 2, L['barra_y'] + 3 * u)

    # la franja clara detrás del paso que toca: baja de un paso al siguiente
    pos = sum(B.suave(B.tramo(t, fines[i], fines[i] + 0.35)) for i in range(n - 1))
    a_res = B.suave(B.tramo(t, inicios[0] - 0.05, inicios[0] + 0.25)) * (1 - B.suave(B.tramo(t, fines[-1], fines[-1] + 0.45)))
    if a_res > 0.003:
        en(L['resalte'], w / 2, L['filas_y'] + L['FILA'] * (pos + 0.5), a_res)

    # los pasos
    for i, f in enumerate(L['filas']):
        activo = B.suave(B.tramo(t, inicios[i], inicios[i] + 0.25))
        hecho = B.suave(B.tramo(t, fines[i], fines[i] + 0.30))
        a_txt = 0.40 + 0.60 * activo - 0.14 * hecho
        en(f['nombre'].capa, *f['nombre_c'], a_txt)
        if f['dato'] is not None:
            en(f['dato'].capa, *f['dato_c'], 0.45 + 0.55 * activo)
        ix, iy = L['ico_x'], f['y']
        if activo < 1:
            en(L['aro'], ix, iy, 1 - activo)
        a_giro = activo * (1 - B.suave(B.tramo(t, fines[i], fines[i] + 0.15)))
        if a_giro > 0.003:
            en(L['giro'], ix, iy, a_giro, giro=(t - inicios[i]) * 400.0)
        if t >= fines[i]:
            dt = t - fines[i]
            if dt >= POP:
                capa = L['marca_llena']
            else:                                                # la marca se dibuja: se guarda por trozos
                q = round(B.sale(B.tramo(dt, 0.10, 0.40)) * 24) / 24
                capa = L['marcas_cache'].get(q)
                if capa is None:
                    capa = L['marcas_cache'][q] = icono_marca(L['ICO'], q)
            esc = 0.35 + 0.65 * B.rebote(B.tramo(dt, 0, 0.32), 1.7)
            en(capa, ix, iy, B.tramo(dt, 0, 0.10), escala=esc)
