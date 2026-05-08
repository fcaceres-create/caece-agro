"""
Conocimiento agronómico de los cultivos extensivos cubiertos por
AgroSmart: ciclo (verano/invierno) y viabilidad por región productiva.

Este módulo es la **única fuente de verdad** para estos hechos. Lo
consume tanto el pipeline Python (consolidación del dataset maestro)
como, indirectamente, las reglas Prolog de la Fase III (los hechos
``cultivo_viable(C, R)`` y ``ciclo(C, V)`` se exportarán desde acá).

Mantenerlo acá (separado de ``departamentos.py``, que es puramente
geográfico) evita duplicar conocimiento agronómico en varios lugares.
"""

from __future__ import annotations


# === Ciclo de cultivo ===

# Convención de fechas (ver src/apis/open_meteo.py:resumen_campania):
#   verano  : 1-oct año X  → 31-mar año X+1
#   invierno: 1-abr año X  → 30-nov año X
_CICLO_CULTIVO: dict[str, str] = {
    "soja":    "verano",
    "maiz":    "verano",
    "sorgo":   "verano",
    "girasol": "verano",
    "arroz":   "verano",
    "algodon": "verano",
    "mani":    "verano",
    "trigo":   "invierno",
    "cebada":  "invierno",
    "avena":   "invierno",
    "centeno": "invierno",
}


def ciclo_cultivo(cultivo: str) -> str:
    """
    Devuelve ``'verano'`` o ``'invierno'`` según el cultivo canónico.

    Parámetros
    ----------
    cultivo
        Nombre canónico del cultivo (ver
        ``src/apis/magyp.CULTIVOS_SOPORTADOS``).

    Raises
    ------
    ValueError
        Si el cultivo no está cubierto por el conocimiento agronómico
        del módulo.
    """
    if cultivo not in _CICLO_CULTIVO:
        raise ValueError(
            f"Cultivo '{cultivo}' no tiene ciclo definido. "
            f"Válidos: {sorted(_CICLO_CULTIVO)}"
        )
    return _CICLO_CULTIVO[cultivo]


# === Viabilidad cultivo × región productiva ===

REGIONES: tuple[str, ...] = (
    "pampeana", "noa", "nea", "cuyo", "patagonia",
)
"""Regiones productivas de Argentina cubiertas por AgroSmart."""


# Mapeo cultivo -> set de regiones donde es viable como cultivo extensivo.
# Decisiones agronómicas:
#   - "Cuyo" se considera viable solo para cereales que se cultivan bajo
#     riego (maíz, trigo, cebada). El resto de los extensivos no es
#     significativo en condiciones cuyanas.
#   - Patagonia: solo avena (verdeo para ganadería). Todo lo demás está
#     fuera de las condiciones agroclimáticas de la región.
#   - "trigo en NOA" se acepta por la presencia en valles bajos
#     (ej: valle de Lerma en Salta).
#   - "maní" queda como cultivo pampeano (núcleo en Córdoba sur).
_VIABILIDAD: dict[str, frozenset[str]] = {
    "soja":    frozenset({"pampeana", "noa", "nea"}),
    "maiz":    frozenset({"pampeana", "noa", "nea", "cuyo"}),
    "trigo":   frozenset({"pampeana", "noa", "cuyo"}),
    "girasol": frozenset({"pampeana", "noa"}),
    "cebada":  frozenset({"pampeana", "cuyo"}),
    "sorgo":   frozenset({"pampeana", "noa", "nea"}),
    "avena":   frozenset({"pampeana", "patagonia"}),
    "centeno": frozenset({"pampeana"}),
    "arroz":   frozenset({"nea"}),
    "algodon": frozenset({"noa", "nea"}),
    "mani":    frozenset({"pampeana"}),
}


def cultivo_viable_en_region(cultivo: str, region: str) -> bool:
    """
    Indica si un cultivo es viable como extensivo en una región dada.

    Parámetros
    ----------
    cultivo
        Nombre canónico del cultivo.
    region
        Una de ``REGIONES``.

    Raises
    ------
    ValueError
        Si el cultivo o la región no están cubiertos.
    """
    if cultivo not in _VIABILIDAD:
        raise ValueError(
            f"Cultivo '{cultivo}' no tiene viabilidad definida. "
            f"Válidos: {sorted(_VIABILIDAD)}"
        )
    if region not in REGIONES:
        raise ValueError(
            f"Región '{region}' no reconocida. Válidas: {REGIONES}"
        )
    return region in _VIABILIDAD[cultivo]


def regiones_viables_para(cultivo: str) -> frozenset[str]:
    """Conjunto de regiones donde el cultivo es viable."""
    if cultivo not in _VIABILIDAD:
        raise ValueError(f"Cultivo '{cultivo}' no soportado.")
    return _VIABILIDAD[cultivo]
