"""
Constantes geográficas usadas por el pipeline de AgroSmart.

Define las regiones agrícolas argentinas, sus provincias, los partidos /
departamentos relevantes y las coordenadas representativas (centroide o
ciudad cabecera) que se usan para parametrizar las consultas a las APIs
de clima y suelo.

La estructura está pensada para mantenerse estable: si se agrega un
cultivo o una región nueva, se modifica acá y se propaga al resto del
pipeline sin tocar los clientes de APIs.
"""
