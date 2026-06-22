# Módulo validador: genera un HTML autónomo con diagrama, texto y trazabilidad interactiva.

from abc import ABC, abstractmethod
from pathlib import Path
import html
import json


class Validador(ABC):
    """Interfaz abstracta del validador."""

    @abstractmethod
    def generar(self, modelo, texto, trazabilidad, ruta_svg, ruta_salida):
        ...


class ValidadorWeb(Validador):
    """Genera un HTML autónomo con SVG embebido, texto y trazabilidad bidireccional."""

    def generar(self, modelo, texto, trazabilidad, ruta_svg, ruta_salida):
        # SVG embebido literal para que el JS pueda acceder a su DOM por ID.
        svg = Path(ruta_svg).read_text(encoding="utf-8")

        # Quitamos <?xml?> si existe; dentro de HTML no es válido.
        if svg.lstrip().startswith("<?xml"):
            svg = svg[svg.index("?>") + 2:].lstrip()

        # Atributos inferidos agrupados por entidad.
        inferidos_por_entidad = {
            entidad["nombre"]: [
                {
                    "nombre": a["nombre"],
                    "tipo":   a["tipo"],
                    "razon":  a.get("razon", ""),
                }
                for a in entidad.get("atributos", [])
                if a.get("inferido", False)
            ]
            for entidad in modelo.get("entidades", [])
        }

        datos_js = {
            "texto": texto,
            "trazabilidad": trazabilidad,
            "inferidos": inferidos_por_entidad,
        }

        html_final = _PLANTILLA.format(
            svg=svg,
            texto_html=html.escape(texto),
            datos_json=json.dumps(datos_js, ensure_ascii=False),
        )

        ruta_salida = Path(ruta_salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        ruta_salida.write_text(html_final, encoding="utf-8")
        return str(ruta_salida)


# Plantilla HTML con tres marcadores: {svg}, {texto_html} y {datos_json}.
# Las llaves de CSS y JS van dobladas ({{ }}) por str.format().
_PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Validador</title>
<style>
  body {{
    font-family: system-ui, sans-serif;
    margin: 0;
    padding: 1em;
    background: #fafafa;
    color: #222;
  }}
  h1 {{
    margin-top: 0;
    font-size: 1.2em;
    color: #555;
  }}
  .panels {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1em;
    align-items: start;
  }}
  .panel {{
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 1em;
  }}
  .panel h2 {{
    margin-top: 0;
    font-size: 1em;
    color: #555;
    border-bottom: 1px solid #eee;
    padding-bottom: 0.4em;
  }}
  #diagrama svg {{
    max-width: 100%;
    height: auto;
  }}
  #texto {{
    margin: 0;
    white-space: pre-wrap;
    line-height: 1.5;
    font-family: Georgia, serif;
    font-size: 1.05em;
    cursor: text;
  }}
  /* .activo = hover efímero; .fijado = click persistente. Ambos sobre <g> del SVG. */
  svg .activo,
  svg .fijado {{
    filter: drop-shadow(0 0 6px #f59e0b);
  }}
  .resaltado {{
    background: #fde68a;
    border-radius: 3px;
  }}
  #inferidos {{
    margin-top: 1em;
    font-size: 0.9em;
    color: #555;
  }}
  #inferidos h3 {{
    margin: 0 0 0.3em 0;
    font-size: 0.95em;
  }}
  #inferidos ul {{
    margin: 0;
    padding: 0;
    list-style: none;
  }}
  #inferidos li {{
    margin: 0.4em 0;
    padding: 0.4em 0.6em;
    border-left: 3px solid #fcd34d;
    background: #fffbeb;
    border-radius: 0 4px 4px 0;
    cursor: pointer;
    transition: background 120ms;
  }}
  #inferidos li:hover {{
    background: #fef3c7;
  }}
  #inferidos li.fijado {{
    background: #fde68a;
    border-left-color: #f59e0b;
  }}
  #inferidos .ent {{
    color: #555;
    font-size: 0.85em;
  }}
  #inferidos .nom {{
    font-weight: bold;
    color: #92400e;
  }}
  #inferidos .tipo {{
    font-family: ui-monospace, monospace;
    background: #fff;
    padding: 0.05em 0.35em;
    border: 1px solid #fcd34d;
    border-radius: 3px;
    font-size: 0.85em;
  }}
  #inferidos .razon {{
    margin-top: 0.25em;
    font-size: 0.85em;
    color: #6b7280;
    font-style: italic;
  }}
</style>
</head>
<body>

<h1>Validador del modelo conceptual</h1>

<div class="panels">

  <div class="panel" id="panel-diagrama">
    <h2>Diagrama entidad–relación</h2>
    <div id="diagrama">
      {svg}
    </div>

    <div id="inferidos">
      <h3>Información completada por el sistema</h3>
      <ul id="inferidos-lista"></ul>
    </div>
  </div>

  <div class="panel" id="panel-texto">
    <h2>Texto original</h2>
    <pre id="texto">{texto_html}</pre>
  </div>

</div>

<script>
const DATOS = {datos_json};

