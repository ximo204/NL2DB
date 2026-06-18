# Cositas

Prototipo del TFG. Implementación de la arquitectura descrita en el Capítulo 3
de la memoria: transformación de descripciones en lenguaje natural a un modelo
conceptual entidad-relación y a sentencias SQL DDL.

Este repositorio es el "esqueleto inicial" del que habla la Sección 1.4: cada
carpeta de `src/` corresponde a uno de los módulos del Capítulo 3, aunque varios
empiezan vacíos y se irán incorporando de forma incremental.

## Estructura

```
src/
  representacion/   §3.7  Gestor de representación intermedia (núcleo)
  generador_sql/    §3.10 Generador de SQL
  generador_er/     §3.8  Generador de modelo E/R
  nlp/              §3.5  Módulo NLP                        (pendiente)
  etl/              §3.6  Fase ETL                          (pendiente)
  controlador/      §3.4  Módulo controlador                (pendiente)
  comunicacion/     §3.3  Gestor de comunicación            (pendiente)
  validador/        §3.9  Módulo validador                  (pendiente)
ejemplos/           JSONs para probar los módulos sin pasar por el LLM
```
