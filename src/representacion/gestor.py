# Gestor de representación intermedia: custodia el escenario activo y construye la trazabilidad.

import unicodedata

from src.representacion.escenario import Escenario, Interaccion


class GestorRepresentacionIntermedia:
    """Custodia el escenario activo y sirve sus datos al resto del sistema."""

    def __init__(self):
        self._escenario = None

    def iniciar_escenario(self, nombre):
        """Empieza un escenario nuevo y lo deja como activo."""
        self._escenario = Escenario(nombre=nombre)

    def abrir_escenario(self, escenario):
        """Instala un escenario ya construido como activo."""
        self._escenario = escenario

    def cerrar_escenario(self):
        """Deja al gestor sin escenario activo (el JSON en disco se conserva)."""
        self._escenario = None

    def escenario_actual(self):
        return self._escenario

    def hay_escenario(self):
        return self._escenario is not None

    def añadir_interaccion(self, modelo, texto, trazabilidad=None):
        """Registra una interacción; si no llega trazabilidad la construye por alineamiento léxico."""
        if self._escenario is None:
            raise RuntimeError(
                "No hay escenario activo: invoca iniciar_escenario antes "
                "de añadir interacciones."
            )
        if trazabilidad is None:
            trazabilidad = _alinear_lexicamente(modelo, texto)
        self._escenario.añadir(
            Interaccion(texto=texto, modelo=modelo, trazabilidad=trazabilidad)
        )

    def consultar_modelo(self):
        actual = self._actual()
        return actual.modelo if actual else None

    def consultar_texto(self):
        actual = self._actual()
        return actual.texto if actual else None

    def consultar_trazabilidad(self):
        actual = self._actual()
        return actual.trazabilidad if actual else {}

    def hay_interaccion_anterior(self):
        return self._escenario is not None and self._escenario.hay_anterior()

    def hay_interaccion_siguiente(self):
        return self._escenario is not None and self._escenario.hay_siguiente()

    def retroceder(self):
        if self._escenario is None:
            return False
        return self._escenario.retroceder()

    def avanzar(self):
        if self._escenario is None:
            return False
        return self._escenario.avanzar()

    def _actual(self):
        return self._escenario.activa() if self._escenario else None


def _foldear(texto):
    """Minúsculas sin tildes, preservando la longitud original para que los offsets sean válidos."""
    resultado = []
    for c in texto:
        descompuesto = unicodedata.normalize("NFD", c)
        base = "".join(
            ch for ch in descompuesto if unicodedata.category(ch) != "Mn"
        )
        # Si la descomposición no es 1:1 (ligaduras, etc.) dejamos el original para no descuadrar offsets.
        if len(base) == 1:
            resultado.append(base.lower())
        else:
            resultado.append(c.lower())
    return "".join(resultado)


def _buscar(nombre, texto_foldeado):
    """Primera aparición del nombre en el texto foldeado, expandida al cierre de cláusula."""
    aguja = _foldear(nombre)
    idx = texto_foldeado.find(aguja)
    if idx >= 0:
        return _expandir(idx, len(aguja), texto_foldeado)

    # Para relaciones en snake_case ("realiza_reserva") probamos solo con el primer término.
    if "_" in aguja:
        primer = aguja.split("_", 1)[0]
        if primer:
            idx = texto_foldeado.find(primer)
            if idx >= 0:
                return _expandir(idx, len(primer), texto_foldeado)
    return None


def _expandir(inicio, longitud, texto_foldeado):
    """Span desde la coincidencia hasta el siguiente "." o ";" (o fin de texto)."""
    fin_min = inicio + longitud
    for i in range(fin_min, len(texto_foldeado)):
        if texto_foldeado[i] in ".;":
            return {"inicio": inicio, "fin": i + 1}
    return {"inicio": inicio, "fin": len(texto_foldeado)}


def _alinear_lexicamente(modelo, texto):
    """Construye el mapa de trazabilidad buscando nombres del modelo en el texto del usuario."""
    if not texto:
        return {"entidades": {}, "relaciones": {}}

    texto_foldeado = _foldear(texto)
    mapa = {"entidades": {}, "relaciones": {}}

    for entidad in modelo.get("entidades", []):
        nombre = entidad.get("nombre")
        if not nombre:
            continue
        offsets = _buscar(nombre, texto_foldeado)
        if offsets:
            mapa["entidades"][nombre] = offsets

    for relacion in modelo.get("relaciones", []):
        nombre = relacion.get("nombre")
        if not nombre:
            continue
        offsets = _buscar(nombre, texto_foldeado)
        if offsets:
            mapa["relaciones"][nombre] = offsets

    return mapa
