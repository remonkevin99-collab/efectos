"""La persona y la cara: lo que el motor necesita saber de cada cuadro para poner cosas DETRÁS de la persona y para no
taparle la cara.

Parte del motor de efectos de Kevin Remón (MIT). Usa dos modelos oficiales de Google para MediaPipe (en `modelos/`,
licencia Apache 2.0): el Selfie Segmenter (quién es persona y quién es fondo) y el detector de caras BlazeFace.

Cómo se hace, paso a paso (cada paso arregla algo que se ve mal en un vídeo):

  1. EL CUADRO ENTERO Y LA CABEZA DE CERCA. El modelo mira las imágenes a 256 × 256: en un vídeo vertical entero, la cabeza
     sale cuadrada y la silla se pega a los hombros. Por eso se pasa dos veces: el cuadro entero (para el cuerpo) y un
     recorte cuadrado alrededor de la cabeza (para la gorra, el pelo y las orejas). El recorte manda dentro de su zona y se
     funde con el cuadro entero hacia sus bordes.
  2. LA CARA, EN ESE MISMO RECORTE. El detector de caras está hecho para caras grandes (selfis): en el cuadro entero, una
     persona sentada lejos sale mal o no sale. En el recorte de la cabeza la encuentra seguro.
  3. QUE NO PARPADEE. Si la imagen de un píxel no cambia, su máscara tampoco debería: cada píxel se promedia en el tiempo
     (hacia delante y hacia atrás, sin retraso) con un peso que depende de cuánto cambia SU imagen. Donde nada se mueve
     (la silla, el micrófono, la pared) se promedia mucho y deja de entrar y salir; donde la persona se mueve, sigue al
     modelo al momento.
  4. LIMPIA. Lo seguro siembra y lo dudoso solo cuenta si toca lo seguro; fuera los trozos sueltos; tapados los agujeritos
     (no los grandes: el hueco entre el brazo y el cuerpo es fondo de verdad); nada cambia por 1 o 2 cuadros; y la forma,
     suave (una apertura y un cierre redondos).
  5. EL BORDE, AL PINTAR. La máscara se decide pequeña (un tercio de 1080) y se afina al tamaño del vídeo con un filtro
     guiado por la propia imagen: el borde se pega al borde de verdad de la persona en vez de salir borroso.
  6. LA CARA, SUAVE Y SIN RETRASO. Los huecos sin detección se rellenan, los saltos sueltos se quitan (mediana de 5) y se
     suaviza con una pasada hacia delante y otra hacia atrás. Si en un tramo no aparece ninguna cara, sale de la parte de
     arriba de la silueta.

Con `--mascaras <carpeta>` la máscara no se calcula: se lee una imagen por cuadro (0000.png, 0001.png…; la máscara en el
canal alfa o en gris): sirve para usar un recorte mejor hecho con otra herramienta (por ejemplo, el de «Quitar fondo» de
macOS o el de un editor). La cara se sigue buscando.
"""
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
MODELOS = os.path.join(os.path.dirname(AQUI), 'modelos')
MODELO_PERSONA = os.path.join(MODELOS, 'selfie_segmenter.tflite')
MODELO_CARA = os.path.join(MODELOS, 'blaze_face_short_range.tflite')

LADO_CORTO_ANALISIS = 540   # el cuadro que se mira (para la cara y el recorte de la cabeza)
LADO_CORTO_MASCARA = 360    # la máscara se decide a este tamaño (un tercio de 1080) y se afina al pintar
LADO_CORTO_AFINAR = 1080    # el borde se afina a este tamaño como mucho (a 4K se sube desde aquí)

# paso 3: cuánto tiene que cambiar la imagen de un píxel (0–255) para que la máscara la siga al momento
QUIETO = 2.5                # por debajo de esto, la imagen «no cambia» (ruido de la cámara)
CAMBIO = 9.0                # a partir de QUIETO + CAMBIO, la máscara sigue al modelo sin promediar
PESO_QUIETO = 0.07          # cuánto pesa el cuadro nuevo donde nada cambia (≈ promedio de medio segundo)
# paso 4
SEGURO, DUDA = 0.62, 0.40
ISLA = 0.005                # los trozos de menos de esto (del trozo más grande) se quitan
AGUJERO = 0.004             # los agujeros de menos de esto (del tamaño de la persona) se tapan


