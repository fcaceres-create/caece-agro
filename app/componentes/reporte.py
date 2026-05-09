"""
Renderizado del ReporteLote en 3 secciones (Recomendados / No / Parciales).

El estilo se apoya 100% en utilidades nativas de Streamlit (st.success,
st.warning, st.metric, st.columns) sin custom CSS. Los emojis dan
señalética visual sin sacrificar accesibilidad.
"""

from __future__ import annotations

from typing import Final

import streamlit as st

from src.bridge.integrador import (
    CultivoAptoParcial,
    CultivoNoRecomendado,
    Recomendacion,
    ReporteLote,
)


# Emojis por cultivo. No-canónicos pero consistentes en toda la UI.
EMOJI_CULTIVO: Final[dict[str, str]] = {
    "soja": "🌱",
    "maiz": "🌽",
    "trigo": "🌾",
    "girasol": "🌻",
    "sorgo": "🟤",
    "cebada": "🍺",
    "avena": "🥣",
    "centeno": "🍞",
    "arroz": "🍚",
    "algodon": "🤍",
    "mani": "🥜",
}

NOMBRE_LEGIBLE: Final[dict[str, str]] = {
    "soja": "Soja",
    "maiz": "Maíz",
    "trigo": "Trigo",
    "girasol": "Girasol",
    "sorgo": "Sorgo",
    "cebada": "Cebada",
    "avena": "Avena",
    "centeno": "Centeno",
    "arroz": "Arroz",
    "algodon": "Algodón",
    "mani": "Maní",
}

# Banner por clasificación: el helper Streamlit que usar y un texto.
BANNER_POR_CLASIFICACION: Final[dict[str, tuple[str, str]]] = {
    "alto": ("success", "RENDIMIENTO ALTO (≥ p90 de la zona)"),
    "medio": ("info", "RENDIMIENTO MEDIO (p50–p90)"),
    "bajo": ("warning", "RENDIMIENTO BAJO (p10–p50)"),
    "muy_bajo": ("error", "RENDIMIENTO MUY BAJO (< p10)"),
    "sin_modelo": ("info", "PREDICCIÓN NO DISPONIBLE"),
    "sin_referencia": ("info", "SIN REFERENCIA HISTÓRICA"),
}

# Texto humano para cada motivo. Los keys vienen del bridge.
MOTIVO_NO_RECOMENDADO: Final[dict[str, str]] = {
    "riesgo_sequia": "Sequía: lluvia bajo el P10 del cultivo (estrés hídrico crítico).",
    "riesgo_helada": "Helada: cultivo sensible a más de 5 días de helada en el ciclo.",
    "riesgo_nutricional": "Nutricional: suelo arenoso con baja MO (déficit estructural).",
    "suelo_fuera_de_rango": "Suelo: pH, MO o textura fuera del rango óptimo del cultivo.",
    "clima_fuera_de_rango": "Clima: precipitación o temperatura fuera del rango óptimo del cultivo.",
}

MOTIVO_APTO_PARCIAL: Final[dict[str, str]] = {
    "apto_parcial_suelo": "Suelo OK; clima fuera de rango. Mitigable con riego o variedad adaptada.",
    "apto_parcial_clima": "Clima OK; suelo fuera de rango. Mitigable con enmiendas (encalado, fertilización).",
}


def _nombre(cultivo: str) -> str:
    return f"{EMOJI_CULTIVO.get(cultivo, '🌿')} {NOMBRE_LEGIBLE.get(cultivo, cultivo)}"


