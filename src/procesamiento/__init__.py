"""
Procesamiento de datos de AgroSmart.

Reúne los módulos que toman las respuestas de las APIs y construyen los
artefactos que consume el resto del sistema:
- `partidos`: constantes geográficas (provincias, partidos, coordenadas
  representativas) usadas para parametrizar las consultas a las APIs.
- `consolidacion`: ensambla el dataset maestro georreferenciado a partir
  de MAGyP + Open-Meteo + SoilGrids.
- `generador_hechos_prolog`: a partir del dataset procesado, calcula
  percentiles por cultivo y emite `hechos_generados.pl`.
"""
