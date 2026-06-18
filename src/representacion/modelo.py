# Helper temporal para el módulo de representación intermedia (§3.7).
#
# El gestor de RI completo (Construir, Consultar modelo, Consultar trazabilidad,
# Restaurar) se implementará cuando lo integremos con el validador y el
# controlador: necesita el texto original del usuario para construir el mapa
# de trazabilidad, y ahora mismo no tenemos ese texto.
#
# Mientras tanto, exponemos un único ayudante para cargar el JSON desde disco
# y poder probar los generadores sin pasar por el LLM. Es la versión "pruebas
# preparadas" que menciona la §1.4 de la metodología.

import json
from pathlib import Path


def cargar_desde_archivo(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))