def _renderizar_recomendacion(rec: Recomendacion) -> None:
    """Tarjeta para un cultivo recomendado."""
    with st.container(border=True):
        # Encabezado: nombre + banner clasificación
        st.markdown(f"### {_nombre(rec.cultivo)}")

        helper, leyenda = BANNER_POR_CLASIFICACION.get(
            rec.clasificacion_rendimiento, ("info", rec.clasificacion_rendimiento.upper())
        )
        getattr(st, helper)(leyenda)

        # Métricas: predicción + intervalo + percentil de la zona
        col1, col2, col3 = st.columns(3)
        if rec.rendimiento_predicho_kg_ha is not None:
            col1.metric(
                "Predicción",
                f"{rec.rendimiento_predicho_kg_ha:,} kg/ha".replace(",", "."),
            )
            if rec.intervalo_prediccion is not None:
                low, high = rec.intervalo_prediccion
                col2.metric(
                    "IC 95%",
                    f"{low:,}–{high:,}".replace(",", "."),
                    help="Intervalo de confianza derivado de la varianza "
                         "entre los árboles individuales del Random Forest.",
                )
        else:
            col1.metric("Predicción", "n/d")
            col2.metric("IC 95%", "n/d")

        p10, p50, p90 = rec.rendimiento_esperado_zona
        col3.metric(
            "Mediana zona",
            f"{p50:,} kg/ha".replace(",", "."),
            help=f"Histórico del cultivo: p10 {p10:,} / p50 {p50:,} / p90 {p90:,}".replace(
                ",", "."
            ),
        )

        # Riesgos no críticos
        if rec.riesgos_observados:
            etiquetas = ", ".join(rec.riesgos_observados)
            st.warning(f"⚠ Observaciones: {etiquetas}")


def _renderizar_no_recomendado(item: CultivoNoRecomendado) -> None:
    motivo_humano = MOTIVO_NO_RECOMENDADO.get(item.motivo, item.motivo)
    st.markdown(f"- **{_nombre(item.cultivo)}** — {motivo_humano}")


def _renderizar_apto_parcial(item: CultivoAptoParcial) -> None:
    motivo_humano = MOTIVO_APTO_PARCIAL.get(item.motivo, item.motivo)
    st.markdown(f"- **{_nombre(item.cultivo)}** — {motivo_humano}")


# ---------------------------------------------------------------------
# Resumen del lote (st.metric en 4 columnas)
# ---------------------------------------------------------------------
def render_resumen_lote(reporte: ReporteLote) -> None:
    """Encabezado con las 7 variables del lote en 4 columnas."""
    lote = reporte.lote
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Región", lote["region"].upper())
    col1.caption(f"Evaluado: {reporte.timestamp}")

    col2.metric("pH", f"{lote['ph']:.2f}")
    col2.metric("MO", f"{lote['materia_organica_pct']:.2f} %")
    col2.metric("Arcilla", f"{lote['arcilla_pct']:.0f} %")

    col3.metric("Precipitación", f"{lote['precipitacion_total_mm']:.0f} mm")
    col3.metric("Temp. media", f"{lote['temp_media_c']:.1f} °C")

    col4.metric("Días helada", f"{lote['dias_helada']:.0f}")
    col4.metric("Arena", f"{lote['arena_pct']:.0f} %")


# ---------------------------------------------------------------------
# Renderizado completo
# ---------------------------------------------------------------------
def render_reporte(reporte: ReporteLote) -> None:
    """Renderiza el ReporteLote completo en 3 secciones de tabs."""
    render_resumen_lote(reporte)
    st.divider()

    n_rec = len(reporte.recomendaciones)
    n_no = len(reporte.no_recomendados)
    n_par = len(reporte.aptos_parciales)

    tab_rec, tab_no, tab_par = st.tabs(
        [
            f"✅ Recomendados ({n_rec})",
            f"❌ No recomendados ({n_no})",
            f"⚠️ Aptos parciales ({n_par})",
        ]
    )

    with tab_rec:
        if not reporte.recomendaciones:
            st.info(
                "Ningún cultivo es recomendado para este lote. "
                "Revisá los riesgos críticos en la pestaña 'No recomendados'."
            )
        else:
            # Distribuyo en columnas de a 2 para aprovechar el ancho.
            for inicio in range(0, n_rec, 2):
                cols = st.columns(2)
                for i, rec in enumerate(reporte.recomendaciones[inicio : inicio + 2]):
                    with cols[i]:
                        _renderizar_recomendacion(rec)

    with tab_no:
        if not reporte.no_recomendados:
            st.info("Ningún cultivo descartado.")
        else:
            for item in reporte.no_recomendados:
                _renderizar_no_recomendado(item)

    with tab_par:
        if not reporte.aptos_parciales:
            st.info("Ningún cultivo en estado parcial.")
        else:
            st.caption(
                "Cultivos que cumplen la aptitud por un lado (suelo o clima) "
                "pero no por el otro. Pueden funcionar con manejo específico."
            )
            for item in reporte.aptos_parciales:
                _renderizar_apto_parcial(item)
