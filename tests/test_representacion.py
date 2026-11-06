# Historial de escenarios y trazabilidad por alineamiento léxico.

import pytest

from src.representacion import escenario as escenario_io
from src.representacion.escenario import Escenario, Interaccion
from src.representacion.gestor import GestorRepresentacionIntermedia


def interaccion(texto):
    return Interaccion(texto=texto, modelo={"entidades": []}, trazabilidad={})


@pytest.fixture
def gestor():
    gestor = GestorRepresentacionIntermedia()
    gestor.iniciar_escenario("prueba")
    return gestor


def test_retroceder_y_avanzar_no_borra_el_historial():
    escenario = Escenario("prueba")
    escenario.añadir(interaccion("primera"))
    escenario.añadir(interaccion("segunda"))

    assert escenario.retroceder() is True
    assert escenario.activa().texto == "primera"
    assert escenario.retroceder() is False
    assert escenario.avanzar() is True
    assert escenario.activa().texto == "segunda"
    assert len(escenario.interacciones) == 2


def test_una_interaccion_nueva_tras_retroceder_conserva_las_anteriores():
    escenario = Escenario("prueba")
    escenario.añadir(interaccion("primera"))
    escenario.añadir(interaccion("segunda"))
    escenario.retroceder()

    escenario.añadir(interaccion("tercera"))

    assert [i.texto for i in escenario.interacciones] == [
        "primera", "segunda", "tercera",
    ]
    assert escenario.activa().texto == "tercera"


def test_un_escenario_se_recupera_igual_tras_guardarlo(tmp_path):
    original = Escenario("prueba")
    original.añadir(interaccion("primera"))
    original.añadir(interaccion("segunda"))
    original.retroceder()

    escenario_io.guardar(original, tmp_path)
    recuperado = escenario_io.cargar("prueba", tmp_path)

    assert recuperado.serializar() == original.serializar()
    assert escenario_io.listar(tmp_path) == ["prueba"]


def test_cargar_un_escenario_inexistente_falla(tmp_path):
    with pytest.raises(FileNotFoundError):
        escenario_io.cargar("nada", tmp_path)


def test_el_gestor_exige_un_escenario_activo():
    with pytest.raises(RuntimeError):
        GestorRepresentacionIntermedia().añadir_interaccion({}, "texto")


def test_la_trazabilidad_manual_tiene_prioridad(gestor):
    manual = {"entidades": {"Venta": {"inicio": 0, "fin": 5}}, "relaciones": {}}
    gestor.añadir_interaccion({"entidades": []}, "texto", manual)
    assert gestor.consultar_trazabilidad() == manual


def test_el_alineamiento_ignora_tildes_y_mayusculas_sin_descuadrar_offsets(gestor):
    texto = "Hay una categoría. Cada préstamo tiene fecha."
    modelo = {"entidades": [{"nombre": "Prestamo"}], "relaciones": []}

    gestor.añadir_interaccion(modelo, texto)

    tramo = gestor.consultar_trazabilidad()["entidades"]["Prestamo"]
    assert texto[tramo["inicio"]:tramo["fin"]] == "préstamo tiene fecha."


def test_el_alineamiento_prueba_el_primer_termino_de_una_relacion(gestor):
    texto = "Cada socio realiza una reserva."
    modelo = {"entidades": [], "relaciones": [{"nombre": "realiza_reserva"}]}

    gestor.añadir_interaccion(modelo, texto)

    tramo = gestor.consultar_trazabilidad()["relaciones"]["realiza_reserva"]
    assert texto[tramo["inicio"]:tramo["fin"]] == "realiza una reserva."


def test_un_nombre_ausente_del_texto_queda_sin_trazabilidad(gestor):
    modelo = {"entidades": [{"nombre": "Factura"}], "relaciones": []}
    gestor.añadir_interaccion(modelo, "Cada socio tiene un nombre.")
    assert gestor.consultar_trazabilidad()["entidades"] == {}
