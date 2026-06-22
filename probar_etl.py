# Demostración de la fase ETL sin LLM: pasa respuestas crudas sintéticas y comprueba
# que produce un JSON limpio o reporta un error claro.

import json

from src.etl.etl import FaseETL, ErrorETL

# JSON base bien formado, que reutilizamos envuelto de varias maneras.
JSON_BASE = """{
  "entidades": [
    {"nombre": "Cliente", "atributos": [
      {"nombre": "id_cliente", "tipo": "INTEGER", "clave_primaria": true, "nullable": false, "inferido": true},
      {"nombre": "nombre", "tipo": "VARCHAR(100)", "clave_primaria": false, "nullable": false, "inferido": true}
    ]}
  ],
  "relaciones": []
}"""

casos = {
    "1. JSON limpio":
        JSON_BASE,

    "2. Envuelto en vallas markdown":
        "```json\n" + JSON_BASE + "\n```",

    "3. Con prosa del modelo alrededor":
        "¡Claro! Aquí tienes el modelo:\n\n" + JSON_BASE
        + "\n\nEspero que te resulte útil.",

    "4. Inconsistencias menores (cardinalidad en minúscula, PK marcada nullable)":
        '{"entidades": [{"nombre": "A", "atributos": ['
        '{"nombre": "id", "tipo": "INTEGER", "clave_primaria": true, "nullable": true, "inferido": false}]}],'
        '"relaciones": [{"nombre": "rel", "entidad_a": "A", "entidad_b": "A",'
        '"cardinalidad_a": "1", "cardinalidad_b": "n",'
        '"participacion_a": "Opcional", "participacion_b": "opcional", "atributos": []}]}',

    "5. Falta un campo obligatorio (error esperado)":
        '{"entidades": [{"nombre": "A", "atributos": ['
        '{"tipo": "INTEGER", "clave_primaria": true}]}], "relaciones": []}',

    "6. La respuesta no contiene JSON (error esperado)":
        "Lo siento, no he sabido modelar eso.",
}


def main() -> None:
    etl = FaseETL()
    for titulo, entrada in casos.items():
        print("=" * 72)
        print(titulo)
        try:
            modelo = etl.procesar(entrada)
            print("  OK → " + json.dumps(modelo, ensure_ascii=False))
        except ErrorETL as e:
            print(f"  ERROR ETL → {e}")


if __name__ == "__main__":
    main()
