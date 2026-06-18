# Generador de SQL — §3.10 del TFG.
#
# A partir del JSON de la representación intermedia (§3.7.1) construye las
# sentencias DDL que crean el esquema en un SGBD relacional. La memoria
# describe este componente como una "interfaz abstracta" para soportar
# distintos dialectos (MySQL, PostgreSQL, SQLite...). Por eso aquí tenemos
# una base abstracta + una implementación concreta sobre SQL estándar.
#
# Las reglas que aplicamos son las del §2.4.2 (paso a tablas) y §3.10.1.
# Dos cosas que el TFG remarca y que conviene tener bien presentes:
#
#   1) La participación de cada lado importa, no solo la cardinalidad.
#      En 1:N la FK del lado N lleva NOT NULL si su participación es
#      "obligatoria"; en 1:1 la FK va precisamente en el lado obligatorio
#      (si solo uno lo es), no por defecto en entidad_a.
#
#   2) El nombre de la columna FK no puede ser simplemente el nombre de
#      la PK referenciada: choca con la propia PK en relaciones reflexivas
#      y consigo misma cuando hay varias relaciones entre el mismo par
#      de entidades. Por eso prefijamos siempre con el nombre de la
#      relación: <nombre_relacion>_<col_pk>.
#
# Resumen de reglas:
#   - cada entidad         -> CREATE TABLE
#   - cada atributo        -> columna con NOT NULL si nullable=false
#   - clave_primaria=true  -> CONSTRAINT pk_<Tabla> PRIMARY KEY (...)
#   - relación 1:N         -> FK en el lado N, columna <rel>_<col_pk>,
#                             CONSTRAINT fk_<Tabla>_<rel>, NOT NULL si la
#                             participación de ese lado es obligatoria
#   - relación N:M         -> tabla intermedia con PK compuesta y dos FKs
#                             (en la intermedia se usan los nombres de PK
#                             directamente, sin prefijo: no colisionan)
#   - relación 1:1         -> FK + UNIQUE en el lado obligatorio (si solo
#                             uno lo es), o en entidad_a por defecto si
#                             ambos son opcionales o ambos obligatorios
#
# El campo "inferido" del JSON no se usa aquí: es metainformación dirigida
# al módulo validador (§3.9.1) para distinguir lo que dijo el usuario de
# lo que rellenó el sistema. Para el SQL es irrelevante.

from abc import ABC, abstractmethod


class GeneradorSQL(ABC):
    """Contrato común para todos los dialectos SQL.

    Es la "interfaz abstracta" de la §3.10. La estructura general de las
    sentencias y las reglas del §2.4.2 / §3.10.1 son las mismas para
    cualquier SGBD; lo que cambia entre dialectos son detalles como los
    nombres de los tipos. Por ahora solo tenemos un dialecto, pero
    dejamos la jerarquía montada porque el TFG lo exige.
    """

    @abstractmethod
    def generar(self, modelo):
        ...


