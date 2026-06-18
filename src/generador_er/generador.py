# Generador E/R: convierte la representación intermedia en un SVG con IDs por nodo.

from abc import ABC, abstractmethod
from pathlib import Path

import graphviz


class GeneradorER(ABC):
    """Contrato común del generador: descripcion_formal + renderizar + generar (atajo)."""

    @abstractmethod
    def descripcion_formal(self, modelo) -> str:
        ...

    @abstractmethod
    def renderizar(self, descripcion: str, ruta_salida) -> str:
        ...

    def generar(self, modelo, ruta_salida) -> str:
        return self.renderizar(self.descripcion_formal(modelo), ruta_salida)


class GeneradorERGraphviz(GeneradorER):
    """Implementación concreta sobre Graphviz."""

    def descripcion_formal(self, modelo) -> str:
        return self._construir_grafo(modelo).source

    def _construir_grafo(self, modelo) -> graphviz.Digraph:
        # Digraph con dir=none: necesitamos taillabel/headlabel para las
        # cardinalidades, pero las relaciones E/R no son direccionales.
        g = graphviz.Digraph("ER")
        g.attr(rankdir="LR")
        g.attr("node", shape="plaintext")
        g.attr("edge", dir="none", fontsize="10")

        for entidad in modelo.get("entidades", []):
            self._anadir_entidad(g, entidad)

        for relacion in modelo.get("relaciones", []):
            self._anadir_relacion(g, relacion)

        return g

    def _anadir_entidad(self, g: graphviz.Digraph, entidad: dict) -> None:
        nombre = entidad["nombre"]
        g.node(
            nombre,
            label=self._etiqueta_entidad(entidad),
            id=f"entidad_{nombre}",
        )

    def _etiqueta_entidad(self, entidad: dict) -> str:
        nombre = entidad["nombre"]
        filas = [
            f'<TR><TD BGCOLOR="lightgray" COLSPAN="2"><B>{nombre}</B></TD></TR>'
        ]
        for atr in entidad["atributos"]:
            filas.append(self._fila_atributo(atr))

        tabla = (
            '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">'
            + "".join(filas)
            + "</TABLE>"
        )
        # En Graphviz una etiqueta HTML va entre < ... >.
        return f"<{tabla}>"

    def _fila_atributo(self, atributo: dict) -> str:
        nombre = atributo["nombre"]
        tipo = atributo["tipo"]
        es_pk = atributo.get("clave_primaria", False)
        es_inferido = atributo.get("inferido", False)

        def decorar(texto: str) -> str:
            if es_pk:
                texto = f"<B>{texto}</B>"
            if es_inferido:
                texto = f"<I>{texto}</I>"
            return texto

        sufijo_pk = " (PK)" if es_pk else ""
        return (
            f'<TR><TD ALIGN="LEFT">{decorar(nombre)}{sufijo_pk}</TD>'
            f'<TD ALIGN="LEFT">{decorar(tipo)}</TD></TR>'
        )

    def _anadir_relacion(self, g: graphviz.Digraph, relacion: dict) -> None:
        ea = relacion["entidad_a"]
        eb = relacion["entidad_b"]
        nombre = relacion["nombre"]

        atributos_rel = relacion.get("atributos", [])
        if atributos_rel:
            nombres = ", ".join(a["nombre"] for a in atributos_rel)
            etiqueta = f"{nombre}\n[{nombres}]"
        else:
            etiqueta = nombre

        # Look-across: (min,max) junto a A = "¿cuántos A por cada B?".
        # min = 1 si la participación del otro lado es obligatoria, 0 si no.
        min_a = "1" if relacion["participacion_b"] == "obligatoria" else "0"
        max_a = relacion["cardinalidad_a"]
        min_b = "1" if relacion["participacion_a"] == "obligatoria" else "0"
        max_b = relacion["cardinalidad_b"]

        g.edge(
            ea,
            eb,
            label=etiqueta,
            taillabel=f"({min_a},{max_a})",
            headlabel=f"({min_b},{max_b})",
            id=f"relacion_{nombre}",
        )

    def renderizar(self, descripcion: str, ruta_salida) -> str:
        # ruta_salida sin extensión: graphviz añade .svg.
        ruta = Path(ruta_salida)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        src = graphviz.Source(descripcion, filename=str(ruta), format="svg")
        return src.render(cleanup=True)
