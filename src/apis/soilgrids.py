"""
Cliente de la API de SoilGrids (ISRIC).

Devuelve propiedades de suelo por coordenadas geográficas: pH, contenido
de arena/limo/arcilla, carbono orgánico, capacidad de intercambio
catiónico, entre otros, a distintas profundidades.

No requiere API key. Usa cache en disco bajo data/cache/suelo/ con clave
MD5 derivada de coordenadas y propiedades solicitadas.

Endpoint base: https://rest.isric.org/soilgrids/v2.0/
"""
