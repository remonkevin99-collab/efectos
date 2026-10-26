"""grafico: la pantalla se divide. Arriba baja un gráfico de barras con tus números y abajo quedas tú en una tarjeta con
las esquinas redondas; tu cabeza sale por encima del corte y queda delante del gráfico.

Las barras crecen una detrás de otra y el número de encima va contando («1 M», «243 mil», «9,9 mil»). Una barra va
destacada con otro color y un brillo suave. Si una barra es mucho más alta que las demás, las pequeñas se quedan con un
mínimo para que se vean, y con su número. Al empezar, el cuadro se encoge y baja hasta la tarjeta mientras el gráfico baja
desde arriba; al acabar, lo mismo al revés.

    .venv/bin/python efectos.py grafico tu_video.mp4 --fotos 0.2,1.5,3.3
    .venv/bin/python efectos.py grafico tu_video.mp4 --op "datos=Enero:1200|Febrero:3400|Marzo:9800" --op destacar=2
"""
from efectos import _dividida as D

NOMBRE = 'grafico'
DESCRIPCION = 'Tus números en un gráfico de barras encima de ti: la pantalla se divide y tu cabeza sale del corte'
OPCIONES = {
    # lo de antes de «/» va en la primera línea, gordo; lo de después, en la segunda, fino. {n} = cuántas barras hay
    'titulo': 'Mis {n} Reels / más vistos',
    # cada barra, «etiqueta:número», separadas por «|»
    'datos': 'Tesla:1043688|Tus locuras:242975|Dinero fácil:147302|Historia:121205|Cerebro:19192|Esperar:13206|'
             'La Fed:9855',
    # qué barra va destacada (0 = la primera; -1 = ninguna)
    'destacar': '0',
    'color': '#8B5CF6',
    'color_destacado': '#FACC15',
    **D.COMUNES,
}
DURACION = 3.5


def dibujar(c):
    D.dibujar(c, 'grafico')
