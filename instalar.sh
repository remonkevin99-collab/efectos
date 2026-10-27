#!/usr/bin/env bash
# Instala el motor de efectos (Mac y Linux). Se puede correr las veces que quieras: lo que ya está, no se toca.
#
#     bash instalar.sh
#
# Hace tres cosas, todas dentro de esta carpeta:
#   1. crea el entorno de Python en .venv (Python 3.10, 3.11 o 3.12; si tienes `uv`, lo usa y él baja Python si falta),
#   2. instala lo necesario (requirements.txt),
#   3. baja los dos modelos de Google (la persona y la cara) a modelos/.
# Y en un Mac, una cuarta: prepara el recorte fino del sistema (motor/sujeto.swift → motor/bin/sujeto). Si no se puede,
# avisa y sigue: el motor funciona igual con su recorte normal.
# Y al final comprueba que todo funciona y dice LISTO.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$AQUI"
VENV="$AQUI/.venv"
PY="$VENV/bin/python"

echo "== Motor de efectos: instalación =="

# ── ffmpeg ──────────────────────────────────────────────────────────────────────────────────────────────────────────
if command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg: lo tienes ($(command -v ffmpeg))"
else
  echo "ffmpeg: no está instalado en tu sistema. No pasa nada: se usará el que trae el paquete imageio-ffmpeg."
  echo "        (Si quieres el tuyo: en Mac, 'brew install ffmpeg'; en Ubuntu/Debian, 'sudo apt install ffmpeg'.)"
fi

# ── ¿el .venv que ya hay sirve? (Python 3.10 a 3.12) ──────────────────────────────────────────────────────────────
venv_sirve() {
  [ -x "$PY" ] && "$PY" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)' 2>/dev/null
}

if venv_sirve; then
  echo "Python: ya hay un entorno en .venv ($("$PY" --version 2>&1)), se usa ese."
elif command -v uv >/dev/null 2>&1; then
  echo "Python: creando .venv con uv (Python 3.12; si no lo tienes, uv lo baja)..."
  rm -rf "$VENV"
  uv venv --seed --python 3.12 "$VENV"
else
  BASE=""
  for candidato in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidato" >/dev/null 2>&1 && \
       "$candidato" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)' 2>/dev/null; then
      BASE="$candidato"
      break
    fi
  done
  if [ -z "$BASE" ]; then
    echo ""
    echo "ERROR: falta Python 3.10, 3.11 o 3.12 (MediaPipe todavía no funciona con versiones más nuevas)."
    echo "  La forma más fácil: instala uv (https://docs.astral.sh/uv/) y vuelve a correr este archivo; uv baja Python solo."
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  O instala Python 3.12 a mano:"
    echo "    Mac:           brew install python@3.12   (o el instalador de https://www.python.org/downloads/)"
    echo "    Ubuntu/Debian: sudo apt install python3.12 python3.12-venv"
    exit 1
  fi
  echo "Python: creando .venv con $BASE ($("$BASE" --version 2>&1))..."
  rm -rf "$VENV"
  "$BASE" -m venv "$VENV"
fi

# un .venv viejo hecho con uv puede no tener pip (y el transcriptor de palabras lo usa): se le pone
if ! "$PY" -m pip --version >/dev/null 2>&1 && command -v uv >/dev/null 2>&1; then
  uv pip install --quiet --python "$PY" pip
fi

# ── los paquetes ────────────────────────────────────────────────────────────────────────────────────────────────────
echo "Paquetes: instalando lo de requirements.txt (la primera vez tarda un par de minutos)..."
if command -v uv >/dev/null 2>&1; then
  uv pip install --quiet --python "$PY" -r requirements.txt
else
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r requirements.txt
fi

# ── los modelos de Google ───────────────────────────────────────────────────────────────────────────────────────────
mkdir -p modelos
bajar() {   # bajar <archivo> <dirección>
  local destino="modelos/$1"
  if [ -s "$destino" ]; then
    echo "Modelo: $1 ya está."
    return
  fi
  echo "Modelo: bajando $1..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$2" -o "$destino.parte"
  else
    "$PY" -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' "$2" "$destino.parte"
  fi
  mv "$destino.parte" "$destino"
}
bajar selfie_segmenter.tflite \
  "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"
bajar blaze_face_short_range.tflite \
  "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"

# ── el recorte fino del Mac (solo en Mac) ───────────────────────────────────────────────────────────────────────────
if [ "$(uname -s)" = "Darwin" ]; then
  if [ -x motor/bin/sujeto ] && [ ! motor/sujeto.swift -nt motor/bin/sujeto ]; then
    echo "Recorte fino del Mac: ya está."
  elif xcode-select -p >/dev/null 2>&1 && command -v swiftc >/dev/null 2>&1; then
    echo "Recorte fino del Mac: preparándolo..."
    mkdir -p motor/bin
    if swiftc -O motor/sujeto.swift -o motor/bin/sujeto.parte >/dev/null 2>&1; then
      mv motor/bin/sujeto.parte motor/bin/sujeto
      echo "Recorte fino del Mac: listo."
    else
      rm -f motor/bin/sujeto.parte
      echo "Recorte fino del Mac: no se pudo preparar (hace falta macOS 14 o más nuevo). Funciona igual, con el recorte normal."
    fi
  else
    echo "Recorte fino del Mac: para tenerlo, corre 'xcode-select --install' y después este archivo otra vez. Sin eso funciona igual."
  fi
fi

# ── la prueba final ─────────────────────────────────────────────────────────────────────────────────────────────────
"$PY" efectos.py --comprobar
echo ""
echo "Para usarlo (desde esta carpeta):"
echo "  .venv/bin/python efectos.py --lista"
echo "  .venv/bin/python efectos.py orbita mi-video.mp4 --desde 2 --hasta 6"
echo ""
echo "LISTO"