class GeneradorSQLEstandar(GeneradorSQL):
    """Implementación sobre SQL estándar (ANSI), sin extensiones de SGBD."""

    def generar(self, modelo):
        bloques = []

        # 1) Una CREATE TABLE por cada entidad. Pasamos el modelo entero a
        #    la rutina porque para cada entidad hay que mirar las relaciones
        #    1:N o 1:1 que la convierten en lado-N o lado-FK: esas añaden
        #    columnas y cláusulas FOREIGN KEY a su tabla.
        for entidad in modelo.get("entidades", []):
            bloques.append(self._crear_tabla_entidad(entidad, modelo))

        # 2) Después, las tablas intermedias de las relaciones N:M. Las
        #    dejamos al final porque referencian a tablas que ya están
        #    creadas en el bloque anterior.
        for relacion in modelo.get("relaciones", []):
            if self._es_n_a_m(relacion):
                bloques.append(self._crear_tabla_intermedia(relacion, modelo))

        return "\n\n".join(bloques)

    # ---------------------------------------------------------------- #
    # CREATE TABLE de una entidad

    def _crear_tabla_entidad(self, entidad, modelo):
        nombre_tabla = entidad["nombre"]
        lineas = []

        # Columnas propias declaradas en la entidad.
        for atributo in entidad["atributos"]:
            lineas.append(self._linea_columna(atributo))

        # Columnas FK que vienen de relaciones donde esta entidad recibe
        # la clave ajena. Las separamos en una lista aparte porque la
        # cláusula FOREIGN KEY va al final, después del PRIMARY KEY.
        fks = []
        for relacion in modelo.get("relaciones", []):
            fk = self._fk_para_entidad(relacion, entidad, modelo)
            if fk is not None:
                lineas.append(fk["linea_columna"])
                fks.append(fk)

        # PRIMARY KEY de la entidad. Convención del §3.10.1: pk_<NombreTabla>.
        # Si la PK es compuesta de varios atributos, todos van dentro del
        # mismo CONSTRAINT (no se puede repetir PRIMARY KEY en cada columna).
        nombres_pk = [a["nombre"] for a in entidad["atributos"] if a.get("clave_primaria")]
        if nombres_pk:
            lineas.append(
                f"CONSTRAINT pk_{nombre_tabla} PRIMARY KEY ({', '.join(nombres_pk)})"
            )

        # Cláusulas FOREIGN KEY al final.
        for fk in fks:
            lineas.append(fk["clausula_fk"])

        cuerpo = ",\n    ".join(lineas)
        return f"CREATE TABLE {nombre_tabla} (\n    {cuerpo}\n);"

    def _linea_columna(self, atributo):
        # Formato sencillo "nombre TIPO [NOT NULL]". El "NOT NULL" se
        # añade salvo que el atributo esté marcado como nullable.
        partes = [atributo["nombre"], atributo["tipo"]]
        if not atributo.get("nullable", False):
            partes.append("NOT NULL")
        return " ".join(partes)

    # ---------------------------------------------------------------- #
    # Reglas para FK en 1:N y 1:1

    def _fk_para_entidad(self, relacion, entidad, modelo):
        """Si la relación deposita una FK en `entidad`, devuelve sus datos.

        Hay tres casos del §3.10.1 que generan FK en una tabla "normal"
        (no intermedia):

          - 1:N : la FK va en el lado N, referencia al lado 1.
          - N:1 : igual, pero con los lados intercambiados.
          - 1:1 : FK con UNIQUE en el lado que tiene participación
                  obligatoria (si solo uno la tiene). Si ambos son
                  opcionales o ambos obligatorios, por convención la
                  ponemos en entidad_a.

        La nulabilidad de la FK depende de la participación del lado que
        la recibe: "obligatoria" -> NOT NULL, "opcional" -> admite NULL.
        Esto es exactamente lo que añade el §2.4.2 con respecto a generar
        SQL teniendo en cuenta la participación.

        Las N:M no caen aquí: producen una tabla intermedia aparte.
        """
        ca = relacion["cardinalidad_a"]
        cb = relacion["cardinalidad_b"]
        pa = relacion["participacion_a"]
        pb = relacion["participacion_b"]
        ea = relacion["entidad_a"]
        eb = relacion["entidad_b"]
        nombre_relacion = relacion["nombre"]
        nombre_entidad = entidad["nombre"]

        # 1:N -> FK en el lado b (el N), apunta al lado a (el 1).
        if ca == "1" and cb == "N" and nombre_entidad == eb:
            return self._datos_fk(
                referenciada=ea,
                modelo=modelo,
                unique=False,
                not_null=(pb == "obligatoria"),
                nombre_relacion=nombre_relacion,
                nombre_constraint=f"fk_{nombre_entidad}_{nombre_relacion}",
            )

        # N:1 -> mismo caso, lados invertidos.
        if ca == "N" and cb == "1" and nombre_entidad == ea:
            return self._datos_fk(
                referenciada=eb,
                modelo=modelo,
                unique=False,
                not_null=(pa == "obligatoria"),
                nombre_relacion=nombre_relacion,
                nombre_constraint=f"fk_{nombre_entidad}_{nombre_relacion}",
            )

        # 1:1 -> FK + UNIQUE. El lado donde va depende de la
        # participación, no es siempre entidad_a (§2.4.2).
        if ca == "1" and cb == "1":
            # Si solo B es obligatoria, la FK va en B referenciando a A.
            # En el resto de casos (solo A obligatoria, ambos opcionales,
            # ambos obligatorios) la FK va en A referenciando a B.
            if pb == "obligatoria" and pa != "obligatoria":
                lado_con_fk, referenciada = eb, ea
                not_null = True
            else:
                lado_con_fk, referenciada = ea, eb
                not_null = (pa == "obligatoria")

            if nombre_entidad == lado_con_fk:
                return self._datos_fk(
                    referenciada=referenciada,
                    modelo=modelo,
                    unique=True,
                    not_null=not_null,
                    nombre_relacion=nombre_relacion,
                    nombre_constraint=f"fk_{nombre_entidad}_{nombre_relacion}",
                )

        return None

    def _datos_fk(self, referenciada, modelo, unique, not_null,
                  nombre_relacion, nombre_constraint):
        # Convención de nombres de columna FK: <nombre_relacion>_<col_pk>.
        # Prefijar con el nombre de la relación garantiza unicidad dentro
        # de la tabla incluso en los dos casos que rompen el nombre directo:
        #   - Relación reflexiva: la PK referenciada existe ya en la propia
        #     tabla. Sin prefijo, colisionaría.
        #   - Varias relaciones entre el mismo par de entidades: todas
        #     traerían el mismo nombre de columna. Sin prefijo, colisionan.
        # El nombre de la relación es único en el modelo, así que el prefijo
        # discrimina sin ambigüedad.
        pk_col, tipo = self._pk_de(referenciada, modelo)
        col = f"{nombre_relacion}_{pk_col}"

        partes = [col, tipo]
        if not_null:
            partes.append("NOT NULL")
        if unique:
            partes.append("UNIQUE")
        linea_columna = " ".join(partes)

        clausula_fk = (
            f"CONSTRAINT {nombre_constraint} "
            f"FOREIGN KEY ({col}) REFERENCES {referenciada}({pk_col})"
        )
        return {"linea_columna": linea_columna, "clausula_fk": clausula_fk}

    # ---------------------------------------------------------------- #
    # Tabla intermedia de una relación N:M

    def _crear_tabla_intermedia(self, relacion, modelo):
        ea = relacion["entidad_a"]
        eb = relacion["entidad_b"]
        # Convención del §3.10.1: <EntidadA>_<EntidadB>.
        nombre_tabla = f"{ea}_{eb}"

        col_a, tipo_a = self._pk_de(ea, modelo)
        col_b, tipo_b = self._pk_de(eb, modelo)

        # En la tabla intermedia las dos FK son siempre NOT NULL,
        # porque forman parte de la PK compuesta. La participación de
        # cada extremo sigue siendo informativa, pero a nivel SQL aquí
        # no cambia la nulabilidad.
        lineas = [
            f"{col_a} {tipo_a} NOT NULL",
            f"{col_b} {tipo_b} NOT NULL",
        ]

        # Atributos propios de la relación (p. ej., 'cantidad' en incluye).
        for atributo in relacion.get("atributos", []):
            lineas.append(self._linea_columna(atributo))

        # PK compuesta + dos FOREIGN KEY a las tablas referenciadas.
        # Convenciones de nombres: pk_<TablaIntermedia> y
        # fk_<TablaIntermedia>_<TablaReferenciada>.
        lineas.append(
            f"CONSTRAINT pk_{nombre_tabla} "
            f"PRIMARY KEY ({col_a}, {col_b})"
        )
        lineas.append(
            f"CONSTRAINT fk_{nombre_tabla}_{ea} "
            f"FOREIGN KEY ({col_a}) REFERENCES {ea}({col_a})"
        )
        lineas.append(
            f"CONSTRAINT fk_{nombre_tabla}_{eb} "
            f"FOREIGN KEY ({col_b}) REFERENCES {eb}({col_b})"
        )

        cuerpo = ",\n    ".join(lineas)
        comentario = (
            f"-- Tabla intermedia generada por la relación N:M entre {ea} y {eb}"
        )
        return f"{comentario}\nCREATE TABLE {nombre_tabla} (\n    {cuerpo}\n);"

    # ---------------------------------------------------------------- #
    # Utilidades pequeñas

    def _pk_de(self, nombre_entidad, modelo):
        # Asumimos que la entidad tiene al menos un atributo con
        # clave_primaria=true y que la PK es simple (un único atributo).
        # El TFG no contempla ahora mismo PK compuestas en entidades
        # "normales" — las tablas intermedias se construyen aparte.
        entidad = next(e for e in modelo["entidades"] if e["nombre"] == nombre_entidad)
        pk = next(a for a in entidad["atributos"] if a.get("clave_primaria"))
        return pk["nombre"], pk["tipo"]

    def _es_n_a_m(self, relacion):
        return (
            relacion["cardinalidad_a"] == "N"
            and relacion["cardinalidad_b"] == "N"
        )
