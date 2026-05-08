"""
Construye el dataset maestro georreferenciado de AgroSmart.

Cruza tres fuentes:
- **MAGyP** (rendimientos): superficie sembrada/cosechada, producción y
  rendimiento por (cultivo, departamento, campaña).
- **Open-Meteo** (clima): resumen agroclimático del ciclo (verano o
  invierno) correspondiente al cultivo, en la coord del departamento.
- **SoilGrids** (suelo): propiedades 0-30 cm en la coord del
  departamento, con fallback en dos anillos.

Cada fila resultante es ``(departamento, cultivo, campaña)`` con la
combinación completa de las tres fuentes. El ciclo del clima se
determina desde ``cultivos.ciclo_cultivo``: por ejemplo, una fila de
soja en la campaña 2023/24 trae el clima de oct-2023 a mar-2024.

Política de fallback (ver CLAUDE.md):
- Si una llamada puntual falla (cualquiera de las tres APIs), se
  loguea, se skipea ese registro y se cuenta en las estadísticas
  finales con el motivo. La corrida no aborta.
- Para suelo NaN tras el fallback de dos anillos, la fila SÍ se
  incluye en el dataset (con propiedades de suelo en NaN); la
  columna ``suelo_calidad`` lo señala como ``'sin_dato'``.

Modos de ejecución
------------------
- ``python -m src.procesamiento.consolidacion``         — corrida de prueba
  reducida (Pergamino + soja + 2022/23 a 2024/25, 3 filas esperadas).
  Pensada para validar el schema antes de la corrida completa.
- ``python -m src.procesamiento.consolidacion --full``  — corrida completa
  sobre los 33 departamentos × 11 cultivos. Guarda el CSV en
  ``data/processed/dataset_maestro.csv``.
"""

from __future__ import annotations

import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from tqdm import tqdm

from src.apis.magyp import CULTIVOS_SOPORTADOS, obtener_estimaciones
from src.apis.open_meteo import resumen_campania
from src.apis.soilgrids import obtener_propiedades_suelo
from src.procesamiento.cultivos import (
    ciclo_cultivo, cultivo_viable_en_region,
)
from src.procesamiento.departamentos import DEPARTAMENTOS, Departamento

logger = logging.getLogger(__name__)


_OUTPUT_PATH: Path = Path("data/processed/dataset_maestro.csv")
_GAP_TOLERANCIA: float = 0.05

# Mapeo del entero ``anillo_fallback`` que devuelve SoilGrids a una
# etiqueta humana que va a alimentar el EDA y, después, hechos Prolog.
_MAPEO_SUELO_CALIDAD: dict[int, str] = {
    0:  "directo",
    1:  "fallback_1km",
    2:  "fallback_3km",
    -1: "sin_dato",
}

# Schema final del DataFrame y CSV. Orden estable para reproducibilidad.
_COLUMNAS_FINALES: tuple[str, ...] = (
    "cultivo", "region", "provincia", "departamento", "campania",
    "latitud", "longitud",
    "superficie_sembrada_ha", "superficie_cosechada_ha",
    "produccion_tn", "rendimiento_kg_ha",
    "temp_media_c", "temp_max_promedio_c", "temp_min_promedio_c",
    "precipitacion_total_mm", "humedad_relativa_promedio",
    "radiacion_solar_total", "dias_helada",
    "dias_clima_disponibles", "dias_clima_esperados",
    "arcilla_pct", "arena_pct", "limo_pct", "materia_organica_pct",
    "ph", "cec",
    "suelo_anillo_fallback", "suelo_capas_disponibles", "suelo_calidad",
)


