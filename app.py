# Punto de entrada integrado: ejecuta el flujo completo para un ejemplo dado.

import json
import os
import sys
from pathlib import Path

from src.nlp.nlp import ModuloNLPSimulado, ModuloNLPOllama
from src.etl.etl import FaseETL
from src.representacion.gestor import GestorRepresentacionIntermedia
from src.generador_er.generador import GeneradorERGraphviz
from src.validador.validador import ValidadorWeb
from src.generador_sql.generador import GeneradorSQLEstandar
from src.controlador.controlador import Controlador


def main(nombre_ejemplo: str) -> None:
    raiz = Path(__file__).parent
    datos = json.loads(
        (raiz / "ejemplos" / f"{nombre_ejemplo}.json").read_text(encoding="utf-8")
    )
    texto = datos["_descripcion_usuario"]

    backend = os.environ.get("NLP_BACKEND", "simulado").lower()
    if backend == "ollama":
        modelo = os.environ.get("OLLAMA_MODELO", "qwen2.5:7b")
        print(f"[app] Usando ModuloNLPOllama con modelo '{modelo}'.")
        # Timeout generoso: qwen2.5:7b en CPU puede tardar ~10 min por descripción.
        nlp = ModuloNLPOllama(modelo=modelo, timeout=1200)
        # Con el LLM real la trazabilidad manual del ejemplo puede no cuadrar;
        # pasamos None y el gestor la construye por alineamiento léxico.
        trazabilidad = None
    else:
        print("[app] Usando ModuloNLPSimulado (respuesta enlatada).")
        respuesta_llm = (
            "```json\n" + json.dumps(datos, ensure_ascii=False, indent=2) + "\n```"
        )
        nlp = ModuloNLPSimulado({texto: respuesta_llm})
        trazabilidad = json.loads(
            (raiz / "ejemplos" / f"{nombre_ejemplo}_trazabilidad.json").read_text(
                encoding="utf-8"
            )
        )

    controlador = Controlador(
        nlp=nlp,
        etl=FaseETL(),
        gestor=GestorRepresentacionIntermedia(),
        generador_er=GeneradorERGraphviz(),
        validador=ValidadorWeb(),
        generador_sql=GeneradorSQLEstandar(),
        raiz_proyecto=raiz,
    )

    base_salida = raiz / "salidas" / nombre_ejemplo

    print("=== Flujo 1: generación y validación del modelo conceptual ===")
    ruta_html = controlador.procesar_descripcion(
        texto, trazabilidad, base_salida, nombre_escenario=nombre_ejemplo
    )
    if ruta_html is None:
        raise SystemExit("El flujo 1 no se ha completado (ver mensaje de la ETL).")
    print(f"Validador generado en: {ruta_html}")
    print(f"Ábrelo con: xdg-open {ruta_html}")

    print("\n=== Flujo 2: generación del SQL (tras la validación) ===\n")
    print(controlador.generar_sql())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tienda_ropa")
