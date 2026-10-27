"""grafico: la pantalla se divide. Arriba baja un gráfico de barras con tus números y abajo quedas tú en una tarjeta con
las esquinas redondas; tu cabeza sale por encima del corte y queda delante del gráfico.

El panel es oscuro (índigo y violeta con luces magenta, una cuadrícula muy tenue y un brillo de cristal). Las barras
crecen una detrás de otra, con un degradado de violeta a rosa, y el número grande de encima va contando mientras suben.
Una barra va destacada en dorado, con un halo y una insignia encima que la señala. Si una barra es mucho más alta que las
demás, las pequeñas se quedan con un mínimo para que se vean, y con su número. Al empezar, el cuadro se encoge y baja
hasta la tarjeta mientras el gráfico baja desde arriba; al acabar, lo mismo al revés.

LOS DATOS DE FÁBRICA SON DE EJEMPLO: cámbialos por tus números de verdad (`datos`). Nunca publiques un gráfico con cifras
inventadas.

    .venv/bin/python efectos.py grafico tu_video.mp4 --fotos 0.2,1.5,3.3
    .venv/bin/python efectos.py grafico tu_video.mp4 --op "datos=A mano:180|Con plantillas:40|Ahora:5"
    .venv/bin/python efectos.py grafico tu_video.mp4 --op "titulo=Mis {n} Reels / más vistos" --op unidad= \\
        --op "datos=Tesla:1043688|Historia:121205|La Fed:9855" --op destacar=0 --op "insignia=el mejor"
"""
from efectos import _dividida as D

NOMBRE = 'grafico'
DESCRIPCION = 'Tus números en un gráfico de barras encima de ti: la pantalla se divide y tu cabeza sale del corte'
OPCIONES = {
    # lo de antes de «/» va en la primera línea, en blanco; lo de después, en la segunda, en color y subrayado.
    # {n} = cuántas barras hay
    'titulo': '¿Cuánto tardo en / editar un Reel?',
    # cada barra, «etiqueta:número», separadas por «|». DE EJEMPLO: pon tus números de verdad
    'datos': 'A mano:180|Con Claude:30',
    # «min»: los números son minutos y se escriben como se leen («4 h», «1 h 30 min», «45 min», «30 s»);
    # vacío: números sueltos («1 M», «243 mil», «850»)
    'unidad': 'min',
    # qué barra va destacada: «ultima», «menor», «mayor», un número (0 = la primera) o «ninguna»
    'destacar': 'ultima',
    # el texto de la insignia encima de la destacada (vacío = sin insignia)
    'insignia': 'el más rápido',
    # el degradado de las barras, «abajo,arriba» (o un solo color)
    'color': '#6D28D9,#EC4899',
    # el degradado de la destacada
    'color_destacado': '#F97316,#FDE68A',
    **D.COMUNES,
}
DURACION = 3.5


def dibujar(c):
    D.dibujar(c, 'grafico')
