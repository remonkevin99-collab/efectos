"""comentario: una tarjeta de comentarios encima de la cabeza donde alguien escribe una palabra, la publica, le dan un
corazón y el creador le contesta.

La tarjeta (diseño propio: blanca, redondeada, con su sombra) entra desde arriba. En el campo se escribe la palabra letra a
letra con su cursor; al tocar el botón de enviar, la palabra vuela del campo a la lista y aparece como comentario con su
círculo de avatar y el usuario. Le sale un corazón que late. Debajo, el creador «está escribiendo» (tres puntos) y llega
su respuesta. La tarjeta crece hacia arriba para hacer sitio, así nunca baja hacia la cara.

    .venv/bin/python efectos.py comentario tu_video.mp4 --fotos 0.3,1.2,2.2,3.0,3.6,4.6
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import base as B

NOMBRE = 'comentario'
DESCRIPCION = 'Alguien comenta una palabra, le dan un corazón y el creador le contesta'
OPCIONES = {
    'texto': 'EFECTOS',
    'usuario': 'tu_usuario',
    'creador': 'tu_cuenta',
    'respuesta': 'Te lo mandé por privado',
    'color': '#8B5CF6',
}
DURACION = 6.0

OSCURO = (28, 21, 55, 255)
GRIS = (118, 112, 136, 255)
CAMPO = (242, 240, 247, 255)
APAGADO = (214, 210, 226, 255)
CORAZON = (244, 63, 94, 255)
SALIDA = 0.40
SS = 4


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
        self.ancho = f.getlength(s)
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


def _pegar(c, rgbp, a, x0, y0, alfa=1.0):
    """Pega con su esquina en (x0, y0), con decimales (reparte entre píxeles vecinos: sin saltitos). `rgbp=None`: solo
    oscurece (para las sombras)."""
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


def colocar(c, capa, cx, cy, alfa=1.0, escala=1.0, giro=0.0):
    """Como base.poner (centro en cx, cy, con decimales), pero sin escala ni giro pega directo con numpy (más rápido)."""
    if alfa <= 0.003:
        return
    if abs(escala - 1) < 1e-6 and abs(giro) < 1e-6:
        rgbp, a = _premult(capa)
        _pegar(c, rgbp, a, cx - capa.width / 2, cy - capa.height / 2, alfa)
    else:
        B.poner(c, capa, cx, cy, escala=escala, giro=giro, alfa=alfa)


def tam_que_cabe(s, peso, tam, ancho):
    largo = B.fuente(peso, 100).getlength(s) / 100.0
    return min(tam, ancho / max(1e-3, largo))


def _bajar(im, w, h=None):
    return im.resize((max(1, round(w)), max(1, round(h if h is not None else w))), Image.LANCZOS)


# ── Piezas dibujadas aquí ───────────────────────────────────────────────────────────────────────────────────────────
def avatar(d, col_a, col_b, letra, u):
    """Un círculo con un degradado en diagonal y la inicial en blanco."""
    D = int(round(d * SS))
    yy, xx = np.mgrid[0:D, 0:D].astype(np.float32) / max(1, D - 1)
    k = ((xx + yy) / 2)[..., None]
    rgb = np.asarray(col_a[:3], np.float32) * (1 - k) + np.asarray(col_b[:3], np.float32) * k
    im = Image.fromarray(rgb.astype(np.uint8), 'RGB').convert('RGBA')
    m = Image.new('L', (D, D), 0)
    ImageDraw.Draw(m).ellipse([0, 0, D - 1, D - 1], fill=255)
    im.putalpha(m)
    im = _bajar(im, d)
    if letra:
        rt = Rotulo(letra, d * 0.46, 'bold', (255, 255, 255, 255))
        cx, cy = rt.centro(im.width / 2, im.height / 2, 'centro')
        im.alpha_composite(rt.capa, (int(round(cx - rt.w / 2)), int(round(cy - rt.h / 2))))
    return im


def _puntos_corazon(cx, cy, tam, n=160):
    """El contorno de un corazón (la curva clásica), centrado en (cx, cy) y de ancho `tam`."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x, y))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    esc = tam / (max(xs) - min(xs))
    my = (max(ys) + min(ys)) / 2
    return [(cx + x * esc, cy + (y - my) * esc) for x, y in pts]


