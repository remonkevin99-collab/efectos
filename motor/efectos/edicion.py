"""edicion: la pantalla se divide. Arriba baja un panel oscuro de edición y abajo quedas tú en una tarjeta con las
esquinas redondas; tu cabeza sale por encima del corte y queda delante del panel.

En el panel: el título, una barra con «EDITANDO» (al acabar, «LISTO»), tu clip en pequeño con su código de tiempo, los
pasos que se van marcando uno a uno, las pistas (toma, subtítulos, color y sonido) con un cabezal que avanza, y una barra
de progreso que llega al 100 %. Al empezar, el cuadro se encoge y baja hasta la tarjeta mientras el panel baja desde
arriba; al acabar, lo mismo al revés.

    .venv/bin/python efectos.py edicion tu_video.mp4 --fotos 0.2,1.5,3.3
    .venv/bin/python efectos.py edicion tu_video.mp4 --op "titulo=Así / lo edito" --op "pasos=corte::listo|color::cálido"
"""
from efectos import _dividida as D

NOMBRE = 'edicion'
DESCRIPCION = 'El panel de edición encima de ti: los pasos se marcan, la línea de tiempo avanza y llega al 100 %'
OPCIONES = {
    # lo de antes de «/» va gordo y blanco; lo de después, fino y lila (en la misma línea)
    'titulo': 'Claude / lo edita',
    # cada paso separado por «|»; lo que va tras «::» es el resultado, que sale a la derecha al marcarse
    'pasos': 'corte::sin pausas|subtítulos::palabra a palabra|color::cálido|efectos::13 listos|sonido::golpes suaves',
    # las palabras de las pastillas de la pista de subtítulos, separadas por «|»
    'subtitulos': 'grabo una vez|y el resto|se hace solo',
    # el color de acento (la barra de progreso y el círculo que gira)
    'color': '#8B5CF6',
    **D.COMUNES,
}
DURACION = 3.5


def dibujar(c):
    D.dibujar(c, 'edicion')
