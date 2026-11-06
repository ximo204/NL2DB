# Flujo completo con el NLP simulado y sin Graphviz ni ficheros reales.

import json

import pytest

from src.controlador.controlador import Controlador
from src.etl.etl import FaseETL
from src.generador_sql.generador import GeneradorSQLEstandar
from src.nlp.nlp import ErrorNLP, ModuloNLPSimulado
from src.representacion.gestor import GestorRepresentacionIntermedia

TEXTO_VALIDO = "Tengo clientes."
TEXTO_INVALIDO = "Respuesta rota."


class GeneradorERFalso:
    def generar(self, modelo, ruta_salida):
        return f"{ruta_salida}.svg"


class ValidadorFalso:
    def generar(self, modelo, texto, trazabilidad, ruta_svg, ruta_salida):
        return ruta_salida


@pytest.fixture
def controlador(entidad):
    modelo = {"entidades": [entidad("Cliente")], "relaciones": []}
    return Controlador(
        nlp=ModuloNLPSimulado({
            TEXTO_VALIDO: "```json\n" + json.dumps(modelo) + "\n```",
            TEXTO_INVALIDO: "Lo siento, no he sabido modelar eso.",
        }),
        etl=FaseETL(),
        gestor=GestorRepresentacionIntermedia(),
        generador_er=GeneradorERFalso(),
        validador=ValidadorFalso(),
        generador_sql=GeneradorSQLEstandar(),
    )


def test_el_flujo_completo_produce_validador_y_sql(controlador):
    ruta = controlador.procesar_descripcion(TEXTO_VALIDO, None, "salida", "prueba")

    assert ruta == "salida_validador.html"
    assert "CREATE TABLE Cliente" in controlador.generar_sql()


def test_no_se_genera_sql_sin_un_modelo_activo(controlador):
    with pytest.raises(RuntimeError):
        controlador.generar_sql()


def test_una_respuesta_rechazada_no_modifica_el_estado(controlador):
    controlador.procesar_descripcion(TEXTO_VALIDO, None, "salida", "prueba")

    ruta = controlador.procesar_descripcion(TEXTO_INVALIDO, None, "salida", "prueba")

    assert ruta is None
    assert len(controlador.escenario_actual().interacciones) == 1
    assert "CREATE TABLE Cliente" in controlador.generar_sql()


def test_un_fallo_del_nlp_no_modifica_el_estado(controlador):
    ruta = controlador.procesar_descripcion("Texto desconocido.", None, "salida")

    assert ruta is None
    assert controlador.escenario_actual() is None


def test_se_puede_retroceder_y_avanzar_entre_interacciones(controlador):
    controlador.procesar_descripcion(TEXTO_VALIDO, None, "salida", "prueba")
    controlador.procesar_descripcion(TEXTO_VALIDO, None, "salida", "prueba")

    assert controlador.hay_interaccion_anterior() is True
    assert controlador.retroceder("salida") == "salida_validador.html"
    assert controlador.hay_interaccion_siguiente() is True
    assert controlador.avanzar("salida") == "salida_validador.html"


def test_el_simulado_rechaza_textos_que_no_conoce():
    with pytest.raises(ErrorNLP):
        ModuloNLPSimulado({}).analizar("Texto desconocido.")
