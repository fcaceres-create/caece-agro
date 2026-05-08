"""
Corre la consolidación SOLO para los departamentos que aún no tienen
filas en ``data/processed/dataset_maestro.csv`` y guarda el resultado
en ``data/processed/dataset_maestro_extra.csv``.

NO toca el CSV principal: la unión la hace el script siguiente
(``scripts/consolidar_csvs.py``).

Pensado como segundo paso de una recuperación tras un incidente de
rate-limiting que dejó el CSV principal con cobertura parcial. El
listado de departamentos faltantes se calcula dinámicamente leyendo el
CSV existente y comparándolo con ``DEPARTAMENTOS``: si el script se
re-ejecuta tras una corrida parcial, levanta sólo los aún faltantes.

Uso
---
    python -m scripts.correr_extra_pampeanas
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

from src.procesamiento.consolidacion import construir_dataset_maestro
from src.procesamiento.departamentos import DEPARTAMENTOS

CSV_PRINCIPAL: Path = Path("data/processed/dataset_maestro.csv")
CSV_EXTRA: Path = Path("data/processed/dataset_maestro_extra.csv")

logger = logging.getLogger(__name__)


def deptos_faltantes(csv_path: Path) -> list[str]:
    """
    Devuelve los nombres de los departamentos del catálogo
    ``DEPARTAMENTOS`` que no aparecen en el CSV indicado.

    Raises
    ------
    FileNotFoundError
        Si el CSV no existe.
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No existe {csv_path}. Corré primero "
            f"`python -m src.procesamiento.consolidacion --full`."
        )
    df = pd.read_csv(csv_path)
    presentes = set(df["departamento"].unique())
    return [d.nombre for d in DEPARTAMENTOS if d.nombre not in presentes]


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        faltantes = deptos_faltantes(CSV_PRINCIPAL)
    except FileNotFoundError as e:
        print(f"[!] {e}")
        return 1

    if not faltantes:
        print(
            "Todos los departamentos del catálogo ya están en "
            f"{CSV_PRINCIPAL}. Nada que hacer."
        )
        return 0

    print(
        f"\n>>> Corriendo consolidación SOLO para los "
        f"{len(faltantes)} departamentos faltantes:"
    )
    for nombre in faltantes:
        d = next(d for d in DEPARTAMENTOS if d.nombre == nombre)
        print(f"  - {nombre:<25} ({d.provincia}, {d.region})")
    print()

    df_extra = construir_dataset_maestro(
        departamentos=faltantes,
        campania_desde="2000/2001",
        guardar_csv=False,  # No tocar el CSV principal en este paso.
    )

    if df_extra.empty:
        print("\n[!] La corrida no generó filas para los deptos faltantes. "
              "Revisar logs por errores de API.")
        return 1

    CSV_EXTRA.parent.mkdir(parents=True, exist_ok=True)
    df_extra.to_csv(CSV_EXTRA, index=False, encoding="utf-8")
    logger.info(
        "[Extra] CSV guardado en %s (%d filas).", CSV_EXTRA, len(df_extra),
    )

    print(f"\n=== {len(df_extra)} filas generadas en {CSV_EXTRA} ===")
    print("\nCobertura por región (extra):")
    for region, n in df_extra["region"].value_counts().items():
        print(f"  {region:<11} {n}")

    print(
        "\nPróximo paso: "
        "`python -m scripts.consolidar_csvs` para unir con el CSV principal."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
