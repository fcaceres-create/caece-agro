# Clientes de APIs

Este paquete contiene los clientes de las APIs externas de las que se
alimenta AgroSmart. Cada cliente es responsable de:

- Construir URLs y parámetros.
- Aplicar reintentos con backoff exponencial (3 intentos: 1s, 2s, 4s).
- Aplicar timeouts explícitos (10 s por request).
- Cachear respuestas en `data/cache/<fuente>/`, clave MD5 sobre los
  parámetros de la consulta.
- Loguear: parámetros, hit/miss de cache, cantidad de registros y tiempo
  de respuesta.

## Fuentes

| Cliente        | Fuente                                  | API key | Cache               |
|----------------|-----------------------------------------|---------|---------------------|
| `magyp.py`     | datos.magyp.gob.ar / datosestimaciones  | No      | `data/cache/magyp/` |
| `open_meteo.py`| archive-api.open-meteo.com              | No      | `data/cache/clima/` |
| `soilgrids.py` | rest.isric.org/soilgrids/v2.0           | No      | `data/cache/suelo/` |

El cache no expira automáticamente. Si se necesita refrescar, borrar la
carpeta correspondiente.
