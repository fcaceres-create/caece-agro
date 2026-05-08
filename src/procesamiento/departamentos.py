"""
Catálogo geográfico de departamentos para la consolidación del dataset
maestro de AgroSmart.

Cobertura
---------
33 departamentos representativos repartidos por las 5 regiones
productivas argentinas:

- Pampeana: 16 — núcleo del MVP, donde está el grueso del dataset.
- NOA: 7 — Salta, Tucumán, Jujuy, Santiago del Estero.
- NEA: 7 — Santa Fe norte, Corrientes, Chaco, Entre Ríos norte.
- Cuyo: 2 — Mendoza (cereales bajo riego).
- Patagonia: 1 — Río Negro.

Esta lista está pensada como **subset representativo para el MVP**. Para
escalar a la totalidad de los ~250 departamentos argentinos, conviene
hacer un join entre el output de MAGyP (que trae ``departamento_id``
INDEC) y un catálogo oficial de centroides INDEC. Esa extensión queda
documentada como evolución natural pero fuera del alcance del MVP.

Coordenadas
-----------
Cada entrada tiene la coordenada de la **cabecera departamental** (la
ciudad principal del departamento), no el centroide geométrico del
polígono administrativo. Justificación: las cabeceras son la
representación geográfica más estable y trazable; los centroides
geométricos pueden caer en zonas remotas, no productivas, o sobre
píxeles sin datos. Este criterio combina bien con el fallback de
SoilGrids (dos anillos paralelos) que ya rescata los casos donde el
píxel exacto cae en un agujero urbano.

Si el EDA detecta resultados anómalos para un departamento puntual
(ej: clima muy distinto al esperado para la región), conviene refinar
manualmente la coordenada de ese caso. Ver comentario al final del
archivo sobre fuentes y refinamiento.

Los nombres de ``nombre`` y ``provincia`` están **validados contra el
CSV maestro de MAGyP** (campo ``departamento`` y ``provincia`` con
tildes y caracteres exactos).
"""

from __future__ import annotations

from typing import NamedTuple


class Departamento(NamedTuple):
    """
    Departamento de cobertura del dataset maestro.

    Attributes
    ----------
    nombre
        Nombre canónico tal como aparece en el CSV maestro de MAGyP.
    provincia
        Nombre de la provincia tal como aparece en MAGyP.
    region
        Una de las 5 regiones productivas argentinas:
        ``'pampeana' | 'noa' | 'nea' | 'cuyo' | 'patagonia'``.
    latitud, longitud
        Coordenadas (WGS84) de la cabecera departamental.
    """
    nombre: str
    provincia: str
    region: str
    latitud: float
    longitud: float


DEPARTAMENTOS: tuple[Departamento, ...] = (
    # === Pampeana — Buenos Aires (5) ===
    Departamento("Pergamino",          "Buenos Aires", "pampeana", -33.89, -60.57),
    Departamento("Junín",              "Buenos Aires", "pampeana", -34.59, -60.95),
    Departamento("9 de Julio",         "Buenos Aires", "pampeana", -35.45, -60.88),
    Departamento("Tres Arroyos",       "Buenos Aires", "pampeana", -38.38, -60.27),
    Departamento("General Pueyrredón", "Buenos Aires", "pampeana", -38.00, -57.55),

    # === Pampeana — Córdoba (3) ===
    Departamento("Marcos Juárez",      "Córdoba",      "pampeana", -32.70, -62.10),
    Departamento("Río Cuarto",         "Córdoba",      "pampeana", -33.13, -64.35),
    Departamento("Unión",              "Córdoba",      "pampeana", -32.63, -62.69),

    # === Pampeana — Santa Fe (3) ===
    Departamento("General López",      "Santa Fe",     "pampeana", -33.74, -61.97),
    Departamento("Las Colonias",       "Santa Fe",     "pampeana", -31.45, -60.93),
    Departamento("San Justo",          "Santa Fe",     "pampeana", -30.78, -60.59),

    # === Pampeana — Entre Ríos (2) ===
    Departamento("Paraná",             "Entre Ríos",   "pampeana", -31.73, -60.53),
    Departamento("Gualeguaychú",       "Entre Ríos",   "pampeana", -33.01, -58.51),

    # === Pampeana — La Pampa (2) ===
    Departamento("Realicó",            "La Pampa",     "pampeana", -35.04, -64.25),
    Departamento("Capital",            "La Pampa",     "pampeana", -36.62, -64.29),

    # === Pampeana — San Luis (1, bisagra Pampa-Cuyo) ===
    Departamento("General Pedernera",  "San Luis",     "pampeana", -33.67, -65.46),

    # === NOA — Salta (2) ===
    Departamento("Anta",               "Salta",                "noa", -25.04, -64.60),
    Departamento("Orán",               "Salta",                "noa", -23.13, -64.32),

    # === NOA — Tucumán (2) ===
    Departamento("Burruyacú",          "Tucumán",              "noa", -26.50, -64.74),
    Departamento("Cruz Alta",          "Tucumán",              "noa", -26.92, -65.12),

    # === NOA — Jujuy (1) ===
    Departamento("San Pedro",          "Jujuy",                "noa", -24.23, -64.87),

    # === NOA — Santiago del Estero (2) ===
    Departamento("Pellegrini",         "Santiago del Estero",  "noa", -26.23, -62.43),
    Departamento("Río Hondo",          "Santiago del Estero",  "noa", -27.49, -64.86),

    # === NEA — Santa Fe norte (1) ===
    Departamento("General Obligado",   "Santa Fe",     "nea", -29.03, -59.65),

    # === NEA — Corrientes (3) ===
    Departamento("Mercedes",           "Corrientes",   "nea", -29.18, -58.08),
    Departamento("Goya",               "Corrientes",   "nea", -29.14, -59.27),
    Departamento("Concepción",         "Corrientes",   "nea", -28.40, -57.91),

    # === NEA — Chaco (2) ===
    Departamento("Comandante Fernández","Chaco",       "nea", -26.78, -60.45),
    Departamento("1° de Mayo",         "Chaco",        "nea", -27.03, -59.10),

    # === NEA — Entre Ríos norte (1) ===
    Departamento("Concordia",          "Entre Ríos",   "nea", -31.39, -58.02),

    # === Cuyo — Mendoza (2) ===
    Departamento("Lavalle",            "Mendoza",      "cuyo", -32.72, -68.53),
    Departamento("General Alvear",     "Mendoza",      "cuyo", -34.97, -67.69),

    # === Patagonia — Río Negro (1) ===
    Departamento("General Roca",       "Río Negro",    "patagonia", -39.03, -67.58),
)


# ──────────────────────────────────────────────────────────────────────
# Fuente de coordenadas
# ──────────────────────────────────────────────────────────────────────
# Las latitudes y longitudes corresponden a la cabecera (ciudad
# principal) de cada departamento, según referencias cruzadas de
# Wikipedia (es), GeoNames y mapas oficiales del INDEC. Precisión
# aproximada: ±0.01° (~1 km), suficiente para los propósitos del MVP
# considerando que:
#   - SoilGrids tiene grilla nativa de ~250 m con fallback en dos
#     anillos (±1.1 km y ±3.3 km) que rescata los huecos urbanos.
#   - Open-Meteo "snappea" a su grilla ERA5 de ~9 km de todos modos.
#
# Si el EDA detecta resultados anómalos en algún departamento puntual
# (ej: temperatura media muy fuera del rango regional), conviene
# refinar manualmente la coord de ese caso para apuntar a una zona
# claramente productiva del partido en lugar de la cabecera urbana.
