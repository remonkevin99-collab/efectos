# Efectos para tus vídeos

**13 efectos de edición para tus Reels, con un comando.** Le pasas a Claude tu vídeo hablando a cámara, le dices qué
efecto quieres y en qué segundo, y en un minuto te deja el vídeo editado al lado del original. Tu voz se queda igual.

![Los 13 efectos](ejemplos/efectos.jpg)

- **Gratis** y de código abierto (MIT).
- **Corre en tu computadora**: tu vídeo no se sube a ningún sitio.
- Mac, Windows y Linux.

Hecho por **Kevin Remón** · Instagram [@kevin.rf99](https://www.instagram.com/kevin.rf99/)

---

## Instalarlo (una vez)

1. Abre **Claude** en tu computadora, en la pestaña **Code**.
2. Pégale esto:
   ```
   Instala los efectos de github.com/remonkevin99-collab/efectos en mi carpeta de skills
   ```
3. Cuando te diga que terminó, cierra Claude y vuelve a abrirlo.

## Usarlo

1. Arrastra tu vídeo al chat de Claude.
2. Escribe el efecto y cuándo:
   ```
   /efectos órbita del segundo 2 al 5
   ```
   ```
   /efectos palabra-detrás con la palabra NEGOCIO del 1 al 3, y la lista del 5 al 8
   ```
3. Claude mira unos cuadros antes, para que nada te tape la cara, y te deja `tuvideo_efectos.mp4`.

¿Algo no te gusta? Díselo con palabras normales: «más pequeño», «más lento», «la palabra más arriba».

## Los 13 efectos

| | Efecto | Qué hace |
|---|---|---|
| 1 | `cristal` | Tarjetas de cristal flotan a tu alrededor: un contador, tu nombre, «sin editor» y una que pasa por detrás de tu brazo |
| 2 | `fondo` | Te cambia el fondo entero: en blanco y negro, con tu nombre, tu titular y un botón de Seguir que alguien pulsa |
| 3 | `órbita` | Tus portadas giran a tu alrededor: pasan por detrás de ti y por delante |
| 4 | `gráfico` | La pantalla se divide: tus números en barras arriba y tú abajo, con la cabeza saliendo del corte |
| 5 | `letrero-led` | Se apaga la luz y se enciende tu letrero detrás de ti, letra a letra |
| 6 | `lista` | Una lista que se va marcando sola |
| 7 | `edición` | La pantalla se divide: el panel de edición arriba (los pasos, la línea de tiempo y el 100 %) y tú abajo |
| 8 | `palabra-detrás` | Una palabra gigante detrás de tu cabeza |
| 9 | `comentario` | Un comentario que se escribe solo, le dan corazón y llega tu respuesta |
| 10 | `línea-tiempo` | Color de cine y una línea de edición encima, con su título |
| 11 | `portada` | Te conviertes en la portada de una revista |
| 12 | `botón-seguir` | Aparece un botón de Seguir y alguien lo pulsa |
| 13 | `tier-list` | Una tabla de la S a la F, y lo tuyo vuela hasta la S |

## Para que quede bien

- **Graba en vertical**, con espacio detrás de ti y, si puedes, sin una silla de respaldo alto: los efectos de «detrás
  de ti» quedan más limpios.
- **Ropa que se separe del fondo.**
- **Sin HDR** (en el iPhone: Ajustes › Cámara › Formatos › Vídeo HDR, desactivado), o los colores salen lavados.
- **¿4K?** Pídelo: «hazlo en 4K». Tarda más.

---

## Para Claude: cómo se instala

Haz esto en orden y dile a la persona cómo va.

1. **Copia el repositorio en la carpeta de skills de la persona**, con el nombre `efectos`:
   - Mac y Linux: `git clone --depth 1 https://github.com/remonkevin99-collab/efectos.git ~/.claude/skills/efectos`
   - Windows (PowerShell): `git clone --depth 1 https://github.com/remonkevin99-collab/efectos.git "$HOME\.claude\skills\efectos"`
   - Sin git: baja https://github.com/remonkevin99-collab/efectos/archive/refs/heads/main.zip, descomprímelo y deja la
     carpeta como `~/.claude/skills/efectos` (que dentro esté `SKILL.md`, no otra carpeta).
   - Si ya existe, actualízala con `git pull` en vez de clonarla.
2. **Corre la instalación** dentro de esa carpeta. Crea su propio Python (3.10 a 3.12), instala lo necesario y baja dos
   modelos de Google. Tarda unos minutos la primera vez.
   - Mac y Linux: `bash instalar.sh`
   - Windows: `powershell -ExecutionPolicy Bypass -File instalar.ps1`
3. **Comprueba** que dice «Todo bien.»:
   - Mac y Linux: `.venv/bin/python efectos.py --comprobar`
   - Windows: `.venv\Scripts\python.exe efectos.py --comprobar`
4. **Dile a la persona** que cierre Claude y lo vuelva a abrir: después ya puede escribir `/efectos`.

Si falta Python 3.10–3.12, `instalar.sh` explica qué hacer. La forma más fácil es instalar [uv](https://docs.astral.sh/uv/),
que baja Python solo. Cómo se usa después está en `SKILL.md`.

## Sin Claude, desde la terminal

```
.venv/bin/python efectos.py --lista                                  # los efectos y sus opciones
.venv/bin/python efectos.py orbita video.mp4 --desde 2 --hasta 6     # uno suelto
.venv/bin/python efectos.py palabra-detras video.mp4 --op texto=HOLA # con opciones
.venv/bin/python efectos.py video.mp4 --plan plan.json               # varios a la vez
.venv/bin/python efectos.py video.mp4 --plan plan.json --fotos 1,3   # solo unas fotos, para revisar
```

Todas las opciones: `.venv/bin/python efectos.py --ayuda`.

## Licencias

- **El código**: MIT, de Kevin Remón (`LICENSE`).
- **La letra Poppins**: SIL Open Font License (`fuentes/LICENCIA-Poppins.txt`).
- **Los dos modelos de Google** que baja la instalación (la persona y la cara, de MediaPipe): Apache 2.0 (`modelos/AVISO.md`).
