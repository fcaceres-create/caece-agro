"""
Cliente de la API del MAGyP (Ministerio de Agricultura, Ganadería y Pesca
de la Nación Argentina).

Expone funciones para descargar series históricas de producción y
rendimiento por cultivo, provincia y partido. Usa cache en disco bajo
data/cache/magyp/ con clave MD5 derivada de los parámetros de consulta.

Endpoints relevantes:
- https://datos.magyp.gob.ar/series/api
- https://datosestimaciones.magyp.gob.ar
"""
