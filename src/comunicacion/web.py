# Gestor de comunicación: interfaz web Flask sobre el controlador. Prototipo de una sesión.

import json
import os
from pathlib import Path

from flask import Flask, request, redirect, url_for, send_file, render_template_string

from src.nlp.nlp import ModuloNLPSimulado, ModuloNLPOllama
from src.etl.etl import FaseETL
from src.representacion.gestor import GestorRepresentacionIntermedia
from src.representacion import escenario as escenario_io
from src.generador_er.generador import GeneradorERGraphviz
from src.validador.validador import ValidadorWeb
from src.generador_sql.generador import GeneradorSQLEstandar
from src.controlador.controlador import Controlador

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLOS = RAIZ / "ejemplos"
SALIDAS = RAIZ / "salidas"


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def _cargar_registro():
    """Carga los ejemplos disponibles y construye:

    - el mapa {texto -> respuesta cruda enlatada} para el stub NLP,
    - el registro {texto_normalizado -> (nombre, texto, trazabilidad)}
      que usa el gestor de comunicación para localizar el ejemplo y su
      trazabilidad cuando el usuario pega un texto.

    La respuesta enlatada es el JSON del ejemplo envuelto en vallas
    markdown, para que la fase ETL haga su trabajo de verdad.
    """
    respuestas = {}
    registro = {}
    for ruta in sorted(EJEMPLOS.glob("*.json")):
        if ruta.stem.endswith("_trazabilidad"):
            continue
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        texto = datos.get("_descripcion_usuario")
        if not texto:
            continue
        traz_path = EJEMPLOS / f"{ruta.stem}_trazabilidad.json"
        trazabilidad = (
            json.loads(traz_path.read_text(encoding="utf-8"))
            if traz_path.exists()
            else {}
        )
        respuesta = "```json\n" + json.dumps(datos, ensure_ascii=False, indent=2) + "\n```"
        respuestas[texto] = respuesta
        registro[_normalizar(texto)] = (ruta.stem, texto, trazabilidad)
    return respuestas, registro