def _par(x):
    return max(2, int(round(x / 2.0)) * 2)


def tamano_con_lado_corto(W, H, lado):
    """(ancho, alto) con el lado corto = `lado`, sin deformar."""
    k = lado / float(min(W, H))
    return _par(W * k), _par(H * k)


@contextmanager
def _callado():
    """Calla los avisos internos de MediaPipe (salen en inglés por la salida de errores y asustan). Solo se usa al cargar
    los modelos y en la primera pasada: los errores de verdad siguen llegando a Python como excepciones."""
    try:
        fd = sys.stderr.fileno()
    except Exception:
        yield
        return
    sys.stderr.flush()
    copia = os.dup(fd)
    nulo = os.open(os.devnull, os.O_WRONLY)
    os.dup2(nulo, fd)
    try:
        yield
    finally:
        sys.stderr.flush()
        os.dup2(copia, fd)
        os.close(copia)
        os.close(nulo)


_VIVOS = []
_CALLADO_AL_SALIR = []


def _callar_al_salir():
    """Al cerrarse el programa, MediaPipe escribe sus despedidas en inglés por la salida de errores: se tapan (para entonces
    todo lo nuestro ya está escrito)."""
    if _CALLADO_AL_SALIR:
        return
    _CALLADO_AL_SALIR.append(True)
    import atexit

    def callar():
        try:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stderr.fileno())
        except Exception:
            pass
    atexit.register(callar)


class Modelos:
    """Los dos modelos de Google, cargados una vez."""

    def __init__(self, con_persona=True):
        for ruta in ([MODELO_PERSONA] if con_persona else []) + [MODELO_CARA]:
            if not os.path.isfile(ruta):
                raise RuntimeError(f'Falta el modelo «{os.path.basename(ruta)}» en {MODELOS}. '
                                   'Corre la instalación otra vez (instalar.sh o instalar.ps1): los baja ella.')
        _callar_al_salir()
        os.environ.setdefault('GLOG_minloglevel', '2')
        os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
        with _callado():
            try:
                import mediapipe as mp
                from mediapipe.tasks.python import BaseOptions, vision
            except ImportError as e:
                raise RuntimeError('Falta MediaPipe. Corre la instalación (instalar.sh o instalar.ps1) y usa el Python '
                                   f'de su .venv. ({e})')
            self.mp = mp
            self.seg = None
            if con_persona:
                self.seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
                    base_options=BaseOptions(model_asset_path=MODELO_PERSONA), running_mode=vision.RunningMode.IMAGE,
                    output_confidence_masks=True, output_category_mask=False))
            self.det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=MODELO_CARA), running_mode=vision.RunningMode.IMAGE,
                min_detection_confidence=0.5))
            # la primera pasada es la que suelta los avisos: se hace aquí, callada
            vacio = np.zeros((64, 64, 4), np.uint8)
            if self.seg:
                self.persona(vacio)
            self.caras(vacio)

    def cerrar(self):
        """Los modelos se quedan vivos hasta el final: cerrarlos a mano tarda ~5 s cada uno (MediaPipe espera a sus hilos).
        Al salir del programa sueltan unos avisos en inglés; `_callar_al_salir` los calla."""
        _VIVOS.append(self)

    def _imagen(self, rgba):
        return self.mp.Image(image_format=self.mp.ImageFormat.SRGBA, data=np.ascontiguousarray(rgba))

    def persona(self, rgba):
        """La confianza de «es persona» (0–1) de cada píxel, del tamaño de la imagen."""
        m = self.seg.segment(self._imagen(rgba)).confidence_masks[0].numpy_view()
        return np.array(m.reshape(m.shape[0], m.shape[1]), np.float32)

    def caras(self, rgba):
        """Las caras: [(x, y, ancho, alto, seguridad)] en píxeles de la imagen."""
        out = []
        for d in self.det.detect(self._imagen(rgba)).detections:
            b = d.bounding_box
            out.append((b.origin_x, b.origin_y, b.width, b.height, d.categories[0].score if d.categories else 0.0))
        return out


