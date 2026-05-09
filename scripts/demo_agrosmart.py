"""
Demo end-to-end de AgroSmart para la defensa oral.

Construye 3 lotes de ejemplo cubriendo escenarios contrastantes y
ejecuta la cascada Python ↔ Prolog completa para cada uno. La salida
en consola está pensada para ser legible por un humano durante la
presentación; los tres reportes también se exportan a JSON en
data/modelos/demo_*.json para entregar al evaluador como evidencia.

Para correr:
    python scripts/demo_agrosmart.py

Requiere modelos entrenados (correr antes
`python -m src.modelos.regresor_rendimiento --entrenar`).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Permitir ejecutar el script con `python scripts/demo_agrosmart.py` sin
# instalar el paquete: agregamos la raíz del repo al path antes de los
# imports propios.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# La consola de Windows por default usa cp1252 y rompe con caracteres
# como '→', '—' o '°C'. Forzamos UTF-8 en stdout para que el demo se
# vea bien tanto en cmd.exe como en terminales modernas.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.bridge.integrador import (  # noqa: E402  (path injection arriba)
    Lote,
    ReporteLote,
    SistemaAgroSmart,
)
from src.modelos.regresor_rendimiento import MODELOS_DIR  # noqa: E402

DEMO_DIR = MODELOS_DIR


# ---------------------------------------------------------------------
# Definición de los 3 lotes
# ---------------------------------------------------------------------
def lote_pergamino_tipico() -> Lote:
    """LOTE 1: condiciones óptimas pampeanas (Pergamino-style)."""
    return Lote(
        region="pampeana",
        ph=6.5,
        materia_organica_pct=3.2,
        arcilla_pct=26.0,
        arena_pct=12.0,
        precipitacion_total_mm=750.0,
        temp_media_c=22.0,
        dias_helada=0,
        nombre="Pergamino tipico",
    )


def lote_sequia_2022_23() -> Lote:
    """LOTE 2: misma base pampeana pero sequía severa La Niña 2022/23."""
    return Lote(
        region="pampeana",
        ph=6.5,
        materia_organica_pct=3.2,
        arcilla_pct=26.0,
        arena_pct=12.0,
        precipitacion_total_mm=320.0,
        temp_media_c=22.0,
        dias_helada=0,
        nombre="Sequia 2022/23 (pampeana)",
    )


def lote_nea_arrocero() -> Lote:
    """LOTE 3: NEA arrocero, alta humedad y lluvia abundante.

    Valores elegidos para caer dentro de los rangos óptimos derivados
    del dataset para arroz NEA, demostrando un caso positivo de
    recomendación regional alternativa.
    """
    return Lote(
        region="nea",
        ph=6.1,
        materia_organica_pct=2.7,
        arcilla_pct=30.0,
        arena_pct=20.0,
        precipitacion_total_mm=850.0,
        temp_media_c=24.0,
        humedad_relativa_promedio=75.0,
        dias_helada=0,
        nombre="NEA arrocero",
    )


# ---------------------------------------------------------------------
# Renderizado para consola
# ---------------------------------------------------------------------
def _separador(titulo: str = "") -> str:
    if titulo:
        return f"\n{'=' * 72}\n  {titulo}\n{'=' * 72}"
    return "=" * 72


def _formatear_recomendaciones(reporte: ReporteLote) -> str:
    if not reporte.recomendaciones:
        return "  (ninguno)"
    lineas: list[str] = []
    for r in reporte.recomendaciones:
        if r.rendimiento_predicho_kg_ha is not None:
            low, high = r.intervalo_prediccion or (0, 0)
            p10, p50, p90 = r.rendimiento_esperado_zona
            cabecera = (
                f"  - {r.cultivo:<8} | predicho: {r.rendimiento_predicho_kg_ha:>5} kg/ha "
                f"(IC95% {low:>5}-{high:<5}) | zona p10/p50/p90: "
                f"{p10:>5}/{p50:>5}/{p90:<5} | {r.clasificacion_rendimiento}"
            )
        else:
            cabecera = f"  - {r.cultivo:<8} | (modelo no disponible)"
        lineas.append(cabecera)
        if r.riesgos_observados:
            lineas.append(f"      observaciones: {', '.join(r.riesgos_observados)}")
    return "\n".join(lineas)


def _formatear_no_recomendados(reporte: ReporteLote) -> str:
    if not reporte.no_recomendados:
        return "  (ninguno)"
    return "\n".join(
        f"  - {nr.cultivo:<8} | motivo: {nr.motivo}" for nr in reporte.no_recomendados
    )


def _formatear_aptos_parciales(reporte: ReporteLote) -> str:
    if not reporte.aptos_parciales:
        return "  (ninguno)"
    return "\n".join(
        f"  - {ap.cultivo:<8} | {ap.motivo}" for ap in reporte.aptos_parciales
    )


def imprimir_reporte(reporte: ReporteLote) -> None:
    print(_separador(reporte.lote["nombre"].upper()))
    print(
        f"\nRegión: {reporte.lote['region']}  |  "
        f"pH: {reporte.lote['ph']}  |  MO: {reporte.lote['materia_organica_pct']}%  |  "
        f"arcilla: {reporte.lote['arcilla_pct']}%"
    )
    print(
        f"Precipitación: {reporte.lote['precipitacion_total_mm']} mm  |  "
        f"temp media: {reporte.lote['temp_media_c']} °C  |  "
        f"días helada: {reporte.lote['dias_helada']}"
    )
    print(f"Timestamp: {reporte.timestamp}")

    print("\nRECOMENDADOS:")
    print(_formatear_recomendaciones(reporte))

    print("\nNO RECOMENDADOS:")
    print(_formatear_no_recomendados(reporte))

    print("\nAPTOS PARCIALES (mitigables):")
    print(_formatear_aptos_parciales(reporte))


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(
        level=logging.WARNING,  # silencioso para que la demo se lea limpia
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    print(_separador("AgroSmart — Demo de la cascada de decisión"))
    print(
        "\nSe evalúan 3 lotes contrastantes a través del sistema híbrido "
        "(Prolog + Random Forest)."
    )

    sistema = SistemaAgroSmart()
    lotes = [
        ("demo_pampeano.json", lote_pergamino_tipico()),
        ("demo_sequia.json", lote_sequia_2022_23()),
        ("demo_nea.json", lote_nea_arrocero()),
    ]

    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    for nombre_archivo, lote in lotes:
        reporte = sistema.evaluar_lote(lote)
        imprimir_reporte(reporte)
        ruta = DEMO_DIR / nombre_archivo
        ruta.write_text(sistema.exportar_json(reporte), encoding="utf-8")
        print(f"\n  → JSON exportado a {ruta}")

    print(_separador("Demo finalizada"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
