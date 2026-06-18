# Punto de entrada provisional del validador (§3.9).
#
# Carga uno de los ejemplos del directorio ejemplos/ (con su JSON, su
# texto original embebido como _descripcion_usuario y su mapa de
# trazabilidad construido a mano), genera el diagrama E/R con el
# generador del §3.8 y produce el HTML autónomo del validador en
# salidas/.
#
# Este script juega el papel de "controlador" mínimo mientras no exista
# el real (§3.4): se limita a invocar a cada pieza en el orden adecuado
# y a pasarle a la siguiente lo que la anterior produjo.

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

    # Cargamos el JSON del modelo y extraemos el texto original que
    # tenemos embebido como metadato (mientras no exista el gestor de
    # RI completo, que es quien debería custodiar texto y modelo
    # juntos según el §3.7).
    modelo = cargar_desde_archivo(ruta_json)
    texto = modelo.get("_descripcion_usuario", "")
    if not texto:
        raise SystemExit(
            f"El ejemplo {nombre_ejemplo} no incluye _descripcion_usuario."
        )

    # El mapa de trazabilidad lo construimos a mano (§3.7.2) hasta que
    # el módulo NLP pueble el JSON desde texto real y el gestor de RI
    # construya la trazabilidad automáticamente.
    trazabilidad = json.loads(ruta_trazabilidad.read_text(encoding="utf-8"))

    # Generamos el SVG con el módulo del §3.8. Lo dejamos en salidas/
    # con un nombre por ejemplo para no pisar entre ejecuciones.
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
    # Sin argumentos lanza el ejemplo de la tienda de ropa por defecto,
    # que es el del §3.7.1.
    main(sys.argv[1] if len(sys.argv) > 1 else "tienda_ropa")