# ── La silueta como respaldo de la cara ─────────────────────────────────────────────────────────────────────────────
def cara_por_silueta(m):
    """(cx, cy, ancho) de la cara, EN FRACCIÓN del cuadro, a partir de la parte de arriba de la silueta (0–1). Sirve de
    respaldo cuando el detector no ve ninguna cara, y para saber dónde recortar la cabeza la primera vez."""
    h, w = m.shape
    filas = np.where((m > 0.5).sum(1) > w * 0.02)[0]
    if not len(filas):
        return None
    arriba = filas[0]
    franja = m[arriba:arriba + max(2, int(h * 0.06))] > 0.5
    xs = np.where(franja.any(0))[0]
    if not len(xs):
        return None
    ancho = max(4.0, (xs.max() - xs.min()) * 0.9)
    return (float(xs.mean()) / w, (arriba + ancho * 0.85) / h, ancho / w)


# ── Paso 3 y 4: que no parpadee y que quede limpia ──────────────────────────────────────────────────────────────────
def _limpiar(s):
    """Un cuadro: histéresis (lo seguro siembra), fuera las islas y tapados los agujeritos. `s` 0–1 → bool."""
    seguro = s > SEGURO
    duda = (s > DUDA).astype(np.uint8)
    k, etq, st, _ = cv2.connectedComponentsWithStats(duda, connectivity=8)
    if k <= 1 or not seguro.any():
        return np.zeros(s.shape, bool)
    con_seguro = np.zeros(k, bool)
    con_seguro[np.unique(etq[seguro])] = True
    con_seguro[0] = False
    areas = st[:, cv2.CC_STAT_AREA]
    grande = areas[1:][con_seguro[1:]].max() if con_seguro[1:].any() else 1
    vale = con_seguro & (areas >= ISLA * grande)
    b = vale[etq]
    return _tapar_agujeritos(b)


def _tapar_agujeritos(b):
    """Los agujeros pequeños que la persona encierra pasan a ser persona (la gorra con huecos). Los grandes no: el hueco
    entre el brazo y el cuerpo, con la silla detrás, es fondo de verdad."""
    h, w = b.shape
    fondo = (~b).astype(np.uint8)
    k, etq, st, _ = cv2.connectedComponentsWithStats(fondo, connectivity=4)
    if k <= 2:
        return b
    x, y, ww, hh, area = (st[:, i] for i in range(5))
    toca_borde = (x == 0) | (y == 0) | (x + ww >= w) | (y + hh >= h)
    tapar = (~toca_borde) & (area < AGUJERO * max(1, int(b.sum())))
    tapar[0] = False
    if not tapar[1:].any():
        return b
    return b | tapar[etq]


def _sin_islas(b):
    k, etq, st, _ = cv2.connectedComponentsWithStats(b.astype(np.uint8), connectivity=8)
    if k <= 2:
        return b
    areas = st[:, cv2.CC_STAT_AREA]
    vale = areas >= ISLA * areas[1:].max()
    vale[0] = False
    return vale[etq]