def crear_app() -> Flask:
    app = Flask(__name__)

    respuestas, registro = _cargar_registro()

    # Selección del módulo NLP por variable de entorno.
    #   - NLP_BACKEND=ollama : LLM real local (qwen2.5:7b por defecto);
    #     acepta cualquier descripción.
    #   - sin variable        : ModuloNLPSimulado; solo conoce los textos
    #     de los ejemplos.
    backend = os.environ.get("NLP_BACKEND", "simulado").lower()
    if backend == "ollama":
        modelo = os.environ.get("OLLAMA_MODELO", "qwen2.5:7b")
        # Timeout generoso (20 min): qwen2.5:7b en CPU puede tardar ~10
        # min por descripción. Subimos margen para que el flujo del Flask
        # no aborte antes de que el modelo termine.
        nlp = ModuloNLPOllama(modelo=modelo, timeout=1200)
        app.logger.info(f"NLP: ModuloNLPOllama con modelo '{modelo}'.")
    else:
        nlp = ModuloNLPSimulado(respuestas)
        app.logger.info("NLP: ModuloNLPSimulado (respuestas enlatadas).")
    usar_ollama = (backend == "ollama")

    # Un único controlador para toda la app (prototipo de una sesión).
    # Le pasamos la raíz del proyecto para que pueda persistir escenarios
    # en disco tras cada interacción exitosa.
    controlador = Controlador(
        nlp=nlp,
        etl=FaseETL(),
        gestor=GestorRepresentacionIntermedia(),
        generador_er=GeneradorERGraphviz(),
        validador=ValidadorWeb(),
        generador_sql=GeneradorSQLEstandar(),
        raiz_proyecto=RAIZ,
    )

    # Estado de presentación: ruta del HTML del validador actual y nombre
    # del escenario activo (para nombrar los ficheros de salida).
    estado = {"html": None, "nombre": None}

    @app.route("/")
    def inicio():
        # Si el usuario está "dentro" de un escenario (ya hay uno activo
        # en el gestor), la página de inicio cambia de cara: pre-rellena
        # el texto y el nombre del escenario, y oculta los ejemplos y la
        # lista de escenarios guardados para evitar que se descarrile a
        # otro flujo sin darse cuenta. Pulsando "Salir del escenario"
        # vuelve a la página neutra.
        escenario_act = controlador.escenario_actual()
        dentro_de_escenario = escenario_act is not None and bool(
            escenario_act.interacciones
        )
        texto_previo = ""
        if dentro_de_escenario:
            ultima = escenario_act.activa()
            if ultima is not None:
                texto_previo = ultima.texto

        escenarios = (
            [] if dentro_de_escenario else controlador.escenarios_disponibles()
        )
        return render_template_string(
            PLANTILLA_INICIO,
            escenarios=escenarios,
            nombre_por_defecto=escenario_io.nombre_por_defecto(),
            error=request.args.get("error"),
            usar_ollama=usar_ollama,
            escenario=escenario_act if dentro_de_escenario else None,
            texto_previo=texto_previo,
        )

    @app.route("/procesar", methods=["POST"])
    def procesar():
        # Flujo de trabajo 1. Recogemos descripción y nombre del escenario.
        texto = request.form.get("descripcion", "").strip()
        nombre_escenario = request.form.get("escenario", "").strip()
        if not texto:
            return redirect(url_for("inicio", error="La descripción está vacía."))

        # Si el usuario ya está dentro de un escenario y no escribió
        # nombre explícito (caso típico cuando viene de "Rechazar y
        # reescribir"), heredamos el nombre del escenario activo para
        # que la nueva interacción se acumule en él en vez de empezar
        # otro escenario con la fecha de hoy.
        escenario_act = controlador.escenario_actual()
        if not nombre_escenario and escenario_act is not None:
            nombre_escenario = escenario_act.nombre

        clave = _normalizar(texto)
        if usar_ollama:
            # Con el LLM real, aceptamos cualquier descripción. Si el
            # texto coincide con un ejemplo conocido reutilizamos su
            # trazabilidad hecha a mano (más rica que la automática);
            # si no, dejamos que el gestor construya el mapa por
            # alineamiento léxico. El nombre del escenario lo
            # decide el usuario (si lo deja vacío, el controlador usará
            # la fecha de hoy).
            if clave in registro:
                _nombre_ejemplo, _texto, trazabilidad = registro[clave]
            else:
                trazabilidad = None
            nombre = nombre_escenario or escenario_io.nombre_por_defecto()
        else:
            # Con el NLP simulado solo conocemos los textos enlatados.
            # El nombre del escenario se hereda del ejemplo para que la
            # trazabilidad hecha a mano siga cuadrando.
            if clave not in registro:
                return redirect(url_for(
                    "inicio",
                    error="Ese texto no corresponde a ningún ejemplo conocido. "
                          "Arranca con NLP_BACKEND=ollama para procesar "
                          "descripciones arbitrarias.",
                ))
            nombre, _texto, trazabilidad = registro[clave]

        base = SALIDAS / nombre
        ruta_html = controlador.procesar_descripcion(
            texto, trazabilidad, base, nombre_escenario=nombre
        )
        if ruta_html is None:
            return redirect(url_for(
                "inicio",
                error="No se ha podido procesar la descripción. "
                      "Mira la consola del servidor para ver el motivo.",
            ))

        estado["html"] = ruta_html
        estado["nombre"] = nombre
        return _pintar_resultado()

    @app.route("/validador")
    def ver_validador():
        # Sirve el HTML del validador actual para incrustarlo en el iframe.
        if not estado["html"]:
            return "Todavía no se ha generado ningún modelo.", 404
        return send_file(estado["html"])

    @app.route("/validar", methods=["POST"])
    def validar():
        # Flujo de trabajo 2: el usuario ha validado, generamos el SQL.
        sql = controlador.generar_sql()
        return render_template_string(PLANTILLA_SQL, sql=sql)

    @app.route("/revertir", methods=["POST"])
    def revertir():
        # Retrocede a la interacción anterior dentro del mismo escenario.
        # No destruye nada: con "Siguiente" se puede volver hacia adelante.
        if estado["nombre"] is None:
            return redirect(url_for("inicio"))
        base = SALIDAS / estado["nombre"]
        ruta_html = controlador.retroceder(base)
        if ruta_html is None:
            return redirect(url_for(
                "inicio",
                error="Ya estás en la primera interacción del escenario.",
            ))
        estado["html"] = ruta_html
        return _pintar_resultado()

    @app.route("/avanzar", methods=["POST"])
    def avanzar():
        # Vuelve hacia adelante en el historial del escenario. Solo tiene
        # sentido si antes se ha retrocedido.
        if estado["nombre"] is None:
            return redirect(url_for("inicio"))
        base = SALIDAS / estado["nombre"]
        ruta_html = controlador.avanzar(base)
        if ruta_html is None:
            return redirect(url_for(
                "inicio",
                error="Ya estás en la última interacción del escenario.",
            ))
        estado["html"] = ruta_html
        return _pintar_resultado()

    @app.route("/salir_escenario", methods=["POST", "GET"])
    def salir_escenario():
        # Despide al usuario del escenario activo: el gestor se queda sin
        # escenario en memoria y el estado de presentación se limpia. El
        # escenario sigue persistido en disco; basta con "abrirlo" para
        # retomarlo. Es el "borrón y cuenta nueva" que pide el usuario al
        # pulsar "empezar de nuevo".
        controlador.cerrar_escenario()
        estado["html"] = None
        estado["nombre"] = None
        return redirect(url_for("inicio"))

    @app.route("/escenario/<nombre>", methods=["GET"])
    def abrir(nombre):
        # Retomar un escenario persistido: el controlador lo recupera de
        # disco y regenera diagrama y validador para la interacción
        # marcada como activa en el momento de la última persistencia.
        base = SALIDAS / nombre
        ruta_html = controlador.abrir_escenario(nombre, base)
        if ruta_html is None:
            return redirect(url_for(
                "inicio", error=f"No se ha podido abrir el escenario '{nombre}'."
            ))
        estado["html"] = ruta_html
        estado["nombre"] = nombre
        return _pintar_resultado()

    def _pintar_resultado():
        """Construye la página del validador con la barra de acciones.

        Centraliza aquí la información que depende del estado actual
        del escenario (nombre, número de interacción, si se puede
        retroceder o avanzar) para que cada ruta no tenga que
        recalcularla.
        """
        escenario_act = controlador.escenario_actual()
        return render_template_string(
            PLANTILLA_RESULTADO,
            puede_revertir=controlador.hay_interaccion_anterior(),
            puede_avanzar=controlador.hay_interaccion_siguiente(),
            escenario=escenario_act,
        )

    return app


