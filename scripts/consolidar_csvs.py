"""
Une el CSV principal (``data/processed/dataset_maestro.csv``, con la
primera corrida exitosa de Pampeana) con el CSV extra
(``data/processed/dataset_maestro_extra.csv``, generado por
``scripts/correr_extra_pampeanas.py`` con los deptos faltantes).

Proceso
-------
1. Carga ambos CSV y valida que tengan exactamente el mismo schema
   (mismo conjunto y orden de columnas).
2. Hace backup del CSV principal en ``dataset_maestro_pampeana.csv``
   para preservar la versión pre-merge con trazabilidad.
3. Concatena ambos DataFrames preservando el orden (principal arriba,
   extra abajo).
4. Reescribe ``dataset_maestro.csv`` como dataset unificado.
5. Reporta totales, cobertura por región y deltas vs el CSV pampeano.

Uso
---
    python -m scripts.consolidar_csvs            # falla si ya hay backup
    python -m scripts.consolidar_csvs --force    # sobrescribe backup

Falla si:
- Alguno de los dos CSV no existe.
- Las columnas no coinciden en cantidad u orden.
- El backup ya existe y no se pasa ``--force``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

CSV_PRINCIPAL: Path = Path("data/processed/dataset_maestro.csv")
CSV_EXTRA: Path = Path("data/processed/dataset_maestro_extra.csv")
CSV_BACKUP: Path = Path("data/processed/dataset_maestro_pampeana.csv")

logger = logging.getLogger(__name__)


def validar_schemas(df_a: pd.DataFrame, df_b: pd.DataFrame) -> None:
    """
    Verifica que dos DataFrames tengan exactamente las mismas columnas
    en el mismo orden. Falla con ValueError describiendo la diferencia.
    """
    cols_a = list(df_a.columns)
    cols_b = list(df_b.columns)
    if cols_a == cols_b:
        return
    solo_a = sorted(set(cols_a) - set(cols_b))
    solo_b = sorted(set(cols_b) - set(cols_a))
    raise ValueError(
        f"Schemas distintos:\n"
        f"  - Principal: {len(cols_a)} columnas\n"
        f"  - Extra:     {len(cols_b)} columnas\n"
        f"  - Solo en principal: {solo_a}\n"
        f"  - Solo en extra:     {solo_b}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Une dataset principal + extra en un único CSV.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribir el backup si ya existe.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not CSV_PRINCIPAL.exists():
        print(f"[!] No existe {CSV_PRINCIPAL}.")
        return 1
    if not CSV_EXTRA.exists():
        print(
            f"[!] No existe {CSV_EXTRA}. Generalo con "
            f"`python -m scripts.correr_extra_pampeanas`."
        )
        return 1
    if CSV_BACKUP.exists() and not args.force:
        print(
            f"[!] El backup {CSV_BACKUP} ya existe. "
            f"Borralo o pasá --force para sobrescribir."
        )
        return 1

    df_principal = pd.read_csv(CSV_PRINCIPAL)
    df_extra = pd.read_csv(CSV_EXTRA)
    logger.info("CSV principal: %d filas", len(df_principal))
    logger.info("CSV extra:     %d filas", len(df_extra))

    try:
        validar_schemas(df_principal, df_extra)
    except ValueError as e:
        print(f"[!] {e}")
        return 1
    logger.info("Schemas coinciden: %d columnas.", len(df_principal.columns))

    df_principal.to_csv(CSV_BACKUP, index=False, encoding="utf-8")
    logger.info("Backup del CSV principal en %s.", CSV_BACKUP)

    df_total = pd.concat([df_principal, df_extra], ignore_index=True)
    df_total.to_csv(CSV_PRINCIPAL, index=False, encoding="utf-8")
    logger.info(
        "CSV unificado guardado en %s (%d filas).",
        CSV_PRINCIPAL, len(df_total),
    )

    print("\n=== Resultado de la consolidación de CSVs ===")
    print(f"Filas pampeanas (principal pre-merge): {len(df_principal):>5}")
    print(f"Filas extra-pampeanas:                  {len(df_extra):>5}")
    print(f"Filas totales (unificado):              {len(df_total):>5}")

    print("\nCobertura por región (final):")
    cov_total = df_total["region"].value_counts().sort_index()
    for region, n in cov_total.items():
        print(f"  {region:<11} {n}")

    print("\nDeltas vs CSV pampeano (filas agregadas por región):")
    cov_principal = df_principal["region"].value_counts()
    cov_extra = df_extra["region"].value_counts()
    for region in cov_total.index:
        n_p = int(cov_principal.get(region, 0))
        n_e = int(cov_extra.get(region, 0))
        signo = "+" if n_e >= 0 else ""
        print(
            f"  {region:<11} principal={n_p:>5}  "
            f"extra={n_e:>5}  delta={signo}{n_e}"
        )

    print(f"\nBackup en:    {CSV_BACKUP}")
    print(f"Unificado en: {CSV_PRINCIPAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