def estabilizar(conf, Y):
    """Pasos 3 y 4 de un trozo de tramo. `conf`: (n, h, w) uint8, la confianza del modelo; `Y`: (n, h, w) uint8, el brillo
    del cuadro (ya suavizado). Devuelve (n, h, w) bool. (Se llama por trozos de unos segundos: así la memoria no crece con
    lo largo que sea el efecto.)"""
    n = len(conf)
    escala = np.float32(1.0 / 255.0)

    def peso(t):
        """Cuánto pesa el cuadro t frente al anterior: poco si su imagen no cambió, todo si cambió."""
        d = np.abs(Y[t].astype(np.int16) - Y[t - 1].astype(np.int16)).astype(np.float32)
        return np.clip((d - QUIETO) * (1.0 / CAMBIO), PESO_QUIETO, 1.0)

    # hacia delante y hacia atrás: el promedio de las dos no tiene retraso
    s = np.empty(conf.shape, np.float32)
    s[0] = conf[0] * escala
    for t in range(1, n):
        s[t] = s[t - 1] + peso(t) * (conf[t] * escala - s[t - 1])
    vuelta = conf[-1] * escala
    s[-1] = (s[-1] + vuelta) * 0.5
    for t in range(n - 2, -1, -1):
        vuelta = vuelta + peso(t + 1) * (conf[t] * escala - vuelta)
        s[t] = (s[t] + vuelta) * 0.5
    b = np.stack([_limpiar(s[t]) for t in range(n)])
    # nada cambia por 1 o 2 cuadros
    for largo in (1, 2):
        for t in range(1, n - largo):
            antes, despues = b[t - 1], b[t + largo]
            arregla = antes == despues
            for j in range(largo):
                arregla &= b[t + j] != antes
            if arregla.any():
                for j in range(largo):
                    b[t + j][arregla] = antes[arregla]
    # la forma, suave: fuera lo fino que sobresale y tapadas las mellas
    redondo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for t in range(n):
        x = b[t].astype(np.uint8)
        x = cv2.morphologyEx(x, cv2.MORPH_OPEN, redondo)
        x = cv2.morphologyEx(x, cv2.MORPH_CLOSE, redondo)
        b[t] = _sin_islas(_tapar_agujeritos(x.astype(bool)))
    return b


# ── Paso 6: la cara, suave ──────────────────────────────────────────────────────────────────────────────────────────
def _ida_y_vuelta(x, peso):
    """Suaviza una serie sin retraso: una pasada hacia delante y otra hacia atrás."""
    y = x.copy()
    for t in range(1, len(y)):
        y[t] = y[t - 1] + peso * (y[t] - y[t - 1])
    for t in range(len(y) - 2, -1, -1):
        y[t] = y[t + 1] + peso * (y[t] - y[t + 1])
    return y


def suavizar_caras(crudas, respaldo):
    """`crudas`: por cuadro, (cx, cy, ancho) en fracción del cuadro, o None. `respaldo`: lo mismo sacado de la silueta.
    Devuelve (n, 3) float."""
    n = len(crudas)
    arr = np.full((n, 3), np.nan)
    for t, cc in enumerate(crudas):
        if cc is not None:
            arr[t] = cc
    validas = ~np.isnan(arr[:, 0])
    if validas.sum() == 0:                       # ninguna cara en todo el tramo: de la silueta
        for t, cc in enumerate(respaldo):
            if cc is not None:
                arr[t] = cc
        validas = ~np.isnan(arr[:, 0])
    if validas.sum() == 0:
        return np.tile(np.array([0.5, 0.33, 0.18]), (n, 1))
    idx = np.arange(n)
    for j in range(3):
        arr[:, j] = np.interp(idx, idx[validas], arr[validas, j])
    if n >= 5:                                   # fuera los saltos sueltos
        rel = np.pad(arr, ((2, 2), (0, 0)), mode='edge')
        arr = np.median(np.stack([rel[i:i + n] for i in range(5)]), axis=0)
    for j, peso in enumerate((0.35, 0.35, 0.12)):
        arr[:, j] = _ida_y_vuelta(arr[:, j], peso)
    return arr


# ── Paso 5: el borde, al pintar ─────────────────────────────────────────────────────────────────────────────────────
def _curva_borde():
    """La tabla del borde: un poco hacia dentro (fuera el halo del fondo) y firme pero sin dientes."""
    x = np.clip((np.arange(256, dtype=np.float32) / 255.0 - 0.22) / 0.56, 0.0, 1.0)
    return np.clip(x * x * (3.0 - 2.0 * x) * 255.0 + 0.5, 0, 255).astype(np.uint8)


