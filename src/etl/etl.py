# Fase ETL: limpia y valida la respuesta cruda del LLM antes de entregarla al sistema.

import json


class ErrorETL(Exception):
    """Error no recuperable durante la fase ETL."""


class FaseETL:
    """Extracción, transformación y carga de la respuesta del modelo."""

    _CARDINALIDADES = {"1", "N"}
    _PARTICIPACIONES = {"obligatoria", "opcional"}

    def procesar(self, respuesta_cruda: str) -> dict:
        texto_json = self._extraer(respuesta_cruda)
        modelo = self._transformar(texto_json)
        return modelo

    def _extraer(self, respuesta_cruda) -> str:
        if not isinstance(respuesta_cruda, str) or not respuesta_cruda.strip():
            raise ErrorETL("La respuesta del modelo está vacía.")

        texto = respuesta_cruda.strip()

        # Los LLM suelen envolver el JSON en vallas markdown aunque se les pida lo contrario.
        if texto.startswith("```"):
            lineas = texto.splitlines()
            if lineas and lineas[0].startswith("```"):
                lineas = lineas[1:]
            if lineas and lineas[-1].strip().startswith("```"):
                lineas = lineas[:-1]
            texto = "\n".join(lineas).strip()

        inicio = texto.find("{")
        if inicio == -1:
            raise ErrorETL(
                "No se ha encontrado ningún objeto JSON en la respuesta del modelo."
            )
        return texto[inicio:]

    def _transformar(self, texto_json: str) -> dict:
        try:
            # raw_decode se detiene al cerrar el primer objeto válido; ignora prosa posterior.
            datos, _ = json.JSONDecoder().raw_decode(texto_json)
        except json.JSONDecodeError as e:
            raise ErrorETL(f"El JSON de la respuesta no es válido: {e}") from e

        if not isinstance(datos, dict):
            raise ErrorETL("La raíz de la respuesta no es un objeto JSON.")

        entidades = datos.get("entidades")
        relaciones = datos.get("relaciones", [])
        if not isinstance(entidades, list) or not entidades:
            raise ErrorETL("La respuesta no contiene una lista de 'entidades'.")
        if not isinstance(relaciones, list):
            raise ErrorETL("El campo 'relaciones' debe ser una lista.")

        return {
            "entidades": [self._normalizar_entidad(e) for e in entidades],
            "relaciones": [self._normalizar_relacion(r) for r in relaciones],
        }

    def _normalizar_entidad(self, entidad) -> dict:
        if not isinstance(entidad, dict):
            raise ErrorETL("Hay una entidad que no es un objeto.")
        nombre = self._exigir_cadena(entidad, "nombre", "una entidad")
        atributos = entidad.get("atributos")
        if not isinstance(atributos, list) or not atributos:
            raise ErrorETL(f"La entidad '{nombre}' no tiene atributos.")
        return {
            "nombre": nombre,
            "atributos": [self._normalizar_atributo(a, nombre) for a in atributos],
        }

    def _normalizar_atributo(self, atributo, contexto: str) -> dict:
        if not isinstance(atributo, dict):
            raise ErrorETL(f"Hay un atributo de '{contexto}' que no es un objeto.")
        nombre = self._exigir_cadena(atributo, "nombre", f"un atributo de '{contexto}'")
        tipo = self._exigir_cadena(atributo, "tipo", f"el atributo '{nombre}'")

        clave_primaria = self._a_bool(atributo.get("clave_primaria", False))
        nullable = self._a_bool(atributo.get("nullable", False))
        inferido = self._a_bool(atributo.get("inferido", False))

        # Una clave primaria nunca puede ser nullable; si el modelo la marcó así, se corrige.
        if clave_primaria:
            nullable = False

        normalizado = {
            "nombre": nombre,
            "tipo": tipo,
            "clave_primaria": clave_primaria,
            "nullable": nullable,
            "inferido": inferido,
        }
        razon = atributo.get("razon")
        if razon:
            normalizado["razon"] = str(razon).strip()
        return normalizado

    def _normalizar_relacion(self, relacion) -> dict:
        if not isinstance(relacion, dict):
            raise ErrorETL("Hay una relación que no es un objeto.")
        nombre = self._exigir_cadena(relacion, "nombre", "una relación")
        ea = self._exigir_cadena(relacion, "entidad_a", f"la relación '{nombre}'")
        eb = self._exigir_cadena(relacion, "entidad_b", f"la relación '{nombre}'")
        ca = self._normalizar_cardinalidad(relacion.get("cardinalidad_a"), nombre)
        cb = self._normalizar_cardinalidad(relacion.get("cardinalidad_b"), nombre)
        pa = self._normalizar_participacion(relacion.get("participacion_a"), nombre)
        pb = self._normalizar_participacion(relacion.get("participacion_b"), nombre)

        atributos = relacion.get("atributos", [])
        if not isinstance(atributos, list):
            raise ErrorETL(
                f"Los atributos de la relación '{nombre}' deben ser una lista."
            )

        return {
            "nombre": nombre,
            "entidad_a": ea,
            "entidad_b": eb,
            "cardinalidad_a": ca,
            "cardinalidad_b": cb,
            "participacion_a": pa,
            "participacion_b": pb,
            "atributos": [self._normalizar_atributo(a, nombre) for a in atributos],
        }

    def _exigir_cadena(self, obj: dict, campo: str, contexto: str) -> str:
        valor = obj.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise ErrorETL(f"Falta el campo obligatorio '{campo}' en {contexto}.")
        return valor.strip()

    def _a_bool(self, valor) -> bool:
        # Algunos modelos devuelven "true"/"false" como cadenas en lugar de booleanos.
        if isinstance(valor, bool):
            return valor
        if isinstance(valor, str):
            return valor.strip().lower() in {"true", "1", "sí", "si"}
        return bool(valor)

    def _normalizar_cardinalidad(self, valor, relacion: str) -> str:
        if not isinstance(valor, str):
            raise ErrorETL(f"Falta la cardinalidad en la relación '{relacion}'.")
        v = valor.strip().upper()
        if v not in self._CARDINALIDADES:
            raise ErrorETL(
                f"Cardinalidad '{valor}' no válida en la relación '{relacion}' "
                f"(se esperaba '1' o 'N')."
            )
        return v

    def _normalizar_participacion(self, valor, relacion: str) -> str:
        if not isinstance(valor, str):
            raise ErrorETL(f"Falta la participación en la relación '{relacion}'.")
        v = valor.strip().lower()
        if v not in self._PARTICIPACIONES:
            raise ErrorETL(
                f"Participación '{valor}' no válida en la relación '{relacion}' "
                f"(se esperaba 'obligatoria' u 'opcional')."
            )
        return v
