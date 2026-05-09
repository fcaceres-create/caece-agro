"""
Detalle expandible por cultivo: tabla "valor del lote vs rango óptimo"
+ boxplot plotly del rendimiento histórico de la región vs predicción.

Muestra al evaluador, para cualquier cultivo evaluado, qué variables
caen dentro del rango P10–P90 del cultivo (✓) y cuáles no (✗ alto/bajo),
y para los recomendados visualiza la predicción del modelo dentro de
la distribución empírica del cultivo en la región.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.componentes.reporte import NOMBRE_LEGIBLE, _nombre
from src.bridge.integrador import Lote, ReporteLote, SistemaAgroSmart


DATASET_PATH: Final[Path] = Path("data/processed/dataset_maestro.csv")

# Variables que el cultivo evalúa contra rango_optimo/4 en Prolog.
# Mapean nombre interno (Prolog) → etiqueta humana para la tabla.
VARIABLES_TABLA: Final[list[tuple[str, str, str]]] = [
    # (clave en Prolog, etiqueta, unidad)
    ("ph", "pH", ""),
    ("materia_organica_pct", "Materia orgánica", "%"),
    ("arcilla_pct", "Arcilla", "%"),
    ("precipitacion_total_mm", "Precipitación", "mm"),
    ("temp_media_c", "Temperatura media", "°C"),
]


@st.cache_data(show_spinner=False)
def _cargar_dataset() -> pd.DataFrame:
    return pd.read_csv(DATASET_PATH)


def _consultar_rango(sistema: SistemaAgroSmart, cultivo: str, variable: str) -> tuple[float, float] | None:
    """rango_optimo/4 vía el backend Prolog del sistema."""
    q = list(
        sistema.backend.prolog.query(f"rango_optimo({cultivo}, {variable}, P10, P90)")
    )
    if not q:
        return None
    return float(q[0]["P10"]), float(q[0]["P90"])


def _estado_variable(valor: float, rango: tuple[float, float] | None) -> str:
    if rango is None:
        return "—"
    p10, p90 = rango
    if valor < p10:
        return f"✗ bajo P10 ({p10:.2f})"
    if valor > p90:
        return f"✗ sobre P90 ({p90:.2f})"
    return "✓ en rango"


def _construir_tabla_variables(
    sistema: SistemaAgroSmart, cultivo: str, lote: Lote
) -> pd.DataFrame:
    valores_lote = lote.features_para_modelo()
    filas = []
    for variable, etiqueta, unidad in VARIABLES_TABLA:
        rango = _consultar_rango(sistema, cultivo, variable)
        valor = valores_lote.get(variable)
        if valor is None:
            valor = getattr(lote, variable, None)
        valor_str = f"{valor:.2f} {unidad}".strip() if valor is not None else "—"
        if rango is None:
            p10_str = p90_str = "—"
        else:
            p10_str, p90_str = f"{rango[0]:.2f}", f"{rango[1]:.2f}"
        filas.append(
            {
                "Variable": etiqueta,
                "Valor del lote": valor_str,
                "P10": p10_str,
                "P90": p90_str,
                "Estado": _estado_variable(float(valor) if valor is not None else 0.0, rango),
            }
        )
    return pd.DataFrame(filas)


def _construir_boxplot_rendimiento(
    cultivo: str, region: str, prediccion: int | None, intervalo: tuple[int, int] | None
) -> go.Figure | None:
    """Boxplot horizontal del rendimiento histórico + marca de predicción."""
    df = _cargar_dataset()
    sub = df[
        (df["cultivo"] == cultivo)
        & (df["region"] == region)
        & (df["rendimiento_kg_ha"] > 0)
    ]
    if sub.empty:
        return None

    fig = go.Figure()
    fig.add_trace(
        go.Box(
            x=sub["rendimiento_kg_ha"],
            name=f"{NOMBRE_LEGIBLE.get(cultivo, cultivo)} en {region}",
            boxmean=True,
            marker_color="#4C78A8",
            orientation="h",
        )
    )

    if prediccion is not None:
        fig.add_vline(
            x=prediccion,
            line_color="#E45756",
            line_width=2,
            annotation_text=f"Predicción: {prediccion:,} kg/ha".replace(",", "."),
            annotation_position="top",
        )
        if intervalo is not None:
            low, high = intervalo
            fig.add_vrect(
                x0=low,
                x1=high,
                fillcolor="#E45756",
                opacity=0.12,
                line_width=0,
                annotation_text="IC 95%",
                annotation_position="bottom right",
            )

    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Rendimiento (kg/ha)",
        yaxis_title=None,
        showlegend=False,
    )
    return fig


def _cultivos_evaluados(reporte: ReporteLote) -> list[str]:
    """Recomendados + no recomendados + aptos parciales (sin duplicados, orden estable)."""
    vistos: list[str] = []
    for r in reporte.recomendaciones:
        if r.cultivo not in vistos:
            vistos.append(r.cultivo)
    for nr in reporte.no_recomendados:
        if nr.cultivo not in vistos:
            vistos.append(nr.cultivo)
    for ap in reporte.aptos_parciales:
        if ap.cultivo not in vistos:
            vistos.append(ap.cultivo)
    return vistos


def render_detalle_cultivo(
    sistema: SistemaAgroSmart, lote: Lote, reporte: ReporteLote
) -> None:
    """Sección expandible con detalle de variables + gráfico por cultivo."""
    cultivos = _cultivos_evaluados(reporte)
    if not cultivos:
        return

    with st.expander("🔬 Detalle por cultivo (variables y predicción)"):
        seleccion = st.selectbox(
            "Seleccioná un cultivo para ver el detalle",
            cultivos,
            format_func=lambda c: _nombre(c),
            key="select_detalle_cultivo",
        )

        st.markdown("**Valor del lote vs rango óptimo del cultivo**")
        tabla = _construir_tabla_variables(sistema, seleccion, lote)
        st.dataframe(tabla, hide_index=True, use_container_width=True)

        # Si el cultivo está entre recomendados, hay predicción cuantitativa.
        rec = next((r for r in reporte.recomendaciones if r.cultivo == seleccion), None)
        prediccion = rec.rendimiento_predicho_kg_ha if rec else None
        intervalo = rec.intervalo_prediccion if rec else None

        st.markdown("**Distribución histórica del rendimiento en la región**")
        fig = _construir_boxplot_rendimiento(
            seleccion, lote.region, prediccion, intervalo
        )
        if fig is None:
            st.info(
                f"No hay datos históricos de {NOMBRE_LEGIBLE.get(seleccion, seleccion)} "
                f"en la región **{lote.region}**. Es coherente con la cobertura del "
                f"dataset (ej: arroz solo se cultiva en NEA)."
            )
        else:
            st.plotly_chart(fig, use_container_width=True)
