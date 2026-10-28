---
name: efectos
description: Pone efectos de edición a un vídeo vertical de alguien hablando a cámara (tarjetas de cristal a su alrededor, órbita de portadas, gráfico de barras en pantalla dividida, palabra gigante detrás de la cabeza, panel de edición en pantalla dividida, letrero LED, fondo nuevo con botón de seguir, comentario que se escribe solo, lista que se marca sola, línea de tiempo con color de cine, portada de revista, botón de seguir, tier list, sus Reels saliendo del móvil en un carrusel, una gráfica de cristal sobre el hombro, un muro de texto detrás, mensajes que llegan, interruptores que se encienden y caer en el centro de su perfil). Úsala cuando la persona escriba /efectos o te pida uno de estos efectos para su vídeo.
argument-hint: "[efecto] [del segundo X al Y]"
---

# Efectos para tus vídeos

Un motor que le pone efectos a un vídeo vertical de alguien hablando a cámara: cosas que pasan **detrás** de la persona
(su cabeza las tapa), tarjetas y letreros. Todo corre en la computadora de la persona: el vídeo no sale de ella. Su voz y
su audio se quedan igual.

En un Mac (macOS 14 o más nuevo) recorta a la persona con el recorte del propio sistema, más fino en orejas, pelo y dedos
(`--recorte normal` usa el de Windows y Linux).

**La carpeta de esta skill** es la que sale arriba como «Base directory». Todo se corre desde ahí:

- Mac y Linux: `.venv/bin/python efectos.py …`
- Windows: `.venv\Scripts\python.exe efectos.py …`

Aquí lo llamamos `PY efectos.py`.

## Antes de nada (una vez por conversación)

1. `PY efectos.py --comprobar`. Si dice «Todo bien.», sigue.
2. Si no existe `.venv` o algo sale «MAL»: corre la instalación y vuelve a comprobar.
   - Mac y Linux: `bash instalar.sh`
   - Windows: `powershell -ExecutionPolicy Bypass -File instalar.ps1`

   La primera vez tarda unos minutos. Dile a la persona que espere.

## Cómo lo pide la persona

- `/efectos órbita del segundo 2 al 5`
- `/efectos palabra-detrás con la palabra NEGOCIO del 1 al 3, y la lista del 5 al 8`
- O con sus palabras: «ponle la portada al principio», «el comentario cuando digo "comenta"».

## Paso a paso

1. **El vídeo.** Es el que arrastró a la conversación (su ruta). Si no hay ninguno, pídeselo.
   - Si es horizontal, avisa: los efectos están pensados para vertical (9:16).
2. **Qué dice y en qué segundo.** Si habla de palabras («cuando digo…») o no dio segundos, saca la transcripción con
   `PY motor/palabras.py video.mp4`. Deja `video.palabras.json`, con el segundo de cada palabra. Úsala para que cada
   efecto caiga justo en lo que dice y para sacar los textos de lo que cuenta.
