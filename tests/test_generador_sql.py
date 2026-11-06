# Reglas de paso a tablas. El DDL se ejecuta en SQLite para comprobar que es válido.

import sqlite3

import pytest

from src.generador_sql.generador import GeneradorSQLEstandar


@pytest.fixture
def generar():
    return GeneradorSQLEstandar().generar


def base_de_datos(sql):
    """Ejecuta el DDL en una base de datos en memoria, con claves ajenas activas."""
    conexion = sqlite3.connect(":memory:")
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.executescript(sql)
    return conexion


def columnas(conexion, tabla):
    return {fila[1]: fila for fila in conexion.execute(f"PRAGMA table_info({tabla})")}


def claves_ajenas(conexion, tabla):
    """Conjunto de (columna, tabla_referenciada, columna_referenciada)."""
    return {
        (fila[3], fila[2], fila[4])
        for fila in conexion.execute(f"PRAGMA foreign_key_list({tabla})")
    }


def es_not_null(conexion, tabla, columna):
    return columnas(conexion, tabla)[columna][3] == 1


def tablas(conexion):
    consulta = "SELECT name FROM sqlite_master WHERE type = 'table'"
    return {fila[0] for fila in conexion.execute(consulta)}


def test_cada_entidad_produce_una_tabla_con_su_clave_primaria(generar, entidad):
    atributo = {"nombre": "email", "tipo": "VARCHAR(100)", "nullable": True}
    conexion = base_de_datos(
        generar({"entidades": [entidad("Cliente", "id", atributo)], "relaciones": []})
    )

    tabla = columnas(conexion, "Cliente")

    assert set(tabla) == {"id", "email"}
    assert tabla["id"][5] == 1
    assert es_not_null(conexion, "Cliente", "id")
    assert not es_not_null(conexion, "Cliente", "email")


def test_una_clave_primaria_compuesta_va_en_una_sola_restriccion(generar, entidad):
    segunda = {"nombre": "linea", "tipo": "INTEGER", "clave_primaria": True}
    conexion = base_de_datos(
        generar({"entidades": [entidad("Linea", "pedido", segunda)], "relaciones": []})
    )
    tabla = columnas(conexion, "Linea")
    assert (tabla["pedido"][5], tabla["linea"][5]) == (1, 2)


@pytest.mark.parametrize(
    "relacion_args",
    [("1", "N"), ("N", "1")],
    ids=["1_a_N", "N_a_1"],
)
def test_en_1_n_la_clave_ajena_va_en_el_lado_n(generar, entidad, relacion, relacion_args):
    ca, cb = relacion_args
    lado_n, lado_1 = ("B", "A") if cb == "N" else ("A", "B")
    modelo = {
        "entidades": [entidad("A"), entidad("B")],
        "relaciones": [relacion("rel", "A", "B", ca, cb)],
    }

    conexion = base_de_datos(generar(modelo))

    assert claves_ajenas(conexion, lado_n) == {("rel_id", lado_1, "id")}
    assert claves_ajenas(conexion, lado_1) == set()


@pytest.mark.parametrize(
    "participacion, not_null",
    [("obligatoria", True), ("opcional", False)],
)
def test_la_participacion_decide_si_la_clave_ajena_admite_nulos(
    generar, entidad, relacion, participacion, not_null
):
    modelo = {
        "entidades": [entidad("A"), entidad("B")],
        "relaciones": [relacion("rel", "A", "B", "1", "N", pb=participacion)],
    }
    conexion = base_de_datos(generar(modelo))
    assert es_not_null(conexion, "B", "rel_id") is not_null


@pytest.mark.parametrize(
    "pa, pb, tabla_con_fk",
    [
        ("opcional", "obligatoria", "B"),
        ("obligatoria", "opcional", "A"),
        ("opcional", "opcional", "A"),
        ("obligatoria", "obligatoria", "A"),
    ],
)
def test_en_1_1_la_clave_ajena_se_coloca_segun_la_participacion(
    generar, entidad, relacion, pa, pb, tabla_con_fk
):
    modelo = {
        "entidades": [entidad("A"), entidad("B")],
        "relaciones": [relacion("rel", "A", "B", "1", "1", pa, pb)],
    }

    sql = generar(modelo)
    conexion = base_de_datos(sql)

    otra = "B" if tabla_con_fk == "A" else "A"
    assert claves_ajenas(conexion, tabla_con_fk) == {("rel_id", otra, "id")}
    assert claves_ajenas(conexion, otra) == set()
    assert "rel_id INTEGER" in sql and "UNIQUE" in sql


