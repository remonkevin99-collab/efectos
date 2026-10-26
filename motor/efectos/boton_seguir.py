"""Botón de seguir: aparece un botón de «Seguir» junto a la cara, entra un puntero, lo pulsa y pasa a «Siguiendo».

El botón es una pastilla del color de acento con un «+» y el texto. Sale con un rebote al lado de la cara (del lado donde
hay más sitio), un puntero dibujado por nosotros entra en curva y lo pulsa (el botón se hunde un poco), el botón se
estira a «Siguiendo» en gris con una marca y un pequeño destello lo rodea. Al final se va con un fundido.

    .venv/bin/python efectos.py boton-seguir tu_video.mp4 --fotos 0.2,0.9,1.45,1.6,2.0,2.8

"""
import math

from PIL import Image, ImageDraw

import base as B

NOMBRE = 'boton-seguir'
DESCRIPCION = 'Un botón de seguir junto a tu cara que alguien pulsa'
OPCIONES = {
    'texto': 'Seguir',              # el texto del botón antes de pulsarlo
    'texto_hecho': 'Siguiendo',     # el texto después de pulsarlo
    'color': '#8B5CF6',             # el color del botón (y del destello)
    'momento': 'mitad',             # el segundo de la pulsación (mitad = a la mitad del efecto)
    'lado': 'auto',                 # izquierda, derecha o auto (el lado de la cara con más sitio)
}
DURACION = 3.0

GRIS = (64, 64, 74, 255)            # el botón ya pulsado
BLANCO = (255, 255, 255, 255)


# ── Dibujos pequeños (se hacen a 4× y se reducen, para que los bordes salgan limpios) ────────────────────────────────
def _mas(tam, grosor, col):
    """Un «+» de palos redondeados."""
    k = 4
    s, g = int(round(tam * k)), grosor * k
    capa = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.rounded_rectangle([0, s / 2 - g / 2, s - 1, s / 2 + g / 2], radius=g / 2, fill=col)
    d.rounded_rectangle([s / 2 - g / 2, 0, s / 2 + g / 2, s - 1], radius=g / 2, fill=col)
    return capa.resize((max(1, int(round(tam))),) * 2, Image.LANCZOS)


def _marca(tam, grosor, col):
    """Una marca de «hecho» (✓) de trazo redondeado."""
    k = 4
    s, g = int(round(tam * k)), int(round(grosor * k))
    capa = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    pts = [(s * 0.10, s * 0.54), (s * 0.38, s * 0.80), (s * 0.90, s * 0.22)]
    d.line(pts, fill=col, width=g, joint='curve')
    for x, y in (pts[0], pts[-1]):                                      # puntas redondas
        d.ellipse([x - g / 2, y - g / 2, x + g / 2, y + g / 2], fill=col)
    return capa.resize((max(1, int(round(tam))),) * 2, Image.LANCZOS)


