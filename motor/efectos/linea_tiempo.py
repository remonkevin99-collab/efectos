"""linea-tiempo: el vídeo se pone con color de cine (cálido y rojizo) y abajo sale una línea de tiempo de edición.

Arriba a la izquierda, un título grande con su subtítulo y un punto rojo de grabación con un código de tiempo que corre.
Abajo, un panel de cristal oscuro con una regla de segundos, cuatro pistas con sus clips (en tonos del color de acento
que van hacia el rojo) y un cabezal que avanza mientras dura el efecto; el clip que pisa el cabezal se ilumina.

    .venv/bin/python efectos.py linea-tiempo tu_video.mp4 --fotos 0.2,0.6,2.0,4.0
"""
import colorsys
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import base as B

try:                       # OpenCV hace el desenfoque y el color mucho más rápido; si no está, se usa numpy y Pillow
    import cv2
except ImportError:
    cv2 = None

NOMBRE = 'linea-tiempo'
DESCRIPCION = 'Color de cine cálido, un título con su código de tiempo y una línea de tiempo de edición que avanza'
OPCIONES = {
    'titulo': 'EDITADO',
    'subtitulo': 'por Claude',
    'color': '#8B5CF6',
}
DURACION = 5.0

ROJO = (255, 72, 72, 255)          # el punto de grabación y el cabezal
SALIDA = 0.45
SS = 4

def _matriz_cine():
    """El color de cine en una sola matriz: primero le quita un 40 % de saturación (si no, una luz morada se vuelve
    fucsia al calentarla), después sube el rojo y baja mucho el azul, y al final le da un poco de contraste. Probado en
    la toma de Kevin: la pared y la luz quedan rojizas y la piel cálida sin quemarse."""
    luz = np.array([0.299, 0.587, 0.114], np.float32)
    menos_saturado = 0.6 * np.eye(3, dtype=np.float32) + 0.4 * np.tile(luz, (3, 1))
    calor = np.diag([1.12, 0.95, 0.70]).astype(np.float32)
    return (1.07 * calor @ menos_saturado).astype(np.float32)


MATRIZ = _matriz_cine()
SUMA = (0.0, -0.02, -0.035)          # los negros, un poco más hondos y sin azul

# Los clips de cada pista, en fracciones del ancho de la regla: (desde, hasta, nombre)
PISTAS = [
    ('V2', 'video', [(0.04, 0.37, 'título'), (0.50, 0.77, 'zoom')]),
    ('V1', 'video', [(0.0, 0.555, 'toma_02'), (0.562, 1.0, 'toma_03')]),
    ('A1', 'audio', [(0.0, 0.94, 'voz')]),
    ('A2', 'audio', [(0.10, 1.0, 'música')]),
]


# ── Ayudantes (los mismos que usan los otros efectos de esta tanda) ─────────────────────────────────────────────────
class Rotulo:
    """Un texto listo para colocar: su capa y dónde cae la tinta dentro de ella (para alinear de verdad, no la caja)."""

    def __init__(self, s, tam, peso, relleno, **kw):
        self.capa = B.texto(s, tam, peso, relleno, **kw)
        f = B.fuente(peso, tam)
        asc, desc = f.getmetrics()
        self.pad = (self.capa.height - (asc + desc)) / 2
        caja_h = f.getbbox('H')
        self.medio = self.pad + (caja_h[1] + caja_h[3]) / 2
        self.ancho = f.getlength(s) + (kw.get('espacio', 0) * tam * max(0, len(s) - 1))
        self.w, self.h = self.capa.size

    def centro(self, x, y, alinear='izq'):
        if alinear == 'izq':
            x0 = x - self.pad
        elif alinear == 'der':
            x0 = x - self.pad - self.ancho
        else:
            x0 = x - self.pad - self.ancho / 2
        return round(x0) + self.w / 2, round(y - self.medio) + self.h / 2


_PREMULT = {}


def _premult(capa):
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


