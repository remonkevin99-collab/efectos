"""El segundo exacto de cada palabra de un vídeo, para que un efecto caiga justo cuando dices algo.

    python motor/palabras.py tu_video.mp4

Escribe cada palabra con su segundo y deja `tu_video.palabras.json` al lado del vídeo. La primera vez instala el
transcriptor (faster-whisper, gratis y en tu computadora: el vídeo no sale de ella). En un Mac con `mlx-whisper`
instalado, usa ese, que va más rápido.
"""
import json
import os
import subprocess
import sys


def _instalar(*paquetes):
    """Instala paquetes en este mismo Python: con pip si lo tiene y, si no (un .venv hecho con uv sin --seed), con uv."""
    import shutil
    tiene_pip = subprocess.run([sys.executable, '-m', 'pip', '--version'], capture_output=True).returncode == 0
    uv = shutil.which('uv') or os.path.expanduser('~/.local/bin/uv')
    if tiene_pip:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *paquetes], check=True)
    elif os.path.exists(uv):
        subprocess.run([uv, 'pip', 'install', '-q', '--python', sys.executable, *paquetes], check=True)
    else:
        sys.exit(f'No puedo instalar {", ".join(paquetes)}: este Python no tiene pip ni encuentro uv. Corre otra vez la '
                 'instalación (instalar.sh o instalar.ps1) y vuelve a probar.')


def audio(ruta):
    """El audio del vídeo a 16 kHz y mono, con el volumen igualado: con un audio muy bajo (un micrófono lejos) el
    transcriptor no oía ninguna palabra. Se lee con el ffmpeg del motor y se le pasa ya hecho al transcriptor."""
    import numpy as np
    import imageio_ffmpeg
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-i', ruta, '-vn', '-ac', '1', '-ar', '16000',
                        '-af', 'loudnorm=I=-18:TP=-2:LRA=11', '-f', 'f32le', '-'], capture_output=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def con_mlx(a):
    import mlx_whisper  # noqa: F401  (solo si ya está instalado)
    r = mlx_whisper.transcribe(a, path_or_hf_repo='mlx-community/whisper-large-v3-turbo', word_timestamps=True,
                               language=os.environ.get('IDIOMA') or None)
    return [(w['word'].strip(), w['start'], w['end']) for s in r['segments'] for w in s.get('words', [])]


def con_faster(a):
    # sin los avisos en inglés de la descarga del modelo, que asustan a quien no programa
    os.environ.setdefault('HF_HUB_VERBOSITY', 'error')
    os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS', '1')
    import warnings
    warnings.filterwarnings('ignore')
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print('Instalando el transcriptor (solo la primera vez, un par de minutos)…', flush=True)
        # «av» 19 no encaja con faster-whisper 1.2 (open() ya no acepta metadata_errors): se fija la 18
        _instalar('faster-whisper', 'av<19')
        from faster_whisper import WhisperModel
    print('Preparando el modelo de voz (la primera vez baja unos 460 MB; después ya no)…', flush=True)
    modelo = WhisperModel(os.environ.get('MODELO_WHISPER', 'small'), device='cpu', compute_type='int8')
    idioma = os.environ.get('IDIOMA') or None
    # primero con el filtro de voz (quita silencios); si no saca nada, sin él
    for vad in (True, False):
        trozos, _ = modelo.transcribe(a, word_timestamps=True, vad_filter=vad, language=idioma)
        palabras = [(w.word.strip(), w.start, w.end) for s in trozos for w in (s.words or [])]
        if palabras:
            return palabras
    return []


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python motor/palabras.py tu_video.mp4')
    ruta = sys.argv[1]
    a = audio(ruta)
    if a.size < 16000 // 2:
        sys.exit('Este vídeo no tiene sonido (o dura menos de medio segundo): no hay palabras que sacar.')
    try:
        palabras = con_mlx(a)
    except ImportError:
        palabras = con_faster(a)
    salida = os.path.splitext(ruta)[0] + '.palabras.json'
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump([{'palabra': p, 'ini': round(a, 2), 'fin': round(b, 2)} for p, a, b in palabras], f, ensure_ascii=False, indent=0)
    for p, a, _ in palabras:
        print(f'{a:7.2f}  {p}')
    print(f'\n{len(palabras)} palabras guardadas en {salida}')
    if not palabras:
        print('No he entendido ninguna palabra: o no se oye voz, o el audio está muy bajo o con mucho ruido. Prueba con '
              'el micrófono más cerca.')


if __name__ == '__main__':
    main()