_CURVA_BORDE = _curva_borde()


def afinar(b, cuadro):
    """La máscara pequeña (`b`, h × w, 0/1) al tamaño del cuadro (uint8, H × W × 3), con el borde pegado al de la imagen
    (filtro guiado rápido: se calcula pequeño y solo la última cuenta se hace grande). Devuelve H × W float32 de 0 a 1."""
    H, W = cuadro.shape[:2]
    hm, wm = b.shape
    if min(W, H) > LADO_CORTO_AFINAR:            # a 4K se afina a 1080 y se sube
        Wg, Hg = tamano_con_lado_corto(W, H, LADO_CORTO_AFINAR)
        guia_rgb = cv2.resize(cuadro, (Wg, Hg), interpolation=cv2.INTER_AREA)
    else:
        Wg, Hg, guia_rgb = W, H, cuadro
    guia = cv2.cvtColor(guia_rgb, cv2.COLOR_RGB2GRAY)
    g = cv2.resize(guia, (wm, hm), interpolation=cv2.INTER_AREA).astype(np.float32) * (1.0 / 255.0)
    p = cv2.GaussianBlur(b.astype(np.float32), (0, 0), 0.8)
    r = 4
    caja = (2 * r + 1, 2 * r + 1)
    mg = cv2.boxFilter(g, -1, caja)
    mp_ = cv2.boxFilter(p, -1, caja)
    var = cv2.boxFilter(g * g, -1, caja) - mg * mg
    cov = cv2.boxFilter(g * p, -1, caja) - mg * mp_
    a = cov / (var + 0.004)
    bb = mp_ - a * mg
    # q = A·guía + B a tamaño grande; la guía va de 0 a 255, así que A se divide entre 255
    A = cv2.resize(cv2.boxFilter(a, -1, caja) * (1.0 / 255.0), (Wg, Hg), interpolation=cv2.INTER_LINEAR)
    B = cv2.resize(cv2.boxFilter(bb, -1, caja), (Wg, Hg), interpolation=cv2.INTER_LINEAR)
    q = cv2.add(cv2.multiply(A, guia, dtype=cv2.CV_32F), B)
    q8 = cv2.convertScaleAbs(cv2.max(q, 0.0), alpha=255.0)       # de 0 a 255, sin negativos
    q8 = cv2.LUT(q8, _CURVA_BORDE)
    if (Wg, Hg) != (W, H):
        q8 = cv2.resize(q8, (W, H), interpolation=cv2.INTER_LINEAR)
    return np.multiply(q8, np.float32(1.0 / 255.0), dtype=np.float32)


