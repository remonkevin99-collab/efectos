"""El motor: coge un vídeo, le pone los efectos de un plan y lo guarda con su audio.

El motor de efectos de Kevin Remón (MIT). Lo usa `efectos.py` (el comando); aquí está todo lo de dentro.

Cómo trabaja:
  1. Lee el vídeo con ffmpeg (sus medidas, los cuadros por segundo, si tiene audio y cómo guarda el color).
  2. Prepara el plan: qué efecto, desde qué segundo y hasta cuál, con qué opciones.
  3. PASADA 1, MIRAR: solo en los tramos con efecto (y medio segundo antes y después, para suavizar), busca a la persona y
     su cara (`persona.py`). Es rápida: se hace con el vídeo pequeño. En un Mac, además, el recorte fino del sistema en los
     cuadros que se pintan (si no se puede, se queda el de siempre).
  4. PASADA 2, PINTAR: lee el vídeo al tamaño final cuadro a cuadro. Donde no hay efecto, el cuadro pasa tal cual; donde
     hay, cada efecto pinta sobre él (en el orden del plan: el último queda encima). Y lo va guardando con ffmpeg, con el
     audio original.
  Si un efecto falla, se avisa y ese tramo sale sin ese efecto: el vídeo no se pierde.

Lo que el motor les deja a los efectos en `c.estado` (además de lo suyo):
  - `ruta_video`: el vídeo que se está editando.
  - `sacar_cuadros(n, ancho=540)`: una función que devuelve n cuadros del propio vídeo repartidos a lo largo (imágenes
    PIL RGBA), por si el efecto los quiere (la órbita los usa cuando no le dan una carpeta de imágenes). Solo se sacan si
    el efecto la llama.
"""
import importlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import unicodedata
from dataclasses import dataclass, field

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))           # la carpeta motor/
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

import base as B  # noqa: E402

MARGEN = 0.5          # segundos que se miran antes y después de cada efecto (para suavizar la persona y la cara)


class ErrorMotor(Exception):
    """Un error explicado en español para quien usa el comando."""


# ── ffmpeg ──────────────────────────────────────────────────────────────────────────────────────────────────────────
_FFMPEG = None


def buscar_ffmpeg():
    """El ffmpeg del sistema; si no hay, el que trae el paquete imageio-ffmpeg."""
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG
    ruta = shutil.which('ffmpeg')
    if not ruta:
        try:
            import imageio_ffmpeg
            ruta = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ruta = None
    if not ruta:
        raise ErrorMotor('No encuentro ffmpeg. Instálalo (Mac: «brew install ffmpeg»; Windows: «winget install ffmpeg»; '
                         'Ubuntu: «sudo apt install ffmpeg») o corre la instalación, que trae uno.')
    _FFMPEG = ruta
    return ruta


def _ffprobe():
    ff = buscar_ffmpeg()
    vecino = os.path.join(os.path.dirname(ff), 'ffprobe' + ('.exe' if os.name == 'nt' else ''))
    return vecino if os.path.isfile(vecino) else shutil.which('ffprobe')


# ── Lo que hay que saber del vídeo ──────────────────────────────────────────────────────────────────────────────────
@dataclass
class InfoVideo:
    ruta: str
    ancho: int
    alto: int
    fps: float
    fps_texto: str          # exacto, para ffmpeg («30», «30000/1001»)
    duracion: float
    cuadros: int
    audio: str              # el códec del audio, o '' si no tiene
    matriz: str             # cómo guarda el color: 'bt709' o 'bt601'
    rango: str              # 'tv' (lo normal) o 'pc'
    hdr: bool