def construir_dataset_maestro(
    cultivos: Optional[list[str]] = None,
    departamentos: Optional[list[str]] = None,
    campania_desde: Optional[str] = None,
    campania_hasta: Optional[str] = None,
    guardar_csv: bool = True,
) -> pd.DataFrame:
    """
    Construye el dataset maestro cruzando MAGyP × Open-Meteo × SoilGrids.

    Parámetros
    ----------
    cultivos
        Lista de cultivos canónicos a incluir. None = los 11 de
        ``CULTIVOS_SOPORTADOS``.
    departamentos
        Lista de nombres de departamento a incluir. None = los 33 de
        ``DEPARTAMENTOS``.
    campania_desde, campania_hasta
        Rango de campañas en formato ``"YYYY/YYYY"``. None = todas las
        que tenga MAGyP.
    guardar_csv
        Si True, escribe el resultado a
        ``data/processed/dataset_maestro.csv``. Útil ponerlo en False
        en corridas de prueba.

    Returns
    -------
    pandas.DataFrame con las columnas declaradas en ``_COLUMNAS_FINALES``.
    """
    cultivos_objetivo: list[str] = (
        list(cultivos) if cultivos else list(CULTIVOS_SOPORTADOS)
    )
    deptos_objetivo: list[Departamento] = (
        [d for d in DEPARTAMENTOS if d.nombre in departamentos]
        if departamentos else list(DEPARTAMENTOS)
    )

    # Resumen al inicio: cuántas combinaciones se van a explorar.
    combos_total = len(deptos_objetivo) * len(cultivos_objetivo)
    combos_viables = sum(
        1
        for d in deptos_objetivo
        for c in cultivos_objetivo
        if cultivo_viable_en_region(c, d.region)
    )
    logger.info(
        "[Consolidación] Inicio. %d departamentos × %d cultivos = "
        "%d combinaciones potenciales, %d viables a explorar. "
        "Rango campañas: %s..%s.",
        len(deptos_objetivo), len(cultivos_objetivo),
        combos_total, combos_viables,
        campania_desde or "(sin filtro)",
        campania_hasta or "(sin filtro)",
    )

    skipeos: Counter[str] = Counter()
    filas: list[dict[str, Any]] = []
    suelo_por_depto: dict[str, dict[str, Any]] = {}

    iter_combos = [
        (d, c) for d in deptos_objetivo for c in cultivos_objetivo
    ]
    pbar = tqdm(iter_combos, desc="Consolidando", unit="combo")

    for depto, cultivo in pbar:
        # 0. Viabilidad cultivo × región.
        if not cultivo_viable_en_region(cultivo, depto.region):
            skipeos["viabilidad"] += 1
            continue

        # 1. MAGyP — filas (cultivo, depto) en el rango pedido.
        try:
            df_magyp = obtener_estimaciones(
                cultivo=cultivo,
                provincia=depto.provincia,
                departamento=depto.nombre,
                campania_desde=campania_desde,
                campania_hasta=campania_hasta,
            )
        except Exception as e:
            logger.warning(
                "[Consolidación] MAGyP falló para (%s/%s, %s): %s",
                depto.provincia, depto.nombre, cultivo, e,
            )
            skipeos["magyp_error"] += 1
            continue

        if df_magyp.empty:
            skipeos["magyp_sin_datos"] += 1
            continue

        # 2. SoilGrids — una sola vez por departamento (ya cacheado en
        # disco, pero evitamos re-deserializar el JSON 11 veces).
        if depto.nombre not in suelo_por_depto:
            try:
                suelo_por_depto[depto.nombre] = obtener_propiedades_suelo(
                    depto.latitud, depto.longitud,
                )
            except Exception as e:
                logger.warning(
                    "[Consolidación] SoilGrids falló para %s: %s",
                    depto.nombre, e,
                )
                skipeos["suelo_error"] += len(df_magyp)
                continue
        suelo = suelo_por_depto[depto.nombre]

        # 3. Open-Meteo — una llamada por (depto, cultivo, campaña).
        ciclo = ciclo_cultivo(cultivo)
        for fila_magyp in df_magyp.itertuples(index=False):
            try:
                anio = int(str(fila_magyp.campania).split("/")[0])
            except (ValueError, AttributeError):
                skipeos["campania_invalida"] += 1
                continue

            try:
                clima = resumen_campania(
                    depto.latitud, depto.longitud, anio, ciclo,
                )
            except ValueError as e:
                # Caso típico: ciclo termina después de hoy.
                logger.debug(
                    "[Consolidación] Clima skip (%s, %s, %s): %s",
                    depto.nombre, cultivo, fila_magyp.campania, e,
                )
                skipeos["clima_fecha_futura"] += 1
                continue
            except Exception as e:
                logger.warning(
                    "[Consolidación] Clima error (%s, %s, %s): %s",
                    depto.nombre, cultivo, fila_magyp.campania, e,
                )
                skipeos["clima_error"] += 1
                continue

            filas.append(_construir_fila(depto, cultivo, fila_magyp, clima, suelo))

            if len(filas) % 50 == 0:
                logger.info("[Consolidación] %d filas generadas.", len(filas))

    df = pd.DataFrame(filas, columns=list(_COLUMNAS_FINALES))

    if guardar_csv and not df.empty:
        _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(_OUTPUT_PATH, index=False, encoding="utf-8")
        logger.info(
            "[Consolidación] CSV guardado en %s (%d filas).",
            _OUTPUT_PATH, len(df),
        )

    _imprimir_estadisticas(df, skipeos)
    return df


