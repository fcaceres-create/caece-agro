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

from app.componentes.consola_prolog import render_consola_prolog  # noqa: E402
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
    page_title="AgroSmart - TFI CAECE",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def _inicializar_sistema() -> SistemaAgroSmart:
    """Carga pyswip + los 11 modelos joblib una sola vez por sesión."""
    return SistemaAgroSmart()


def _cargar_logo_caece() -> Path | None:
    """Devuelve la ruta del logo institucional si existe; None si no.

    El header maneja graciosamente la ausencia del archivo: en lugar de
    romper, simplemente omite la imagen y muestra solo el texto. Útil
    para ambientes donde el .png aún no fue incorporado o se movió.
    """
    ruta = RAIZ / "app" / "assets" / "caece_logo.png"
    return ruta if ruta.exists() else None


# ---------------------------------------------------------------------
# Header institucional
# ---------------------------------------------------------------------
def render_header() -> None:
    """Header con identidad CAECE: logo a la izquierda + bloque institucional."""
    col_logo, col_texto, _col_pad = st.columns([1, 4, 1])

    logo = _cargar_logo_caece()
    with col_logo:
        if logo is not None:
            st.image(str(logo), width=120)
        # Si no hay logo, dejamos la columna vacía: el layout sigue
        # balanceado pero sin marco institucional visual.

    with col_texto:
        st.title("🌾 AgroSmart")
        st.markdown(
            "**Sistema híbrido de decisión agronómica para Argentina** — "
            "razonamiento simbólico (Prolog) + predicción cuantitativa "
            "(Random Forest)."
        )
        st.caption(
            "Universidad CAECE — Maestría en Gestión y Desarrollo de IA  ·  "
            "Trabajo Final Integrador — Fundamentos de IA  ·  Mayo 2026"
        )


# ---------------------------------------------------------------------
# Footer institucional
# ---------------------------------------------------------------------
def render_footer() -> None:
    """Footer con 3 bloques (institucional / académico / autores) + disclaimer."""
    st.divider()

    col_inst, col_acad, col_autores = st.columns(3)

    with col_inst:
        st.markdown(
            "**Universidad CAECE**  \n"
            "Maestría en Gestión y Desarrollo de IA  \n"
            "Modalidad E-distancia"
        )

    with col_acad:
        st.markdown(
            "**Fundamentos de IA**  \n"
            "Prof. Juan Miguel Azcurra  \n"
            "1° Cuatrimestre 2026"
        )

    with col_autores:
        st.markdown(
            "**Autores**  \n"
            "Fernando Cáceres  \n"
            "Ezequiel Díaz Fernández  \n"
            "Mayo 2026"
        )

    st.caption(
        "Sistema desarrollado en el marco del Trabajo Final Integrador. "
        "No usar para decisiones agronómicas en producción real sin "
        "validación profesional."
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

    # Layout principal en dos tabs: el reporte de evaluación (sólo
    # poblado tras apretar "Evaluar lote") y la consola Prolog
    # (siempre disponible: muestra el sistema simbólico independiente
    # de la cascada).
    st.divider()
    tab_reporte, tab_consola = st.tabs(
        ["📋 Reporte de evaluación", "🔍 Consola Prolog"]
    )

    with tab_reporte:
        if reporte is None:
            st.info(
                "Configurá un lote en el sidebar y apretá **Evaluar lote** "
                "para ver la cascada de decisión completa."
            )
        else:
            st.subheader("📋 Reporte de evaluación")
            render_reporte(reporte)
            render_detalle_cultivo(sistema, lote, reporte)

    with tab_consola:
        render_consola_prolog(sistema)

    render_footer()


if __name__ == "__main__":
    main()