def leer_info(ruta):
    if not os.path.isfile(ruta):
        raise ErrorMotor(f'No encuentro el vídeo «{ruta}».')
    ff = buscar_ffmpeg()
    texto = subprocess.run([ff, '-hide_banner', '-i', ruta], capture_output=True, text=True, errors='replace').stderr
    m = re.search(r'Stream #\S+.*?: Video: (.*)', texto)
    if not m:
        raise ErrorMotor(f'«{ruta}» no tiene imagen. ¿Seguro que es un vídeo?')
    linea = m.group(1)
    tam = re.search(r',\s*(\d{2,5})x(\d{2,5})', linea)
    if not tam:
        raise ErrorMotor(f'No sé leer las medidas de «{ruta}».')
    w, h = int(tam.group(1)), int(tam.group(2))
    giro = re.search(r'rotation of (-?[\d.]+) degrees', texto)
    if giro and round(abs(float(giro.group(1)))) % 180 == 90:
        w, h = h, w                              # grabado de lado: ffmpeg lo endereza al leerlo
    f = re.search(r'([\d.]+) fps', linea) or re.search(r'([\d.]+) tbr', linea)
    fps = float(f.group(1)) if f else 30.0
    fps_texto = _fps_exacto(ruta, fps)
    d = re.search(r'Duration: (\d+):(\d+):([\d.]+)', texto)
    dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0.0
    a = re.search(r'Stream #\S+.*?: Audio: (\w+)', texto)
    low = linea.lower()
    matriz = 'bt601' if ('bt470bg' in low or 'smpte170m' in low or 'bt601' in low) else 'bt709'
    rango = 'pc' if re.search(r'\(pc[,)]', low) else 'tv'
    hdr = any(x in low for x in ('bt2020', 'arib-std-b67', 'smpte2084'))
    num, den = (fps_texto.split('/') + ['1'])[:2]
    fps_real = float(num) / float(den)
    return InfoVideo(ruta, w, h, fps_real, fps_texto, dur, int(math.floor(dur * fps_real + 0.5)), a.group(1) if a else '',
                     matriz, rango, hdr)


def _fps_exacto(ruta, aprox):
    """Los cuadros por segundo exactos («30000/1001» y no «29.97»), con ffprobe si está; si no, por los valores típicos."""
    fp = _ffprobe()
    if fp:
        try:
            r = subprocess.run([fp, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=avg_frame_rate,r_frame_rate',
                                '-of', 'default=nw=1:nk=1', ruta], capture_output=True, text=True, timeout=30).stdout.split()
            for valor in r[::-1]:                  # mejor la media (avg) que la nominal
                num, _, den = valor.partition('/')
                if num and den and float(den) > 0 and 1 <= float(num) / float(den) <= 240:
                    return f'{int(num)}/{int(den)}' if int(den) != 1 else str(int(num))
        except Exception:
            pass
    for exacto, txt in ((23.976, '24000/1001'), (29.97, '30000/1001'), (59.94, '60000/1001')):
        if abs(aprox - exacto) < 0.01:
            return txt
    return str(int(round(aprox))) if abs(aprox - round(aprox)) < 0.01 else f'{aprox:.3f}'


