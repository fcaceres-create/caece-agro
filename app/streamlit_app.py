"""
AgroSmart — App web (Streamlit) para defensa oral del TFI.

Sistema híbrido (Prolog + Random Forest) para recomendación de
cultivos extensivos en Argentina. Esta app envuelve la cascada
implementada en src/bridge/integrador.py y la expone con una UI
limpia: sidebar de inputs, mapa interactivo de Argentina, reporte
en 3 secciones (recomendados / no recomendados / aptos parciales)
y detalle expandible por cultivo.

Para correr:
    streamlit run app/streamlit_app.py

URL local por defecto: http://localhost:8501

Pipeline para regenerar todo desde cero antes de levantar la app:
    1. notebooks/02_eda_consolidado.ipynb
    2. python -m src.procesamiento.generar_hechos_prolog
    3. python -m src.modelos.regresor_rendimiento --entrenar
    4. streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Permitir `streamlit run app/streamlit_app.py` sin instalar el paquete:
# agregamos la raíz del repo al sys.path antes de los imports propios.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from app.componentes.detalle_cultivo import render_detalle_cultivo  # noqa: E402
from app.componentes.mapa import render_mapa  # noqa: E402
from app.componentes.reporte import render_reporte  # noqa: E402
from app.componentes.sidebar import construir_lote_desde_estado, render_sidebar  # noqa: E402
from src.bridge.integrador import SistemaAgroSmart  # noqa: E402

# Logging a nivel INFO para que el log de arranque (cwd, raíz, plataforma)
# quede visible en los logs de Streamlit Cloud y ayude a diagnosticar
# problemas de path en el primer deploy.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
)
_logger = logging.getLogger("agrosmart.app")
_logger.info(
    "Arranque de AgroSmart | cwd=%s | raiz_repo=%s | platform=%s",
    Path.cwd(), RAIZ, sys.platform,
)

# ---------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="AgroSmart — Defensa TFI",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def _inicializar_sistema() -> SistemaAgroSmart:
    """Carga pyswip + los 11 modelos joblib una sola vez por sesión."""
    return SistemaAgroSmart()


# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------
def render_header() -> None:
    st.title("🌾 AgroSmart — Recomendación de cultivos para Argentina")
    st.markdown(
        "Sistema híbrido **(Prolog + Random Forest)** para recomendación "
        "de cultivos extensivos en Argentina."
    )
    st.caption(
        "11 cultivos · 30 departamentos · 25 campañas (2000/01–2024/25) · "
        "3.786 registros · 265 hechos Prolog generados desde el dataset"
    )


def render_footer() -> None:
    st.divider()
    st.caption(
        "**TFI Fundamentos de IA — CAECE 2026**  ·  "
        "Fernando Cáceres y Ezequiel  ·  Mayo 2026"
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main() -> None:
    render_header()

    # Inicializar sistema con spinner (primera carga: pyswip + 11 joblibs).
    with st.spinner("Inicializando sistema experto..."):
        sistema = _inicializar_sistema()

    # Layout principal: mapa a la izquierda, info estática a la derecha.
    # El sidebar (donde están los sliders y "Evaluar lote") se renderiza
    # dentro de render_sidebar.
    col_mapa, col_info = st.columns([2, 1])
    with col_mapa:
        render_mapa()
    with col_info:
        st.markdown("**Cómo usar la app**")
        st.markdown(
            "1. Cargá un ejemplo o ajustá manualmente los sliders del **sidebar**.\n"
            "2. Opcional: clickeá un departamento del mapa para autocompletar.\n"
            "3. Apretá **Evaluar lote** para correr la cascada Prolog + RF.\n"
            "4. El reporte aparece debajo, con detalle por cultivo expandible."
        )
        st.info(
            "💡 Los 4 ejemplos del sidebar reproducen los lotes "
            "validados en la sección 13 de la bitácora del proyecto."
        )

    evaluar = render_sidebar()

    # Disparar evaluación: explícita (botón) o si ya hay un reporte previo
    # en sesión (mantener el último resultado al navegar entre tabs).
    if evaluar:
        lote = construir_lote_desde_estado(
            nombre=st.session_state.get("ejemplo_select", "lote_app")
        )
        with st.spinner("Evaluando lote (Prolog + Random Forest)..."):
            reporte = sistema.evaluar_lote(lote)
        st.session_state["ultimo_reporte"] = reporte
        st.session_state["ultimo_lote"] = lote

    reporte = st.session_state.get("ultimo_reporte")
    lote = st.session_state.get("ultimo_lote")

    if reporte is None:
        st.divider()
        st.info(
            "Configurá un lote en el sidebar y apretá **Evaluar lote** "
            "para ver la cascada de decisión completa."
        )
    else:
        st.divider()
        st.subheader("📋 Reporte de evaluación")
        render_reporte(reporte)
        render_detalle_cultivo(sistema, lote, reporte)

    render_footer()


if __name__ == "__main__":
    main()
