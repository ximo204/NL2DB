# Punto de entrada provisional: ejecuta los generadores directamente sobre un JSON de ejemplo.

from pathlib import Path

import graphviz

from src.representacion.modelo import cargar_desde_archivo
from src.generador_sql.generador import GeneradorSQLEstandar
from src.generador_er.generador import GeneradorERGraphviz


def main():
    raiz = Path(__file__).parent
    modelo = cargar_desde_archivo(raiz / "ejemplos" / "tienda_ropa.json")

    print("=== SQL ===\n")
    print(GeneradorSQLEstandar().generar(modelo))

    print("\n=== Diagrama E/R ===\n")
    salida = raiz / "salidas" / "tienda_ropa_er"
    try:
        ruta_svg = GeneradorERGraphviz().generar(modelo, salida)
        print(f"Diagrama renderizado en: {ruta_svg}")
    except graphviz.ExecutableNotFound:
        print(
            "El paquete Python 'graphviz' está instalado, pero falta el\n"
            "binario del sistema. En Linux: sudo apt install graphviz."
        )


if __name__ == "__main__":
    main()