# ── Leer y escribir ─────────────────────────────────────────────────────────────────────────────────────────────────
class Lector:
    """Da los cuadros del vídeo uno a uno (RGB, uint8), desde el primero, al tamaño pedido."""

    def __init__(self, info, ancho, alto, hasta=None):
        self.tam = ancho * alto * 3
        vf = (f'fps={info.fps_texto},scale={ancho}:{alto}:flags=lanczos:in_color_matrix={info.matriz}'
              f':in_range={info.rango},format=rgb24')
        cmd = [buscar_ffmpeg(), '-v', 'error', '-nostdin', '-i', info.ruta, '-map', '0:v:0', '-vf', vf]
        if hasta is not None:
            cmd += ['-frames:v', str(int(hasta))]
        cmd += ['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def leer(self):
        b = self.p.stdout.read(self.tam)
        return b if b and len(b) == self.tam else None

    def cerrar(self):
        try:
            self.p.stdout.close()
        except Exception:
            pass
        try:
            self.p.kill()
        except Exception:
            pass
        self.p.wait()


class Escritor:
    """Guarda los cuadros en un MP4 (H.264) con el audio del vídeo original."""

    def __init__(self, info, ancho, alto, salida, calidad=18, rapidez='medium'):
        self.salida = salida
        self.err = tempfile.TemporaryFile()
        colores = {'bt709': ('bt709', 'bt709', 'bt709'), 'bt601': ('smpte170m', 'smpte170m', 'smpte170m')}[info.matriz]
        cmd = [buscar_ffmpeg(), '-v', 'error', '-nostdin', '-y',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{ancho}x{alto}', '-r', info.fps_texto, '-i', '-',
               '-i', info.ruta, '-map', '0:v:0', '-map', '1:a:0?',
               '-vf', f'scale=out_color_matrix={info.matriz}:out_range={info.rango},format=yuv420p,'
                      f'setparams=colorspace={colores[0]}:color_primaries={colores[1]}:color_trc={colores[2]}:range={info.rango}',
               '-c:v', 'libx264', '-preset', rapidez, '-crf', str(calidad),
               '-colorspace', colores[0], '-color_primaries', colores[1], '-color_trc', colores[2],
               '-color_range', info.rango]
        if info.audio:
            cmd += ['-c:a', 'copy'] if info.audio in ('aac', 'mp3', 'alac') else ['-c:a', 'aac', '-b:a', '256k']
        cmd += ['-movflags', '+faststart', salida]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=self.err)

    def escribir(self, datos):
        try:
            self.p.stdin.write(datos)
        except (BrokenPipeError, OSError):
            self.p.wait()
            raise ErrorMotor('ffmpeg se paró al guardar el vídeo:\n' + self._error())

    def _error(self):
        self.err.seek(0)
        return self.err.read().decode('utf-8', 'replace')[-2000:]

    def cerrar(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        if self.p.wait() != 0:
            raise ErrorMotor('ffmpeg no pudo terminar el vídeo:\n' + self._error())


def sacar_cuadros(info, n, ancho=540):
    """n cuadros del vídeo repartidos a lo largo, como imágenes PIL RGBA. Sin el principio ni el final: ahí uno se
    prepara o se levanta a parar la grabación (al final salía una tarjeta con él agachado)."""
    from PIL import Image
    out = []
    alto = int(round(ancho * info.alto / info.ancho / 2)) * 2
    ini = min(1.0, 0.15 * info.duracion)
    fin = info.duracion - min(1.5, 0.2 * info.duracion)
    for k in range(int(n)):
        seg = ini + (fin - ini) * (k + 0.5) / max(1, int(n))
        crudo = subprocess.run([buscar_ffmpeg(), '-v', 'error', '-nostdin', '-ss', f'{seg:.3f}', '-i', info.ruta,
                                '-frames:v', '1', '-vf', f'scale={ancho}:{alto}:flags=lanczos,format=rgb24',
                                '-f', 'rawvideo', '-'], capture_output=True).stdout
        if len(crudo) >= ancho * alto * 3:
            arr = np.frombuffer(crudo[:ancho * alto * 3], np.uint8).reshape(alto, ancho, 3)
            out.append(Image.fromarray(arr, 'RGB').convert('RGBA'))
    return out


# ── Los efectos ─────────────────────────────────────────────────────────────────────────────────────────────────────
def normalizar(nombre):
    """«Órbita», «orbita», «palabra_detras», «Palabra Detrás» → «orbita», «palabra-detras»."""
    s = unicodedata.normalize('NFKD', str(nombre)).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[\s_]+', '-', s.strip().lower())


_EFECTOS = None
_NO_CARGAN = {}


def efectos():
    """{nombre normalizado: módulo} de todos los efectos de `efectos/`. Si uno no carga (un error al escribirlo), los
    demás siguen funcionando y se apunta por qué."""
    global _EFECTOS
    if _EFECTOS is not None:
        return _EFECTOS
    _EFECTOS = {}
    try:
        from efectos import TODOS
        for nombre, mod in TODOS.items():
            _EFECTOS[normalizar(nombre)] = mod
        return _EFECTOS
    except Exception:
        pass
    # el registro no cargó entero: uno a uno, para saber cuál falla
    carpeta = os.path.join(AQUI, 'efectos')
    for archivo in sorted(os.listdir(carpeta)):
        if not archivo.endswith('.py') or archivo.startswith('_'):
            continue
        nombre_mod = archivo[:-3]
        try:
            spec = importlib.util.spec_from_file_location(f'efecto_{nombre_mod}', os.path.join(carpeta, archivo))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, 'NOMBRE') and hasattr(mod, 'dibujar'):
                _EFECTOS[normalizar(mod.NOMBRE)] = mod
        except Exception as e:
            _NO_CARGAN[nombre_mod] = f'{type(e).__name__}: {e}'
    return _EFECTOS


def efectos_que_no_cargan():
    efectos()
    return dict(_NO_CARGAN)


def buscar_efecto(nombre):
    todos = efectos()
    clave = normalizar(nombre)
    if clave in todos:
        return todos[clave]
    import difflib
    parecidos = difflib.get_close_matches(clave, list(todos), n=3, cutoff=0.5)
    pista = f' ¿Quisiste decir {", ".join("«" + p + "»" for p in parecidos)}?' if parecidos else ''
    raise ErrorMotor(f'No conozco el efecto «{nombre}».{pista} Para verlos todos: efectos.py --lista')