def _construir_fila(
    depto: Departamento,
    cultivo: str,
    fila_magyp: Any,
    clima: dict[str, Any],
    suelo: dict[str, Any],
) -> dict[str, Any]:
    """Combina las tres fuentes en una fila del schema final."""
    af = int(suelo.get("anillo_fallback", 0))
    return {
        "cultivo": cultivo,
        "region": depto.region,
        "provincia": depto.provincia,
        "departamento": depto.nombre,
        "campania": fila_magyp.campania,
        "latitud": depto.latitud,
        "longitud": depto.longitud,
        "superficie_sembrada_ha": fila_magyp.superficie_sembrada_ha,
        "superficie_cosechada_ha": fila_magyp.superficie_cosechada_ha,
        "produccion_tn": fila_magyp.produccion_tn,
        "rendimiento_kg_ha": fila_magyp.rendimiento_kg_ha,
        "temp_media_c": clima["temp_media_c"],
        "temp_max_promedio_c": clima["temp_max_promedio_c"],
        "temp_min_promedio_c": clima["temp_min_promedio_c"],
        "precipitacion_total_mm": clima["precipitacion_total_mm"],
        "humedad_relativa_promedio": clima["humedad_relativa_promedio"],
        "radiacion_solar_total": clima["radiacion_solar_total"],
        "dias_helada": clima["dias_helada"],
        "dias_clima_disponibles": clima["dias_disponibles"],
        "dias_clima_esperados": clima["dias_esperados"],
        "arcilla_pct": suelo["arcilla_pct"],
        "arena_pct": suelo["arena_pct"],
        "limo_pct": suelo["limo_pct"],
        "materia_organica_pct": suelo["materia_organica_pct"],
        "ph": suelo["ph"],
        "cec": suelo["cec"],
        "suelo_anillo_fallback": af,
        "suelo_capas_disponibles": int(suelo.get("capas_disponibles", 0)),
        "suelo_calidad": _MAPEO_SUELO_CALIDAD.get(af, "desconocido"),
    }


def _imprimir_estadisticas(df: pd.DataFrame, skipeos: Counter[str]) -> None:
    """Imprime resumen al final de la corrida."""
    print("\n=== Estadísticas finales de la consolidación ===")
    print(f"Total filas generadas: {len(df)}")

    print("\nSkipeos por motivo:")
    if skipeos:
        for motivo, n in skipeos.most_common():
            print(f"  {motivo:<22} {n}")
    else:
        print("  (ninguno)")

    if df.empty:
        print()
        return

    print("\nCobertura por cultivo:")
    cov_c = df["cultivo"].value_counts().sort_index()
    for c, n in cov_c.items():
        print(f"  {c:<10} {n}")

    print("\nCobertura por región:")
    cov_r = df["region"].value_counts()
    for r, n in cov_r.items():
        print(f"  {r:<11} {n}")

    n_suelo_sin_dato = int((df["suelo_anillo_fallback"] == -1).sum())
    print(f"\nFilas con suelo NaN (sin_dato): {n_suelo_sin_dato}")

    gap_relativo = 1 - df["dias_clima_disponibles"] / df["dias_clima_esperados"]
    n_gap = int((gap_relativo > _GAP_TOLERANCIA).sum())
    print(f"Filas con gap climático > 5%:   {n_gap}")
    print()


