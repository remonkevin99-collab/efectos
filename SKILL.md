---
name: efectos
description: Pone efectos de edición a un vídeo vertical de alguien hablando a cámara (tarjetas de cristal a su alrededor, órbita de portadas, gráfico de barras en pantalla dividida, palabra gigante detrás de la cabeza, panel de edición en pantalla dividida, letrero LED, fondo nuevo con botón de seguir, comentario que se escribe solo, lista que se marca sola, línea de tiempo con color de cine, portada de revista, botón de seguir y tier list). Úsala cuando la persona escriba /efectos o te pida uno de estos efectos para su vídeo.
argument-hint: "[efecto] [del segundo X al Y]"
---

# Efectos para tus vídeos

Un motor que le pone efectos a un vídeo vertical de alguien hablando a cámara: cosas que pasan **detrás** de la persona
(su cabeza las tapa), tarjetas y letreros. Todo corre en la computadora de la persona: el vídeo no sale de ella. Su voz y
su audio se quedan igual.

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

1. **El vídeo.** Es el que arrastró al chat (su ruta). Si no hay ninguno, pídeselo.
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
   - **Los textos, de la persona.** Los de fábrica son de ejemplo: cámbialos por lo suyo.
     - `comentario`: `creador` es su cuenta (pregúntasela una vez si no la sabes) y `texto`, la palabra que pide comentar.
     - `lista`: los pasos de lo que explica.
     - `tier-list` y `portada`: su tema.
     - `orbita`: una carpeta con sus imágenes (sus portadas, sus productos, capturas). Sin carpeta, usa cuadros del
       propio vídeo.
     - `grafico`: sus números de verdad (`datos`). Pregúntaselos; los de fábrica son de ejemplo.
     - `fondo`: su nombre y su cuenta (`nombre`, `usuario`) y su titular (`lineas`).
     - `cristal`: su nombre y su cuenta, lo que cuenta el contador (`numero`, `texto_numero`) y el calendario (`dia`,
       `fecha`, `evento`: el día que lo sube; o `fecha` vacía, y el calendario no sale).
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
   - Deja `video_efectos.mp4` al lado del original, que nunca se toca.
   - Dile dónde está y que lo mire antes de subirlo.
   - En 4K, añade `--ancho 2160` (tarda unas 4 veces más).
6. **Los cambios, con sus palabras.**
   - «más largo» o «más corto»: mueve `desde` y `hasta`.
   - «otro color»: la opción `color`, en hexadecimal (#FF3B30).
   - «más grande» o «más rápido» en la órbita: `tamano` y `velocidad`; «más separadas»: `radio`; «que se aceleren cuando
     hago el gesto»: `acelera` con el segundo del gesto (míralo en los cuadros).
   - Lo que no tenga opción («más arriba», «la letra más gorda»): cada efecto es un archivo corto en `motor/efectos/`,
     con sus medidas arriba y comentadas. Cambia el número y dile qué cambiaste.

## Los 13 efectos

| Efecto | Qué hace | Dura | Opciones (y lo que traen) |
|---|---|---|---|
| `cristal` | 8 tarjetas grandes de cristal a su alrededor, varias por detrás (su cabeza y sus brazos pasan por delante): el número enorme, la barra de exportar, su ficha con su foto, un calendario, lo que se está editando, el anillo 4K, una marca que se dibuja y la pastilla de abajo | 3,5 s | `marca`, `numero`=13, `texto_numero`, `exportando`, `resolucion`=4K, `fps`=30, `nombre`, `usuario`, `dia`, `fecha`, `evento`, `editando_titulo`, `editando`, `etiqueta`, `pastilla`, `color` (un texto vacío quita su tarjeta) |
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

**Que la mano señale lo que sale**: si la persona señala arriba, a un lado o levanta el pulgar, mira los cuadros y pon
el efecto justo ahí (el gráfico cuando señala arriba, el botón de seguir del lado al que apunta).

`PY efectos.py --lista` enseña los mismos, con sus opciones al día.

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