# ---------------------------------------------------------------------- #
# Plantillas HTML embebidas (render_template_string). Mínimas y con un
# poco de estilo. Se mantienen aquí por simplicidad del prototipo.

PLANTILLA_INICIO = """<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>NL2SQL</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2em auto;
         padding: 0 1em; color: #222; }
  h1 { color: #555; font-size: 1.3em; }
  textarea { width: 100%; height: 7em; font-size: 1em; padding: 0.6em;
             border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
  button, .boton { font-size: 1em; padding: 0.5em 1.1em; border: 0;
                   border-radius: 6px; background: #2563eb; color: white;
                   cursor: pointer; }
  .error { background: #fee2e2; border: 1px solid #fca5a5; color: #991b1b;
           padding: 0.7em; border-radius: 6px; margin-bottom: 1em; }

</style></head>
<body>
  <h1>Generador de modelos de base de datos a partir de texto</h1>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  {% if escenario %}
    <div style="background:#ecfdf5;border:1px solid #6ee7b7;
                color:#065f46;padding:0.7em 0.9em;border-radius:6px;
                margin-bottom:1em;display:flex;align-items:center;
                justify-content:space-between;gap:1em;">
      <div>
        Estás dentro del escenario <b>{{ escenario.nombre }}</b>
        &middot; interacción
        <b>{{ escenario.indice_activa + 1 }}</b> de
        {{ escenario.interacciones|length }}. Si reescribes la
        descripción se añadirá como nueva interacción al mismo
        escenario.
      </div>
      <form action="/salir_escenario" method="post" style="margin:0">
        <button type="submit"
                style="background:#64748b;color:white;border:0;
                       padding:0.4em 0.9em;border-radius:6px;
                       cursor:pointer;font-size:0.9em;">
          Salir del escenario
        </button>
      </form>
    </div>
  {% endif %}
  {% if usar_ollama %}
    <p style="font-size:0.9em;color:#0c4a6e;background:#e0f2fe;
              border:1px solid #7dd3fc;padding:0.6em;border-radius:6px;">
      Modo <b>OLLAMA</b>: el modelo de lenguaje local procesa cualquier
      descripción. Sin GPU, cada llamada puede tardar varios minutos
      (alrededor de 10 con <code>qwen2.5:7b</code>). Ten paciencia tras
      pulsar Continuar.
    </p>
  {% else %}
    <p style="font-size:0.9em;color:#78350f;background:#fef3c7;
              border:1px solid #fcd34d;padding:0.6em;border-radius:6px;">
      Modo <b>simulado</b>: solo se reconocen los textos de los ejemplos.
      Para procesar cualquier descripción, arranca con
      <code>NLP_BACKEND=ollama</code>.
    </p>
  {% endif %}
  <p>
    {% if escenario %}
      Edita la descripción y vuelve a pulsar Continuar para añadir otra
      interacción al escenario.
    {% else %}
      Describe tu base de datos en lenguaje natural y pulsa Continuar.
    {% endif %}
  </p>
  <form action="/procesar" method="post" id="formulario">
    <p style="margin-bottom:0.3em">
      <label for="escenario" style="font-size:0.92em;color:#555">
        Nombre del escenario
        {% if not escenario %}
          <span style="color:#999">(si lo dejas vacío, se usará la fecha
          de hoy: <code>{{ nombre_por_defecto }}</code>)</span>
        {% else %}
          <span style="color:#999">(fijo al escenario activo)</span>
        {% endif %}
      </label>
    </p>
    <input type="text" id="escenario" name="escenario"
           value="{{ escenario.nombre if escenario else '' }}"
           {% if escenario %}readonly{% endif %}
           placeholder="p. ej. hotel_demo" style="width:100%;
           padding:0.5em;font-size:0.95em;border:1px solid #ccc;
           border-radius:6px;box-sizing:border-box;margin-bottom:0.8em;
           {% if escenario %}background:#f1f5f9;{% endif %}">
    <textarea id="descripcion" name="descripcion"
              placeholder="Escribe aquí tu descripción...">{{ texto_previo }}</textarea>
    <p>
      <button type="submit" id="btn-continuar">Continuar</button>
      <span id="cargando" style="display:none;color:#0c4a6e;margin-left:0.8em;">
        Procesando con el modelo de lenguaje… (en CPU puede tardar varios minutos)
      </span>
    </p>
  </form>

  {% if escenarios %}
  <h2 style="font-size:1em;color:#555">Escenarios guardados</h2>
  <p style="font-size:0.9em;color:#777">
    Trabajos anteriores que puedes retomar. Al abrirlos vuelves al
    último estado en que los dejaste.</p>
  <ul style="list-style:none;padding:0">
    {% for esc in escenarios %}
      <li style="background:#f1f5f9;border:1px solid #cbd5e1;
                 border-radius:6px;padding:0.5em 0.8em;margin:0.4em 0;
                 font-size:0.92em;display:flex;align-items:center;
                 justify-content:space-between">
        <code>{{ esc }}</code>
        <a href="/escenario/{{ esc }}"
           style="background:#0ea5e9;color:white;text-decoration:none;
                  padding:0.3em 0.8em;border-radius:6px;font-size:0.85em">
          abrir
        </a>
      </li>
    {% endfor %}
  </ul>
  {% endif %}

  <script>
    document.getElementById('formulario').addEventListener('submit', function() {
      document.getElementById('btn-continuar').disabled = true;
      document.getElementById('btn-continuar').textContent = 'Procesando…';
      document.getElementById('cargando').style.display = 'inline';
    });
  </script>
</body>
</html>
"""