# ── Las máscaras de una carpeta ─────────────────────────────────────────────────────────────────────────────────────
class CarpetaMascaras:
    """Una máscara por cuadro: 0000.png, 0001.png… (o las que haya, en orden). La máscara va en el canal alfa (blanco con
    transparencia, como las usa Remotion) o en gris."""

    def __init__(self, carpeta):
        if not os.path.isdir(carpeta):
            raise RuntimeError(f'No encuentro la carpeta de máscaras «{carpeta}».')
        self.carpeta = carpeta
        self.lista = sorted(n for n in os.listdir(carpeta) if n.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')))
        if not self.lista:
            raise RuntimeError(f'La carpeta de máscaras «{carpeta}» no tiene imágenes.')
        self.avisado = False
        self.avisado_rota = False
        self._ultimas = {}

    def leer(self, i, ancho, alto):
        """La máscara del cuadro i al tamaño pedido, float32 de 0 a 1."""
        nombre = f'{i:04d}.png'
        if nombre not in self.lista:
            if i >= len(self.lista) and not self.avisado:
                print(f'  Aviso: hay {len(self.lista)} máscaras y el vídeo tiene más cuadros; '
                      'en los que faltan se repite la última.')
                self.avisado = True
            nombre = self.lista[min(i, len(self.lista) - 1)]
        ruta = os.path.join(self.carpeta, nombre)
        im = cv2.imread(ruta, cv2.IMREAD_UNCHANGED) if os.path.isfile(ruta) else None
        if im is None:                                   # no se puede leer: la última que sí (mejor que ninguna)
            if not self.avisado_rota:
                print(f'  Aviso: no puedo leer la máscara «{nombre}»; en las que fallen uso la anterior.')
                self.avisado_rota = True
            previa = self._ultimas.get((ancho, alto))
            return previa.copy() if previa is not None else np.zeros((alto, ancho), np.float32)
        if im.ndim == 3 and im.shape[2] == 4 and im[..., 3].min() < 255:
            m = im[..., 3]
        elif im.ndim == 3:
            m = cv2.cvtColor(im[..., :3], cv2.COLOR_BGR2GRAY)
        else:
            m = im
        if m.dtype != np.uint8:
            m = (m.astype(np.float32) * (255.0 / np.iinfo(m.dtype).max)).astype(np.uint8)
        if m.shape[:2] != (alto, ancho):
            m = cv2.resize(m, (ancho, alto), interpolation=cv2.INTER_LINEAR if ancho > m.shape[1] else cv2.INTER_AREA)
        m = m.astype(np.float32) * (1.0 / 255.0)
        self._ultimas[(ancho, alto)] = m
        return m


# ── El trabajo de un tramo ──────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class Tramo:
    i0: int
    i1: int
    forma: tuple            # (h, w) de la máscara pequeña
    mascaras: object        # (n, bytes) bits empaquetados, o None si vienen de una carpeta
    caras: np.ndarray       # (n, 3): cx, cy, ancho en fracción del cuadro


class Persona:
    """Calcula la persona y la cara en los tramos con efecto y se las da al motor cuadro a cuadro."""

    def __init__(self, info, carpeta_mascaras=None, avisar=print):
        self.info = info
        self.avisar = avisar
        self.carpeta = CarpetaMascaras(carpeta_mascaras) if carpeta_mascaras else None
        self.wa, self.ha = tamano_con_lado_corto(info.ancho, info.alto, LADO_CORTO_ANALISIS)
        self.wm, self.hm = tamano_con_lado_corto(info.ancho, info.alto, LADO_CORTO_MASCARA)
        self.tramos = []
        self.modelos = None
        self.sin_detector = False
        self._ultima = None          # la última cara encontrada: (cx, cy, ancho) en fracción, y en qué cuadro
        self._ultima_i = -999
        self._v = None               # el tramo que se está mirando

    # pasada 1: mirar ----------------------------------------------------------------------------------------------
    def analizar(self, ventanas, lector_de):
        """Mira los cuadros de las `ventanas` [(i0, i1), …] (ordenadas y sin pisarse). `lector_de(ancho, alto, hasta)`
        devuelve un lector que da los cuadros desde el 0, del mismo modo que los da al pintar."""
        if not ventanas:
            return
        try:
            self.modelos = Modelos(con_persona=self.carpeta is None)
        except RuntimeError:
            if self.carpeta is None:
                raise
            self.sin_detector = True
            self.avisar('  Aviso: sin MediaPipe no busco la cara; la saco de la silueta de tus máscaras.')
        fin = ventanas[-1][1]
        lector = lector_de(self.wa, self.ha, fin)
        k = 0
        fps = self.info.fps
        try:
            for i in range(fin):
                crudo = lector.leer()
                if crudo is None:
                    break
                if i < ventanas[k][0]:
                    continue
                if i == ventanas[k][0]:
                    a, b = ventanas[k]
                    self.avisar(f'  Mirando a la persona: tramo {k + 1} de {len(ventanas)} '
                                f'({a / fps:.1f} s a {b / fps:.1f} s)…')
                    self._abrir(a)
                cuadro = np.frombuffer(crudo, np.uint8).reshape(self.ha, self.wa, 3)
                self._guardar(*self._mirar(i, cuadro))
                if i == ventanas[k][1] - 1:
                    self._cerrar()
                    k += 1
                    if k >= len(ventanas):
                        break
        finally:
            lector.cerrar()
        if self._v is not None:                      # el vídeo acabó antes de lo que decía
            self._cerrar()
        if self.modelos is not None:
            self.modelos.cerrar()
            self.modelos = None

    # cada tramo se estabiliza por trozos de BLOQUE cuadros, con SOLAPE cuadros de contexto a cada lado
    BLOQUE, SOLAPE = 180, 30

    def _abrir(self, i0):
        self._v = {'i0': i0, 'b0': i0, 'listo': i0, 'conf': [], 'brillo': [], 'caras': [], 'respaldo': [],
                   'mascaras': []}

    def _guardar(self, conf, brillo, cara, resp):
        v = self._v
        v['caras'].append(cara)
        if self.carpeta is not None:                 # las máscaras vienen hechas: solo hace falta la cara
            v['respaldo'].append(resp)
            return
        v['conf'].append(conf)
        v['brillo'].append(brillo)
        if len(v['conf']) >= self.BLOQUE + 2 * self.SOLAPE:
            self._trozo(final=False)

    def _trozo(self, final):
        """Estabiliza lo que hay en el búfer y guarda las máscaras que ya tienen contexto de los dos lados."""
        v = self._v
        if not v['conf']:
            return
        b = estabilizar(np.stack(v['conf']), np.stack(v['brillo']))
        ini = v['listo'] - v['b0']
        fin = len(b) if final else len(b) - self.SOLAPE
        for t in range(ini, fin):
            v['mascaras'].append(np.packbits(b[t].reshape(-1)))
            v['respaldo'].append(cara_por_silueta(b[t].astype(np.float32)))   # el respaldo de la cara, ya limpio
        v['listo'] = v['b0'] + fin
        if not final:                                # se quedan SOLAPE cuadros de contexto y SOLAPE sin guardar
            corte = len(b) - 2 * self.SOLAPE
            v['conf'] = v['conf'][corte:]
            v['brillo'] = v['brillo'][corte:]
            v['b0'] += corte

    def _cerrar(self):
        v = self._v
        self._v = None
        n = len(v['caras'])
        if n == 0:
            return
        mascaras = None
        if self.carpeta is None:
            self._v = v
            self._trozo(final=True)
            self._v = None
            mascaras = v['mascaras']
        self.tramos.append(Tramo(v['i0'], v['i0'] + n, (self.hm, self.wm), mascaras,
                                 suavizar_caras(v['caras'], v['respaldo'])))

    def _recorte_cabeza(self, guia):
        """El cuadrado alrededor de la cabeza (x0, y0, lado) en el cuadro de análisis."""
        cx, cy, ancho = guia[0] * self.wa, guia[1] * self.ha, guia[2] * self.wa
        lado = int(np.clip(3.4 * ancho, 0.30 * min(self.wa, self.ha), min(self.wa, self.ha)))
        x0 = int(round(np.clip(cx - lado / 2, 0, self.wa - lado)))
        y0 = int(round(np.clip(cy + 0.1 * lado - lado / 2, 0, self.ha - lado)))
        return x0, y0, lado

    def _mirar(self, i, cuadro):
        """Un cuadro de análisis → (confianza uint8 pequeña, brillo uint8 pequeño, cara o None, cara por silueta o None)."""
        reciente = self._ultima is not None and i - self._ultima_i <= 15
        if self.carpeta is not None:
            # con máscaras hechas, aquí solo sirven para saber dónde buscar la cara: se leen solo si hace falta (leer
            # una imagen grande por cuadro es lo que más tarda) y una de cada diez, para el respaldo
            y = None
            conf = self.carpeta.leer(i, self.wm, self.hm) if (not reciente or i % 10 == 0) else None
        else:
            pequeno = cv2.resize(cuadro, (self.wm, self.hm), interpolation=cv2.INTER_AREA)
            y = cv2.blur(cv2.cvtColor(pequeno, cv2.COLOR_RGB2GRAY), (3, 3))
            conf = self.modelos.persona(cv2.cvtColor(pequeno, cv2.COLOR_RGB2RGBA))
        resp = cara_por_silueta(conf) if conf is not None else None
        guia = self._ultima if reciente else resp
        cara = None
        if guia is not None and self.modelos is not None:
            x0, y0, lado = self._recorte_cabeza(guia)
            trozo = cv2.resize(cuadro[y0:y0 + lado, x0:x0 + lado], (256, 256), interpolation=cv2.INTER_AREA)
            trozo = cv2.cvtColor(trozo, cv2.COLOR_RGB2RGBA)
            if self.carpeta is None:
                conf = self._fundir_cabeza(conf, self.modelos.persona(trozo), x0, y0, lado)
            mejores = sorted(self.modelos.caras(trozo), key=lambda d: -d[4])
            if mejores:
                fx, fy, fw, fh, _ = mejores[0]
                k = lado / 256.0
                cara = ((x0 + (fx + fw / 2) * k) / self.wa, (y0 + (fy + fh / 2) * k) / self.ha, fw * k / self.wa)
                self._ultima, self._ultima_i = cara, i
        if self.carpeta is not None:
            return None, None, cara, resp
        return (np.clip(conf * 255 + 0.5, 0, 255).astype(np.uint8), y, cara, resp)

    def _fundir_cabeza(self, conf, cabeza, x0, y0, lado):
        """Pone la máscara del recorte de la cabeza (más fina) sobre la del cuadro entero, fundida hacia sus bordes (salvo
        los que coinciden con el borde del cuadro)."""
        k = self.wm / float(self.wa)
        X0, Y0 = int(round(x0 * k)), int(round(y0 * k))
        L = max(4, int(round(lado * k)))
        X1, Y1 = min(self.wm, X0 + L), min(self.hm, Y0 + L)
        L_x, L_y = X1 - X0, Y1 - Y0
        if L_x < 4 or L_y < 4:
            return conf
        cab = cv2.resize(cabeza, (L_x, L_y), interpolation=cv2.INTER_LINEAR)
        borde = max(2, int(0.14 * L))

        def rampa(n, pegado_ini, pegado_fin):
            r = np.ones(n, np.float32)
            v = np.linspace(0, 1, borde, dtype=np.float32)
            if not pegado_ini:
                r[:borde] = np.minimum(r[:borde], v)
            if not pegado_fin:
                r[-borde:] = np.minimum(r[-borde:], v[::-1])
            return r

        peso = np.outer(rampa(L_y, Y0 == 0, Y1 == self.hm), rampa(L_x, X0 == 0, X1 == self.wm))
        out = conf.copy()
        out[Y0:Y1, X0:X1] = conf[Y0:Y1, X0:X1] * (1 - peso) + cab * peso
        return out

    # pasada 2: dar la persona y la cara al pintar ------------------------------------------------------------------
    def tramo_de(self, i):
        for t in self.tramos:
            if t.i0 <= i < t.i1:
                return t
        return None

    def en(self, i, cuadro):
        """(máscara H × W float32 0–1, cara (cx, cy, ancho) en píxeles) del cuadro i, que se va a pintar (`cuadro`, uint8
        a su tamaño final)."""
        H, W = cuadro.shape[:2]
        t = self.tramo_de(i)
        if self.carpeta is not None:
            m = self.carpeta.leer(i, W, H)
        elif t is not None:
            n_px = t.forma[0] * t.forma[1]
            b = np.unpackbits(t.mascaras[i - t.i0])[:n_px].reshape(t.forma)
            m = afinar(b, cuadro)
        else:
            m = np.zeros((H, W), np.float32)
        if t is not None:
            cx, cy, an = t.caras[i - t.i0]
        else:
            r = cara_por_silueta(cv2.resize(m, (self.wm, self.hm), interpolation=cv2.INTER_AREA))
            cx, cy, an = r if r else (0.5, 0.33, 0.18)
        return m, (float(cx * W), float(cy * H), float(an * W))
