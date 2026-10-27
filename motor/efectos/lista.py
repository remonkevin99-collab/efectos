"""lista: los pasos de una tarea que se van marcando uno a uno, bajo la barbilla (o encima de la cabeza si abajo no cabe).

Tiene cuatro aspectos (la opción `estilo`); en los cuatro, los pasos, sus datos y cuándo se marca cada uno son lo mismo:

- «actual»: la tarjeta de cristal esmerilado de siempre. Arriba, un destello, el título, un contador («2 de 5») y una barra
  fina; el paso que toca lleva un círculo que gira y una franja clara detrás; al terminar, un círculo verde con una marca
  que se dibuja.
- «a» · Terminal: un cristal casi negro y grande, con letra gruesa. El contador («2/5») y los datos van en verde y en
  letra de máquina; el dato de cada paso se escribe solo, letra a letra, al marcarse. Arriba, una barra en tramos (uno por
  paso). Al acabar, un brillo cruza la tarjeta.
- «b» · Notificación: una tarjeta clara, como un aviso del teléfono, con un icono de app, letra oscura y los datos en el
  color de acento. La barra de progreso se pone verde al terminar.
- «c» · Progreso: una cabecera de color con el porcentaje en grande y una barra gruesa, y cada paso en su propia pastilla:
  la que toca se va llenando de color de izquierda a derecha y, al llenarse, sale la marca. Las pastillas entran en
  cascada.

    .venv/bin/python efectos.py lista tu_video.mp4 --duracion 6 --op estilo=a --fotos 0.2,1.0,2.0,3.5,5.5
"""
import math
import os
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import base as B

try:                       # OpenCV hace el desenfoque y el color mucho más rápido; si no está, se usa numpy y Pillow
    import cv2
except ImportError:
    cv2 = None

NOMBRE = 'lista'
DESCRIPCION = 'Una tarjeta con los pasos de una tarea que se van marcando uno a uno'
OPCIONES = {
    'titulo': 'Claude está editando tu clip',
    # cada paso separado por «|»; lo que va tras «::» es el dato pequeño de la derecha
    'pasos': 'Encontró tu cara::cada cuadro|Te recortó del fondo::IA|Puso el texto detrás::profundidad|'
             'Corrigió el color::cálido|Lo dejó en 4K::2160p',
    # los segundos en que queda HECHO cada paso, separados por «|» (por ejemplo «1,2|2|3,1|4|4,8»).
    # Vacío: se reparten solos por la duración.
    'marcas': '',
    'color': '#8B5CF6',
    # el aspecto: «notificacion» (una tarjeta clara, como un aviso del teléfono), «progreso» (porcentaje grande y
    # pastillas que se llenan de color) o «cristal» (una tarjeta de cristal oscuro)
    'estilo': 'notificacion',
}
DURACION = 6.0

VERDE = (34, 197, 94, 255)
VERDE_CLARO = (74, 222, 128, 255)    # el verde de la terminal: se lee bien sobre negro
TINTA = (28, 21, 55, 255)            # el texto oscuro de la casa (#1C1537)
GRIS = (91, 86, 112, 255)            # #5B5670
BLANCO = (255, 255, 255, 255)
LILA = (221, 214, 254, 255)          # #DDD6FE
OSCURO = (91, 33, 182, 255)          # morado oscuro de la casa (#5B21B6)
ENTRADA = 0.35       # lo que tarda la tarjeta en subir
SALIDA = 0.40        # el fundido del final
POP = 0.45           # lo que tarda la marca verde en salir entera
SS = 4               # los iconos se dibujan 4 veces más grandes y se reducen: bordes suaves