PLANTILLA_RESULTADO = """<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Revisión del modelo</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 1em; color: #222; }
  h1 { color: #555; font-size: 1.2em; }
  iframe { width: 100%; height: 70vh; border: 1px solid #ddd; border-radius: 6px; }
  .barra { margin: 0.8em 0; display: flex; gap: 0.6em; align-items: center; }
  button { font-size: 1em; padding: 0.5em 1.1em; border: 0; border-radius: 6px;
           cursor: pointer; color: white; }
  .validar { background: #16a34a; }
  .rechazar { background: #64748b; }
  .revertir { background: #d97706; }
  form { display: inline; }
</style></head>
<body>
  <h1>Revisa el modelo conceptual</h1>
  {% if escenario %}
    <p style="font-size:0.9em;color:#475569;background:#f8fafc;
              border:1px solid #e2e8f0;padding:0.5em 0.8em;
              border-radius:6px;">
      Escenario: <b>{{ escenario.nombre }}</b> &middot;
      interacción <b>{{ escenario.indice_activa + 1 }}</b> de
      {{ escenario.interacciones|length }}
    </p>
  {% endif %}
  <p>Comprueba el diagrama y la trazabilidad. Si es correcto, valida para
     generar el SQL. Si no, rechaza y reescribe la descripción.</p>
  <div class="barra">
    <form action="/validar" method="post">
      <button class="validar" type="submit">Validar y generar SQL</button>
    </form>
    <a href="/" style="text-decoration:none">
      <button class="rechazar" type="button">Rechazar y reescribir</button>
    </a>
    {% if puede_revertir %}
    <form action="/revertir" method="post">
      <button class="revertir" type="submit">← Anterior</button>
    </form>
    {% endif %}
    {% if puede_avanzar %}
    <form action="/avanzar" method="post">
      <button class="revertir" type="submit">Siguiente →</button>
    </form>
    {% endif %}
  </div>
  <iframe src="/validador"></iframe>
</body>
</html>
"""

PLANTILLA_SQL = """<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>SQL generado</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2em auto;
         padding: 0 1em; color: #222; }
  h1 { color: #555; font-size: 1.2em; }
  pre { background: #0f172a; color: #e2e8f0; padding: 1em; border-radius: 6px;
        overflow-x: auto; font-size: 0.9em; }
  .boton { display: inline-block; margin-top: 1em; font-size: 1em;
           padding: 0.5em 1.1em; border-radius: 6px; background: #2563eb;
           color: white; text-decoration: none; }
</style></head>
<body>
  <h1>Diseño físico relacional (SQL DDL)</h1>
  <pre>{{ sql }}</pre>
  <form action="/salir_escenario" method="post" style="margin-top:1em">
    <button class="boton" type="submit"
            style="border:0;font-family:inherit;cursor:pointer">
      Empezar de nuevo
    </button>
  </form>
</body>
</html>
"""


# Permite arrancar con:  .venv/bin/python -m src.comunicacion.web
if __name__ == "__main__":
    crear_app().run(debug=True, port=5001)
