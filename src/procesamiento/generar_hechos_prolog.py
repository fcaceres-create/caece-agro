"""
Generador automático de hechos Prolog para el sistema AgroSmart.

Materializa el primer puente del aporte propio (Datos -> Conocimiento):
toma los percentiles por cultivo calculados en el EDA (Fase II) y los
emite como hechos Prolog en ``src/prolog/hechos_generados.pl``.

Las reglas del sistema experto (Fase III) consumen esos hechos en lugar
de tener umbrales hardcodeados, de modo que todo rango óptimo proviene
de evidencia estadística sobre datos argentinos reales.

Se ejecuta como módulo desde la raíz del proyecto::

    python -m src.procesamiento.generar_hechos_prolog

Lecturas de entrada:
- ``data/processed/rangos_optimos_por_cultivo.csv`` (producido por el
  notebook ``02_eda_consolidado.ipynb``).
- ``data/processed/dataset_maestro.csv`` (producido por
  ``src/procesamiento/consolidacion.py``).

Salida:
- ``src/prolog/hechos_generados.pl`` con 6 bloques de hechos:
  ``cultivo_soportado/1``, ``region_operacional/1``,
  ``cultivo_en_region/2``, ``rango_optimo/4``, ``mediana_optima/3``,
  ``rendimiento_esperado/4``.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

# ---------------------------------------------------------------------------
# Constantes del módulo
# ---------------------------------------------------------------------------

#: Raíz del repositorio (este archivo vive en ``src/procesamiento/``).
RAIZ_PROYECTO: Path = Path(__file__).resolve().parents[2]

CSV_RANGOS: Path = RAIZ_PROYECTO / "data" / "processed" / "rangos_optimos_por_cultivo.csv"
CSV_DATASET: Path = RAIZ_PROYECTO / "data" / "processed" / "dataset_maestro.csv"
PL_SALIDA: Path = RAIZ_PROYECTO / "src" / "prolog" / "hechos_generados.pl"

#: Regiones donde el sistema opera efectivamente (ver
#: ``docs/recuperacion_de_datos.md`` sección 6: Cuyo y Patagonia quedaron
#: con 0 filas porque MAGyP no reporta esos cultivos en esas regiones).
REGIONES_OPERACIONALES: tuple[str, ...] = ("pampeana", "noa", "nea")

#: Orden canónico de cultivos para el bloque ``cultivo_soportado/1``.
#: Coincide con el orden agronómico usado en el EDA.
ORDEN_CULTIVOS: tuple[str, ...] = (
    "soja",
    "maiz",
    "trigo",
    "girasol",
    "cebada",
    "sorgo",
    "avena",
    "centeno",
    "arroz",
    "algodon",
    "mani",
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def _configurar_logging() -> None:
    """Configura logging con timestamp ISO y nivel INFO si no hay handlers."""
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Carga de inputs
# ---------------------------------------------------------------------------


def cargar_rangos_optimos(path: Path = CSV_RANGOS) -> pd.DataFrame:
    """Carga el CSV de rangos óptimos por cultivo y variable.

    Espera columnas: ``cultivo, variable, p10, mediana, p90, n_filas``.

    Parameters
    ----------
    path:
        Ruta al CSV de rangos óptimos.

    Returns
    -------
    DataFrame con los rangos óptimos.

    Raises
    ------
    FileNotFoundError
        Si el archivo no existe (típicamente porque el notebook 02 no
        se corrió todavía).
    """
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Para regenerarlo, abrir y ejecutar el notebook "
            f"'notebooks/02_eda_consolidado.ipynb' (sección de exportación de "
            f"rangos óptimos)."
        )
    df = pd.read_csv(path)
    columnas_requeridas = {"cultivo", "variable", "p10", "mediana", "p90"}
    faltantes = columnas_requeridas - set(df.columns)
    if faltantes:
        raise ValueError(
            f"El CSV de rangos óptimos {path} no contiene las columnas "
            f"requeridas: faltan {sorted(faltantes)}."
        )
    logger.info(
        "Rangos óptimos cargados desde %s: %d filas, %d cultivos, %d variables.",
        path.name,
        len(df),
        df["cultivo"].nunique(),
        df["variable"].nunique(),
    )
    return df


def cargar_dataset_maestro(path: Path = CSV_DATASET) -> pd.DataFrame:
    """Carga el dataset maestro consolidado.

    Necesario para derivar dos bloques de hechos:
    - ``cultivo_en_region/2``: por presencia (n>0) en ``groupby(cultivo, region)``.
    - ``rendimiento_esperado/4``: percentiles 10/50/90 de ``rendimiento_kg_ha``
      sobre el dataset completo (sin filtrar por rinde > 0).

    Raises
    ------
    FileNotFoundError
        Si el archivo no existe (correr antes ``consolidacion.py``).
    """
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Para regenerarlo correr "
            f"'python -m src.procesamiento.consolidacion'."
        )
    df = pd.read_csv(path)
    columnas_requeridas = {"cultivo", "region", "rendimiento_kg_ha"}
    faltantes = columnas_requeridas - set(df.columns)
    if faltantes:
        raise ValueError(
            f"El dataset maestro {path} no contiene las columnas requeridas: "
            f"faltan {sorted(faltantes)}."
        )
    logger.info(
        "Dataset maestro cargado desde %s: %d filas, %d columnas.",
        path.name,
        len(df),
        len(df.columns),
    )
    return df


# ---------------------------------------------------------------------------
# Derivaciones
# ---------------------------------------------------------------------------


def derivar_cultivos_soportados(rangos: pd.DataFrame) -> list[str]:
    """Lista cultivos soportados respetando el orden canónico.

    Cualquier cultivo presente en el CSV de rangos pero ausente del orden
    canónico se anexa al final (defensivo: no debería pasar).
    """
    presentes = set(rangos["cultivo"].unique())
    ordenados: list[str] = [c for c in ORDEN_CULTIVOS if c in presentes]
    extra = sorted(presentes - set(ordenados))
    if extra:
        logger.warning(
            "Cultivos en el CSV de rangos no contemplados en ORDEN_CULTIVOS: %s. "
            "Se anexan al final.",
            extra,
        )
    return ordenados + extra


def derivar_cultivo_en_region(
    dataset: pd.DataFrame, regiones: Iterable[str]
) -> list[tuple[str, str]]:
    """Devuelve los pares (cultivo, region) presentes en el dataset.

    Criterio: simple presencia (al menos una fila para esa combinación).
    NO se filtra por ``rendimiento_kg_ha > 0``: agronómicamente, el hecho
    "avena se cultiva en pampeana" es verdadero aunque algunas campañas
    sean catastróficas o sean siembras para verdeo con rinde 0.

    El resultado se filtra a las regiones operacionales del sistema y se
    ordena por (cultivo, region) según el orden canónico de cultivos para
    que el ``.pl`` salga determinístico.
    """
    regiones_validas = set(regiones)
    grupos = (
        dataset.groupby(["cultivo", "region"])
        .size()
        .reset_index(name="n")
    )
    grupos = grupos[(grupos["n"] > 0) & (grupos["region"].isin(regiones_validas))]

    orden_cultivo = {c: i for i, c in enumerate(ORDEN_CULTIVOS)}
    orden_region = {r: i for i, r in enumerate(regiones)}
    grupos = grupos.assign(
        _oc=grupos["cultivo"].map(lambda c: orden_cultivo.get(c, 999)),
        _or=grupos["region"].map(lambda r: orden_region.get(r, 999)),
    ).sort_values(["_oc", "_or"])

    pares: list[tuple[str, str]] = list(zip(grupos["cultivo"], grupos["region"]))
    logger.info(
        "Pares cultivo×region derivados (n>0) en regiones operacionales: %d.",
        len(pares),
    )
    return pares


def derivar_rendimiento_esperado(
    dataset: pd.DataFrame, cultivos: Iterable[str]
) -> dict[str, tuple[int, int, int]]:
    """Calcula percentiles 10/50/90 de rendimiento por cultivo.

    Se calcula sobre el **dataset completo** (no solo sobre campañas
    exitosas), excluyendo solo NaN. Las filas con rinde 0 (campañas
    catastróficas) se conservan: forman parte legítima de la
    distribución observada del cultivo en la zona productiva.

    Returns
    -------
    Mapeo ``cultivo -> (p10, mediana, p90)`` en kg/ha redondeados a int.
    """
    resultado: dict[str, tuple[int, int, int]] = {}
    for cultivo in cultivos:
        serie = dataset.loc[
            dataset["cultivo"] == cultivo, "rendimiento_kg_ha"
        ].dropna()
        if serie.empty:
            logger.warning(
                "Sin datos de rendimiento para cultivo '%s'. Se omite del bloque "
                "rendimiento_esperado.",
                cultivo,
            )
            continue
        p10 = int(round(float(serie.quantile(0.10))))
        med = int(round(float(serie.quantile(0.50))))
        p90 = int(round(float(serie.quantile(0.90))))
        resultado[cultivo] = (p10, med, p90)
    logger.info(
        "Rendimiento esperado calculado para %d cultivos.", len(resultado)
    )
    return resultado


# ---------------------------------------------------------------------------
# Renderizado del .pl
# ---------------------------------------------------------------------------


def _formato_num(valor: float) -> str:
    """Formatea un float para el .pl con 2 decimales y notación canónica."""
    return f"{valor:.2f}"


def renderizar_pl(
    cultivos: list[str],
    regiones: tuple[str, ...],
    pares_cultivo_region: list[tuple[str, str]],
    rangos: pd.DataFrame,
    rendimiento: dict[str, tuple[int, int, int]],
    timestamp_iso: str,
) -> str:
    """Construye el contenido completo del archivo Prolog generado."""
    lineas: list[str] = []
    lineas.append(
        "% ====================================================================="
    )
    lineas.append("% AgroSmart - Hechos generados automáticamente desde el dataset")
    lineas.append("% Generado por: src/procesamiento/generar_hechos_prolog.py")
    lineas.append("% Fuente: data/processed/rangos_optimos_por_cultivo.csv")
    lineas.append("%         data/processed/dataset_maestro.csv")
    lineas.append(f"% Fecha de generación: {timestamp_iso}")
    lineas.append("% No editar manualmente. Para regenerar:")
    lineas.append("%   python -m src.procesamiento.generar_hechos_prolog")
    lineas.append(
        "% ====================================================================="
    )
    lineas.append("")

    # --- Bloque 1: cultivo_soportado/1 ---
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    lineas.append("% Cultivos soportados por el sistema (los 11 cultivos canónicos)")
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    for c in cultivos:
        lineas.append(f"cultivo_soportado({c}).")
    lineas.append("")

    # --- Bloque 2: region_operacional/1 ---
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    lineas.append("% Regiones operacionales del sistema")
    lineas.append("% (Cuyo y Patagonia quedaron sin cobertura efectiva en MAGyP;")
    lineas.append("%  ver docs/recuperacion_de_datos.md sección 6)")
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    for r in regiones:
        lineas.append(f"region_operacional({r}).")
    lineas.append("")

    # --- Bloque 3: cultivo_en_region/2 ---
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    lineas.append("% Cultivo se siembra en región")
    lineas.append("% Criterio: presencia en el dataset (n>0), sin filtrar por")
    lineas.append("% rendimiento. Una campaña con rinde 0 igual cuenta como siembra.")
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    for cultivo, region in pares_cultivo_region:
        lineas.append(f"cultivo_en_region({cultivo}, {region}).")
    lineas.append("")

    # --- Bloque 4: rango_optimo/4 ---
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    lineas.append("% Rangos óptimos por cultivo y variable")
    lineas.append("% Formato: rango_optimo(Cultivo, Variable, P10, P90)")
    lineas.append("% Derivación: percentiles 10 y 90 sobre campañas con rinde > mediana")
    lineas.append("% (calculados en notebooks/02_eda_consolidado.ipynb)")
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    rangos_ordenados = _ordenar_rangos(rangos, cultivos)
    for _, fila in rangos_ordenados.iterrows():
        lineas.append(
            f"rango_optimo({fila['cultivo']}, {fila['variable']}, "
            f"{_formato_num(fila['p10'])}, {_formato_num(fila['p90'])})."
        )
    lineas.append("")

    # --- Bloque 5: mediana_optima/3 ---
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    lineas.append("% Mediana óptima por cultivo y variable")
    lineas.append("% Formato: mediana_optima(Cultivo, Variable, Mediana)")
    lineas.append("% Útil para reglas de 'condición ideal' (centro del rango).")
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    for _, fila in rangos_ordenados.iterrows():
        lineas.append(
            f"mediana_optima({fila['cultivo']}, {fila['variable']}, "
            f"{_formato_num(fila['mediana'])})."
        )
    lineas.append("")

    # --- Bloque 6: rendimiento_esperado/4 ---
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    lineas.append("% Rendimiento esperado por cultivo (kg/ha)")
    lineas.append("% Formato: rendimiento_esperado(Cultivo, P10, Mediana, P90)")
    lineas.append("% Derivación: percentiles del dataset COMPLETO (no solo campañas")
    lineas.append("% exitosas). Útil para diagnosticar si un cultivo está rindiendo")
    lineas.append("% por debajo de lo esperado para esa zona.")
    lineas.append(
        "% ---------------------------------------------------------------------"
    )
    for cultivo in cultivos:
        if cultivo not in rendimiento:
            continue
        p10, med, p90 = rendimiento[cultivo]
        lineas.append(f"rendimiento_esperado({cultivo}, {p10}, {med}, {p90}).")
    lineas.append("")

    return "\n".join(lineas)


def _ordenar_rangos(rangos: pd.DataFrame, cultivos: list[str]) -> pd.DataFrame:
    """Ordena el DataFrame de rangos según el orden canónico de cultivos.

    Dentro de cada cultivo conserva el orden original de variables del CSV
    (tal como el EDA las exportó), para que el .pl sea determinístico y
    legible.
    """
    orden_cultivo = {c: i for i, c in enumerate(cultivos)}
    df = rangos.copy()
    df["_orden_cultivo"] = df["cultivo"].map(lambda c: orden_cultivo.get(c, 999))
    df["_orden_variable"] = range(len(df))
    return df.sort_values(["_orden_cultivo", "_orden_variable"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Validación con pyswip
# ---------------------------------------------------------------------------


def validar_con_pyswip(path_pl: Path) -> None:
    """Carga el .pl recién generado y corre 5 consultas de prueba.

    Si alguna consulta falla, lanza ``RuntimeError``.
    """
    try:
        from pyswip import Prolog
    except Exception as exc:
        raise RuntimeError(
            "No se pudo importar pyswip. Verificar instalación de SWI-Prolog y "
            "variables de entorno (ver CLAUDE.md → Setup local)."
        ) from exc

    prolog = Prolog()
    # Path Prolog usa forward slashes incluso en Windows.
    ruta_prolog = str(path_pl).replace("\\", "/")
    list(prolog.query(f"consult('{ruta_prolog}')"))
    logger.info("Archivo .pl cargado en SWI-Prolog: %s", ruta_prolog)

    # 1) cultivo_soportado(soja).
    res1 = list(prolog.query("cultivo_soportado(soja)"))
    if not res1:
        raise RuntimeError("Falló: cultivo_soportado(soja) debería ser true.")
    logger.info("OK consulta 1: cultivo_soportado(soja) -> true")

    # 2) cultivo_en_region(arroz, nea).
    res2 = list(prolog.query("cultivo_en_region(arroz, nea)"))
    if not res2:
        raise RuntimeError("Falló: cultivo_en_region(arroz, nea) debería ser true.")
    logger.info("OK consulta 2: cultivo_en_region(arroz, nea) -> true")

    # 3) cultivo_en_region(arroz, pampeana). DEBE ser false (lista vacía).
    res3 = list(prolog.query("cultivo_en_region(arroz, pampeana)"))
    if res3:
        raise RuntimeError(
            "Falló: cultivo_en_region(arroz, pampeana) debería ser false."
        )
    logger.info("OK consulta 3: cultivo_en_region(arroz, pampeana) -> false")

    # 4) rango_optimo(soja, ph, P10, P90).
    res4 = list(prolog.query("rango_optimo(soja, ph, P10, P90)"))
    if not res4:
        raise RuntimeError(
            "Falló: rango_optimo(soja, ph, P10, P90) no devolvió resultados."
        )
    p10, p90 = float(res4[0]["P10"]), float(res4[0]["P90"])
    if not (6.0 <= p10 <= 6.5 and 6.7 <= p90 <= 7.1):
        raise RuntimeError(
            f"Falló: rango_optimo(soja, ph) devolvió P10={p10}, P90={p90}; "
            f"se esperaba P10≈6.18, P90≈6.96."
        )
    logger.info(
        "OK consulta 4: rango_optimo(soja, ph) -> P10=%.2f, P90=%.2f", p10, p90
    )

    # 5) rendimiento_esperado(maiz, P10, MED, P90).
    res5 = list(prolog.query("rendimiento_esperado(maiz, P10, MED, P90)"))
    if not res5:
        raise RuntimeError(
            "Falló: rendimiento_esperado(maiz, ...) no devolvió resultados."
        )
    logger.info(
        "OK consulta 5: rendimiento_esperado(maiz) -> P10=%s, MED=%s, P90=%s",
        res5[0]["P10"],
        res5[0]["MED"],
        res5[0]["P90"],
    )


# ---------------------------------------------------------------------------
# Estadísticas finales
# ---------------------------------------------------------------------------


def imprimir_estadisticas(
    path_pl: Path,
    cultivos: list[str],
    regiones: tuple[str, ...],
    pares_cultivo_region: list[tuple[str, str]],
    rangos: pd.DataFrame,
    rendimiento: dict[str, tuple[int, int, int]],
) -> None:
    """Reporta cantidad de hechos por tipo, total y tamaño del archivo."""
    n_cs = len(cultivos)
    n_ro = len(regiones)
    n_cer = len(pares_cultivo_region)
    n_rango = len(rangos)
    n_med = len(rangos)
    n_rend = len(rendimiento)
    total = n_cs + n_ro + n_cer + n_rango + n_med + n_rend
    tamanio = path_pl.stat().st_size

    logger.info("=" * 70)
    logger.info("RESUMEN DE GENERACIÓN")
    logger.info("=" * 70)
    logger.info("Archivo generado: %s", path_pl)
    logger.info("Tamaño: %d bytes (%.1f KB)", tamanio, tamanio / 1024)
    logger.info("Total de hechos: %d", total)
    logger.info("  - cultivo_soportado/1   : %d", n_cs)
    logger.info("  - region_operacional/1  : %d", n_ro)
    logger.info("  - cultivo_en_region/2   : %d", n_cer)
    logger.info("  - rango_optimo/4        : %d", n_rango)
    logger.info("  - mediana_optima/3      : %d", n_med)
    logger.info("  - rendimiento_esperado/4: %d", n_rend)
    logger.info("=" * 70)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> int:
    """Genera el .pl y lo valida. Devuelve código de salida."""
    _configurar_logging()
    logger.info("Inicio de generación de hechos Prolog para AgroSmart.")

    rangos = cargar_rangos_optimos()
    dataset = cargar_dataset_maestro()

    cultivos = derivar_cultivos_soportados(rangos)
    pares = derivar_cultivo_en_region(dataset, REGIONES_OPERACIONALES)
    rendimiento = derivar_rendimiento_esperado(dataset, cultivos)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contenido = renderizar_pl(
        cultivos=cultivos,
        regiones=REGIONES_OPERACIONALES,
        pares_cultivo_region=pares,
        rangos=rangos,
        rendimiento=rendimiento,
        timestamp_iso=timestamp,
    )

    PL_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    PL_SALIDA.write_text(contenido, encoding="utf-8")
    logger.info("Archivo Prolog escrito en %s", PL_SALIDA)

    validar_con_pyswip(PL_SALIDA)
    imprimir_estadisticas(PL_SALIDA, cultivos, REGIONES_OPERACIONALES, pares, rangos, rendimiento)

    logger.info("Generación completada exitosamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