function escapeHtml(s) {{
  return String(s).replace(/&/g, '&amp;')
                  .replace(/</g, '&lt;')
                  .replace(/>/g, '&gt;');
}}

(function pintarInferidos() {{
  const ul = document.getElementById('inferidos-lista');
  let total = 0;
  for (const entidad in DATOS.inferidos) {{
    const attrs = DATOS.inferidos[entidad];
    for (const a of attrs) {{
      const li = document.createElement('li');
      li.dataset.entidad = entidad;
      li.innerHTML =
        '<span class="ent">' + escapeHtml(entidad) + ' · </span>' +
        '<span class="nom">' + escapeHtml(a.nombre) + '</span>' +
        ' : <span class="tipo">' + escapeHtml(a.tipo) + '</span>' +
        (a.razon
          ? '<div class="razon">' + escapeHtml(a.razon) + '</div>'
          : '');
      li.addEventListener('mouseenter', () => activarEntidad(entidad));
      li.addEventListener('mouseleave', () => activarEntidad(null));
      li.addEventListener('click', () => fijarDesdeLista(li, entidad));
      ul.appendChild(li);
      total += 1;
    }}
  }}
  if (total === 0) {{
    ul.innerHTML = '<li style="color:#888">(ninguno)</li>';
  }}
}})();

// Highlight efímero sobre una entidad del SVG; null lo limpia.
function activarEntidad(nombre) {{
  document.querySelectorAll('svg .activo').forEach(g =>
    g.classList.remove('activo'));
  if (!nombre) return;
  const el = document.getElementById('entidad_' + nombre);
  if (el) el.classList.add('activo');
}}

// Toggle "fijado" en el <li> y en su entidad del SVG; desfija el anterior.
function fijarDesdeLista(li, entidad) {{
  const yaEstaba = li.classList.contains('fijado');
  document.querySelectorAll('#inferidos li.fijado').forEach(x =>
    x.classList.remove('fijado'));
  document.querySelectorAll('svg .fijado').forEach(g =>
    g.classList.remove('fijado'));
  if (yaEstaba) return;
  li.classList.add('fijado');
  const el = document.getElementById('entidad_' + entidad);
  if (el) el.classList.add('fijado');
}}

const elTexto = document.getElementById('texto');
const textoOriginal = DATOS.texto;

function resaltarTexto(rango) {{
  const antes = textoOriginal.slice(0, rango.inicio);
  const medio = textoOriginal.slice(rango.inicio, rango.fin);
  const final = textoOriginal.slice(rango.fin);
  elTexto.innerHTML = escapeHtml(antes)
                    + '<span class="resaltado">' + escapeHtml(medio) + '</span>'
                    + escapeHtml(final);
}}

function limpiarTexto() {{
  elTexto.textContent = textoOriginal;
}}

function instalarListenersDiagrama() {{
  const enlazar = (prefijoId, nombre, rango) => {{
    const el = document.getElementById(prefijoId + nombre);
    if (!el) return;
    el.style.cursor = 'pointer';
    el.addEventListener('mouseenter', () => resaltarTexto(rango));
    el.addEventListener('mouseleave', limpiarTexto);
  }};
  for (const e in DATOS.trazabilidad.entidades) {{
    enlazar('entidad_', e, DATOS.trazabilidad.entidades[e]);
  }}
  for (const r in DATOS.trazabilidad.relaciones) {{
    enlazar('relacion_', r, DATOS.trazabilidad.relaciones[r]);
  }}
}}
instalarListenersDiagrama();

// Usa caretPositionFromPoint (estándar) o caretRangeFromPoint (WebKit legado).
function posicionDeCaracter(evento) {{
  if (document.caretPositionFromPoint) {{
    const cp = document.caretPositionFromPoint(evento.clientX, evento.clientY);
    if (cp && cp.offsetNode === elTexto.firstChild) return cp.offset;
  }} else if (document.caretRangeFromPoint) {{
    const r = document.caretRangeFromPoint(evento.clientX, evento.clientY);
    if (r && r.startContainer === elTexto.firstChild) return r.startOffset;
  }}
  return null;
}}

function activarDiagrama(posicion) {{
  document.querySelectorAll('svg .activo').forEach(g =>
    g.classList.remove('activo'));
  if (posicion === null) return;
  const marcar = (prefijoId, nombre, rango) => {{
    if (posicion < rango.inicio || posicion >= rango.fin) return;
    const el = document.getElementById(prefijoId + nombre);
    if (el) el.classList.add('activo');
  }};
  for (const e in DATOS.trazabilidad.entidades) {{
    marcar('entidad_', e, DATOS.trazabilidad.entidades[e]);
  }}
  for (const r in DATOS.trazabilidad.relaciones) {{
    marcar('relacion_', r, DATOS.trazabilidad.relaciones[r]);
  }}
}}

elTexto.addEventListener('mousemove', e => {{
  const p = posicionDeCaracter(e);
  activarDiagrama(p);
}});
elTexto.addEventListener('mouseleave', () => activarDiagrama(null));
</script>

</body>
</html>
"""
