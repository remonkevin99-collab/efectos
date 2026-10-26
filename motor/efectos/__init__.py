"""Los efectos: cada archivo de esta carpeta es uno (los que empiezan por «_» son ejemplos y no cuentan).

Cada módulo tiene:
- NOMBRE: el nombre del comando, en español y con guiones («orbita», «palabra-detras»…).
- DESCRIPCION: una frase sencilla de lo que hace.
- OPCIONES: los valores por defecto (todos en texto), en español.
- dibujar(c): cambia el cuadro `c.img` (ver `base.Cuadro`).
- Opcional: DURACION (segundos que le quedan bien si no se dice otra cosa).
"""
import importlib
import os
import pkgutil

TODOS = {}
for _m in pkgutil.iter_modules([os.path.dirname(__file__)]):
    if _m.name.startswith('_'):
        continue
    _mod = importlib.import_module(f'{__name__}.{_m.name}')
    if hasattr(_mod, 'NOMBRE') and hasattr(_mod, 'dibujar'):
        TODOS[_mod.NOMBRE] = _mod