def _puntero(alto, u):
    """Un puntero propio: una punta de flecha con una muesca atrás, blanca con borde oscuro y sombra suave. Devuelve la
    capa y dónde queda la punta (x, y) dentro de ella."""
    k = 4
    a = alto * k
    borde = 4.5 * u * k
    m = borde + 4 * k                                                   # margen para el borde
    pts = [(0, 0), (0.80 * a, 0.36 * a), (0.42 * a, 0.47 * a), (0.30 * a, 0.86 * a)]   # punta, ala, muesca, ala
    pts = [(x + m, y + m) for x, y in pts]
    w, h = int(0.80 * a + 2 * m), int(0.86 * a + 2 * m)
    capa = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.line(pts + [pts[0], pts[1]], fill=(28, 21, 55, 255), width=int(borde * 2), joint='curve')
    for x, y in pts:
        d.ellipse([x - borde, y - borde, x + borde, y + borde], fill=(28, 21, 55, 255))
    d.polygon(pts, fill=BLANCO)
    capa = capa.resize((max(1, w // k), max(1, h // k)), Image.LANCZOS)
    punta = (m / k, m / k)
    pad = int(9 * u * 2 + 6 * u)                                        # el aire que añade con_sombra
    return B.con_sombra(capa, 9 * u, 6 * u, 120), (punta[0] + pad, punta[1] + pad)


def _escribir(capa, s, tam, peso, x, y_centro, col):
    """Escribe con las mayúsculas centradas en y_centro (así el texto queda en el centro del botón)."""
    f = B.fuente(peso, tam)
    alto_mayus = -f.getbbox('H', anchor='ls')[1]
    ImageDraw.Draw(capa).text((x, y_centro + alto_mayus / 2), s, font=f, fill=col, anchor='ls')


# ── El botón ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _medidas(c):
    u = c.u
    alto = 112 * u
    tam_letra = 48 * u
    icono = 34 * u
    hueco = 16 * u
    lado = 46 * u
    f = B.fuente('bold', tam_letra)
    w1 = lado * 2 + icono + hueco + f.getlength(c.op.get('texto', 'Seguir'))
    w2 = lado * 2 + icono + hueco + f.getlength(c.op.get('texto_hecho', 'Siguiendo'))
    return dict(alto=alto, tam=tam_letra, icono=icono, hueco=hueco, lado=lado, w1=w1, w2=w2)


def _boton(c, w, fondo, k_viejo, k_nuevo, k_marca):
    """El botón con ancho w y color de fondo `fondo`, con el contenido de antes (k_viejo) y el de después (k_nuevo)."""
    e = c.estado
    md = e['md']
    h = md['alto']
    capa = B.caja(w, h, h / 2, fondo)
    yc = capa.height / 2
    for k, icono, s in ((k_viejo, e['mas'], c.op.get('texto', 'Seguir')),
                        (k_nuevo, e['marca'], c.op.get('texto_hecho', 'Siguiendo'))):
        if k <= 0.01:
            continue
        contenido = Image.new('RGBA', capa.size, (0, 0, 0, 0))
        x = md['lado']
        ic = icono
        if icono is e['marca'] and k_marca < 0.999:                     # la marca entra creciendo
            lado_ic = max(1, int(round(icono.width * (0.4 + 0.6 * k_marca))))
            ic = icono.resize((lado_ic, lado_ic), Image.LANCZOS)
        contenido.alpha_composite(ic, (int(round(x + (md['icono'] - ic.width) / 2)), int(round(yc - ic.height / 2))))
        _escribir(contenido, s, md['tam'], 'bold', x + md['icono'] + md['hueco'], yc, BLANCO)
        if k < 0.999:
            a = contenido.split()[3].point(lambda v, k=k: int(v * k))
            contenido.putalpha(a)
        capa.alpha_composite(contenido)
    return capa


def _preparar(c):
    u = c.u
    e = c.estado
    md = _medidas(c)
    e['md'] = md
    e['mas'] = _mas(md['icono'] * 0.86, 7 * u, BLANCO)
    e['marca'] = _marca(md['icono'], 7 * u, BLANCO)
    e['acento'] = B.color(c.op.get('color', '#8B5CF6'))
    cx, cy, ancho = c.cara
    izq, der = B.zona_segura(c)
    hueco_cara = 0.72 * ancho + 40 * u                                   # del centro de la cara al botón
    sitio_der = der - (cx + hueco_cara)
    sitio_izq = (cx - hueco_cara) - izq
    lado = (c.op.get('lado', 'auto') or 'auto').strip().lower()
    if lado not in ('izquierda', 'derecha'):
        lado = 'derecha' if sitio_der >= sitio_izq else 'izquierda'
    sitio = sitio_der if lado == 'derecha' else sitio_izq
    e['escala'] = max(0.55, min(1.0, sitio / max(md['w1'], md['w2'])))  # si no cabe, el botón se achica
    e['derecha'] = lado == 'derecha'
    e['pos'] = None                                                     # dónde está el botón (sigue a la cara, suave)
    e['puntero'], e['punta'] = _puntero(80 * u, u)
    e['listo'] = True


def _seguir_cara(c):
    """Dónde va el botón en este cuadro: el borde que da a la cara (el ancla) y la altura. Sigue a la cara despacio (como
    un muelle blando), para que la persona no se le acerque al moverse y para que nada tiemble."""
    e = c.estado
    u = c.u
    cx, cy, ancho = c.cara
    izq, der = B.zona_segura(c)
    hueco = 0.72 * ancho + 40 * u
    w2 = max(e['md']['w1'], e['md']['w2']) * e['escala']
    if e['derecha']:
        ancla = min(cx + hueco, der - w2)
    else:
        ancla = max(cx - hueco, izq + w2)
    objetivo = (ancla, cy + 0.05 * ancho)
    antes = e.get('pos')
    t_antes = e.get('t_pos')
    paso = 1.0 / max(1.0, c.fps)
    if antes is None or t_antes is None or abs(c.t - t_antes - paso) > 0.5 * paso:
        pos = objetivo                                                  # primer cuadro (o un salto): sin muelle
    else:
        k = 1 - math.exp(-paso / 0.35)                                  # tarda ~1/3 s en alcanzar a la cara
        pos = (antes[0] + (objetivo[0] - antes[0]) * k, antes[1] + (objetivo[1] - antes[1]) * k)
    e['pos'], e['t_pos'] = pos, c.t
    return pos


def _momento(c):
    m = str(c.op.get('momento', 'mitad') or 'mitad').strip().lower()
    try:
        m = float(m.replace(',', '.'))
    except ValueError:
        m = c.dur / 2
    return min(max(m, min(1.0, c.dur * 0.35)), max(1.0, c.dur - 0.9))


def _destello(c, cx, cy, w, h, k, col, signo):
    """El destello cuando se pulsa (k de 0 a 1): un aro con la forma del botón que se abre y se apaga, y rayitas que
    salen del borde del botón hacia fuera (unas blancas y otras del color de acento)."""
    if k <= 0 or k >= 1:
        return
    u = c.u
    e = c.estado
    claro = tuple(int(B.mezclar(v, 255, 0.45)) for v in col[:3]) + (255,)
    # el aro: la silueta del botón, cada vez más grande y más fina
    k_aro = min(1.0, k / 0.75)
    if k_aro < 1:                                                      # se dibuja una vez y luego solo se agranda
        if 'aro' not in e:
            d0 = 6 * u
            e['aro'] = B.caja(w + 2 * d0, h + 2 * d0, (h + 2 * d0) / 2, (0, 0, 0, 0), borde=claro, grosor=5 * u)
        crece = 1 + (52 * u / e['aro'].width) * 1.6 * B.sale(k_aro)
        B.poner(c, e['aro'], cx, cy, escala=crece, alfa=0.9 * (1 - B.sale(k_aro)) * min(1, k_aro * 8))
    # las rayitas, apuntando hacia fuera del borde del botón (una pastilla: dos medios círculos y dos lados rectos)
    if 'rayas' not in e:
        e['rayas'] = [B.caja(36 * u, 9 * u, 4.5 * u, (255, 255, 255, 255)), B.caja(36 * u, 9 * u, 4.5 * u, claro)]
    a = max(0.0, w / 2 - h / 2)                                        # dónde empiezan los medios círculos
    r = h / 2
    sale = B.sale(k)
    dist = (18 + 52 * sale) * u
    sitios = []
    for ang in (-62, -22, 22, 62):                                     # el medio círculo de fuera (no el de la cara)
        th = math.radians(ang)
        sitios.append((signo * (a + (r + dist) * math.cos(th)), (r + dist) * math.sin(th),
                       th if signo > 0 else math.pi - th))
    for fx in (-0.1, 0.55):                                            # los lados de arriba y de abajo
        fx *= signo
        for arriba in (True, False):
            th = math.atan2(-1 if arriba else 1, fx * 0.9)
            sitios.append((fx * a + math.cos(th) * dist * 0.45, (-1 if arriba else 1) * (r + dist), th))
    alfa = (1 - B.entra(k)) * min(1.0, k * 7)
    largo = 1.0 - 0.6 * k
    for n, (x, y, th) in enumerate(sitios):
        B.poner(c, e['rayas'][n % 2], cx + x, cy + y, escala=largo, giro=math.degrees(th), alfa=alfa)


# ── Cada cuadro ─────────────────────────────────────────────────────────────────────────────────────────────────────
def dibujar(c):
    e = c.estado
    if not e.get('listo'):
        _preparar(c)
    u = c.u
    t = c.t
    md = e['md']
    esc = e['escala']
    m = _momento(c)
    signo = 1 if e['derecha'] else -1

    # el cambio de «Seguir» a «Siguiendo» (0,2 s desde la pulsación): el botón se estira y se vuelve gris; lo de antes
    # se va mientras se estira, y lo nuevo entra cuando ya cabe (así ninguna letra queda cortada por el borde)
    k_cambio = B.suave(B.tramo(t, m, m + 0.2))
    w = B.mezclar(md['w1'], md['w2'], k_cambio)
    fondo = tuple(int(round(B.mezclar(a, b, k_cambio))) for a, b in zip(e['acento'], GRIS))
    k_viejo = 1 - B.tramo(t, m + 0.04, m + 0.14)
    k_nuevo = B.tramo(k_cambio, 0.72, 1.0)
    k_marca = B.rebote(B.tramo(t, m + 0.12, m + 0.4), 1.6)
    if k_cambio <= 0:                                                    # lo que no cambia, se guarda hecho
        if 'antes' not in e:
            e['antes'] = B.con_sombra(_boton(c, md['w1'], e['acento'], 1, 0, 0), 16 * u, 9 * u, 110)
        capa = e['antes']
    elif k_cambio >= 1 and k_marca >= 0.999 and t > m + 0.5:
        if 'despues' not in e:
            e['despues'] = B.con_sombra(_boton(c, md['w2'], GRIS, 0, 1, 1), 16 * u, 9 * u, 110)
        capa = e['despues']
    else:
        capa = B.con_sombra(_boton(c, w, fondo, k_viejo, k_nuevo, k_marca), 16 * u, 9 * u, 110)

    # la pulsación: el botón se hunde un poco y vuelve
    k_pulsa = B.tramo(t, m - 0.07, m + 0.05) * (1 - B.suave(B.tramo(t, m + 0.05, m + 0.3)))
    hundir = 1 - 0.07 * B.suave(k_pulsa)
    # aparece con rebote y se va con un fundido
    k_entra = B.rebote(B.tramo(t, 0, 0.5), 1.5)
    k_sale = B.suave(B.tramo(c.queda, 0, 0.4))
    escala = esc * (0.35 + 0.65 * k_entra) * hundir * (0.9 + 0.1 * k_sale)
    alfa = B.tramo(t, 0, 0.2) * k_sale
    ancho_px = w * esc
    ancla, y_boton = _seguir_cara(c)
    bx = ancla + signo * ancho_px / 2                                    # el centro del botón
    by = y_boton + 3 * u * B.suave(k_pulsa)
    B.poner(c, capa, bx, by, escala=escala, alfa=alfa)

    # el destello alrededor del botón ya pulsado
    _destello(c, bx, by, md['w2'] * esc, md['alto'] * esc, B.tramo(t, m + 0.16, m + 0.8), e['acento'], signo)

    # el puntero: entra en curva, pulsa y se va
    k_va = B.sale(B.tramo(t, m - 0.85, m - 0.06))
    k_vuelve = B.suave(B.tramo(t, m + 0.4, m + 0.95))
    alfa_p = B.tramo(t, m - 0.85, m - 0.6) * (1 - B.tramo(t, m + 0.6, m + 0.95)) * k_sale
    if alfa_p > 0:
        destino = (ancla + signo * md['w1'] * esc * 0.58, y_boton + md['alto'] * esc * 0.12)
        inicio = (destino[0] + signo * 230 * u, destino[1] + 340 * u)
        control = (destino[0] + signo * 260 * u, destino[1] + 80 * u)
        s = k_va
        px = (1 - s) ** 2 * inicio[0] + 2 * (1 - s) * s * control[0] + s * s * destino[0]
        py = (1 - s) ** 2 * inicio[1] + 2 * (1 - s) * s * control[1] + s * s * destino[1]
        px += signo * 120 * u * k_vuelve                                 # al irse, baja hacia fuera
        py += 200 * u * k_vuelve
        esc_p = 1 - 0.14 * B.suave(k_pulsa)
        cap = e['puntero']
        tx, ty = e['punta']
        ccx = px + (cap.width / 2 - tx) * esc_p
        ccy = py + (cap.height / 2 - ty) * esc_p
        # el aro del clic, en la punta
        k_aro = B.tramo(t, m - 0.04, m + 0.36)
        if 0 < k_aro < 1:
            r = (12 + 40 * B.sale(k_aro)) * u
            aro = Image.new('RGBA', (int(r * 2 + 8 * u) * 3,) * 2, (0, 0, 0, 0))
            d = ImageDraw.Draw(aro)
            o = aro.width / 2
            d.ellipse([o - r * 3, o - r * 3, o + r * 3, o + r * 3], outline=(255, 255, 255, 255), width=int(5 * u * 3))
            aro = aro.resize((aro.width // 3, aro.height // 3), Image.LANCZOS)
            B.poner(c, aro, px, py, alfa=0.85 * (1 - k_aro) * alfa_p)
        B.poner(c, cap, ccx, ccy, escala=esc_p, alfa=alfa_p)
