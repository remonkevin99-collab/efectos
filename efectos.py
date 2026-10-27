"""Motor de efectos de vídeo de Kevin Remón: le pone efectos a un vídeo vertical de alguien hablando a cámara (cosas
detrás de la persona, tarjetas, letreros) con un comando. Código MIT (ver LICENSE).

Uso:
  python efectos.py --lista                                   los efectos que hay, con sus opciones
  python efectos.py orbita video.mp4 --desde 2 --hasta 6      un efecto suelto
  python efectos.py orbita video.mp4 --op imagenes=portadas   …con opciones (clave=valor, las que quieras)
  python efectos.py video.mp4 --plan plan.json                varios efectos a la vez, con un plan
  python efectos.py --comprobar                               mira que todo esté bien instalado

Opciones:
  --salida archivo.mp4   dónde guardarlo (por defecto, <nombre>_efectos.mp4 al lado del vídeo)
  --ancho 1080           el ancho del vídeo final (2160 = 4K); el alto, proporcional
  --fotos 1.2,3.4        en vez del vídeo, guarda esos segundos en PNG para revisar rápido
  --mascaras carpeta     usa tus propias máscaras de la persona (0000.png, 0001.png…) en vez de calcularlas
  --recorte normal       en un Mac, no usa el recorte fino del sistema (de fábrica, «auto»: en Mac lo usa)
  --calidad 18           la calidad del vídeo (de 0 a 51: más bajo, mejor y más pesado; 18 se ve igual que el original)
  --rapidez medium       cuánto se esfuerza al comprimir: ultrafast … medium … slow (más lento, archivo más pequeño)

El plan es un JSON así:
  {"efectos": [
     {"efecto": "orbita", "desde": 1.2, "hasta": 4.0, "opciones": {"imagenes": "portadas"}},
     {"efecto": "palabra-detras", "desde": 5, "hasta": 8, "opciones": {"texto": "HOLA"}}
  ]}
Los nombres valen con tilde o sin ella («órbita» = «orbita»).
"""
import argparse
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, 'motor'))

AYUDA = __doc__.split('\n', 3)[3] if __doc__ else ''


class _Argumentos(argparse.ArgumentParser):
    """argparse, pero los errores en español."""

    def error(self, mensaje):
        for en, es in (('unrecognized arguments', 'no conozco estas opciones'),
                       ('expected one argument', 'le falta el valor'),
                       ('invalid float value', 'no es un número'),
                       ('invalid int value', 'no es un número entero'),
                       ('argument', 'la opción')):
            mensaje = mensaje.replace(en, es)
        print(f'Error en el comando: {mensaje}\nPara ver cómo se usa: python efectos.py --ayuda', file=sys.stderr)
        sys.exit(2)


def lista():
    import nucleo
    todos = nucleo.efectos()
    print(f'Hay {len(todos)} efectos:\n')
    for clave in sorted(todos):
        mod = todos[clave]
        dur = getattr(mod, 'DURACION', None)
        print(f'  {mod.NOMBRE}' + (f'   (le quedan bien {dur:g} s)' if dur else ''))
        print(f'      {getattr(mod, "DESCRIPCION", "")}')
        op = getattr(mod, 'OPCIONES', {})
        if op:
            print('      opciones: ' + ' · '.join(f'{k}={v!s}' if v != '' else f'{k}=(nada)' for k, v in op.items()))
        print()
    for nombre, error in nucleo.efectos_que_no_cargan().items():
        print(f'  ({nombre}: no carga por un error: {error})')


def comprobar():
    """Mira que todo esté instalado y funcione. Devuelve 0 si sí."""
    bien = True

    def mal(texto):
        nonlocal bien
        bien = False
        print('  MAL  ' + texto)

    print('Comprobando el motor de efectos…')
    v = sys.version_info
    if (3, 10) <= v[:2] <= (3, 12):
        print(f'  bien Python {v[0]}.{v[1]}')
    else:
        mal(f'Python {v[0]}.{v[1]}: hace falta 3.10, 3.11 o 3.12 (MediaPipe). Corre la instalación y usa su .venv.')
    for paquete in ('numpy', 'PIL', 'cv2', 'mediapipe'):
        try:
            __import__(paquete)
            print(f'  bien {paquete}')
        except Exception as e:
            mal(f'{paquete} no está ({e}). Corre la instalación.')
    import subprocess
    import nucleo
    try:
        ff = nucleo.buscar_ffmpeg()
        cod = subprocess.run([ff, '-hide_banner', '-encoders'], capture_output=True, text=True).stdout
        if 'libx264' in cod:
            print(f'  bien ffmpeg ({ff})')
        else:
            mal(f'tu ffmpeg ({ff}) no tiene libx264 para guardar en MP4. Instala uno completo (brew install ffmpeg).')
    except nucleo.ErrorMotor as e:
        mal(str(e))
    try:
        import persona
        persona.Modelos().cerrar()
        print('  bien los modelos de Google (la persona y la cara)')
    except Exception as e:
        mal(str(e))
    try:
        import persona
        ok, por_que = persona.probar_recorte_mac()
        print('  recorte fino del Mac: ' + ('sí' if ok else f'no ({por_que})'))
    except Exception as e:
        print(f'  recorte fino del Mac: no ({e})')
    todos = nucleo.efectos()
    print(f'  bien {len(todos)} efectos: {", ".join(sorted(m.NOMBRE for m in todos.values()))}')
    for nombre, error in nucleo.efectos_que_no_cargan().items():
        mal(f'el efecto «{nombre}» no carga: {error}')
    print('Todo bien.' if bien else 'Hay cosas que arreglar (arriba).')
    return 0 if bien else 1


