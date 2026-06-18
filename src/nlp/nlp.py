# Módulo NLP: recibe texto del usuario y devuelve la respuesta cruda del LLM.

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from src.nlp.prompt import construir_prompt


class ErrorNLP(Exception):
    """Error del módulo NLP (red, API o texto desconocido en el simulado)."""


class ModuloNLP(ABC):
    """Contrato del módulo NLP: texto del usuario → respuesta cruda."""

    @abstractmethod
    def analizar(self, texto: str) -> str:
        ...


class ModuloNLPSimulado(ModuloNLP):
    """Devuelve respuestas enlatadas para textos de ejemplo conocidos.

    Permite ejercitar todo el flujo sin depender del LLM real.
    El emparejamiento normaliza espacios para tolerar variaciones de copia-pega.
    """

    def __init__(self, respuestas_por_texto: dict):
        self._respuestas = {
            self._normalizar(texto): respuesta
            for texto, respuesta in respuestas_por_texto.items()
        }

    def analizar(self, texto: str) -> str:
        clave = self._normalizar(texto)
        if clave not in self._respuestas:
            raise ErrorNLP(
                "El módulo NLP simulado solo conoce los textos de ejemplo. "
                "El módulo real (con la API del modelo de lenguaje) haría "
                "falta para procesar una descripción arbitraria."
            )
        return self._respuestas[clave]

    @staticmethod
    def _normalizar(texto: str) -> str:
        # Colapsa espacios/saltos para hacer robusto el emparejamiento.
        return " ".join(texto.split())


class ModuloNLPOllama(ModuloNLP):
    """Cliente HTTP mínimo contra un servidor OLLAMA local."""

    URL_POR_DEFECTO = "http://localhost:11434/api/generate"
    MODELO_POR_DEFECTO = "llama3.2"

    def __init__(self, modelo: str = MODELO_POR_DEFECTO,
                 url: str = URL_POR_DEFECTO, timeout: float = 120.0):
        self._modelo = modelo
        self._url = url
        self._timeout = timeout

    def analizar(self, texto: str) -> str:
        prompt = construir_prompt(texto)
        # stream:false para obtener la respuesta completa en una sola llamada.
        cuerpo = json.dumps({
            "model": self._modelo,
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")

        peticion = urllib.request.Request(
            self._url,
            data=cuerpo,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(peticion, timeout=self._timeout) as resp:
                bruto = resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as e:
            motivo = getattr(e, "reason", str(e))
            raise ErrorNLP(
                f"No se ha podido contactar con OLLAMA en {self._url}: {motivo}. "
                f"Asegúrate de que el servidor está arrancado (`ollama serve`) "
                f"y de que el modelo '{self._modelo}' está descargado "
                f"(`ollama pull {self._modelo}`)."
            )

        try:
            datos = json.loads(bruto)
            return datos["response"]
        except (json.JSONDecodeError, KeyError) as e:
            raise ErrorNLP(
                f"Respuesta inesperada de OLLAMA: {e}. Cuerpo recibido: "
                f"{bruto[:200]}..."
            )
