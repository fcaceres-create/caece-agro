"""
Cliente de la API de Open-Meteo (archive-api.open-meteo.com).

Provee acceso al historial climático por coordenadas geográficas:
temperatura media, mínimas, máximas, precipitación, humedad relativa y
otras variables agronómicamente relevantes.

No requiere API key. Usa cache en disco bajo data/cache/clima/ con clave
MD5 derivada de coordenadas y rango de fechas.

Endpoint base: https://archive-api.open-meteo.com/v1/archive
"""
