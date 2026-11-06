# Utilidades compartidas: construcción de modelos mínimos y acceso a los ejemplos.

import json
from pathlib import Path

import pytest

EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos"


def _entidad(nombre, pk="id", *otros_atributos):
    return {
        "nombre": nombre,
        "atributos": [
            {
                "nombre": pk,
                "tipo": "INTEGER",
                "clave_primaria": True,
                "nullable": False,
                "inferido": False,
            },
            *otros_atributos,
        ],
    }


def _relacion(nombre, ea, eb, ca, cb, pa="opcional", pb="opcional", atributos=None):
    return {
        "nombre": nombre,
        "entidad_a": ea,
        "entidad_b": eb,
        "cardinalidad_a": ca,
        "cardinalidad_b": cb,
        "participacion_a": pa,
        "participacion_b": pb,
        "atributos": atributos or [],
    }


@pytest.fixture
def entidad():
    return _entidad


@pytest.fixture
def relacion():
    return _relacion


@pytest.fixture(params=["tienda_ropa", "universidad"])
def ejemplo(request):
    """Cada ejemplo incluido en el repositorio, como (nombre, datos)."""
    ruta = EJEMPLOS / f"{request.param}.json"
    return request.param, json.loads(ruta.read_text(encoding="utf-8"))