3. **El plan.** Escribe `plan.json` al lado del vídeo:
   ```json
   {"efectos": [
     {"efecto": "orbita", "desde": 1.2, "hasta": 4.0, "opciones": {"imagenes": "portadas"}},
     {"efecto": "palabra-detras", "desde": 5, "hasta": 8, "opciones": {"texto": "NEGOCIO"}}
   ]}
   ```
   - Los nombres valen con tilde o sin ella (órbita = orbita).
   - Sin `hasta`, cada efecto dura lo suyo (la tabla de abajo).
   - Que no se pisen dos efectos que ocupan el mismo sitio.
   - **Antes de pintar, pregúntale en UN solo mensaje lo que te falte** para los efectos que pidió (su nombre, su @, los
     números del gráfico, la palabra, los pasos…). Si no contesta algo, quita esa tarjeta (texto vacío): nunca sale «TU
     NOMBRE» ni «@tu_usuario» en su vídeo.
   - **Los textos, de la persona.** Los de fábrica son de ejemplo: cámbialos por lo suyo.
     - `comentario`: `creador` es su cuenta (pregúntasela una vez si no la sabes) y `texto`, la palabra que pide comentar.
     - `lista`: los pasos de lo que explica.
     - `tier-list` y `portada`: su tema. La portada pone sola el mes de hoy (`numero`).
     - `palabra-detras` y `letrero-led`: la palabra clave de lo que dice en ese momento.
     - `orbita`: una carpeta con sus imágenes (sus portadas, sus productos, capturas). Sin carpeta, usa cuadros del
       propio vídeo.
     - `grafico`: sus números de verdad (`datos`). Pregúntaselos; los de fábrica son de ejemplo.
     - `fondo`: su nombre y su cuenta (`nombre`, `usuario`) y su titular (`lineas`).
     - `cristal`: su nombre y su cuenta y lo que cuenta el contador (`numero`, `texto_numero`). El calendario sale con
       la fecha de hoy (`fecha`=hoy) y `evento`; si lo sube otro día, pon ese día (`dia`, `fecha`), o `fecha` vacía y no
       sale.
     - `carrusel` y `cuadricula`: sus portadas (una carpeta) y sus vistas de verdad, en el mismo orden. Sin vistas,
       sin números. En el carrusel, además, dónde está su móvil (`movil`), mirándolo en un cuadro.
     - `sobre-el-hombro`: su número de verdad (`final`) y qué cuenta (`titulo`).
     - `mensajes` e `interruptores`: frases suyas y cortas. `muro`: la palabra que se resalta.
     - Nunca te inventes cifras, nombres o resultados que la persona no te dio.
4. **Revisa antes de hacer el vídeo.** Saca fotos de 2 o 3 momentos de cada efecto: el principio, la mitad y el final.
   ```
   PY efectos.py video.mp4 --plan plan.json --fotos 1.5,2.8,3.9
   ```
   Salen como `video_efectos_1.50s.png`. **Míralas tú** y comprueba:
   - que nada le tape la cara;
   - que los textos se lean enteros y sin faltas;
   - que nada se corte en los bordes (Instagram se come un poco de cada lado al abrir el vídeo).

   Si algo falla, cambia el plan y repite.
5. **El vídeo.**
   ```
   PY efectos.py video.mp4 --plan plan.json
   ```
   - **Cada pedido, su propio archivo**, al lado del original (que nunca se toca): `--salida video_<efecto>.mp4` (con
     varios efectos, sus nombres). Así un `/efectos` nuevo no borra el anterior. Si dice «añádelo al de antes», el vídeo
     de entrada es el último que hiciste.
   - Dile dónde está y que lo mire antes de subirlo.
   - **Sale a 1080 de ancho.** Si su vídeo es 4K, pregúntale si lo quiere en 4K: `--ancho 2160` (tarda unas 4 veces más).
