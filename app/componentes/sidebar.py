"""
Sidebar de la app: selector de ejemplo + sliders de las 7 variables del lote.

La interacción usa st.session_state como única fuente de verdad para
los valores: cada widget tiene `key="input_<variable>"` y NO se le
pasa `value=`. Esto permite que (1) los sliders mantengan estado entre
reruns y (2) cargar un ejemplo o un click del mapa pueda escribir
directamente en session_state y los widgets lo reflejen.
"""

from __future__ import annotations

from typing import Final

import streamlit as st

from src.bridge.integrador import Lote


# ---------------------------------------------------------------------
# Defaults y ejemplos preconfigurados
# ---------------------------------------------------------------------
REGIONES: Final[list[str]] = ["pampeana", "noa", "nea"]

# Defaults iniciales (Pergamino-style "personalizable").
DEFAULTS: Final[dict[str, float | int | str]] = {
    "input_region": "pampeana",
    "input_ph": 6.5,
    "input_mo": 3.0,
    "input_arcilla": 25,
    "input_arena": 15,
    "input_precip": 750,
    "input_temp": 20.0,
    "input_helada": 0,
}

# Ejemplos cargables. None = "Personalizado" (no toca los sliders).
EJEMPLOS: Final[dict[str, dict | None]] = {
    "Personalizado": None,
    "Pergamino típico": {
        "input_region": "pampeana",
        "input_ph": 6.5,
        "input_mo": 3.2,
        "input_arcilla": 26,
        "input_arena": 12,
        "input_precip": 750,
        "input_temp": 22.0,
        "input_helada": 0,
    },
    "Sequía 2022/23": {
        "input_region": "pampeana",
        "input_ph": 6.5,
        "input_mo": 3.2,
        "input_arcilla": 26,
        "input_arena": 12,
        "input_precip": 320,
        "input_temp": 22.0,
        "input_helada": 0,
    },
    "NEA arrocero": {
        "input_region": "nea",
        "input_ph": 6.1,
        "input_mo": 2.7,
        "input_arcilla": 30,
        "input_arena": 20,
        "input_precip": 850,
        "input_temp": 24.0,
        "input_helada": 0,
    },
    "Lote ácido": {
        "input_region": "pampeana",
        "input_ph": 4.5,
        "input_mo": 3.2,
        "input_arcilla": 26,
        "input_arena": 12,
        "input_precip": 750,
        "input_temp": 22.0,
        "input_helada": 0,
    },
}


def _inicializar_estado() -> None:
    """Inicializa session_state la primera vez que se renderiza el sidebar."""
    for clave, valor in DEFAULTS.items():
        st.session_state.setdefault(clave, valor)
    st.session_state.setdefault("ejemplo_anterior", "Personalizado")


def _aplicar_ejemplo_si_cambio(ejemplo: str) -> None:
    """Si el ejemplo elegido cambió, escribe sus valores en session_state.

    Se ejecuta antes de renderizar los sliders; los widgets levantan los
    nuevos valores desde session_state automáticamente porque comparten
    `key`.
    """
    if ejemplo == st.session_state["ejemplo_anterior"]:
        return
    st.session_state["ejemplo_anterior"] = ejemplo
    config = EJEMPLOS[ejemplo]
    if config is None:
        return
    for clave, valor in config.items():
        st.session_state[clave] = valor


def aplicar_autocompletado(valores: dict[str, float | int | str]) -> None:
    """Hook público para que el mapa autocomplete los inputs.

    Llamarlo ANTES de renderizar el sidebar (típicamente al detectar
    un click en un marcador). Marca el ejemplo como "Personalizado"
    para que un cambio posterior del selectbox no pise estos valores.
    """
    for clave, valor in valores.items():
        st.session_state[clave] = valor
    st.session_state["ejemplo_select"] = "Personalizado"
    st.session_state["ejemplo_anterior"] = "Personalizado"


def construir_lote_desde_estado(nombre: str = "lote_app") -> Lote:
    """Construye un Lote a partir de los valores actuales del sidebar."""
    return Lote(
        region=st.session_state["input_region"],
        ph=float(st.session_state["input_ph"]),
        materia_organica_pct=float(st.session_state["input_mo"]),
        arcilla_pct=float(st.session_state["input_arcilla"]),
        arena_pct=float(st.session_state["input_arena"]),
        precipitacion_total_mm=float(st.session_state["input_precip"]),
        temp_media_c=float(st.session_state["input_temp"]),
        dias_helada=int(st.session_state["input_helada"]),
        nombre=nombre,
    )


# ---------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------
def render_sidebar() -> bool:
    """Renderiza el sidebar completo. Devuelve True si se clickeó "Evaluar lote"."""
    _inicializar_estado()

    with st.sidebar:
        st.header("Lote bajo análisis")

        # --- Ejemplos preconfigurados -----------------------------------
        ejemplo = st.selectbox(
            "Cargar ejemplo:",
            list(EJEMPLOS.keys()),
            key="ejemplo_select",
            help="Carga rápida de los lotes de la defensa oral. "
                 "Cualquier slider modificado vuelve el ejemplo a 'Personalizado'.",
        )
        _aplicar_ejemplo_si_cambio(ejemplo)

        st.divider()

        # --- Región ------------------------------------------------------
        st.selectbox(
            "Región",
            REGIONES,
            key="input_region",
            help="El sistema experto Prolog filtra por viabilidad geográfica. "
                 "Arroz solo aparece en NEA; algodón en NOA/NEA.",
        )

        st.divider()

        # --- Suelo -------------------------------------------------------
        st.subheader("Suelo")
        st.slider("pH", 4.0, 9.0, step=0.1, key="input_ph")
        st.slider("Materia orgánica %", 0.5, 8.0, step=0.1, key="input_mo")
        st.slider("Arcilla %", 5, 60, step=1, key="input_arcilla")
        st.slider("Arena %", 5, 80, step=1, key="input_arena")

        st.divider()

        # --- Clima -------------------------------------------------------
        st.subheader("Clima")
        st.slider("Precipitación (mm)", 100, 1800, step=10, key="input_precip")
        st.slider("Temperatura media (°C)", 5.0, 30.0, step=0.5, key="input_temp")
        st.slider("Días de helada", 0, 30, step=1, key="input_helada")

        st.divider()

        # --- Acción ------------------------------------------------------
        evaluar = st.button("Evaluar lote", type="primary", width="stretch")

    return evaluar
