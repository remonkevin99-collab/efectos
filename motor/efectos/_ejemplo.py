"""Ejemplo de cómo se escribe un efecto (no cuenta como efecto: empieza por «_»).

Una etiqueta en forma de pastilla que aparece junto a la cara con un rebote, flota un poco y se va con un fundido.
    Para probarlo, cópialo con otro nombre (sin «_» delante) y:
    .venv/bin/python efectos.py <su nombre> tu_video.mp4 --fotos 0.2,0.8,1.6
"""
import math

import base as B

NOMBRE = '_ejemplo'
DESCRIPCION = 'Una etiqueta que aparece junto a tu cara'
OPCIONES = {'texto': 'Hola', 'color': '#8B5CF6'}
DURACION = 2.0


def dibujar(c):
    u = c.u
    cx, cy, ancho = c.cara
    if 'pastilla' not in c.estado:                       # lo que no cambia, se hace una vez
        t = B.texto(c.op['texto'], 54 * u, 'bold')
        fondo = B.caja(t.width + 40 * u, t.height + 6 * u, (t.height + 6 * u) / 2, B.color(c.op['color']))
        fondo.alpha_composite(t, (int((fondo.width - t.width) / 2), int((fondo.height - t.height) / 2)))
        c.estado['pastilla'] = B.con_sombra(fondo, 14 * u, 8 * u, 110)
    entra = B.rebote(B.tramo(c.t, 0, 0.45))              # aterriza con un rebote corto
    flota = math.sin(c.t * 2.2) * 6 * u                  # sube y baja unos píxeles para que no parezca pegada
    x = cx + ancho * 1.25
    y = cy - ancho * 0.2 + flota
    B.poner(c, c.estado['pastilla'], x, y, escala=0.6 + 0.4 * entra, giro=-4, alfa=B.fundido(c, 0.2, 0.3))