6. **Los cambios, con sus palabras.**
   - «más largo» o «más corto»: mueve `desde` y `hasta`.
   - «otro color»: la opción `color`, en hexadecimal (#FF3B30).
   - «más grande» o «más rápido» en la órbita: `tamano` y `velocidad`; «más separadas»: `radio`; «que se aceleren cuando
     hago el gesto»: `acelera` con el segundo del gesto (míralo en los cuadros).
   - Lo que no tenga opción («más arriba», «la letra más gorda», «el contador más pequeño»): cada efecto es un archivo en
     `motor/efectos/`, con sus medidas comentadas (arriba o en la función de cada tarjeta). Cambia el número, haz fotos
     y dile qué cambiaste. Ese cambio queda para sus vídeos siguientes; antes de actualizar con `git pull`, guárdalo con
     `git stash` (y `git stash pop` después) o se pisará.

## Los 19 efectos

| Efecto | Qué hace | Dura | Opciones (y lo que traen) |
|---|---|---|---|
| `cristal` | 8 tarjetas grandes de cristal a su alrededor, varias por detrás (su cabeza y sus brazos pasan por delante): el número enorme, la barra de exportar, su ficha con su foto, un calendario, lo que se está editando, el anillo 4K, una marca que se dibuja y la pastilla de abajo | 3,5 s | `marca`, `numero`=13, `texto_numero`, `exportando`, `resolucion`=4K, `fps`=30, `nombre`, `usuario`, `dia`, `fecha`=hoy, `evento`, `editando_titulo`, `editando`, `etiqueta`, `pastilla`, `color` (un texto vacío quita su tarjeta) |
| `fondo` | Le cambia el fondo entero: en blanco y negro, con un aro de luz, su titular, su nombre y un botón de Seguir que se pulsa | 3,5 s | `lineas` (`UNO.\|DOS.\|TRES.`), `nombre`, `usuario`, `color`, `boton`=si, `texto`, `texto_hecho`, `momento`, `lado`, `color_persona`=no, `letras`, `techo`=210 (250 si es para la portada) |
| `orbita` | De 3 a 6 tarjetas con fotos giran alrededor de su cabeza: pasan por detrás y por delante, sin taparle la cara; empiezan pegadas y se abren, y si se pide se aceleran en el segundo de un gesto suyo | 4 s | `imagenes` (carpeta), `cantidad`=5, `tamano`=300, `velocidad`=1, `radio`=1.3, `radio_inicio`=1, `acelera` (segundos desde que empieza; vacío = nunca), `acelera_por`=3, `acelera_dura`=1.2 |
| `grafico` | La pantalla se divide: arriba, un gráfico de barras con sus números; abajo, la persona, con la cabeza saliendo del corte | 3,5 s | `titulo` (`primera línea/segunda`), `datos` (`etiqueta:número\|…`), `unidad`=min (minutos: «3 h», «30 min»; vacía = números sueltos), `destacar`=ultima (o menor, mayor, un número, ninguna), `insignia`, `color` y `color_destacado` (`#abajo,#arriba`), `fondo`, `alto`=0.5, `zoom`=auto, `asoma`=120 |
| `letrero-led` | Se apaga la luz y detrás de su cabeza se enciende un letrero de neón, letra a letra | 4 s | `texto`=SIN EDITOR, `color`=#FFA43A, `persona`=0.2 (cuánto se apaga también la persona: 0 = nada) |
| `tier-list` | Una tabla de la S a la F, y lo suyo entra volando hasta su fila | 4,5 s | `titulo`, `filas` (`S:\|A:\|B:cosa, otra\|…`), `elemento`, `fila`=S, `color` |
| `linea-tiempo` | Color de cine cálido, un título y una línea de edición que avanza | 5 s | `titulo`=EDITADO, `subtitulo`, `color` |
| `edicion` | La pantalla se divide: arriba, el panel de edición (pasos que se marcan, línea de tiempo, 100 %); abajo, la persona | 3,5 s | `titulo` (`Claude/lo edita`), `pasos` (`paso::dato\|…`), `subtitulos` (`texto\|texto\|texto`), `color`, `fondo`, `alto`, `zoom`, `asoma` |
| `palabra-detras` | Una palabra gigante detrás de su cabeza | 3 s | `texto`=EFECTOS, `color`=#FFFFFF |
| `comentario` | Alguien comenta una palabra, le dan corazón y llega la respuesta | 6 s | `texto`=EFECTOS, `usuario`, `creador`, `respuesta`, `color` |
| `lista` | Una tarjeta con los pasos de una tarea que se van marcando uno a uno | 6 s | `titulo`, `pasos` (`paso::dato\|paso::dato`), `marcas` (el segundo en que se marca cada paso: `1,2\|2\|3,1`), `color`, `estilo`=notificacion (o progreso, cristal) |
| `portada` | Le convierte en la portada de una revista, con el título detrás de la cabeza | 4 s | `titulo`, `numero`, `lineas` (`grande\|otra\|otra`), `color`, `lado` (izquierda, derecha o auto), `zoom`=1.2 |
| `boton-seguir` | Aparece un botón de Seguir junto a su cara y alguien lo pulsa | 3 s | `texto`=Seguir, `texto_hecho`=Siguiendo, `color`, `momento` (el segundo, o `mitad`), `lado` |
| `carrusel` | Sus Reels salen de la pantalla de su móvil y giran en un carrusel encima de él; el que se pida pasa por delante con su número grande y dorado. Hace falta un plano con el móvil (de pie en la mesa o en la mano quieta, con la pantalla hacia la cámara) | 3 s | `imagenes` (carpeta), `vistas` (`1M\|114K\|…`, en el orden de las imágenes por nombre), `destaca` (el número grande, el de alguna tarjeta: «1M»), `movil` (`x,y` de la pantalla del móvil a 1080×1920: míralo en un cuadro), `ancho_movil`=240, `cantidad`=6, `tamano`=260, `velocidad`=1 |
| `sobre-el-hombro` | La cámara se acerca a su lado y arriba aparece una tarjeta de cristal con su número subiendo y su gráfica de línea dibujándose | 3,5 s | `titulo`=VISTAS, `inicio`=0, `final` («125000», «125K», «1,2M»), `color`, `barras` (`40,65,52,80`; vacía = no sale), `titulo_barras`, `lado`=auto, `zoom`=1.22 |
| `muro` | Detrás de la persona, una página de periódico llena de texto que se desliza, con una palabra resaltada en una caja de color encima de su cabeza | 3 s | `resalta`=Claude, `color`=#E5484D, `texto` (el párrafo del muro) |
| `mensajes` | Le llegan mensajes uno detrás de otro, como las notificaciones del iPhone (el último queda arriba). Queda muy bien sobre un plano del móvil en la mesa | 3 s | `mensajes` (`uno\|otro\|…`), `app`=Mensajes, `hora`=ahora, `intervalo`=0.5, `maximo`=4, `lugar`=auto (arriba, centro o la y), `color` |
| `interruptores` | Encima de su cabeza, una tarjeta de ajustes con interruptores que se encienden uno a uno | 3 s | `lineas` (`Un clip\|Escribo /efectos\|Cero apps de edición`), `color`=#34C759, `cada`=0.45, `detras`=auto |
| `cuadricula` | Se aleja y cae en el centro de su perfil, rodeado de sus Reels con sus vistas | 3 s | `imagenes` (carpeta: sus portadas), `vistas` (`1M\|114K\|…`), `fondo`=oscuro (o claro), `icono`=reproducir (u ojo, o nada), `color`, `alejar`=0.88 |

**Que la mano señale lo que sale**: si la persona señala arriba, a un lado o levanta el pulgar, mira los cuadros y pon
el efecto justo ahí (el gráfico cuando señala arriba, el botón de seguir del lado al que apunta).

`PY efectos.py --lista` enseña los mismos, con sus opciones al día.

## Si te pide subtítulos

No son uno de los 19 efectos, pero se pueden poner sobre el último vídeo que hiciste (o el que diga):
1. Las palabras con su segundo: `PY motor/palabras.py video.mp4`. **Enséñale el texto y que lo corrija** antes de
   quemarlo (los nombres y las palabras raras salen mal a veces). Si sale «No he entendido ninguna palabra», su audio está
   muy bajo: díselo.
2. Quémalos con el ffmpeg del motor (`imageio_ffmpeg.get_ffmpeg_exe()`; el del sistema puede no tener el filtro), filtro
   `subtitles=...:fontsdir=fuentes` (Poppins), el audio igual. Frases cortas, abajo y sin taparle la cara.
3. Una foto antes del vídeo entero.

## Si algo falla

- Los errores salen en español y dicen qué hacer: léelos y arréglalo.
- Si un efecto falla en un cuadro, ese tramo sale sin él y el resto del vídeo se guarda igual. Avisa a la persona.
- **Vídeo en HDR** (el iPhone graba así por defecto): los colores pueden salir lavados. Para la próxima vez:
  Ajustes › Cámara › Formatos › Vídeo HDR, desactivado.
- **El recorte de la persona sale mal** (fondo muy parecido a su ropa, una silla de respaldo alto detrás): elige otro
  tramo o un efecto que vaya delante (lista, comentario, botón de seguir, tier list).

## Un efecto nuevo

Cada efecto es un archivo en `motor/efectos/`. El motor los encuentra solos.

1. Copia `_ejemplo.py` con otro nombre, sin «_» delante (los que empiezan por «_» no cuentan).
2. Cambia `NOMBRE`, `DESCRIPCION`, `OPCIONES` y `DURACION`.
3. Escribe su función `dibujar(c)`, que pinta sobre el cuadro. Las piezas están en `motor/base.py`:
   - texto, cajas, cristal y sombras;
   - `poner(…, detras=True)`, que lo pone detrás de la persona;
   - las curvas de entrada y salida.
4. Pruébalo con `--fotos` antes de hacer el vídeo.