def _pegar(c, rgbp, a, x0, y0, alfa=1.0, detras=False):
    """Pega con su esquina en (x0, y0), con decimales (reparte entre píxeles vecinos: sin saltitos)."""
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
    if detras:                                          # queda detrás de la persona: la máscara la tapa
        alfa = alfa * (1.0 - c.mascara[Y0:Y1, X0:X1, None])
        zona *= 1.0 - al * alfa
        if rgbp is not None:
            zona += rgbp[sy:sy + Y1 - Y0, sx:sx + X1 - X0] * alfa
        return
    zona *= (1.0 - al * alfa) if alfa < 0.999 else (1.0 - al)
    if rgbp is not None:
        col = rgbp[sy:sy + Y1 - Y0, sx:sx + X1 - X0]
        zona += col * alfa if alfa < 0.999 else col


def colocar(c, capa, cx, cy, alfa=1.0, escala=1.0, giro=0.0, detras=False):
    """Como base.poner (centro en cx, cy, con decimales), pero sin escala ni giro pega directo con numpy (más rápido)."""
    if alfa <= 0.003:
        return
    if abs(escala - 1) < 1e-6 and abs(giro) < 1e-6:
        rgbp, a = _premult(capa)
        _pegar(c, rgbp, a, cx - capa.width / 2, cy - capa.height / 2, alfa, detras)
    else:
        B.poner(c, capa, cx, cy, escala=escala, giro=giro, alfa=alfa, detras=detras)


def vidrio(c, x, y, w, h, r, tinte=(18, 14, 30), opacidad=0.60, desenfoque=30, brillo=0.20):
    """Cristal esmerilado con lo que hay detrás (más rápido que base.cristal). Devuelve (color premultiplicado,
    transparencia) con su esquina en (x, y)."""
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
    fondo = fondo * (1 - filo) + filo
    return fondo * mascara, mascara


def tam_que_cabe(s, peso, tam, ancho):
    largo = B.fuente(peso, 100).getlength(s) / 100.0
    return min(tam, ancho / max(1e-3, largo))


# ── Colores ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def tonos_calidos(acento, n=4):
    """n tonos que salen del color de acento y van girando hacia el rojo cálido (el camino corto en el círculo de color)."""
    r, g, b = [v / 255.0 for v in acento[:3]]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    destino = 0.015                                         # rojo anaranjado
    giro = ((destino - h + 0.5) % 1.0) - 0.5
    out = []
    for k in range(n):
        f = k / max(1, n - 1)
        hh = (h + giro * f) % 1.0
        ll = min(0.62, max(0.48, l + 0.03 * (1 - f)))
        ss = min(1.0, max(0.62, s))
        rr, gg, bb = colorsys.hls_to_rgb(hh, ll, ss)
        out.append((int(rr * 255), int(gg * 255), int(bb * 255), 255))
    return out


def aclarar(col, k):
    return tuple(int(v + (255 - v) * k) for v in col[:3]) + (col[3] if len(col) > 3 else 255,)


def oscurecer_col(col, k, alfa=255):
    return tuple(int(v * (1 - k)) for v in col[:3]) + (alfa,)


# ── Piezas dibujadas aquí ───────────────────────────────────────────────────────────────────────────────────────────
def punto(d, col):
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([0, 0, D - 1, D - 1], fill=col)
    return im.resize((max(1, round(d)), max(1, round(d))), Image.LANCZOS)


def halo(d, col):
    """Un brillo suave alrededor del punto rojo."""
    D = int(round(d * 2.6))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([D * 0.3, D * 0.3, D * 0.7, D * 0.7], fill=col[:3] + (150,))
    return im.filter(ImageFilter.GaussianBlur(D * 0.12))


def cabezal(u, alto, col):
    """El cabezal de reproducción: una pestaña arriba con su punta y una línea fina hasta abajo."""
    w = int(round(24 * u))
    cab = 20 * u
    punta = 8 * u
    H = int(round(alto))
    k = SS
    im = Image.new('RGBA', (w * k, H * k), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, w * k - 1, cab * k], radius=6 * u * k, fill=col)
    dr.polygon([(0, cab * k - 6 * u * k), (w * k - 1, cab * k - 6 * u * k), (w * k / 2, (cab + punta) * k)], fill=col)
    gl = 2.6 * u * k
    dr.rectangle([w * k / 2 - gl / 2, cab * k, w * k / 2 + gl / 2, H * k - 1], fill=col)
    return im.resize((w, H), Image.LANCZOS)