# ── Ayudantes ───────────────────────────────────────────────────────────────────────────────────────────────────────
# La letra de máquina (monoespaciada) para los datos del estilo «a». No se reparte con el motor: se usa la del sistema
# (Mac, Windows o Linux) y, si no hay ninguna, Poppins.
_MONOS = (('/System/Library/Fonts/SFNSMono.ttf', 0, 'Semibold'),
          ('/System/Library/Fonts/Menlo.ttc', 1, None),
          (os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts', 'consolab.ttf'), 0, None),
          ('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 0, None),
          ('/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf', 0, None))


@lru_cache(maxsize=32)
def fuente_mono(tam):
    for ruta, indice, variante in _MONOS:
        if not os.path.isfile(ruta):
            continue
        try:
            f = ImageFont.truetype(ruta, max(4, int(round(tam))), index=indice)
            if variante:
                f.set_variation_by_name(variante)
            return f
        except Exception:
            continue
    return B.fuente('medium', tam)


def _texto_con(s, f, relleno):
    """Como base.texto, pero con cualquier fuente (la de máquina)."""
    pad = int(math.ceil(f.size * 0.08))
    asc, desc = f.getmetrics()
    capa = Image.new('RGBA', (int(math.ceil(f.getlength(s))) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(capa).text((pad, pad), s, font=f, fill=relleno)
    return capa


class Rotulo:
    """Un texto listo para colocar: su capa y dónde cae la tinta dentro de ella (para alinear de verdad, no la caja).
    Con `fuente`, se escribe con esa fuente (la de máquina) en vez de Poppins."""

    def __init__(self, s, tam, peso, relleno, fuente=None):
        f = fuente or B.fuente(peso, tam)
        self.capa = B.texto(s, tam, peso, relleno) if fuente is None else _texto_con(s, f, relleno)
        asc, desc = f.getmetrics()
        self.pad = (self.capa.height - (asc + desc)) / 2          # texto() deja el mismo aire por los cuatro lados
        caja_h = f.getbbox('H')
        self.medio = self.pad + (caja_h[1] + caja_h[3]) / 2        # la mitad de la altura de las mayúsculas
        self.mayus = caja_h[3] - caja_h[1]                          # lo alto de las mayúsculas
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


def _mezcla(a, b, k):
    """Mezcla dos colores RGBA (k = 0 → a, k = 1 → b)."""
    return tuple(int(round(x + (y - x) * k)) for x, y in zip(a, b))


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


def _degradado(w, h, r, c1, c2, diagonal=0.25):
    """Un rectángulo redondeado con un degradado de c1 (izquierda, arriba) a c2 (derecha, abajo)."""
    w, h = max(1, int(round(w))), max(1, int(round(h)))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    k = (xx / max(1, w - 1)) * (1 - diagonal) + (yy / max(1, h - 1)) * diagonal
    a1, a2 = np.asarray(c1[:3], np.float32), np.asarray(c2[:3], np.float32)
    rgb = (a1 + (a2 - a1) * k[..., None]).clip(0, 255).astype(np.uint8)
    alfa = np.asarray(B.caja(w, h, r, (255, 255, 255, 255)).split()[3])
    return Image.fromarray(np.dstack([rgb, alfa]), 'RGBA')


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


def icono_giro(d, u, col, aro=(255, 255, 255, 60), grosor=3.4):
    """El círculo que gira mientras un paso se está haciendo: un aro tenue y un trozo de arco en el color de acento."""
    D = int(round(d * SS))
    g = grosor * u * SS
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, D - 1, D - 1], outline=aro, width=int(round(g)))
    dr.arc([0, 0, D - 1, D - 1], start=-90, end=40, fill=col, width=int(round(g)))
    rr = (D - g) / 2
    for ang in (-90, 40):                                   # las puntas del arco, redondas
        a = math.radians(ang)
        x, y = D / 2 + rr * math.cos(a), D / 2 + rr * math.sin(a)
        dr.ellipse([x - g / 2, y - g / 2, x + g / 2, y + g / 2], fill=col)
    return _bajar(im, d)


def icono_aro(d, u, col=(255, 255, 255, 85), grosor=2.6):
    """El paso que falta: un aro apagado."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([0, 0, D - 1, D - 1], outline=col, width=int(round(grosor * u * SS)))
    return _bajar(im, d)


def icono_marca(d, p, fondo=VERDE, tinta=BLANCO, trazo=0.19):
    """El círculo (verde) con la marca dibujada hasta `p` (0–1)."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, D - 1, D - 1], fill=fondo)
    if p > 0:
        R = D / 2
        pts = [(D / 2 + x * R, D / 2 + y * R) for x, y in ((-0.40, 0.02), (-0.12, 0.30), (0.42, -0.27))]
        g = trazo * R
        largos = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        queda = p * sum(largos)
        dr.ellipse([pts[0][0] - g / 2, pts[0][1] - g / 2, pts[0][0] + g / 2, pts[0][1] + g / 2], fill=tinta)
        for i, L in enumerate(largos):
            if queda <= 0:
                break
            k = min(1.0, queda / L)
            a, b = pts[i], pts[i + 1]
            fin = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            dr.line([a, fin], fill=tinta, width=int(round(g)))
            dr.ellipse([fin[0] - g / 2, fin[1] - g / 2, fin[0] + g / 2, fin[1] + g / 2], fill=tinta)
            queda -= L
    return _bajar(im, d)


def icono_onda(d, u, col, grosor=3.0):
    """La onda que sale de una marca recién puesta: un aro fino (se agranda y se apaga al dibujarlo)."""
    D = int(round(d * SS))
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([0, 0, D - 1, D - 1], outline=col, width=int(round(grosor * u * SS)))
    return _bajar(im, d)


def icono_brillo(d, col=(255, 255, 255), fuerza=1.0):
    """Un brillo redondo y difuso (la punta de una barra que se llena)."""
    D = max(2, int(round(d)))
    yy, xx = np.mgrid[0:D, 0:D].astype(np.float32)
    rr = np.hypot(xx - (D - 1) / 2, yy - (D - 1) / 2) / (D / 2)
    a = (np.exp(-(rr * 1.9) ** 2) * 255 * fuerza).clip(0, 255).astype(np.uint8)
    rgb = np.empty((D, D, 3), np.uint8)
    rgb[:] = col[:3]
    return Image.fromarray(np.dstack([rgb, a]), 'RGBA')


def icono_app(d, acento):
    """El icono de app de la notificación: un cuadrado redondeado de color con el destello blanco."""
    cap = _degradado(d, d, d * 0.24, _mezcla(acento, BLANCO, 0.12), _mezcla(acento, OSCURO, 0.75), diagonal=0.6)
    est = icono_destello(d * 0.56, BLANCO)
    cap.alpha_composite(est, (int(round((cap.width - est.width) / 2 + d * 0.02)), int(round((cap.height - est.height) / 2))))
    return cap


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


def _lugar(c, w, h):
    """Dónde va la tarjeta (su esquina de arriba a la izquierda): por debajo de la barbilla; si abajo no cabe, por encima
    de la cabeza. Centrada a lo ancho."""
    u = c.u
    cx, cy, ac = (float(v) for v in c.cara)
    barbilla = cy + 1.05 * ac
    coronilla = cabeza_arriba(c)
    abajo_max = c.H - 230 * u
    y = barbilla + 40 * u
    if y + h > abajo_max:
        arriba = coronilla - 40 * u - h
        y = arriba if arriba >= 150 * u else max(barbilla + 16 * u, abajo_max - h)
    return int(round((c.W - w) / 2)), int(round(y))


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


def _contador(en, nums, nums_c, t, fines, n, salto):
    """El número del paso que toca: al cambiar, el viejo se va hacia arriba y después entra el nuevo desde abajo (uno
    detrás del otro, para que no se monten)."""
    k = sum(1 for i in range(n - 1) if t >= fines[i])           # índice del paso que toca
    if k:
        t0 = fines[k - 1]
        va = B.suave(B.tramo(t, t0, t0 + 0.16))
        viene = B.suave(B.tramo(t, t0 + 0.08, t0 + 0.32))
        vx, vy = nums_c[k - 1]
        nx, ny = nums_c[k]
        if va < 1:
            en(nums[k - 1].capa, vx, vy - va * salto, 1 - va)
        en(nums[k].capa, nx, ny + (1 - viene) * salto, viene)
    else:
        en(nums[0].capa, *nums_c[0])


def _marca(L, dt, fondo, tinta):
    """La capa de la marca `dt` segundos después de quedar hecho el paso (se dibuja; se guarda por trozos)."""
    if dt >= POP:
        return L['marca_llena']
    q = round(B.sale(B.tramo(dt, 0.10, 0.40)) * 24) / 24
    capa = L['marcas_cache'].get(q)
    if capa is None:
        capa = L['marcas_cache'][q] = icono_marca(L['ICO'], q, fondo, tinta)
    return capa


def _icono_paso(en, L, t, i, ix, iy, fondo_marca, tinta_marca):
    """El icono de un paso: el aro mientras falta, el círculo que gira mientras se hace y la marca (con su onda) al
    terminar."""
    inicios, fines = L['inicios'], L['fines']
    activo = B.suave(B.tramo(t, inicios[i], inicios[i] + 0.25))
    if activo < 1:
        en(L['aro'], ix, iy, 1 - activo)
    a_giro = activo * (1 - B.suave(B.tramo(t, fines[i], fines[i] + 0.15)))
    if a_giro > 0.003:
        en(L['giro'], ix, iy, a_giro, giro=(t - inicios[i]) * 400.0)
    if t >= fines[i]:
        dt = t - fines[i]
        if dt < 0.45:                                               # la onda: sale del círculo y se apaga
            q = B.sale(B.tramo(dt, 0.04, 0.45))
            en(L['onda'], ix, iy, 0.9 * (1 - q) ** 1.5, escala=0.55 + 0.45 * q)
        esc = 0.35 + 0.65 * B.rebote(B.tramo(dt, 0, 0.32), 1.7)
        en(_marca(L, dt, fondo_marca, tinta_marca), ix, iy, B.tramo(dt, 0, 0.10), escala=esc)


# ── Estilo «actual»: la tarjeta de cristal de siempre ───────────────────────────────────────────────────────────────
def _preparar_actual(c):
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
    L['x'], L['y'] = _lugar(c, w, h)

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
    return L


def _dibujar_actual(c, L):
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
    _contador(en, L['nums'], L['nums_c'], t, fines, n, 12 * u)

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
            esc = 0.35 + 0.65 * B.rebote(B.tramo(dt, 0, 0.32), 1.7)
            en(_marca(L, dt, VERDE, BLANCO), ix, iy, B.tramo(dt, 0, 0.10), escala=esc)


# ── Estilo «a» · Terminal: cristal casi negro, letra gruesa, datos verdes que se escriben solos ──────────────────────
ESCRIBE = 0.035      # lo que tarda cada letra del dato en escribirse


def _preparar_a(c):
    u, op = c.u, c.op
    acento = B.color(op.get('color') or '#8B5CF6')
    pasos = _pasos(op)
    n = len(pasos)
    L = {'n': n, 'acento': acento}

    w = int(round(960 * u))                                     # de x 60 a x 1020: lo más ancho que deja la zona segura
    PX, PT, PB = 40 * u, 30 * u, 22 * u
    CAB, FILA, ICO, BARRA = 68 * u, 86 * u, 48 * u, 8 * u
    cab_y = PT + CAB / 2
    barra_y = PT + CAB + 12 * u
    filas_y = barra_y + BARRA + 14 * u
    h = int(round(filas_y + n * FILA + PB))
    r = 40 * u
    L.update(w=w, h=h, r=r, PX=PX, FILA=FILA, ICO=ICO, BARRA=BARRA, cab_y=cab_y, barra_y=barra_y, filas_y=filas_y)
    L['x'], L['y'] = _lugar(c, w, h)

    # cabecera: destello, título grueso y el contador («2/5») en letra de máquina
    L['destello'] = icono_destello(ICO, acento)
    mono_cab = fuente_mono(34 * u)
    L['de_n'] = Rotulo(f'/{n}', 34 * u, None, (255, 255, 255, 120), fuente=mono_cab)
    L['nums'] = [Rotulo(str(k), 34 * u, None, VERDE_CLARO, fuente=mono_cab) for k in range(1, n + 1)]
    titulo = str(op.get('titulo') or '')
    x_tit = PX + ICO + 16 * u
    libre = w - PX - x_tit - L['de_n'].ancho - L['nums'][-1].ancho - 24 * u
    L['titulo'] = Rotulo(titulo, tam_que_cabe(titulo, 'extrabold', 46 * u, libre), 'extrabold', BLANCO)
    L['titulo_c'] = L['titulo'].centro(x_tit, cab_y)
    L['de_n_c'] = L['de_n'].centro(w - PX, cab_y, 'der')
    x_num = w - PX - L['de_n'].ancho
    L['nums_c'] = [rt.centro(x_num, cab_y, 'der') for rt in L['nums']]

    # la barra en tramos: uno por paso
    hueco = 8 * u
    L['seg_w'] = (w - 2 * PX - (n - 1) * hueco) / n
    L['hueco'] = hueco
    L['seg_fondo'] = B.caja(L['seg_w'], BARRA, BARRA / 2, (255, 255, 255, 34))
    L['seg_lleno'] = B.caja(L['seg_w'], BARRA, BARRA / 2, VERDE_CLARO)

    # filas
    L['giro'] = icono_giro(ICO, u, VERDE_CLARO, aro=(255, 255, 255, 50), grosor=4.2)
    L['aro'] = icono_aro(ICO, u, (255, 255, 255, 95), 3.2)
    L['marca_llena'] = icono_marca(ICO, 1.0, VERDE, BLANCO, 0.21)
    L['marcas_cache'] = {}
    L['onda'] = icono_onda(ICO * 1.9, u, VERDE_CLARO, 2.4)
    L['resalte'] = B.caja(w - 2 * 16 * u, FILA - 8 * u, 20 * u, (255, 255, 255, 24))
    L['raya'] = B.caja(5 * u, FILA - 34 * u, 2.5 * u, VERDE_CLARO)
    mono = fuente_mono(32 * u)
    filas = []
    for i, (nombre, dato) in enumerate(pasos):
        yc = filas_y + FILA * (i + 0.5)
        ancho_dato = mono.getlength(dato) if dato else 0
        x_dato = w - PX - ancho_dato                            # el dato se escribe de izquierda a derecha desde aquí
        libre = w - 2 * PX - ICO - 22 * u - (ancho_dato + 28 * u if dato else 0)
        rn = Rotulo(nombre, tam_que_cabe(nombre, 'bold', 44 * u, libre), 'bold', BLANCO)
        filas.append({'y': yc, 'nombre': rn, 'nombre_c': rn.centro(PX + ICO + 22 * u, yc),
                      'dato': dato, 'x_dato': x_dato, 'trozos': {}})
    L['filas'] = filas
    L['mono'] = mono
    L['mayus_dato'] = Rotulo('H', 32 * u, None, VERDE_CLARO, fuente=mono).mayus
    L['cursor'] = B.caja(max(2, round(0.55 * mono.size)), round(L['mayus_dato'] * 1.25), 2 * u, VERDE_CLARO)
    L['ico_x'] = PX + ICO / 2
    L['inicios'], L['fines'] = _tiempos(c.dur, n, _numeros(op.get('marcas')))
    L['sombra'] = sombra_de(w, h, r, 30 * u, 120)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    L['diagonal'] = xx + 0.35 * yy                               # para el brillo que cruza la tarjeta al final
    return L


def _dibujar_a(c, L):
    u, t = c.u, c.t
    alfa = B.suave(B.tramo(t, 0, ENTRADA * 0.9)) * B.suave(B.tramo(c.queda, 0, SALIDA))
    if alfa <= 0.003:
        return
    sube = (1 - B.suave(B.tramo(t, 0, ENTRADA))) * 70 * u
    X, Y = L['x'], L['y'] + sube
    w, h, n = L['w'], L['h'], L['n']
    inicios, fines = L['inicios'], L['fines']

    def en(capa, rx, ry, a=1.0, **kw):
        colocar(c, capa, X + rx, Y + ry, alfa=alfa * a, **kw)

    # la tarjeta: cristal casi negro (deja ver un poco lo de detrás, pero el texto manda)
    rgbp, a_vid = vidrio(c, X, Y, w, h, L['r'], tinte=(9, 7, 16), opacidad=0.82, desenfoque=34, brillo=0.24)
    colocar(c, L['sombra'], X + w / 2, Y + h / 2 + round(14 * u), alfa=alfa, solo_sombra=True)
    _pegar(c, rgbp, a_vid, X, Y, alfa)

    todo_hecho = B.tramo(t, fines[-1], fines[-1] + 0.5)

    # cabecera
    late = 1 + 0.08 * math.sin(t * 2 * math.pi * 0.9) * (1 - todo_hecho)
    en(L['destello'], L['ico_x'], L['cab_y'], escala=late, giro=math.sin(t * 1.7) * 7 * (1 - todo_hecho))
    en(L['titulo'].capa, *L['titulo_c'])
    en(L['de_n'].capa, *L['de_n_c'])
    _contador(en, L['nums'], L['nums_c'], t, fines, n, 14 * u)

    # la barra en tramos: cada tramo se llena mientras se hace su paso
    BARRA, sw = L['BARRA'], L['seg_w']
    by = L['barra_y'] + BARRA / 2
    for i in range(n):
        sx = L['PX'] + i * (sw + L['hueco'])
        en(L['seg_fondo'], sx + sw / 2, by)
        p = B.tramo(t, inicios[i], fines[i])
        if p >= 1:
            en(L['seg_lleno'], sx + sw / 2, by)
        elif p > 0:
            fw = max(BARRA, sw * p)
            capa = B.caja(fw, BARRA, BARRA / 2, VERDE_CLARO)
            en(capa, sx + capa.width / 2, by, min(1.0, sw * p / BARRA))

    # la franja del paso que toca (con su raya verde a la izquierda): baja de un paso al siguiente
    pos = sum(B.suave(B.tramo(t, fines[i], fines[i] + 0.35)) for i in range(n - 1))
    a_res = B.suave(B.tramo(t, inicios[0] - 0.05, inicios[0] + 0.25)) * (1 - B.suave(B.tramo(t, fines[-1], fines[-1] + 0.30)))
    if a_res > 0.003:
        yr = L['filas_y'] + L['FILA'] * (pos + 0.5)
        en(L['resalte'], w / 2, yr, a_res)
        en(L['raya'], 16 * u + 9 * u, yr, a_res)

    # los pasos
    mono = L['mono']
    for i, f in enumerate(L['filas']):
        activo = B.suave(B.tramo(t, inicios[i], inicios[i] + 0.25))
        hecho = B.suave(B.tramo(t, fines[i], fines[i] + 0.30))
        en(f['nombre'].capa, *f['nombre_c'], 0.42 + 0.58 * activo - 0.06 * hecho)
        _icono_paso(en, L, t, i, L['ico_x'], f['y'], VERDE, BLANCO)

        # el dato: un cursor que late mientras se hace el paso; al marcarse, se escribe letra a letra
        dato = f['dato']
        if not dato:
            continue
        x_cur = f['x_dato']
        a_cur = 0.0
        if t >= fines[i]:
            dt = t - fines[i] - 0.10
            k = 0 if dt <= 0 else min(len(dato), int(dt / ESCRIBE) + 1)
            if k:
                capa = f['trozos'].get(k)
                if capa is None:
                    capa = f['trozos'][k] = Rotulo(dato[:k], 32 * u, None, VERDE_CLARO, fuente=mono)
                en(capa.capa, *capa.centro(f['x_dato'], f['y']))
                x_cur = f['x_dato'] + mono.getlength(dato[:k]) + 4 * u
            fin_escribir = fines[i] + 0.10 + ESCRIBE * len(dato)
            a_cur = 1 - B.suave(B.tramo(t, fin_escribir + 0.05, fin_escribir + 0.30))
        elif activo > 0:
            a_cur = activo * (0.55 + 0.45 * math.cos((t - inicios[i]) * 2 * math.pi * 1.6))
        if a_cur > 0.003:
            en(L['cursor'], x_cur + L['cursor'].width / 2, f['y'], a_cur)

    # al acabar, un brillo cruza la tarjeta en diagonal
    t_brillo = fines[-1] + 0.10
    k = B.tramo(t, t_brillo, max(t_brillo + 0.30, min(t_brillo + 0.70, c.dur - SALIDA)))
    if 0 < k < 1:
        largo = w + 0.35 * h
        centro = -0.15 * largo + B.suave(k) * 1.3 * largo
        brillo = 0.13 * np.exp(-((L['diagonal'] - centro) / (70 * u)) ** 2)[..., None] * a_vid
        _pegar(c, np.repeat(brillo, 3, axis=2), brillo, X, Y, alfa)


# ── Estilo «b» · Notificación: tarjeta clara de teléfono ────────────────────────────────────────────────────────────
def _preparar_b(c):
    u, op = c.u, c.op
    acento = B.color(op.get('color') or '#8B5CF6')
    acento_txt = _mezcla(acento, TINTA, 0.30)                   # el acento algo más oscuro: se lee mejor sobre blanco
    pasos = _pasos(op)
    n = len(pasos)
    L = {'n': n, 'acento': acento}

    w = int(round(960 * u))
    PX, PT, PB = 34 * u, 28 * u, 24 * u
    APP, FILA, ICO, BARRA = 68 * u, 82 * u, 46 * u, 10 * u
    cab_y = PT + APP / 2
    barra_y = PT + APP + 20 * u
    filas_y = barra_y + BARRA + 12 * u
    h = int(round(filas_y + n * FILA + PB))
    r = 46 * u
    L.update(w=w, h=h, r=r, PX=PX, FILA=FILA, ICO=ICO, BARRA=BARRA, cab_y=cab_y, barra_y=barra_y, filas_y=filas_y)
    L['x'], L['y'] = _lugar(c, w, h)

    # cabecera: el icono de app, el título oscuro y el contador gris a la derecha (donde un aviso pone la hora)
    L['app'] = icono_app(APP, acento)
    L['app_x'] = PX + APP / 2
    L['de_n'] = Rotulo(f' de {n}', 30 * u, 'medium', GRIS)
    L['nums'] = [Rotulo(str(k), 30 * u, 'bold', TINTA) for k in range(1, n + 1)]
    titulo = str(op.get('titulo') or '')
    x_tit = PX + APP + 20 * u
    libre = w - PX - x_tit - L['de_n'].ancho - L['nums'][-1].ancho - 24 * u
    L['titulo'] = Rotulo(titulo, tam_que_cabe(titulo, 'bold', 42 * u, libre), 'bold', TINTA)
    L['titulo_c'] = L['titulo'].centro(x_tit, cab_y)
    L['de_n_c'] = L['de_n'].centro(w - PX, cab_y, 'der')
    x_num = w - PX - L['de_n'].ancho
    L['nums_c'] = [rt.centro(x_num, cab_y, 'der') for rt in L['nums']]

    # la barra de progreso
    L['barra_w'] = w - 2 * PX
    L['barra_fondo'] = B.caja(L['barra_w'], BARRA, BARRA / 2, (237, 233, 254, 255))

    # filas
    L['giro'] = icono_giro(ICO, u, acento, aro=(229, 223, 244, 255), grosor=4.0)
    L['aro'] = icono_aro(ICO, u, (200, 193, 218, 255), 3.0)
    L['marca_llena'] = icono_marca(ICO, 1.0, VERDE, BLANCO, 0.21)
    L['marcas_cache'] = {}
    L['onda'] = icono_onda(ICO * 1.9, u, VERDE, 2.4)
    L['resalte'] = B.caja(w - 2 * 14 * u, FILA - 8 * u, 22 * u, acento[:3] + (30,))
    filas = []
    for i, (nombre, dato) in enumerate(pasos):
        yc = filas_y + FILA * (i + 0.5)
        rd = Rotulo(dato, 30 * u, 'medium', acento_txt) if dato else None
        libre = w - 2 * PX - ICO - 22 * u - (rd.ancho + 24 * u if rd else 0)
        rn = Rotulo(nombre, tam_que_cabe(nombre, 'bold', 42 * u, libre), 'bold', TINTA)
        filas.append({'y': yc, 'nombre': rn, 'nombre_c': rn.centro(PX + ICO + 22 * u, yc),
                      'dato': rd, 'dato_c': rd.centro(w - PX, yc, 'der') if rd else None})
    L['filas'] = filas
    L['ico_x'] = PX + ICO / 2
    L['inicios'], L['fines'] = _tiempos(c.dur, n, _numeros(op.get('marcas')))
    L['sombra'] = sombra_de(w, h, r, 34 * u, 130)
    return L


def _dibujar_b(c, L):
    u, t = c.u, c.t
    alfa = B.suave(B.tramo(t, 0, ENTRADA * 0.8)) * B.suave(B.tramo(c.queda, 0, SALIDA))
    if alfa <= 0.003:
        return
    sube = (1 - B.rebote(B.tramo(t, 0, 0.50), 1.3)) * 110 * u   # sube con un rebote corto, como un aviso
    X, Y = L['x'], L['y'] + sube
    w, h, n = L['w'], L['h'], L['n']
    inicios, fines = L['inicios'], L['fines']

    def en(capa, rx, ry, a=1.0, **kw):
        colocar(c, capa, X + rx, Y + ry, alfa=alfa * a, **kw)

    # la tarjeta: cristal blanco (se adivina un poco lo de detrás)
    rgbp, a_vid = vidrio(c, X, Y, w, h, L['r'], tinte=(255, 255, 255), opacidad=0.93, desenfoque=40, brillo=0.6)
    colocar(c, L['sombra'], X + w / 2, Y + h / 2 + round(16 * u), alfa=alfa, solo_sombra=True)
    _pegar(c, rgbp, a_vid, X, Y, alfa)

    todo_hecho = B.suave(B.tramo(t, fines[-1], fines[-1] + 0.45))

    # cabecera
    en(L['app'], L['app_x'], L['cab_y'])
    en(L['titulo'].capa, *L['titulo_c'])
    en(L['de_n'].capa, *L['de_n_c'])
    _contador(en, L['nums'], L['nums_c'], t, fines, n, 12 * u)

    # la barra: se llena seguida y, al acabar, se pone verde
    prog = sum(B.tramo(t, inicios[i], fines[i]) for i in range(n)) / n
    bw, BARRA = L['barra_w'], L['BARRA']
    by = L['barra_y'] + BARRA / 2
    en(L['barra_fondo'], L['PX'] + bw / 2, by)
    fw = bw * prog
    if fw > 0.5 * u:
        capa = B.caja(max(BARRA, fw), BARRA, BARRA / 2, _mezcla(L['acento'], VERDE, todo_hecho))
        en(capa, L['PX'] + capa.width / 2, by, min(1.0, fw / BARRA))

    # la franja del paso que toca
    pos = sum(B.suave(B.tramo(t, fines[i], fines[i] + 0.35)) for i in range(n - 1))
    a_res = B.suave(B.tramo(t, inicios[0] - 0.05, inicios[0] + 0.25)) * (1 - todo_hecho)
    if a_res > 0.003:
        en(L['resalte'], w / 2, L['filas_y'] + L['FILA'] * (pos + 0.5), a_res)

    # los pasos
    for i, f in enumerate(L['filas']):
        activo = B.suave(B.tramo(t, inicios[i], inicios[i] + 0.25))
        en(f['nombre'].capa, *f['nombre_c'], 0.38 + 0.62 * activo)
        if f['dato'] is not None:
            en(f['dato'].capa, *f['dato_c'], 0.40 + 0.60 * activo)
        _icono_paso(en, L, t, i, L['ico_x'], f['y'], VERDE, BLANCO)


# ── Estilo «c» · Progreso: cabecera de color con el porcentaje y una pastilla por paso ──────────────────────────────
def _preparar_c(c):
    u, op = c.u, c.op
    acento = B.color(op.get('color') or '#8B5CF6')
    oscuro = _mezcla(acento, OSCURO, 0.8)
    pasos = _pasos(op)
    n = len(pasos)
    L = {'n': n, 'acento': acento}

    w = int(round(960 * u))
    PX = 36 * u
    CAB, PIL, HUECO, ICO, BARRA = 150 * u, 80 * u, 12 * u, 46 * u, 16 * u
    filas_y = CAB + 16 * u
    h = int(round(filas_y + n * PIL + (n - 1) * HUECO))
    L.update(w=w, h=h, PX=PX, CAB=CAB, PIL=PIL, HUECO=HUECO, ICO=ICO, BARRA=BARRA, filas_y=filas_y)
    L['x'], L['y'] = _lugar(c, w, h)

    # la cabecera: degradado de color, destello, título y el porcentaje grande; debajo, la barra gruesa
    L['cab'] = _degradado(w, CAB, 38 * u, _mezcla(acento, BLANCO, 0.08), oscuro)
    L['cab_sombra'] = sombra_de(w, CAB, 38 * u, 22 * u, 110)
    tit_y = 60 * u
    L['tit_y'] = tit_y
    L['destello'] = icono_destello(40 * u, BLANCO)
    L['destello_x'] = PX + 20 * u
    pct_tam = 64 * u
    L['pct_tam'] = pct_tam
    L['pcts'] = {}
    titulo = str(op.get('titulo') or '')
    x_tit = PX + 40 * u + 14 * u
    libre = w - PX - x_tit - B.fuente('extrabold', pct_tam).getlength('100%') - 24 * u
    L['titulo'] = Rotulo(titulo, tam_que_cabe(titulo, 'extrabold', 42 * u, libre), 'extrabold', BLANCO)
    L['titulo_c'] = L['titulo'].centro(x_tit, tit_y)
    L['barra_y'] = 116 * u
    L['barra_w'] = w - 2 * PX
    L['barra_fondo'] = B.caja(L['barra_w'], BARRA, BARRA / 2, (20, 6, 48, 120))
    L['punta'] = icono_brillo(BARRA * 3.2, (255, 255, 255), 0.85)

    # las pastillas
    L['pil_base'] = B.caja(w, PIL, PIL / 2, (22, 12, 48, 232), borde=(255, 255, 255, 30), grosor=1.5 * u)
    L['pil_sombra'] = sombra_de(w, PIL, PIL / 2, 16 * u, 80)
    lleno = _degradado(w, PIL, PIL / 2, acento, oscuro, diagonal=0.15)
    L['pil_lleno'] = _premult(lleno)
    L['pil_lleno_capa'] = lleno
    L['pil_flash'] = B.caja(w, PIL, PIL / 2, BLANCO)
    L['pil_punta'] = icono_brillo(PIL * 0.9, (255, 255, 255), 0.40)
    L['giro'] = icono_giro(ICO, u, BLANCO, aro=(255, 255, 255, 55), grosor=4.0)
    L['aro'] = icono_aro(ICO, u, (255, 255, 255, 110), 3.0)
    L['marca_llena'] = icono_marca(ICO, 1.0, BLANCO, oscuro, 0.21)
    L['oscuro'] = oscuro
    L['marcas_cache'] = {}
    L['onda'] = icono_onda(ICO * 1.9, u, BLANCO, 2.4)
    L['ico_x'] = PIL / 2
    filas = []
    for i, (nombre, dato) in enumerate(pasos):
        top = filas_y + i * (PIL + HUECO)
        rd = Rotulo(dato, 30 * u, 'medium', LILA) if dato else None
        x_nom = PIL / 2 + ICO / 2 + 20 * u
        libre = w - PX - x_nom - (rd.ancho + 24 * u if rd else 0)
        rn = Rotulo(nombre, tam_que_cabe(nombre, 'bold', 42 * u, libre), 'bold', BLANCO)
        filas.append({'top': top, 'nombre': rn, 'nombre_c': rn.centro(x_nom, PIL / 2),       # (dentro de su pastilla)
                      'dato': rd, 'dato_c': rd.centro(w - PX, PIL / 2, 'der') if rd else None})
    L['filas'] = filas
    L['inicios'], L['fines'] = _tiempos(c.dur, n, _numeros(op.get('marcas')))
    return L


def _pct(L, k):
    capa = L['pcts'].get(k)
    if capa is None:
        capa = L['pcts'][k] = Rotulo(f'{k}%', L['pct_tam'], 'extrabold', BLANCO)
    return capa


def _dibujar_c(c, L):
    u, t = c.u, c.t
    fuera = B.suave(B.tramo(c.queda, 0, SALIDA))
    if fuera <= 0.003 or t <= 0:
        return
    X, Y0 = L['x'], L['y']
    w, n, PIL = L['w'], L['n'], L['PIL']
    inicios, fines = L['inicios'], L['fines']
    todo_hecho = B.suave(B.tramo(t, fines[-1], fines[-1] + 0.45))

    def entrada(j):
        """Cuánto ha entrado la pieza j (0 = la cabecera; 1… = las pastillas): entran en cascada, subiendo."""
        d = 0.06 * j
        return B.suave(B.tramo(t, d, d + 0.30)), (1 - B.sale(B.tramo(t, d, d + 0.42))) * 50 * u

    # primero todas las sombras (si no, la sombra de cada pastilla oscurece el borde de abajo de la anterior)
    piezas = []
    for j in range(n + 1):
        aj, dy = entrada(j)
        piezas.append((aj * fuera, dy))
    for j, (aj, dy) in enumerate(piezas):
        if aj > 0.003:
            if j == 0:
                colocar(c, L['cab_sombra'], X + w / 2, Y0 + dy + L['CAB'] / 2 + round(12 * u), alfa=aj, solo_sombra=True)
            else:
                top = L['filas'][j - 1]['top']
                colocar(c, L['pil_sombra'], X + w / 2, Y0 + top + dy + PIL / 2 + round(8 * u), alfa=aj, solo_sombra=True)

    # la cabecera
    a0, dy0 = piezas[0]
    if a0 > 0.003:
        Y = Y0 + dy0

        def en(capa, rx, ry, a=1.0, **kw):
            colocar(c, capa, X + rx, Y + ry, alfa=a0 * a, **kw)

        en(L['cab'], w / 2, L['CAB'] / 2)
        late = 1 + 0.08 * math.sin(t * 2 * math.pi * 0.9) * (1 - todo_hecho)
        en(L['destello'], L['destello_x'], L['tit_y'], escala=late, giro=math.sin(t * 1.7) * 7 * (1 - todo_hecho))
        en(L['titulo'].capa, *L['titulo_c'])
        prog = sum(B.tramo(t, inicios[i], fines[i]) for i in range(n)) / n
        pct = _pct(L, int(round(prog * 100)))
        en(pct.capa, *pct.centro(w - L['PX'], L['tit_y'], 'der'))
        # la barra gruesa, con un brillo en la punta mientras avanza; al acabar, verde
        bw, BARRA = L['barra_w'], L['BARRA']
        by = L['barra_y']
        en(L['barra_fondo'], L['PX'] + bw / 2, by)
        fw = bw * prog
        if fw > 0.5 * u:
            capa = B.caja(max(BARRA, fw), BARRA, BARRA / 2, _mezcla(BLANCO, VERDE_CLARO, todo_hecho))
            en(capa, L['PX'] + capa.width / 2, by, min(1.0, fw / BARRA))
            if prog < 1:
                en(L['punta'], L['PX'] + max(BARRA, fw) - BARRA / 2, by, min(1.0, fw / (2 * BARRA)))

    # las pastillas
    rgb_lleno, a_lleno = L['pil_lleno']
    for i, f in enumerate(L['filas']):
        aj, dy = piezas[i + 1]
        if aj <= 0.003:
            continue
        Y = Y0 + f['top'] + dy

        def en(capa, rx, ry, a=1.0, **kw):
            colocar(c, capa, X + rx, Y + ry, alfa=aj * a, **kw)

        en(L['pil_base'], w / 2, PIL / 2)
        # el color se llena de izquierda a derecha mientras se hace el paso
        p = B.tramo(t, inicios[i], fines[i])
        if p > 0:
            fw = int(round(PIL + (w - PIL) * p))
            if fw >= w:
                en(L['pil_lleno_capa'], w / 2, PIL / 2)
            else:
                m = np.asarray(B.caja(fw, PIL, PIL / 2, BLANCO).split()[3], np.float32)[..., None] / 255.0
                _pegar(c, rgb_lleno[:, :fw] * m, a_lleno[:, :fw] * m, X, Y, aj * min(1.0, p * 12))
                en(L['pil_punta'], fw - PIL / 2, PIL / 2, min(1.0, p * 6))
        if t >= fines[i]:                                       # un destello claro al llenarse
            dt = t - fines[i]
            if dt < 0.45:                                       # sube en 0,08 s (nada de golpe) y se apaga
                en(L['pil_flash'], w / 2, PIL / 2, 0.24 * B.suave(B.tramo(dt, 0, 0.08)) * (1 - B.sale(B.tramo(dt, 0.08, 0.45))))
        activo = B.suave(B.tramo(t, inicios[i], inicios[i] + 0.25))
        en(f['nombre'].capa, *f['nombre_c'], 0.55 + 0.45 * activo)
        if f['dato'] is not None:
            en(f['dato'].capa, *f['dato_c'], 0.40 + 0.60 * activo)
        _icono_paso(en, L, t, i, L['ico_x'], PIL / 2, BLANCO, L['oscuro'])


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
ESTILOS = {
    'actual': (_preparar_actual, _dibujar_actual),
    'b': (_preparar_b, _dibujar_b),
    'c': (_preparar_c, _dibujar_c),
}
NOMBRES = {'notificacion': 'b', 'notificación': 'b', 'aviso': 'b', 'progreso': 'c', 'color': 'c',
           'cristal': 'actual', '': 'b'}


def dibujar(c):
    L = c.estado.get('lista')
    if L is None:
        estilo = str(c.op.get('estilo') or '').strip().lower()
        estilo = NOMBRES.get(estilo, estilo)
        preparar, pintar = ESTILOS.get(estilo, ESTILOS['b'])
        L = preparar(c)
        L['pintar'] = pintar
        c.estado['lista'] = L
    L['pintar'](c, L)
