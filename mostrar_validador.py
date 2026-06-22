# Genera el HTML del validador para un ejemplo dado sin pasar por el servidor web.

import json
import sys
from pathlib import Path

from src.representacion.modelo import cargar_desde_archivo
from src.generador_er.generador import GeneradorERGraphviz
from src.validador.validador import ValidadorWeb


def main(nombre_ejemplo: str) -> None:
    raiz = Path(__file__).parent
    ruta_json = raiz / "ejemplos" / f"{nombre_ejemplo}.json"
    ruta_trazabilidad = raiz / "ejemplos" / f"{nombre_ejemplo}_trazabilidad.json"

    modelo = cargar_desde_archivo(ruta_json)
    texto = modelo.get("_descripcion_usuario", "")
    if not texto:
        raise SystemExit(
            f"El ejemplo {nombre_ejemplo} no incluye _descripcion_usuario."
        )

    trazabilidad = json.loads(ruta_trazabilidad.read_text(encoding="utf-8"))

    ruta_svg_base = raiz / "salidas" / f"{nombre_ejemplo}_er"
    ruta_svg = GeneradorERGraphviz().generar(modelo, ruta_svg_base)

    # Y finalmente el validador produce el HTML autónomo.
    ruta_html = raiz / "salidas" / f"{nombre_ejemplo}_validador.html"
    ValidadorWeb().generar(
        modelo=modelo,
        texto=texto,
        trazabilidad=trazabilidad,
        ruta_svg=ruta_svg,
        ruta_salida=ruta_html,
    )

    print(f"Validador generado en: {ruta_html}")
    print(f"Ábrelo con: xdg-open {ruta_html}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tienda_ropa")