def test_una_relacion_1_1_no_admite_dos_filas_con_la_misma_referencia(
    generar, entidad, relacion
):
    modelo = {
        "entidades": [entidad("A"), entidad("B")],
        "relaciones": [relacion("rel", "A", "B", "1", "1", "obligatoria", "obligatoria")],
    }
    conexion = base_de_datos(generar(modelo))
    conexion.execute("INSERT INTO B (id) VALUES (1)")
    conexion.execute("INSERT INTO A (id, rel_id) VALUES (1, 1)")
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("INSERT INTO A (id, rel_id) VALUES (2, 1)")


def test_una_relacion_1_n_reflexiva_no_colisiona_con_la_clave_primaria(
    generar, entidad, relacion
):
    modelo = {
        "entidades": [entidad("Empleado")],
        "relaciones": [relacion("supervisa", "Empleado", "Empleado", "1", "N")],
    }
    conexion = base_de_datos(generar(modelo))
    assert claves_ajenas(conexion, "Empleado") == {("supervisa_id", "Empleado", "id")}


def test_n_m_genera_tabla_intermedia_con_clave_compuesta(generar, entidad, relacion):
    cantidad = {"nombre": "cantidad", "tipo": "INTEGER"}
    modelo = {
        "entidades": [entidad("Venta", "id_venta"), entidad("Producto", "id_producto")],
        "relaciones": [
            relacion("incluye", "Venta", "Producto", "N", "N", atributos=[cantidad])
        ],
    }

    conexion = base_de_datos(generar(modelo))
    tabla = columnas(conexion, "Venta_Producto")

    assert set(tabla) == {"id_venta", "id_producto", "cantidad"}
    assert (tabla["id_venta"][5], tabla["id_producto"][5]) == (1, 2)
    assert claves_ajenas(conexion, "Venta_Producto") == {
        ("id_venta", "Venta", "id_venta"),
        ("id_producto", "Producto", "id_producto"),
    }


def test_n_m_reflexiva_no_duplica_columnas_ni_restricciones(generar, entidad, relacion):
    modelo = {
        "entidades": [entidad("Curso", "id_curso")],
        "relaciones": [relacion("requiere", "Curso", "Curso", "N", "N")],
    }

    conexion = base_de_datos(generar(modelo))

    assert set(columnas(conexion, "Curso_Curso")) == {
        "requiere_a_id_curso",
        "requiere_b_id_curso",
    }
    assert claves_ajenas(conexion, "Curso_Curso") == {
        ("requiere_a_id_curso", "Curso", "id_curso"),
        ("requiere_b_id_curso", "Curso", "id_curso"),
    }


def test_n_m_entre_entidades_con_pk_homonimas_no_duplica_columnas(
    generar, entidad, relacion
):
    modelo = {
        "entidades": [entidad("A", "codigo"), entidad("B", "codigo")],
        "relaciones": [relacion("rel", "A", "B", "N", "N")],
    }
    conexion = base_de_datos(generar(modelo))
    assert claves_ajenas(conexion, "A_B") == {
        ("rel_a_codigo", "A", "codigo"),
        ("rel_b_codigo", "B", "codigo"),
    }


def test_varias_n_m_entre_las_mismas_entidades_generan_tablas_distintas(
    generar, entidad, relacion
):
    modelo = {
        "entidades": [entidad("Socio", "id_socio"), entidad("Libro", "id_libro")],
        "relaciones": [
            relacion("reserva", "Socio", "Libro", "N", "N"),
            relacion("presta", "Socio", "Libro", "N", "N"),
        ],
    }
    conexion = base_de_datos(generar(modelo))
    assert {"Socio_Libro_reserva", "Socio_Libro_presta"} <= tablas(conexion)


def test_el_ddl_de_los_ejemplos_es_ejecutable(generar, ejemplo):
    _, datos = ejemplo
    conexion = base_de_datos(generar(datos))
    assert {e["nombre"] for e in datos["entidades"]} <= tablas(conexion)
