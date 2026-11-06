# La descripción DOT no necesita Graphviz; el render sí requiere el binario `dot`.

import shutil
from pathlib import Path

import pytest

from src.generador_er.generador import GeneradorERGraphviz

necesita_graphviz = pytest.mark.skipif(
    shutil.which("dot") is None,
    reason="El binario de Graphviz no está instalado.",
)


@pytest.fixture
def generador():
    return GeneradorERGraphviz()


@pytest.fixture
def modelo(entidad, relacion):
    cantidad = {"nombre": "cantidad", "tipo": "INTEGER"}
    inferido = {"nombre": "alias", "tipo": "TEXT", "inferido": True}
    return {
        "entidades": [entidad("Venta", "id_venta", inferido), entidad("Producto")],
        "relaciones": [
            relacion(
                "incluye", "Venta", "Producto", "N", "N",
                pa="obligatoria", atributos=[cantidad],
            )
        ],
    }


def test_la_descripcion_incluye_entidades_y_relaciones(generador, modelo):
    dot = generador.descripcion_formal(modelo)
    assert "entidad_Venta" in dot
    assert "entidad_Producto" in dot
    assert "relacion_incluye" in dot


def test_marca_la_clave_primaria_y_los_atributos_inferidos(generador, modelo):
    dot = generador.descripcion_formal(modelo)
    assert "id_venta</B> (PK)" in dot
    assert "<I>alias</I>" in dot


def test_muestra_los_atributos_de_la_relacion(generador, modelo):
    assert "[cantidad]" in generador.descripcion_formal(modelo)


def test_la_cardinalidad_minima_sale_de_la_participacion_opuesta(generador, modelo):
    dot = generador.descripcion_formal(modelo)
    assert 'taillabel="(0,N)"' in dot
    assert 'headlabel="(1,N)"' in dot


@necesita_graphviz
def test_renderiza_un_svg_con_identificadores_para_la_trazabilidad(
    generador, ejemplo, tmp_path
):
    nombre, datos = ejemplo

    ruta = Path(generador.generar(datos, tmp_path / nombre))

    svg = ruta.read_text(encoding="utf-8")
    assert ruta.suffix == ".svg"
    for entidad in datos["entidades"]:
        assert f'id="entidad_{entidad["nombre"]}"' in svg
    for relacion in datos["relaciones"]:
        assert f'id="relacion_{relacion["nombre"]}"' in svg