@dataclass
class Entrada:
    """Un efecto del plan, listo para pintar."""
    mod: object
    nombre: str
    desde: float
    hasta: float
    op: dict
    estado: dict = field(default_factory=dict)
    fallo: bool = False


def _a_texto(v):
    if isinstance(v, bool):
        return 'si' if v else 'no'
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def preparar_plan(plan, info, carpeta_plan=None, avisar=print):
    """El plan (dict, lista o ruta a un JSON) → [Entrada]."""
    if isinstance(plan, str):
        if not os.path.isfile(plan):
            raise ErrorMotor(f'No encuentro el plan «{plan}».')
        carpeta_plan = os.path.dirname(os.path.abspath(plan))
        try:
            with open(plan, encoding='utf-8') as fh:
                plan = json.load(fh)
        except json.JSONDecodeError as e:
            raise ErrorMotor(f'El plan no es un JSON válido (línea {e.lineno}, columna {e.colno}): {e.msg}')
    lista = plan.get('efectos', []) if isinstance(plan, dict) else plan
    if not isinstance(lista, list) or not lista:
        raise ErrorMotor('El plan no tiene efectos. Tiene que ser así: {"efectos": [{"efecto": "orbita", "desde": 1, "hasta": 4}]}')
    entradas = []
    for n, e in enumerate(lista, 1):
        if not isinstance(e, dict) or not e.get('efecto'):
            raise ErrorMotor(f'El efecto número {n} del plan no dice qué efecto es (falta "efecto").')
        mod = buscar_efecto(e['efecto'])
        try:
            desde = float(e.get('desde', 0))
            if e.get('hasta') is not None:
                hasta = float(e['hasta'])
            elif e.get('duracion') is not None:
                hasta = desde + float(e['duracion'])
            else:
                hasta = desde + float(getattr(mod, 'DURACION', 3.0))
        except (TypeError, ValueError):
            raise ErrorMotor(f'En el efecto número {n} («{e["efecto"]}»), "desde" y "hasta" tienen que ser segundos (números).')
        if info.duracion and hasta > info.duracion + 0.01:
            avisar(f'  Aviso: «{mod.NOMBRE}» acaba en el segundo {hasta:.2f} y el vídeo dura {info.duracion:.2f}; se corta ahí.')
            hasta = info.duracion
        if hasta - desde < 0.1:
            raise ErrorMotor(f'«{mod.NOMBRE}» va del segundo {desde:.2f} al {hasta:.2f}: tiene que durar algo.')
        op = dict(getattr(mod, 'OPCIONES', {}))
        for clave, valor in (e.get('opciones') or {}).items():
            clave = normalizar(clave).replace('-', '_') if normalizar(clave).replace('-', '_') in op else clave
            if clave not in op:
                avisar(f'  Aviso: «{mod.NOMBRE}» no tiene la opción «{clave}» (tiene: {", ".join(op) or "ninguna"}). '
                       'Se le pasa igual.')
            valor = _a_texto(valor)
            # una ruta relativa se busca primero al lado del plan
            if carpeta_plan and valor and not os.path.isabs(valor) and os.path.exists(os.path.join(carpeta_plan, valor)):
                valor = os.path.join(carpeta_plan, valor)
            op[clave] = valor
        entradas.append(Entrada(mod, mod.NOMBRE, desde, hasta, op))
    return entradas


def _ventanas(entradas, fps, total, hasta_cuadro=None):
    """Los tramos que hay que mirar (en cuadros), juntando los que se pisan."""
    v = []
    for e in entradas:
        a = max(0, int(math.floor((e.desde - MARGEN) * fps)))
        b = min(total, int(math.ceil((e.hasta + MARGEN) * fps)) + 1)
        if hasta_cuadro is not None:
            b = min(b, hasta_cuadro)
        if b > a:
            v.append([a, b])
    v.sort()
    juntas = []
    for a, b in v:
        if juntas and a <= juntas[-1][1]:
            juntas[-1][1] = max(juntas[-1][1], b)
        else:
            juntas.append([a, b])
    return [tuple(x) for x in juntas]