def onda(w, h, u, col, semilla, voz=True):
    """La forma de onda de un clip de audio: barras finas con alturas que suben y bajan como una voz o una música."""
    k = SS
    im = Image.new('RGBA', (int(w * k), int(h * k)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    paso, grueso = 5.5 * u, 2.6 * u
    n = int(w / paso)
    for i in range(n):
        x = i * paso + paso / 2
        f = x / max(1.0, w)
        if voz:     # frases con pausas
            env = 0.25 + 0.75 * max(0.0, math.sin(f * 23.0 + semilla) * 0.6 + math.sin(f * 61.0 + semilla * 2) * 0.4)
            v = env * (0.55 + 0.45 * abs(math.sin(i * 1.7 + semilla * 3.1)))
        else:       # la música: más pareja
            v = 0.45 + 0.25 * math.sin(f * 40 + semilla) + 0.2 * abs(math.sin(i * 0.9 + semilla))
        hh = max(2 * u, min(1.0, v) * h * 0.78)
        dr.rounded_rectangle([(x - grueso / 2) * k, (h / 2 - hh / 2) * k, (x + grueso / 2) * k, (h / 2 + hh / 2) * k],
                             radius=grueso * k / 2, fill=col)
    return im.resize((max(1, int(round(w))), max(1, int(round(h)))), Image.LANCZOS)


# ── Lo que no cambia ────────────────────────────────────────────────────────────────────────────────────────────────
def _mapa_luz(c):
    """Lo que oscurece el cine: una viñeta suave en las esquinas y una franja más oscura arriba para que el título se
    lea sobre una pared clara. 1 = igual, menos de 1 = más oscuro."""
    H, W, u = c.H, c.W, c.u
    ys = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
    xs = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
    d = np.sqrt((xs * 0.9) ** 2 + (ys * 0.62) ** 2)
    vineta = 1.0 - 0.30 * np.clip((d - 0.55) / 0.75, 0, 1) ** 1.6
    y = np.arange(H, dtype=np.float32)[:, None]
    arriba = 1.0 - 0.38 * np.clip(1 - (y - 330 * u) / (330 * u), 0, 1) ** 1.3
    return (vineta * arriba).astype(np.float32)


def _preparar(c):
    u, op = c.u, c.op
    acento = B.color(op.get('color') or '#8B5CF6')
    tonos = tonos_calidos(acento)
    L = {'mapa': _mapa_luz(c)}
    if cv2 is not None:
        L['mapa3'] = cv2.merge([L['mapa']] * 3)
        L['matriz34'] = np.hstack([MATRIZ, np.asarray(SUMA, np.float32)[:, None]]).astype(np.float32)

    # ── arriba a la izquierda: grabación, título y subtítulo
    x0 = 84 * u
    blanco = (255, 255, 255, 255)
    L['punto'] = punto(18 * u, ROJO)
    L['halo'] = halo(18 * u, ROJO)
    rec_y = 228 * u
    L['punto_c'] = (round(x0) + L['punto'].width / 2, round(rec_y - L['punto'].height / 2) + L['punto'].height / 2)
    L['rec'] = Rotulo('REC', 25 * u, 'bold', blanco, sombra=3 * u, color_sombra=(0, 0, 0, 120))
    L['rec_c'] = L['rec'].centro(x0 + 18 * u + 12 * u, rec_y)
    # el código de tiempo con las cifras en casillas del mismo ancho (si no, baila al correr)
    f_tc = B.fuente('medium', 25 * u)
    L['glifos'] = {ch: Rotulo(ch, 25 * u, 'medium', (255, 255, 255, 235), sombra=3 * u, color_sombra=(0, 0, 0, 120))
                   for ch in '0123456789:'}
    L['casilla'] = max(f_tc.getlength(d) for d in '0123456789')
    L['dos_puntos'] = f_tc.getlength(':') + 2 * u
    L['tc_x'] = x0 + 18 * u + 12 * u + L['rec'].ancho + 18 * u
    L['rec_y'] = rec_y

    titulo = str(op.get('titulo') or '')
    tam = tam_que_cabe(titulo, 'extrabold', 138 * u, 900 * u)
    L['titulo'] = Rotulo(titulo, tam, 'extrabold', blanco, sombra=10 * u, color_sombra=(0, 0, 0, 110), espacio=0.01)
    tit_y = rec_y + 26 * u + tam * 0.36 + 22 * u
    L['titulo_c'] = L['titulo'].centro(x0 - tam * 0.03, tit_y)
    sub = str(op.get('subtitulo') or '')
    sub_tam = tam_que_cabe(sub, 'medium', 46 * u, 900 * u)
    L['sub'] = Rotulo(sub, sub_tam, 'medium', aclarar(tonos[2], 0.72), sombra=6 * u, color_sombra=(0, 0, 0, 150))
    L['sub_c'] = L['sub'].centro(x0, tit_y + tam * 0.36 + 22 * u + sub_tam * 0.36)

    # ── abajo: el panel de la línea de tiempo
    w, h = int(round(940 * u)), int(round(334 * u))
    L['w'], L['h'], L['r'] = w, h, 28 * u
    L['x'] = int(round((c.W - w) / 2))
    L['y'] = int(round(c.H - 262 * u - h))
    # si la cara bajara mucho, el panel no la tapa: se queda por debajo de la barbilla
    _, cy, ac = (float(v) for v in c.cara)
    L['y'] = max(L['y'], int(round(min(c.H - 120 * u - h, cy + 1.05 * ac + 30 * u))))
    PX = 24 * u
    gris = (255, 255, 255, 140)

    # todo lo fijo del panel se dibuja en una sola capa
    capa = Image.new('RGBA', (w, h), (0, 0, 0, 0))

    def pega(rt, cx, cy):
        capa.alpha_composite(rt.capa, (int(round(cx - rt.w / 2)), int(round(cy - rt.h / 2))))

    cab_y = 30 * u
    rt = Rotulo('Línea de tiempo', 21 * u, 'bold', (255, 255, 255, 215))
    pega(rt, *rt.centro(PX, cab_y))
    rt = Rotulo(f'Secuencia 01  ·  {int(round(c.fps))} fps', 19 * u, 'medium', gris)
    pega(rt, *rt.centro(w - PX, cab_y, 'der'))

    ax0 = PX + 64 * u                                    # donde empieza la regla
    aw = w - PX - ax0
    L['ax0'], L['aw'] = ax0, aw
    ventana = max(4, int(math.ceil(c.dur + 0.6)))       # segundos que caben en la regla
    L['ventana'] = ventana
    regla_y = 64 * u
    dr = ImageDraw.Draw(capa)
    for i in range(ventana * 4 + 1):                    # rayitas cada cuarto de segundo, más largas en cada segundo
        x = ax0 + aw * i / (ventana * 4)
        largo = 12 * u if i % 4 == 0 else (7 * u if i % 2 == 0 else 4 * u)
        dr.rectangle([round(x - 0.75 * u), round(regla_y + 26 * u - largo), round(x + 0.75 * u), round(regla_y + 26 * u)],
                     fill=(255, 255, 255, 120 if i % 4 == 0 else 70))
        if i % 4 == 0 and i < ventana * 4:
            rt = Rotulo(f'0:{i // 4:02d}', 17 * u, 'medium', gris)
            pega(rt, *rt.centro(x + 6 * u, regla_y + 6 * u))
    dr.rectangle([round(ax0), round(regla_y + 27 * u), round(ax0 + aw), round(regla_y + 28 * u)], fill=(255, 255, 255, 40))

    pista_y0, pista_h, hueco = 106 * u, 46 * u, 8 * u
    L['clips'] = []
    for p, (nombre, tipo, clips) in enumerate(PISTAS):
        y0 = pista_y0 + p * (pista_h + hueco)
        etiqueta = B.caja(50 * u, pista_h, 10 * u, (255, 255, 255, 20))
        capa.alpha_composite(etiqueta, (int(round(PX)), int(round(y0))))
        rt = Rotulo(nombre, 18 * u, 'bold', (255, 255, 255, 170))
        pega(rt, *rt.centro(PX + 25 * u, y0 + pista_h / 2, 'centro'))
        tono = tonos[p]
        for a, b, rot in clips:
            cx0 = ax0 + aw * a + (1.5 * u if a > 0 else 0)
            cx1 = ax0 + aw * b - (1.5 * u if b < 1 else 0)
            cw = cx1 - cx0
            if tipo == 'video':
                cuerpo = B.caja(cw, pista_h, 9 * u, oscurecer_col(tono, 0.12, 240))
                # un filo más claro arriba, recortado con la forma del clip (que no se salga por las esquinas)
                brillo = Image.new('RGBA', cuerpo.size, (0, 0, 0, 0))
                ImageDraw.Draw(brillo).rectangle([0, 0, cuerpo.width, round(3 * u)], fill=aclarar(tono, 0.35))
                forma = np.minimum(np.asarray(brillo.split()[3]), np.asarray(cuerpo.split()[3]))
                brillo.putalpha(Image.fromarray(forma))
                cuerpo.alpha_composite(brillo)
            else:
                cuerpo = B.caja(cw, pista_h, 9 * u, oscurecer_col(tono, 0.45, 225))
                ondas = onda(cw - 14 * u, pista_h - 10 * u, u, aclarar(tono, 0.30), semilla=p * 1.9 + a * 7, voz=(p == 2))
                cuerpo.alpha_composite(ondas, (int(7 * u), int(5 * u)))
            borde = B.caja(cw, pista_h, 9 * u, (0, 0, 0, 0), borde=(255, 255, 255, 50), grosor=1.2 * u)
            cuerpo.alpha_composite(borde)
            capa.alpha_composite(cuerpo, (int(round(cx0)), int(round(y0))))
            rt = Rotulo(rot, 17 * u, 'bold', (255, 255, 255, 235), sombra=2 * u, color_sombra=(0, 0, 0, 90))
            if rt.ancho + 22 * u < cw:
                if tipo == 'video':
                    pega(rt, *rt.centro(cx0 + 11 * u, y0 + pista_h / 2))
                else:                                   # en el audio, el nombre en una pastillita para que se lea
                    fondo = B.caja(rt.ancho + 16 * u, 24 * u, 8 * u, oscurecer_col(tono, 0.6, 210))
                    capa.alpha_composite(fondo, (int(round(cx0 + 8 * u)), int(round(y0 + 6 * u))))
                    pega(rt, *rt.centro(cx0 + 16 * u, y0 + 6 * u + 12 * u))
            # el marco que se enciende cuando el cabezal pasa por el clip
            marco = B.caja(cw + 4 * u, pista_h + 4 * u, 11 * u, (0, 0, 0, 0), borde=(255, 255, 255, 235), grosor=2.4 * u)
            L['clips'].append({'a': a, 'b': b, 'marco': marco,
                               'c': (round(cx0 - 2 * u) + marco.width / 2, round(y0 - 2 * u) + marco.height / 2)})
    L['fijo'] = capa
    alto_cab = pista_y0 + 4 * (pista_h + hueco) - hueco + 8 * u - regla_y + 4 * u
    L['cabezal'] = cabezal(u, alto_cab, ROJO)
    L['cabezal_y'] = regla_y - 4 * u + L['cabezal'].height / 2
    c.estado['linea'] = L
    return L


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def color_de_cine(c, L, k):
    """Lo mismo que base.colorear(c, MATRIZ, SUMA, k) más la viñeta, pero mucho más rápido: con OpenCV (la matriz y la
    suma en una sola operación) o, si no está, con la imagen aplanada en una lista de píxeles."""
    if cv2 is not None:
        nuevo = cv2.transform(c.img, L['matriz34'])
        cv2.threshold(nuevo, 1.0, 1.0, cv2.THRESH_TRUNC, dst=nuevo)       # nada pasa de 1
        cv2.threshold(nuevo, 0.0, 0.0, cv2.THRESH_TOZERO, dst=nuevo)      # ni baja de 0
        cv2.multiply(nuevo, L['mapa3'], dst=nuevo)
        if k >= 0.999:
            c.img[...] = nuevo
        else:
            c.img[...] = cv2.addWeighted(nuevo, float(k), c.img, float(1 - k), 0.0)
        return
    plano = c.img.reshape(-1, 3)
    nuevo = plano @ MATRIZ.T
    nuevo += np.asarray(SUMA, np.float32)
    np.clip(nuevo, 0, 1, out=nuevo)
    nuevo *= L['mapa'].reshape(-1, 1)
    if k >= 0.999:
        c.img[...] = nuevo.reshape(c.img.shape)
    else:
        nuevo -= plano
        nuevo *= k
        c.img += nuevo.reshape(c.img.shape)


def dibujar(c):
    L = c.estado.get('linea') or _preparar(c)
    u, t = c.u, c.t
    fuera = B.suave(B.tramo(c.queda, 0, SALIDA))           # 1 mientras dura, baja a 0 al final

    # 1) el color de cine: entra y sale suave
    k = B.suave(B.tramo(t, 0, 0.5)) * fuera
    if k > 0.003:
        color_de_cine(c, L, k)

    # 2) arriba: grabación, título y subtítulo (detrás de la persona: si alguien sale muy cerca, no le tapan la cara)
    a_rec = B.suave(B.tramo(t, 0.0, 0.35)) * fuera
    late = 0.35 + 0.65 * (0.5 + 0.5 * math.cos(2 * math.pi * t / 1.1))
    colocar(c, L['halo'], *L['punto_c'], alfa=a_rec * late * 0.8, detras=True)
    colocar(c, L['punto'], *L['punto_c'], alfa=a_rec * late, detras=True)
    colocar(c, L['rec'].capa, *L['rec_c'], alfa=a_rec, detras=True)
    cuadros = int(t * c.fps + 1e-6)
    fps = max(1, int(round(c.fps)))
    ss, ff = divmod(cuadros, fps)
    mm, ss = divmod(ss, 60)
    hh, mm = divmod(mm, 60)
    x = L['tc_x']
    for i, ch in enumerate(f'{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}'):
        rt = L['glifos'][ch]
        paso = L['dos_puntos'] if ch == ':' else L['casilla']
        colocar(c, rt.capa, *rt.centro(x + paso / 2, L['rec_y'], 'centro'), alfa=a_rec, detras=True)
        x += paso

    a_tit = B.suave(B.tramo(t, 0.10, 0.65)) * fuera
    sube = (1 - B.sale(B.tramo(t, 0.10, 0.75))) * 14 * u
    colocar(c, L['titulo'].capa, L['titulo_c'][0], L['titulo_c'][1] + sube, alfa=a_tit, detras=True)
    a_sub = B.suave(B.tramo(t, 0.25, 0.80)) * fuera
    sube = (1 - B.sale(B.tramo(t, 0.25, 0.90))) * 14 * u
    colocar(c, L['sub'].capa, L['sub_c'][0], L['sub_c'][1] + sube, alfa=a_sub, detras=True)

    # 3) abajo: el panel entra subiendo
    a_pan = B.suave(B.tramo(t, 0.05, 0.45)) * fuera
    if a_pan <= 0.003:
        return
    X = L['x']
    Y = L['y'] + (1 - B.suave(B.tramo(t, 0.05, 0.55))) * 90 * u
    w, h = L['w'], L['h']
    rgbp, a_v = vidrio(c, X, Y, w, h, L['r'], tinte=(16, 11, 12), opacidad=0.76, desenfoque=28, brillo=0.16)
    f_rgbp, f_a = _premult(L['fijo'])                      # la regla y los clips encima del cristal, en una pasada
    rgbp = f_rgbp + rgbp * (1.0 - f_a)
    _pegar(c, rgbp, a_v, X, Y, a_pan)

    # el cabezal avanza a ritmo constante (como al reproducir) y el clip que pisa se ilumina
    pos = t / L['ventana']
    for clip in L['clips']:
        dentro = min(B.tramo(pos, clip['a'] - 0.012, clip['a'] + 0.012), 1 - B.tramo(pos, clip['b'] - 0.012, clip['b'] + 0.012))
        if dentro > 0.003:
            colocar(c, clip['marco'], X + clip['c'][0], Y + clip['c'][1], alfa=a_pan * B.suave(dentro))
    cx = X + L['ax0'] + L['aw'] * pos
    colocar(c, L['cabezal'], cx, Y + L['cabezal_y'], alfa=a_pan)
