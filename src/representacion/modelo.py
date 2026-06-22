# Ayudante para cargar el JSON del modelo desde disco sin pasar por el LLM.

import json
from pathlib import Path


def cargar_desde_archivo(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))
