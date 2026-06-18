# Controlador: orquesta el flujo de dos fases entre todos los módulos del sistema.

from src.etl.etl import ErrorETL
from src.nlp.nlp import ErrorNLP
from src.representacion import escenario as escenario_io


class Controlador:
    """Orquesta el flujo de dos fases del sistema."""

    def __init__(self, nlp, etl, gestor, generador_er, validador, generador_sql,
                 raiz_proyecto=None):
        self._nlp = nlp
        self._etl = etl
        self._gestor = gestor
        self._generador_er = generador_er
        self._validador = validador
        self._generador_sql = generador_sql
        # Sin raiz_proyecto el flujo funciona pero no persiste escenarios en disco.
        self._raiz_proyecto = raiz_proyecto

    def procesar_descripcion(self, texto, trazabilidad, base_salida,
                             nombre_escenario=None):
        """Flujo 1: texto → NLP → ETL → gestor → ER → validador.

        Devuelve la ruta del HTML, o None si NLP/ETL fallan
        (en ese caso el estado del sistema no se modifica).
        """
        try:
            respuesta_cruda = self._nlp.analizar(texto)
        except ErrorNLP as e:
            print(f"[controlador] El módulo NLP ha fallado: {e}")
            return None

        try:
            modelo = self._etl.procesar(respuesta_cruda)
        except ErrorETL as e:
            print(f"[controlador] La fase ETL ha rechazado la respuesta: {e}")
            return None

        self._asegurar_escenario(nombre_escenario)
        self._gestor.añadir_interaccion(modelo, texto, trazabilidad)
        ruta_html = self._regenerar_artefactos(base_salida)
        self._persistir()
        return ruta_html

    def generar_sql(self):
        """Flujo 2: genera el SQL del modelo activo (solo tras validación del usuario)."""
        modelo = self._gestor.consultar_modelo()
        if modelo is None:
            raise RuntimeError(
                "No hay modelo activo: ejecuta primero el flujo 1 "
                "(procesar_descripcion)."
            )
        return self._generador_sql.generar(modelo)

    def retroceder(self, base_salida):
        """Vuelve a la interacción anterior y regenera los artefactos."""
        if not self._gestor.retroceder():
            print("[controlador] No hay interacción anterior a la que volver.")
            return None
        ruta_html = self._regenerar_artefactos(base_salida)
        self._persistir()
        return ruta_html

    def avanzar(self, base_salida):
        """Avanza a la siguiente interacción y regenera los artefactos."""
        if not self._gestor.avanzar():
            print("[controlador] No hay interacción siguiente a la que ir.")
            return None
        ruta_html = self._regenerar_artefactos(base_salida)
        self._persistir()
        return ruta_html

    def abrir_escenario(self, nombre, base_salida):
        """Carga un escenario persistido y regenera sus artefactos."""
        if self._raiz_proyecto is None:
            print(
                "[controlador] No se puede abrir escenarios: el controlador "
                "no recibió raiz_proyecto."
            )
            return None
        try:
            escenario = escenario_io.cargar(nombre, self._raiz_proyecto)
        except FileNotFoundError:
            print(f"[controlador] No existe el escenario '{nombre}'.")
            return None
        self._gestor.abrir_escenario(escenario)
        return self._regenerar_artefactos(base_salida)

    def hay_interaccion_anterior(self):
        return self._gestor.hay_interaccion_anterior()

    def hay_interaccion_siguiente(self):
        return self._gestor.hay_interaccion_siguiente()

    def escenarios_disponibles(self):
        if self._raiz_proyecto is None:
            return []
        return escenario_io.listar(self._raiz_proyecto)

    def escenario_actual(self):
        return self._gestor.escenario_actual()

    def cerrar_escenario(self):
        self._gestor.cerrar_escenario()

    def _asegurar_escenario(self, nombre_solicitado):
        nombre = nombre_solicitado or escenario_io.nombre_por_defecto()
        actual = self._gestor.escenario_actual()
        if actual is None or actual.nombre != nombre:
            self._gestor.iniciar_escenario(nombre)

    def _regenerar_artefactos(self, base_salida):
        ruta_svg = self._generador_er.generar(
            self._gestor.consultar_modelo(), f"{base_salida}_er"
        )
        return self._validador.generar(
            modelo=self._gestor.consultar_modelo(),
            texto=self._gestor.consultar_texto(),
            trazabilidad=self._gestor.consultar_trazabilidad(),
            ruta_svg=ruta_svg,
            ruta_salida=f"{base_salida}_validador.html",
        )

    def _persistir(self):
        if self._raiz_proyecto is None:
            return
        escenario = self._gestor.escenario_actual()
        if escenario is None:
            return
        escenario_io.guardar(escenario, self._raiz_proyecto)
