"""Palabra detrás: una palabra gigante DETRÁS de la cabeza, como el título de una portada de revista: la cabeza tapa la
parte de abajo de las letras que tiene detrás y el resto se lee entero.

La palabra se encaja al ancho de la zona segura (de 60 a 1020 a 1080 de ancho), en Poppins ExtraBold, con una sombra
suave para que se separe de la pared. Entra subiendo desde abajo con un fundido y creciendo un poco (0,4 s), se queda
subiendo muy despacio y se va con un fundido. Se coloca al empezar, según dónde está la cabeza, y ya no la persigue: si la
persona se mueve, la palabra se queda en su sitio, como un decorado.

    python efectos.py palabra-detras mi-video.mp4 --desde 1 --hasta 4 --op texto=HOLA
"""
import base as B

NOMBRE = 'palabra-detras'
DESCRIPCION = 'Una palabra gigante detrás de tu cabeza (tu cabeza tapa parte de las letras), como una portada de revista'
OPCIONES = {'texto': 'EFECTOS', 'color': '#FFFFFF'}
DURACION = 3.0

ENTRA, SALE = 0.4, 0.35
SUBE = 70           # cuánto sube al entrar (a 1080 de ancho)
DERIVA = 9          # lo que sigue subiendo cada segundo, muy despacio
TAPA = 0.45         # qué parte de la altura de las letras queda por debajo de lo alto de la cabeza


def _preparar(c):
    u = c.u
    texto = (c.op.get('texto') or 'EFECTOS').strip()
    izq, der = B.zona_segura(c)
    relleno = B.color(c.op.get('color') or '#FFFFFF')
    # la misma palabra sin sombra, para saber dónde está la tinta (las letras no llenan su capa: hay aire arriba)
    limpia = B.encajar(texto, der - izq, 'extrabold', tam_max=360 * u, relleno=relleno)
    x0, y0, x1, y1 = limpia.getchannel('A').getbbox() or (0, 0, limpia.width, limpia.height)
    alto_tinta = y1 - y0
    capa = B.encajar(texto, der - izq, 'extrabold', tam_max=360 * u, relleno=relleno, sombra=max(2, round(14 * u)),
                     color_sombra=(20, 10, 40, 120))
    # el centro de la tinta respecto al centro de la capa (la capa con sombra tiene más margen, pero centrado igual)
    desfase = (y0 + y1) / 2 - limpia.height / 2
    cx, cy, fw = c.cara
    arriba_cabeza = cy - 1.05 * fw
    centro = arriba_cabeza + (0.5 - TAPA) * alto_tinta          # el centro de la tinta
    centro = max(centro, 170 * u + alto_tinta / 2)              # que no se salga por arriba
    return {'capa': capa, 'x': (izq + der) / 2, 'y': centro - desfase}


def dibujar(c):
    if 'palabra' not in c.estado:
        c.estado['palabra'] = _preparar(c)
    e = c.estado['palabra']
    u = c.u
    ent = B.sale(B.tramo(c.t, 0, ENTRA))
    y = e['y'] + (1 - ent) * SUBE * u - DERIVA * u * c.t
    escala = (0.94 + 0.06 * ent) * (1 + 0.006 * c.t)
    alfa = ent * B.suave(B.tramo(c.queda, 0, SALE))
    B.poner(c, e['capa'], e['x'], y, escala=escala, alfa=alfa, detras=True)
