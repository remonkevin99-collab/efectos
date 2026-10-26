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


def _instalar(paquete):
    """Instala un paquete en este mismo Python: con pip si lo tiene y, si no (un .venv hecho con uv sin --seed), con uv."""
    import shutil
    tiene_pip = subprocess.run([sys.executable, '-m', 'pip', '--version'], capture_output=True).returncode == 0
    if tiene_pip:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', paquete], check=True)
    elif shutil.which('uv'):
        subprocess.run(['uv', 'pip', 'install', '-q', '--python', sys.executable, paquete], check=True)
    else:
        sys.exit(f'No puedo instalar {paquete}: este Python no tiene pip ni encuentro uv. Corre otra vez la instalación '
                 '(instalar.sh o instalar.ps1) y vuelve a probar.')


def con_mlx(ruta):
    import mlx_whisper  # noqa: F401  (solo si ya está instalado)
    r = mlx_whisper.transcribe(ruta, path_or_hf_repo='mlx-community/whisper-large-v3-turbo', word_timestamps=True,
                               language=os.environ.get('IDIOMA') or None)
    return [(w['word'].strip(), w['start'], w['end']) for s in r['segments'] for w in s.get('words', [])]


def con_faster(ruta):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print('Instalando el transcriptor (solo la primera vez, un minuto)…', flush=True)
        _instalar('faster-whisper')
        from faster_whisper import WhisperModel
    modelo = WhisperModel(os.environ.get('MODELO_WHISPER', 'small'), device='cpu', compute_type='int8')
    trozos, _ = modelo.transcribe(ruta, word_timestamps=True, vad_filter=True, language=os.environ.get('IDIOMA') or None)
    return [(w.word.strip(), w.start, w.end) for s in trozos for w in (s.words or [])]


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python motor/palabras.py tu_video.mp4')
    ruta = sys.argv[1]
    try:
        palabras = con_mlx(ruta)
    except ImportError:
        palabras = con_faster(ruta)
    salida = os.path.splitext(ruta)[0] + '.palabras.json'
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump([{'palabra': p, 'ini': round(a, 2), 'fin': round(b, 2)} for p, a, b in palabras], f, ensure_ascii=False, indent=0)
    for p, a, _ in palabras:
        print(f'{a:7.2f}  {p}')
    print(f'\n{len(palabras)} palabras guardadas en {salida}')


if __name__ == '__main__':
    main()
