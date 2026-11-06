# La ETL es la frontera con el LLM: su salida se trata como entrada no fiable.

import json

import pytest

from src.etl.etl import ErrorETL, FaseETL


@pytest.fixture
def etl():
    return FaseETL()


@pytest.fixture
def modelo_valido(entidad, relacion):
    return {
        "entidades": [entidad("Cliente"), entidad("Pedido")],
        "relaciones": [relacion("realiza", "Cliente", "Pedido", "1", "N")],
    }


@pytest.mark.parametrize(
    "envoltorio",
    [
        "{}",
        "```json\n{}\n```",
        "```\n{}\n```",
        "¡Claro! Aquí tienes el modelo:\n\n{}\n\nEspero que te resulte útil.",
    ],
    ids=["limpio", "vallas_json", "vallas_sin_lenguaje", "con_prosa"],
)
def test_extrae_el_mismo_modelo_de_cualquier_envoltorio(etl, modelo_valido, envoltorio):
    respuesta = envoltorio.replace("{}", json.dumps(modelo_valido))
    assert etl.procesar(respuesta) == etl.procesar(json.dumps(modelo_valido))


def test_normaliza_cardinalidad_y_participacion(etl, modelo_valido):
    relacion = modelo_valido["relaciones"][0]
    relacion["cardinalidad_b"] = "n"
    relacion["participacion_a"] = "  OBLIGATORIA "

    resultado = etl.procesar(json.dumps(modelo_valido))["relaciones"][0]

    assert resultado["cardinalidad_b"] == "N"
    assert resultado["participacion_a"] == "obligatoria"


def test_una_clave_primaria_nunca_es_nullable(etl, modelo_valido):
    modelo_valido["entidades"][0]["atributos"][0]["nullable"] = True
    resultado = etl.procesar(json.dumps(modelo_valido))
    assert resultado["entidades"][0]["atributos"][0]["nullable"] is False


@pytest.mark.parametrize(
    "valor, esperado",
    [("true", True), ("false", False), ("sí", True), (True, True), (False, False)],
)
def test_convierte_booleanos_escritos_como_cadena(etl, modelo_valido, valor, esperado):
    atributo = {"nombre": "activo", "tipo": "BOOLEAN", "nullable": valor}
    modelo_valido["entidades"][0]["atributos"].append(atributo)

    resultado = etl.procesar(json.dumps(modelo_valido))

    assert resultado["entidades"][0]["atributos"][1]["nullable"] is esperado


def test_conserva_la_razon_de_un_elemento_inferido(etl, modelo_valido):
    atributo = modelo_valido["entidades"][0]["atributos"][0]
    atributo.update(inferido=True, razon="  Clave sintética.  ")

    resultado = etl.procesar(json.dumps(modelo_valido))["entidades"][0]["atributos"][0]

    assert resultado["inferido"] is True
    assert resultado["razon"] == "Clave sintética."


def test_ignora_campos_que_no_forman_parte_del_modelo(etl, modelo_valido):
    modelo_valido["_descripcion_usuario"] = "texto"
    assert "_descripcion_usuario" not in etl.procesar(json.dumps(modelo_valido))


@pytest.mark.parametrize(
    "respuesta",
    ["", "   ", None, "Lo siento, no he sabido modelar eso.", "{ esto no es json", "[1, 2]"],
    ids=["vacia", "espacios", "none", "sin_json", "json_roto", "lista"],
)
def test_rechaza_respuestas_sin_un_modelo(etl, respuesta):
    with pytest.raises(ErrorETL):
        etl.procesar(respuesta)


def test_rechaza_un_modelo_sin_entidades(etl):
    with pytest.raises(ErrorETL, match="entidades"):
        etl.procesar('{"entidades": [], "relaciones": []}')


def test_rechaza_un_atributo_sin_nombre(etl, modelo_valido):
    del modelo_valido["entidades"][0]["atributos"][0]["nombre"]
    with pytest.raises(ErrorETL, match="nombre"):
        etl.procesar(json.dumps(modelo_valido))


def test_rechaza_una_entidad_sin_clave_primaria(etl, modelo_valido):
    modelo_valido["entidades"][0]["atributos"][0]["clave_primaria"] = False
    with pytest.raises(ErrorETL, match="clave primaria"):
        etl.procesar(json.dumps(modelo_valido))


@pytest.mark.parametrize(
    "campo, valor",
    [("cardinalidad_a", "M"), ("participacion_b", "a veces")],
)
def test_rechaza_valores_fuera_de_dominio(etl, modelo_valido, campo, valor):
    modelo_valido["relaciones"][0][campo] = valor
    with pytest.raises(ErrorETL, match="no válida"):
        etl.procesar(json.dumps(modelo_valido))


@pytest.mark.parametrize("campo", ["entidad_a", "entidad_b"])
def test_rechaza_relaciones_hacia_entidades_no_definidas(etl, modelo_valido, campo):
    modelo_valido["relaciones"][0][campo] = "Fantasma"
    with pytest.raises(ErrorETL, match="Fantasma"):
        etl.procesar(json.dumps(modelo_valido))


def test_acepta_los_ejemplos_incluidos(etl, ejemplo):
    _, datos = ejemplo
    resultado = etl.procesar(json.dumps(datos, ensure_ascii=False))
    assert len(resultado["entidades"]) == len(datos["entidades"])
    assert len(resultado["relaciones"]) == len(datos["relaciones"])
