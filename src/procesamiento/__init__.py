"""
Procesamiento de datos de AgroSmart.

Reúne los módulos que toman las respuestas de las APIs y construyen los
artefactos que consume el resto del sistema:
- `departamentos`: constantes geográficas (provincias, departamentos,
  regiones, coordenadas representativas) y predicados de viabilidad
  cultivo/región usados para parametrizar las consultas a las APIs.
- `consolidacion`: ensambla el dataset maestro georreferenciado a partir
  de MAGyP + Open-Meteo + SoilGrids.
- `generar_hechos_prolog`: a partir del dataset procesado, calcula
  percentiles por cultivo y emite `hechos_generados.pl`.
"""
