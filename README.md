# NL2DB

Sistema de generación de bases de datos relacionales a partir de descripciones en lenguaje natural.

## Requisitos previos

- Python 3 con el gestor de paquetes `pip`.
- El binario de Graphviz instalado en el sistema operativo.
- OLLAMA instalado y en ejecución como servicio local, accesible en `http://localhost:11434`.

## Instalación

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Instalar el binario de Graphviz mediante el gestor de paquetes del sistema. En distribuciones basadas en Debian o Ubuntu:

```bash
sudo apt install graphviz
```

## Instalación de OLLAMA

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Una vez instalado, OLLAMA arranca automáticamente como servicio en `http://localhost:11434`.

## Preparación del modelo de lenguaje

Con OLLAMA en ejecución, descargar el modelo utilizado por defecto:

```bash
ollama pull qwen2.5:7b
```

## Configuración y arranque

```bash
export NLP_BACKEND=ollama
export OLLAMA_MODELO=qwen2.5:7b
python app.py
```

## Modo simulado

Para ejecutar el sistema sin llamadas al LLM (respuesta enlatada):

```bash
export NLP_BACKEND=simulado
python app.py
```

## Nota sobre el rendimiento

En una máquina sin GPU dedicada, la inferencia del modelo se ejecuta sobre la CPU y cada llamada puede tardar varios minutos en completarse. En un equipo con GPU dedicada o utilizando una API de un modelo en la nube, la misma operación se resuelve en unos pocos segundos.
