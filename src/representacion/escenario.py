# Escenarios e interacciones: unidades de trabajo del usuario.

import json
from datetime import date, datetime
from pathlib import Path


class Interaccion:
    """Una pasada del usuario por el sistema dentro de un escenario."""

    def __init__(self, texto, modelo, trazabilidad, fecha=None):
        self.texto = texto
        self.modelo = modelo
        self.trazabilidad = trazabilidad
        self.fecha = fecha or datetime.now().isoformat(timespec="seconds")

    def serializar(self):
        return {
            "texto": self.texto,
            "modelo": self.modelo,
            "trazabilidad": self.trazabilidad,
            "fecha": self.fecha,
        }

    @classmethod
    def deserializar(cls, datos):
        return cls(
            texto=datos["texto"],
            modelo=datos["modelo"],
            trazabilidad=datos.get("trazabilidad") or {},
            fecha=datos.get("fecha"),
        )


class Escenario:
    """Conjunto cronológico de interacciones sobre un mismo planteamiento.

    Mantiene un puntero indice_activa: retroceder lo mueve atrás,
    añadir lo coloca al final. El historial nunca se borra.
    """

    def __init__(self, nombre, interacciones=None, indice_activa=None):
        self.nombre = nombre
        self.interacciones = list(interacciones) if interacciones else []
        if indice_activa is None:
            self.indice_activa = len(self.interacciones) - 1
        else:
            self.indice_activa = indice_activa

    def añadir(self, interaccion):
        """Añade una interacción al final y la deja como activa."""
        self.interacciones.append(interaccion)
        self.indice_activa = len(self.interacciones) - 1

    def activa(self):
        """Interacción que el usuario está viendo, o None."""
        if 0 <= self.indice_activa < len(self.interacciones):
            return self.interacciones[self.indice_activa]
        return None

    def hay_anterior(self):
        return self.indice_activa > 0

    def hay_siguiente(self):
        return self.indice_activa < len(self.interacciones) - 1

    def retroceder(self):
        """Mueve el puntero a la interacción anterior. True si pudo."""
        if self.hay_anterior():
            self.indice_activa -= 1
            return True
        return False

    def avanzar(self):
        """Mueve el puntero a la siguiente interacción. True si pudo."""
        if self.hay_siguiente():
            self.indice_activa += 1
            return True
        return False

    def serializar(self):
        return {
            "nombre": self.nombre,
            "interacciones": [i.serializar() for i in self.interacciones],
            "indice_activa": self.indice_activa,
        }

    @classmethod
    def deserializar(cls, datos):
        interacciones = [
            Interaccion.deserializar(i) for i in datos.get("interacciones", [])
        ]
        return cls(
            nombre=datos["nombre"],
            interacciones=interacciones,
            indice_activa=datos.get("indice_activa", len(interacciones) - 1),
        )


def directorio_escenarios(raiz_proyecto):
    """Ruta del directorio de escenarios, creándolo si hace falta."""
    ruta = Path(raiz_proyecto) / "escenarios"
    ruta.mkdir(exist_ok=True)
    return ruta


def guardar(escenario, raiz_proyecto):
    """Persiste el escenario en disco. Sobrescribe el fichero anterior."""
    ruta = directorio_escenarios(raiz_proyecto) / f"{escenario.nombre}.json"
    ruta.write_text(
        json.dumps(escenario.serializar(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ruta


def cargar(nombre, raiz_proyecto):
    """Recupera un escenario por nombre. Lanza FileNotFoundError si no existe."""
    ruta = directorio_escenarios(raiz_proyecto) / f"{nombre}.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return Escenario.deserializar(datos)


def listar(raiz_proyecto):
    """Nombres de escenarios disponibles, ordenados por fecha de modificación descendente."""
    directorio = directorio_escenarios(raiz_proyecto)
    return [
        p.stem
        for p in sorted(
            directorio.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
    ]


def nombre_por_defecto():
    """Nombre asignado al escenario cuando el usuario no escribe ninguno."""
    return date.today().isoformat()