# ── Todo junto ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _medida(info, ancho):
    ancho = int(ancho)
    if ancho < 64:
        raise ErrorMotor('El ancho es demasiado pequeño.')
    ancho -= ancho % 2
    alto = int(round(ancho * info.alto / info.ancho / 2.0)) * 2
    return ancho, alto


def _reloj(seg):
    seg = int(round(seg))
    return f'{seg // 60} min {seg % 60:02d} s' if seg >= 60 else f'{seg} s'


def procesar(video, plan, salida=None, ancho=1080, fotos=None, mascaras=None, calidad=18, rapidez='medium',
             recorte='auto', avisar=print):
    """Pone los efectos del `plan` en el `video`. Devuelve la ruta del vídeo (o la lista de fotos, con `fotos`).
    `recorte`: 'auto' (en un Mac, el fino del sistema; si no, el normal) o 'normal'."""
    inicio = time.time()
    if recorte not in ('auto', 'normal'):
        raise ErrorMotor(f'--recorte puede ser «auto» o «normal», no «{recorte}».')
    info = leer_info(video)
    W, H = _medida(info, ancho)
    base_salida = os.path.splitext(os.path.abspath(video))[0] + '_efectos'
    if salida:
        base_salida = os.path.splitext(os.path.abspath(salida))[0]
    salida = base_salida + '.mp4'
    if os.path.abspath(salida) == os.path.abspath(video):
        raise ErrorMotor('La salida no puede ser el mismo vídeo de entrada.')
    avisar(f'Vídeo: {os.path.basename(video)} · {info.ancho}×{info.alto} · {info.fps:g} cuadros/s · {info.duracion:.1f} s'
           + ('' if info.audio else ' · sin audio'))
    if info.hdr:
        avisar('  Aviso: este vídeo está grabado en HDR; los colores pueden salir lavados. Para la próxima, grábalo sin HDR '
               '(en el iPhone: Ajustes › Cámara › Formatos › Vídeo HDR, desactivado).')
    entradas = preparar_plan(plan, info, avisar=avisar)
    for e in entradas:
        avisar(f'  · {e.nombre}: del segundo {e.desde:.2f} al {e.hasta:.2f}')
    total = info.cuadros
    fps = info.fps

    # con --fotos: solo esos cuadros, y nada más allá del último
    fotos_i = {}
    hasta_cuadro = total
    if fotos:
        for s in fotos:
            i = min(max(0, int(round(float(s) * fps))), max(0, total - 1))
            fotos_i[i] = float(s)
        hasta_cuadro = max(fotos_i) + 1
    ventanas = _ventanas(entradas, fps, total, None if not fotos else min(total, hasta_cuadro + int(MARGEN * fps)))
    if fotos:
        ventanas = [v for v in ventanas if any(v[0] <= i < v[1] for i in fotos_i)]

    # pasada 1: la persona y la cara
    from persona import Persona
    persona = Persona(info, mascaras, avisar=avisar)
    t0 = time.time()
    persona.analizar(ventanas, lambda w, h, hasta: Lector(info, w, h, hasta))
    t_mirar = time.time() - t0

    # pasada 1b, solo en Mac: el recorte fino del sistema, en los cuadros que se pintan
    t_fino = 0.0
    if recorte == 'auto' and not mascaras:
        t0 = time.time()
        pintar = sorted(fotos_i) if fotos else [i for i in range(hasta_cuadro)
                                                if any(e.desde <= i / fps < e.hasta for e in entradas)]
        if persona.recorte_fino(pintar, lambda w, h, hasta: Lector(info, w, h, hasta), W, H):
            t_fino = time.time() - t0

    # lo que el motor les da a los efectos
    cache_cuadros = {}

    def dar_cuadros(n, ancho_img=540):
        clave = (int(n), int(ancho_img))
        if clave not in cache_cuadros:
            cache_cuadros[clave] = sacar_cuadros(info, n, ancho_img)
        return cache_cuadros[clave]

    for e in entradas:
        e.estado['ruta_video'] = os.path.abspath(video)
        e.estado['sacar_cuadros'] = dar_cuadros

    # pasada 2: pintar
    lector = Lector(info, W, H, hasta_cuadro)
    escritor = None if fotos else Escritor(info, W, H, salida, calidad, rapidez)
    hechas = []
    # los cuadros se pintan siempre en las mismas dos memorias (a 4K son 100 MB cada vez: pedirlas en cada cuadro es lento)
    lienzo = np.empty((H, W, 3), np.float32)
    listo_u8 = np.empty((H, W, 3), np.uint8)
    avisar(f'Pintando a {W}×{H}' + (f' (solo {len(fotos_i)} foto{"s" if len(fotos_i) > 1 else ""})…' if fotos else '…'))
    t0 = time.time()
    ultimo_aviso = t0
    pintados = 0
    try:
        for i in range(hasta_cuadro):
            crudo = lector.leer()
            if crudo is None:
                break
            if fotos and i not in fotos_i:
                continue
            seg = i / fps
            activas = [e for e in entradas if not e.fallo and e.desde <= seg < e.hasta]
            if activas:
                cuadro = np.frombuffer(crudo, np.uint8).reshape(H, W, 3)
                img = lienzo
                np.multiply(cuadro, np.float32(1.0 / 255.0), out=img)
                mascara, cara = persona.en(i, cuadro)
                bien = []
                for e in activas:
                    c = B.Cuadro(img=img, mascara=mascara, cara=cara, t=seg - e.desde, dur=e.hasta - e.desde,
                                 fps=fps, op=e.op, estado=e.estado)
                    try:
                        e.mod.dibujar(c)
                        bien.append(e)
                    except Exception as ex:
                        e.fallo = True
                        donde = traceback.extract_tb(ex.__traceback__)[-1]
                        avisar(f'  Aviso: el efecto «{e.nombre}» falló en el segundo {seg:.2f} '
                               f'({type(ex).__name__}: {ex}; {os.path.basename(donde.filename)}, línea {donde.lineno}). '
                               'Desde ahí, su tramo sale sin él.')
                        # el cuadro vuelve a como estaba y se repintan los que sí funcionaron
                        np.multiply(cuadro, np.float32(1.0 / 255.0), out=img)
                        for ok in bien:
                            try:
                                ok.mod.dibujar(B.Cuadro(img=img, mascara=mascara, cara=cara, t=seg - ok.desde,
                                                        dur=ok.hasta - ok.desde, fps=fps, op=ok.op, estado=ok.estado))
                            except Exception:
                                pass
                np.clip(img, 0.0, 1.0, out=img)
                salida_cuadro = cv2.convertScaleAbs(img, dst=listo_u8, alpha=255.0)   # ×255, redondeado, en una pasada
                datos = salida_cuadro.data
                pintados += 1
            else:
                salida_cuadro = None
                datos = crudo
            if fotos:
                from PIL import Image
                im = Image.fromarray(salida_cuadro if salida_cuadro is not None
                                     else np.frombuffer(crudo, np.uint8).reshape(H, W, 3))
                ruta = f'{base_salida}_{fotos_i[i]:.2f}s.png'
                im.save(ruta)
                hechas.append(ruta)
                avisar(f'  foto: {ruta}')
            else:
                escritor.escribir(datos)
            ahora = time.time()
            if not fotos and (ahora - ultimo_aviso > 3 or i == hasta_cuadro - 1):
                ultimo_aviso = ahora
                hecho = (i + 1) / max(1, hasta_cuadro)
                ritmo = (i + 1) / max(1e-6, ahora - t0)
                avisar(f'  {hecho * 100:3.0f} % · cuadro {i + 1} de {hasta_cuadro} · {ritmo:.1f} cuadros/s · '
                       f'faltan ~{_reloj((hasta_cuadro - i - 1) / max(ritmo, 1e-6))}')
    finally:
        lector.cerrar()
    if escritor:
        escritor.cerrar()
    t_pintar = time.time() - t0
    total_seg = time.time() - inicio
    video_seg = hasta_cuadro / fps
    avisar(f'Listo en {_reloj(total_seg)} (mirar: {t_mirar:.1f} s; '
           + (f'recorte fino: {t_fino:.1f} s; ' if t_fino else '') + f'pintar: {t_pintar:.1f} s; '
           f'{total_seg / max(video_seg, 1e-6):.2f} s por cada segundo de vídeo).')
    fallados = [e.nombre for e in entradas if e.fallo]
    if fallados:
        avisar(f'  Ojo: {", ".join(fallados)} falló y su tramo salió sin él (mira el aviso de arriba).')
    if fotos:
        return hechas
    avisar(f'→ {salida}')
    return salida
