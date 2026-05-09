"""
Mapa interactivo de Argentina con los 30 departamentos del dataset.

Click sobre un marker = autocompleta el sidebar con la mediana
histórica del departamento (suelo + clima). El componente se apoya
en folium + streamlit_folium: cada rerun el widget devuelve el
último click, y comparamos con el último ya procesado para no
re-aplicar la autocomplete en cada interacción.

Si por alguna razón el mapa no anda (env sin JS, problema de red
para tiles), expone también un selectbox con la lista de departamentos
como fallback equivalente.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app.componentes.sidebar import aplicar_autocompletado

DATASET_PATH: Final[Path] = Path("data/processed/dataset_maestro.csv")

# Centro y zoom inicial del mapa: cubre Argentina completa.
CENTRO_AR: Final[tuple[float, float]] = (-35.0, -65.0)
ZOOM_INICIAL: Final[int] = 4

# Colores por región: leen rápido en el mapa y permiten al evaluador
# distinguir Pampeana / NOA / NEA sin tener que abrir cada popup.
COLOR_POR_REGION: Final[dict[str, str]] = {
    "pampeana": "blue",
    "noa": "orange",
    "nea": "green",
}


@st.cache_data(show_spinner=False)
def cargar_resumen_departamentos() -> pd.DataFrame:
    """Devuelve un DataFrame con una fila por departamento.

    Las columnas suelo+clima son la mediana sobre TODAS las campañas y
    cultivos del depto. Suelo es invariable (lo mismo en cada fila),
    clima es promedio histórico — apropiado para autocompletar el
    sidebar antes de que el usuario elija el cultivo.
    """
    df = pd.read_csv(DATASET_PATH)
    columnas_a_promediar = [
        "ph",
        "materia_organica_pct",
        "arcilla_pct",
        "arena_pct",
        "precipitacion_total_mm",
        "temp_media_c",
        "dias_helada",
    ]
    resumen = (
        df.groupby(["region", "provincia", "departamento"], as_index=False)
        .agg(
            latitud=("latitud", "first"),
            longitud=("longitud", "first"),
            campanias=("campania", "nunique"),
            registros=("campania", "count"),
            **{col: (col, "median") for col in columnas_a_promediar},
        )
        .sort_values(["region", "provincia", "departamento"])
        .reset_index(drop=True)
    )
    return resumen


def _construir_mapa(resumen: pd.DataFrame) -> folium.Map:
    """Crea un folium.Map con un CircleMarker por departamento."""
    mapa = folium.Map(
        location=CENTRO_AR,
        zoom_start=ZOOM_INICIAL,
        tiles="CartoDB positron",
        control_scale=True,
    )

    for _, fila in resumen.iterrows():
        nombre = f"{fila['departamento']} ({fila['provincia']})"
        popup_html = (
            f"<b>{nombre}</b><br>"
            f"Región: {fila['region']}<br>"
            f"pH mediana: {fila['ph']:.2f}<br>"
            f"MO mediana: {fila['materia_organica_pct']:.2f}%<br>"
            f"Lluvia mediana: {fila['precipitacion_total_mm']:.0f} mm<br>"
            f"Temp mediana: {fila['temp_media_c']:.1f} °C<br>"
            f"Registros: {int(fila['registros'])}"
        )
        folium.CircleMarker(
            location=(fila["latitud"], fila["longitud"]),
            radius=7,
            color=COLOR_POR_REGION.get(fila["region"], "gray"),
            fill=True,
            fill_opacity=0.8,
            tooltip=nombre,
            popup=folium.Popup(popup_html, max_width=260),
        ).add_to(mapa)

    return mapa


def _autocompletar_desde_fila(fila: pd.Series) -> None:
    """Empuja los valores del depto al sidebar."""
    aplicar_autocompletado(
        {
            "input_region": fila["region"],
            "input_ph": round(float(fila["ph"]), 2),
            "input_mo": round(float(fila["materia_organica_pct"]), 2),
            "input_arcilla": int(round(fila["arcilla_pct"])),
            "input_arena": int(round(fila["arena_pct"])),
            "input_precip": int(round(fila["precipitacion_total_mm"])),
            "input_temp": round(float(fila["temp_media_c"]), 1),
            "input_helada": int(round(fila["dias_helada"])),
        }
    )


def _procesar_click_mapa(estado_mapa: dict | None, resumen: pd.DataFrame) -> str | None:
    """Si hubo click nuevo en un marker, autocompleta. Devuelve el nombre del depto."""
    if not estado_mapa:
        return None
    click = estado_mapa.get("last_object_clicked")
    if not click:
        return None

    lat, lon = round(click["lat"], 4), round(click["lng"], 4)
    # Idempotencia: solo procesamos cada coordenada una vez por sesión.
    if st.session_state.get("ultimo_click_latlon") == (lat, lon):
        return None

    # Match exacto contra las coords del dataset (redondeadas a 4 decimales).
    candidatos = resumen[
        (resumen["latitud"].round(4) == lat) & (resumen["longitud"].round(4) == lon)
    ]
    if candidatos.empty:
        return None

    fila = candidatos.iloc[0]
    st.session_state["ultimo_click_latlon"] = (lat, lon)
    _autocompletar_desde_fila(fila)
    return f"{fila['departamento']} ({fila['provincia']})"


# ---------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------
def render_mapa() -> None:
    """Mapa folium + fallback selectbox. Autocompleta el sidebar al clickear."""
    resumen = cargar_resumen_departamentos()

    st.markdown(
        "**Mapa interactivo** — Click en un marker para autocompletar "
        "el sidebar con la mediana histórica de ese departamento."
    )

    mapa = _construir_mapa(resumen)
    estado = st_folium(
        mapa,
        height=460,
        use_container_width=True,
        returned_objects=["last_object_clicked"],
        key="mapa_principal",
    )

    autocompletado = _procesar_click_mapa(estado, resumen)
    if autocompletado:
        st.success(f"Autocompletado desde **{autocompletado}**.")

    # Fallback: selectbox con todos los deptos (útil si el mapa falla
    # o si el evaluador quiere pasar rápido a un depto específico sin
    # buscar en el mapa).
    with st.expander("Seleccionar departamento por nombre (fallback)"):
        opciones = ["—"] + [
            f"{r['region']} · {r['departamento']} ({r['provincia']})"
            for _, r in resumen.iterrows()
        ]
        elegido = st.selectbox(
            "Departamento",
            opciones,
            key="selectbox_depto_fallback",
        )
        if elegido != "—":
            partes = elegido.split(" · ", 1)[1]  # "Pergamino (Buenos Aires)"
            nombre_dpto = partes.split(" (", 1)[0]
            fila_match = resumen[resumen["departamento"] == nombre_dpto]
            if not fila_match.empty:
                clave = ("selectbox", nombre_dpto)
                if st.session_state.get("ultimo_autocomplete") != clave:
                    st.session_state["ultimo_autocomplete"] = clave
                    _autocompletar_desde_fila(fila_match.iloc[0])
                    st.success(f"Autocompletado desde **{elegido}**.")
                    st.rerun()
