"""
Construye el dataset maestro georreferenciado de AgroSmart.

Toma el listado de (cultivo, partido, año) relevantes, consulta las APIs
de MAGyP (rendimiento), Open-Meteo (clima) y SoilGrids (suelo) y
ensambla un único DataFrame que se guarda en
`data/processed/dataset_maestro.csv`.

Política de fallback (ver CLAUDE.md):
- Si una llamada puntual falla, se loguea, se skipea ese registro y se
  reporta el total de skipeos al final.
- Si una API entera está caída, se aborta con mensaje claro.

Este módulo se ejecuta como script:
    python -m src.procesamiento.consolidacion
"""