def main(argv=None):
    # en Windows, si la salida va a un archivo, algún carácter (→) no cabe en su codificación: se cambia por «?» en vez de
    # parar el programa
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors='replace')
        except Exception:
            pass
    ap = _Argumentos(prog='efectos.py', add_help=False)
    ap.add_argument('cosas', nargs='*')
    ap.add_argument('-h', '--ayuda', '--help', action='store_true')
    ap.add_argument('--lista', action='store_true')
    ap.add_argument('--comprobar', action='store_true')
    ap.add_argument('--plan')
    ap.add_argument('--desde', type=float)
    ap.add_argument('--hasta', type=float)
    ap.add_argument('--duracion', type=float)
    ap.add_argument('--op', action='append', default=[])
    ap.add_argument('--salida')
    ap.add_argument('--ancho', type=int, default=1080)
    ap.add_argument('--fotos')
    ap.add_argument('--mascaras')
    ap.add_argument('--calidad', type=int, default=18)
    ap.add_argument('--rapidez', default='medium')
    ap.add_argument('--recorte', default='auto')
    a = ap.parse_args(argv)

    if a.ayuda or (not a.cosas and not a.lista and not a.comprobar):
        print(AYUDA)
        return 0
    if a.lista:
        lista()
        return 0
    if a.comprobar:
        return comprobar()

    import nucleo
    try:
        cosas = list(a.cosas)
        plan = a.plan
        video = None
        efecto = None
        # qué es cada cosa: el vídeo es el archivo que existe y no es un .json
        for x in cosas:
            if x.lower().endswith('.json'):
                plan = x
            elif os.path.isfile(x) and video is None:
                video = x
            elif efecto is None:
                efecto = x
            else:
                raise nucleo.ErrorMotor(f'No sé qué es «{x}». ¿El vídeo existe? Para ver cómo se usa: --ayuda')
        if video is None:
            raise nucleo.ErrorMotor('Falta el vídeo (o no lo encuentro). Ejemplo: python efectos.py orbita mi-video.mp4')
        if plan and efecto:
            raise nucleo.ErrorMotor('O un efecto suelto o un plan, no los dos a la vez.')
        if not plan and not efecto:
            raise nucleo.ErrorMotor('Falta qué efecto poner (o un --plan). Para verlos: python efectos.py --lista')
        if efecto:
            opciones = {}
            for kv in a.op:
                if '=' not in kv:
                    raise nucleo.ErrorMotor(f'La opción «{kv}» tiene que ir como clave=valor (por ejemplo, texto=HOLA).')
                k, v = kv.split('=', 1)
                opciones[k.strip()] = v
            mod = nucleo.buscar_efecto(efecto)
            desde = a.desde if a.desde is not None else 0.0
            if a.hasta is not None:
                hasta = a.hasta
            else:
                hasta = desde + (a.duracion if a.duracion is not None else float(getattr(mod, 'DURACION', 3.0)))
            plan = {'efectos': [{'efecto': efecto, 'desde': desde, 'hasta': hasta, 'opciones': opciones}]}
        elif a.op or a.desde is not None or a.hasta is not None:
            print('Aviso: con un plan, --desde, --hasta y --op no se usan (van dentro del plan).')
        fotos = [float(x) for x in a.fotos.replace(' ', '').split(',') if x] if a.fotos else None
        nucleo.procesar(video, plan, salida=a.salida, ancho=a.ancho, fotos=fotos, mascaras=a.mascaras,
                        calidad=a.calidad, rapidez=a.rapidez, recorte=a.recorte.strip().lower())
        return 0
    except nucleo.ErrorMotor as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nParado.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