def corazon(d, col, lleno=True, grosor=0.0):
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    g = grosor * SS
    pts = _puntos_corazon(D / 2, D / 2, D - 2 - g)
    if lleno:
        dr.polygon(pts, fill=col)
    else:
        dr.line(pts + [pts[0]], fill=col, width=int(round(g)), joint='curve')
    return _bajar(im, d)


def aro(d, col, grosor):
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([0, 0, D - 1, D - 1], outline=col, width=int(round(grosor * SS)))
    return _bajar(im, d)


def boton_enviar(d, fondo, u):
    """El botón de enviar: un círculo con una flecha hacia arriba."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, D - 1, D - 1], fill=fondo)
    g = 3.4 * u * SS
    cx, arriba, abajo = D / 2, D * 0.29, D * 0.71
    blanco = (255, 255, 255, 255)
    dr.line([(cx, abajo), (cx, arriba + g * 0.3)], fill=blanco, width=int(round(g)))
    for lado in (-1, 1):
        dr.line([(cx, arriba), (cx + lado * D * 0.17, arriba + D * 0.17)], fill=blanco, width=int(round(g)))
    for x, y in ((cx, abajo), (cx, arriba), (cx - D * 0.17, arriba + D * 0.17), (cx + D * 0.17, arriba + D * 0.17)):
        dr.ellipse([x - g / 2, y - g / 2, x + g / 2, y + g / 2], fill=blanco)
    return _bajar(im, d)


def pastilla(w, h, col):
    return B.caja(w, h, h / 2, col)


def _rebanadas(capa, corte):
    """Parte una capa (en números) en tres para poder estirarla a lo alto sin deformar las esquinas: lo de arriba hasta
    `corte`, una fila que se repite y lo de abajo."""
    rgbp, a = _premult(capa)
    return (rgbp[:corte], a[:corte]), (rgbp[corte:corte + 1], a[corte:corte + 1]), (rgbp[corte + 1:], a[corte + 1:])


def _estirar(reb, extra):
    (r0, a0), (r1, a1), (r2, a2) = reb
    n = max(0, int(extra)) + 1
    return (np.concatenate([r0, np.repeat(r1, n, 0), r2], 0), np.concatenate([a0, np.repeat(a1, n, 0), a2], 0))


def renglones(s, peso, tam, ancho):
    """Parte el texto en renglones que quepan en `ancho` (palabra a palabra)."""
    f = B.fuente(peso, tam)
    out, linea = [], ''
    for palabra in s.split():
        prueba = (linea + ' ' + palabra).strip()
        if linea and f.getlength(prueba) > ancho:
            out.append(linea)
            linea = palabra
        else:
            linea = prueba
    if linea:
        out.append(linea)
    return out or ['']


def texto_respuesta(s, ancho, u):
    """La respuesta: en un renglón a 31·u si cabe; si no, en dos (y más pequeña solo si ni así cabe)."""
    tam = 31 * u
    if B.fuente('regular', tam).getlength(s) <= ancho:
        return [s], tam
    lineas = renglones(s, 'regular', tam, ancho)
    while len(lineas) > 2 and tam > 22 * u:
        tam *= 0.94
        lineas = renglones(s, 'regular', tam, ancho)
    if len(lineas) > 2:                                       # muy larga: dos renglones y que quepa cada uno
        mitad = len(s.split()) // 2
        lineas = [' '.join(s.split()[:mitad]), ' '.join(s.split()[mitad:])]
        tam = min(tam_que_cabe(lineas[0], 'regular', tam, ancho), tam_que_cabe(lineas[1], 'regular', tam, ancho))
    return lineas, tam


def _inicial(nombre):
    for ch in nombre:
        if ch.isalnum():
            return ch.upper()
    return ''


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
def _preparar(c):
    op = c.op
    acento = B.color(op.get('color') or '#8B5CF6')
    claro = tuple(int(v + (255 - v) * 0.86) for v in acento[:3]) + (255,)
    vivo = tuple(int(v + (255 - v) * 0.35) for v in acento[:3]) + (255,)
    L = {}

    # medidas: si encima de la cabeza no cabe la tarjeta entera, se hace todo un poco más pequeño
    u0 = c.u
    abajo = min(cabeza_arriba(c) - 36 * u0, c.H * 0.42)
    techo = 120 * u0
    respuesta = str(op.get('respuesta') or '')
    lineas0, tam0 = texto_respuesta(respuesta, (900 - 30 - 12 - 178) * u0, u0)
    extra_res = (len(lineas0) - 1) * tam0 * 1.32 / u0          # lo que crece la fila si la respuesta va en dos renglones
    ALTO_TOTAL = 416 + extra_res
    k = float(max(0.62, min(1.0, (abajo - techo) / (ALTO_TOTAL * u0))))
    u = u0 * k
    L['u'] = u
    w = int(round(900 * u))
    PAD, PAD_B = 30 * u, 26 * u
    L.update(w=w, PAD=PAD, BASE=204 * u, FC=110 * u, FR=(102 + extra_res) * u, r=34 * u, FILA0=92 * u)
    L['x'] = int(round((c.W - w) / 2))
    L['abajo'] = int(round(abajo))

    # la tarjeta y su sombra, en rebanadas para estirarlas a lo alto según crece
    r = L['r']
    h0 = int(round(2 * r + 8 * u))
    tarjeta = B.caja(w, h0, r, (255, 255, 255, 250))
    L['reb_tarjeta'] = _rebanadas(tarjeta, h0 // 2)
    L['h0'] = h0
    des = 26 * u
    pad = int(des * 2.5)
    a = B.caja(w, h0, r, (0, 0, 0, 255)).split()[3].point(lambda v: v * 95 // 255)
    sm = Image.new('RGBA', (w + 2 * pad, h0 + 2 * pad), (0, 0, 0, 0))
    negro = Image.new('RGBA', a.size, (0, 0, 0, 255))
    negro.putalpha(a)
    sm.alpha_composite(negro, (pad, pad))
    sm = sm.filter(ImageFilter.GaussianBlur(des))
    L['reb_sombra'] = _rebanadas(sm, pad + h0 // 2)
    L['sombra_pad'], L['sombra_dy'] = pad, round(14 * u)

    # cabecera
    L['cab'] = Rotulo('Comentarios', 27 * u, 'bold', OSCURO)
    L['cab_c'] = L['cab'].centro(PAD + 4 * u, PAD + 16 * u)
    L['raya'] = B.caja(w - 2 * PAD, max(1, 1.6 * u), 0.8 * u, (28, 21, 55, 22))
    L['raya_y'] = PAD + 42 * u

    # el campo de escribir (abajo)
    usuario = str(op.get('usuario') or 'tu_usuario')
    creador = str(op.get('creador') or 'tu_cuenta')
    col_u = ((251, 146, 60, 255), (236, 72, 153, 255))         # el avatar de quien comenta: de naranja a rosa
    col_c = (acento, vivo)                                     # el del creador, en el color de acento
    L['av_campo'] = avatar(46 * u, *col_u, _inicial(usuario), u)
    L['campo_y'] = -(PAD_B + 36 * u)                           # desde abajo
    L['av_campo_x'] = PAD + 23 * u
    px0, px1 = PAD + 60 * u, w - PAD
    L['campo'] = pastilla(px1 - px0, 64 * u, CAMPO)
    L['campo_x'] = px0 + (px1 - px0) / 2
    L['hint'] = Rotulo('Añade un comentario…', 26 * u, 'regular', GRIS)
    L['hint_x'] = round(px0 + 24 * u)
    L['btn_gris'] = boton_enviar(48 * u, APAGADO, u)
    L['btn_vivo'] = boton_enviar(48 * u, acento, u)
    L['btn_x'] = px1 - 8 * u - 24 * u

    # la palabra, letra a letra (con la misma letra en el campo y en el comentario: así puede volar de uno a otro)
    texto = str(op.get('texto') or '')
    libre = (L['btn_x'] - 34 * u) - L['hint_x']
    tam = tam_que_cabe(texto, 'bold', 34 * u, libre)
    f = B.fuente('bold', tam)
    L['letras'] = []
    for i, ch in enumerate(texto):
        rt = Rotulo(ch, tam, 'bold', OSCURO)
        L['letras'].append((rt, round(f.getlength(texto[:i]))))
    L['texto_ancho'] = f.getlength(texto)
    L['cursor'] = B.caja(3.2 * u, 36 * u, 1.6 * u, acento)

    # el comentario
    FC = L['FC']
    L['av_com'] = avatar(62 * u, *col_u, _inicial(usuario), u)
    L['av_com_x'], L['av_com_dy'] = PAD + 31 * u, 47 * u
    L['nom'] = Rotulo(usuario, 26 * u, 'bold', OSCURO)
    L['nom_x'], L['nom_dy'] = PAD + 80 * u, 25 * u
    L['ahora'] = Rotulo('ahora', 22 * u, 'regular', GRIS)
    L['com_x'], L['com_dy'] = round(PAD + 80 * u), 70 * u     # donde aterriza la palabra
    L['cor_x'], L['cor_dy'] = w - PAD - 28 * u, 40 * u
    L['cor_vacio'] = corazon(34 * u, GRIS, lleno=False, grosor=2.6 * u)
    L['cor_lleno'] = corazon(34 * u, CORAZON)
    L['cor_aro'] = aro(70 * u, CORAZON, 3 * u)
    L['me_gusta'] = Rotulo('1', 20 * u, 'medium', GRIS)

    # la respuesta del creador
    L['av_res'] = avatar(52 * u, *col_c, _inicial(creador), u)
    L['av_res_x'], L['av_res_dy'] = PAD + 80 * u + 26 * u, 44 * u
    L['res_x'] = round(PAD + 80 * u + 52 * u + 16 * u)
    L['nom_c'] = Rotulo(creador, 25 * u, 'bold', OSCURO)
    insignia_t = Rotulo('Creador', 17 * u, 'bold', acento)
    insignia = pastilla(insignia_t.ancho + 22 * u, 28 * u, claro)
    icx, icy = insignia_t.centro(insignia.width / 2, insignia.height / 2, 'centro')
    insignia.alpha_composite(insignia_t.capa, (int(round(icx - insignia_t.w / 2)), int(round(icy - insignia_t.h / 2))))
    L['insignia'] = insignia
    libre = w - PAD - 12 * u - L['res_x']
    lineas, tam_r = texto_respuesta(respuesta, libre, u)
    L['res'] = [Rotulo(ln, tam_r, 'regular', OSCURO) for ln in lineas]
    L['res_dy'], L['res_salto'] = 68 * u, tam_r * 1.32
    L['escribiendo'] = pastilla(78 * u, 40 * u, CAMPO)
    L['punto'] = avatar(10 * u, (150, 144, 168, 255), (150, 144, 168, 255), '', u)

    # los tiempos, repartidos por la duración
    d = c.dur
    n = max(1, len(texto))
    t0 = max(0.45, 0.08 * d)
    t1 = max(t0 + 0.06 * n, 0.27 * d)
    L['t_letras'] = [t0 + (t1 - t0) * i / n for i in range(n)]
    L['t_fin_escribir'] = t1
    L['t_pub'] = max(t1 + 0.2, 0.31 * d)
    L['t_cor'] = max(L['t_pub'] + 0.7, 0.45 * d)
    L['t_puntos'] = max(L['t_cor'] + 0.5, 0.55 * d)
    L['t_res'] = max(L['t_puntos'] + 0.6, 0.68 * d)
    c.estado['comentario'] = L
    return L


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def dibujar(c):
    L = c.estado.get('comentario') or _preparar(c)
    u, t = L['u'], c.t
    alfa = B.suave(B.tramo(t, 0, 0.30)) * B.suave(B.tramo(c.queda, 0, SALIDA))
    if alfa <= 0.003:
        return
    w, PAD, FC, FR = L['w'], L['PAD'], L['FC'], L['FR']
    t_pub, t_cor, t_pun, t_res = L['t_pub'], L['t_cor'], L['t_puntos'], L['t_res']

    # la tarjeta crece hacia arriba: primero para el comentario y después para la respuesta
    g1 = B.suave(B.tramo(t, t_pub + 0.05, t_pub + 0.45))
    g2 = B.suave(B.tramo(t, t_pun, t_pun + 0.40))
    alto = int(round(L['BASE'] + FC * g1 + FR * g2))
    # entra bajando un poco desde arriba y al final se va subiendo un poco
    dy = -(1 - B.suave(B.tramo(t, 0, 0.35))) * 26 * u - (1 - B.suave(B.tramo(c.queda, 0, SALIDA))) * 12 * u
    X = L['x']
    abajo = L['abajo'] + dy
    arriba = abajo - alto

    def en(capa, rx, ry, a=1.0, **kw):
        colocar(c, capa, X + rx, arriba + ry, alfa=alfa * a, **kw)

    def en_abajo(capa, rx, ry, a=1.0, **kw):
        colocar(c, capa, X + rx, abajo + ry, alfa=alfa * a, **kw)

    # sombra y tarjeta (estiradas a la altura de este cuadro)
    extra = alto - L['h0']
    s_rgbp, s_a = _estirar(L['reb_sombra'], extra)
    _pegar(c, None, s_a, X - L['sombra_pad'], arriba - L['sombra_pad'] + L['sombra_dy'], alfa)
    t_rgbp, t_a = _estirar(L['reb_tarjeta'], extra)
    _pegar(c, t_rgbp, t_a, X, arriba, alfa)

    # cabecera
    en(L['cab'].capa, *L['cab_c'])
    en(L['raya'], w / 2, L['raya_y'])

    # el campo de escribir
    cy = L['campo_y']
    en_abajo(L['av_campo'], L['av_campo_x'], cy)
    en_abajo(L['campo'], L['campo_x'], cy)
    letras = L['letras']
    escritas = [i for i, tl in enumerate(L['t_letras']) if t >= tl]
    hint_fuera = B.suave(B.tramo(t, L['t_letras'][0] - 0.12, L['t_letras'][0])) if letras else 0
    hint_vuelve = B.suave(B.tramo(t, t_pub + 0.35, t_pub + 0.6))
    a_hint = max(1 - hint_fuera, hint_vuelve)
    hx, hy = L['hint'].centro(L['hint_x'], 0)
    en_abajo(L['hint'].capa, hx, hy + cy, a_hint)

    # el botón: gris sin texto, del color de acento con texto; al publicar se hunde y vuelve
    vivo = B.suave(B.tramo(t, L['t_letras'][0], L['t_letras'][0] + 0.2)) if letras else 0
    vivo *= 1 - B.suave(B.tramo(t, t_pub + 0.25, t_pub + 0.45))
    hunde = 1 - 0.14 * math.sin(math.pi * B.tramo(t, t_pub - 0.08, t_pub + 0.22))
    en_abajo(L['btn_gris'], L['btn_x'], cy, 1.0, escala=hunde)
    if vivo > 0.003:
        en_abajo(L['btn_vivo'], L['btn_x'], cy, vivo, escala=hunde)

    # la palabra: se escribe en el campo y al publicar vuela a su sitio en la lista
    vuela = B.suave(B.tramo(t, t_pub + 0.05, t_pub + 0.50))
    x_campo, y_campo = L['hint_x'], abajo + cy                  # (en coordenadas del cuadro)
    fila_com = arriba + L['FILA0']
    x_lista, y_lista = L['com_x'], fila_com + L['com_dy']
    bx = B.mezclar(x_campo, x_lista, vuela)
    by = B.mezclar(y_campo, y_lista, vuela)
    for i in escritas:
        rt, desp = letras[i]
        aparece = B.sale(B.tramo(t, L['t_letras'][i], L['t_letras'][i] + 0.08))
        cx, cyl = rt.centro(desp, 0)
        colocar(c, rt.capa, X + bx + cx, by + cyl + (1 - aparece) * 5 * u, alfa=alfa * aparece)

    # el cursor: parpadea suave cuando espera, fijo mientras escribe, y se va al publicar
    if letras:
        ultimo = escritas[-1] if escritas else -1
        if ultimo >= 0:
            rt, desp = letras[ultimo]
            k = B.sale(B.tramo(t, L['t_letras'][ultimo], L['t_letras'][ultimo] + 0.08))
            ancho_ant = desp
            ancho_nuevo = L['texto_ancho'] if ultimo == len(letras) - 1 else letras[ultimo + 1][1]
            x_cur = B.mezclar(ancho_ant, ancho_nuevo, k) + 3 * u
        else:
            x_cur = 0
        escribiendo = L['t_letras'][0] - 0.05 <= t <= L['t_fin_escribir'] + 0.1
        parpadeo = 1.0 if escribiendo else 0.5 + 0.5 * math.cos(2 * math.pi * t / 0.9)
        a_cur = parpadeo * (1 - B.suave(B.tramo(t, t_pub - 0.05, t_pub + 0.1)))
        if a_cur > 0.003:
            colocar(c, L['cursor'], X + x_campo + x_cur, y_campo, alfa=alfa * a_cur)

    # el comentario: avatar, usuario y corazón entran con la palabra
    a_com = B.suave(B.tramo(t, t_pub + 0.20, t_pub + 0.55))
    if a_com > 0.003:
        sube = (1 - B.sale(B.tramo(t, t_pub + 0.20, t_pub + 0.6))) * 14 * u
        en(L['av_com'], L['av_com_x'], L['FILA0'] + L['av_com_dy'] + sube, a_com)
        nx, ny = L['nom'].centro(L['nom_x'], L['nom_dy'])
        en(L['nom'].capa, nx, L['FILA0'] + ny + sube, a_com)
        ax, ay = L['ahora'].centro(L['nom_x'] + L['nom'].ancho + 12 * u, L['nom_dy'])
        en(L['ahora'].capa, ax, L['FILA0'] + ay + sube, a_com)
        # el corazón: vacío, después se llena con un salto y late
        cx, cyc = L['cor_x'], L['FILA0'] + L['cor_dy'] + sube
        lleno = B.tramo(t, t_cor, t_cor + 0.12)
        if lleno < 1:
            en(L['cor_vacio'], cx, cyc, a_com * (1 - lleno))
        if t >= t_cor:
            dt = t - t_cor
            esc = 0.45 + 0.55 * B.rebote(B.tramo(dt, 0, 0.38), 1.8)
            fase = max(0.0, dt - 0.6) % 1.1                   # late: dos golpes cortos y una pausa
            golpe = math.exp(-((fase - 0.10) / 0.07) ** 2) + 0.7 * math.exp(-((fase - 0.32) / 0.07) ** 2)
            esc *= 1 + 0.13 * golpe * B.tramo(dt, 0.5, 0.7)
            en(L['cor_lleno'], cx, cyc, lleno, escala=esc)
            onda = B.tramo(dt, 0.02, 0.45)
            if 0 < onda < 1:
                en(L['cor_aro'], cx, cyc, (1 - onda) * 0.55, escala=0.45 + 0.75 * B.sale(onda))
            gx, gy = L['me_gusta'].centro(cx, L['FILA0'] + L['cor_dy'] + 35 * u, 'centro')
            en(L['me_gusta'].capa, gx, gy + sube, B.suave(B.tramo(dt, 0.15, 0.45)))

    # la respuesta del creador: primero «escribiendo…» y después el texto
    a_fila = B.suave(B.tramo(t, t_pun + 0.10, t_pun + 0.40))
    if a_fila > 0.003:
        fila = L['FILA0'] + FC
        en(L['av_res'], L['av_res_x'], fila + L['av_res_dy'], a_fila)
        a_pun = a_fila * (1 - B.suave(B.tramo(t, t_res - 0.05, t_res + 0.12)))
        if a_pun > 0.003:
            pw = L['escribiendo']
            px = L['res_x'] + pw.width / 2
            py = fila + L['av_res_dy']
            en(pw, px, py, a_pun)
            for i in range(3):
                salto = max(0.0, math.sin(2 * math.pi * (t * 1.7) - i * 0.9)) * 6 * u
                en(L['punto'], px + (i - 1) * 18 * u, py - salto, a_pun)
        a_res = B.suave(B.tramo(t, t_res, t_res + 0.35))
        if a_res > 0.003:
            sube = (1 - B.sale(B.tramo(t, t_res, t_res + 0.4))) * 10 * u
            nx, ny = L['nom_c'].centro(L['res_x'], 24 * u)
            en(L['nom_c'].capa, nx, fila + ny + sube, a_res)
            ix = L['res_x'] + L['nom_c'].ancho + 10 * u + L['insignia'].width / 2
            en(L['insignia'], round(ix - L['insignia'].width / 2) + L['insignia'].width / 2,
               fila + round(24 * u - L['insignia'].height / 2) + L['insignia'].height / 2 + sube, a_res)
            ax, ay = L['ahora'].centro(ix + L['insignia'].width / 2 + 10 * u, 24 * u)
            en(L['ahora'].capa, ax, fila + ay + sube, a_res)
            for i, rt in enumerate(L['res']):
                rx, ry = rt.centro(L['res_x'], L['res_dy'] + i * L['res_salto'])
                en(rt.capa, rx, fila + ry + sube, a_res)