def _imprimir_muestras_y_cobertura_deptos(df: pd.DataFrame) -> None:
    """
    Output extra para corrida completa: primeras 10 filas absolutas,
    muestra estratificada (2 por cultivo) y top/bottom de departamentos
    con detección de departamentos sin filas.
    """
    print("\n=== Primeras 10 filas (orden de generación) ===")
    print(df.head(10).to_string(index=False))

    print("\n=== Muestra estratificada: 2 primeras filas por cultivo ===")
    muestra = df.groupby("cultivo", group_keys=False).head(2)
    print(muestra.to_string(index=False))

    conteo_dept = df["departamento"].value_counts()
    print("\n=== Top 5 departamentos por cantidad de filas ===")
    for nombre, n in conteo_dept.head(5).items():
        print(f"  {nombre:<25} {n}")
    print("\n=== Bottom 5 departamentos por cantidad de filas ===")
    for nombre, n in conteo_dept.tail(5).items():
        print(f"  {nombre:<25} {n}")

    deptos_configurados = {d.nombre for d in DEPARTAMENTOS}
    deptos_con_filas = set(df["departamento"].unique())
    deptos_sin_filas = sorted(deptos_configurados - deptos_con_filas)
    if not deptos_sin_filas:
        print("\n=== Departamentos con 0 filas: ninguno ===")
        return

    print(f"\n=== Departamentos con 0 filas ({len(deptos_sin_filas)}) ===")
    for nombre in deptos_sin_filas:
        d = next(d for d in DEPARTAMENTOS if d.nombre == nombre)
        n_viables = sum(
            1 for c in CULTIVOS_SOPORTADOS
            if cultivo_viable_en_region(c, d.region)
        )
        print(
            f"  {nombre:<25} region={d.region:<10} "
            f"cultivos viables en region={n_viables}"
        )


# === Bloque de ejecución ===

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if "--full" in sys.argv:
        # Limitamos a campañas post-2000 para garantizar comparabilidad
        # tecnológica del período de referencia: post-introducción de
        # soja RR y consolidación de la siembra directa. Las campañas
        # 1969-1999 introducirían ruido agronómico (paquetes
        # tecnológicos heterogéneos) que contamina tanto la regresión
        # de Fase II como los rangos óptimos de Prolog.
        print(
            ">>> Corrida COMPLETA: 33 departamentos × 11 cultivos, "
            "campañas desde 2000/2001.\n"
        )
        df_final = construir_dataset_maestro(campania_desde="2000/2001")
    else:
        print(
            ">>> Corrida de PRUEBA: Pergamino + soja + 2022/2023..2024/2025.\n"
            "    Para correr el dataset completo: --full\n"
        )
        df_final = construir_dataset_maestro(
            cultivos=["soja"],
            departamentos=["Pergamino"],
            campania_desde="2022/2023",
            campania_hasta="2024/2025",
            guardar_csv=False,
        )

    print("\n=== DataFrame resultante ===")
    if df_final.empty:
        print("(vacío)")
    else:
        with pd.option_context(
            "display.max_columns", None,
            "display.width", 220,
            "display.max_rows", None,
        ):
            if "--full" in sys.argv:
                _imprimir_muestras_y_cobertura_deptos(df_final)
            else:
                # En prueba, mostrar todas las filas transpuestas.
                print(df_final.T)
