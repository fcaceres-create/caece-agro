"""
Tab "🔍 Consola Prolog" — vidriera del sistema simbólico para defensa.

Este componente expone todo lo que normalmente queda detrás del bridge:
las reglas Prolog, los hechos generados desde el dataset, consultas
predefinidas que se ejecutan en vivo y una consola libre con sandbox.

El objetivo no es operacional sino académico: permitir al evaluador
verificar que el sistema simbólico es real y razonar sobre él.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import streamlit as st

from src.bridge.integrador import SistemaAgroSmart


# ---------------------------------------------------------------------
# Rutas y metadatos
# ---------------------------------------------------------------------
PROLOG_DIR = Path(__file__).resolve().parents[2] / "src" / "prolog"

# Bloque 1 — los 5 archivos de reglas + el de hechos expertos.
# La descripción se muestra en el caption de cada bloque para dar
# contexto sin que el evaluador tenga que leer todo el .pl.
ARCHIVOS_REGLAS: Final[list[tuple[str, str]]] = [
    (
        "agrosmart.pl",
        "Punto de entrada: carga la base de conocimiento y declara los "
        "predicados seguros para la consola libre.",
    ),
    (
        "reglas_aptitud.pl",
        "Define apto/2 y los auxiliares apto_suelo/2, apto_clima/2 y los "
        "dos parciales. Sin umbrales hardcodeados.",
    ),
    (
        "reglas_riesgo.pl",
        "7 tipos de riesgo (sequía, exceso, térmico, helada, nutricional, "
        "acidez, alcalinidad) + agregador todos_los_riesgos/3.",
    ),
    (
        "reglas_recomendacion.pl",
        "Combina aptitud + riesgo crítico para producir recomendar/2 y "
        "el reporte completo del lote.",
    ),
    (
        "hechos_expertos.pl",
        "Conocimiento agronómico de manual: ciclos, sensibilidad a helada, "
        "rotaciones recomendadas, categorización del cultivo.",
    ),
]

# Bloque 2 — un selector por cultivo permite filtrar los 265 hechos.
CULTIVOS_DISPONIBLES: Final[list[str]] = [
    "soja", "maiz", "trigo", "girasol", "cebada",
    "sorgo", "avena", "centeno", "arroz", "algodon", "mani",
]

# Bloque 3 — las 8 consultas predefinidas. Cada una tiene:
#   - etiqueta UI (lo que ve el evaluador en el selectbox)
#   - consulta Prolog real (lo que se muestra como código y se ejecuta)
#   - resultado esperado (texto descriptivo, NO se compara, solo informa)
CONSULTAS_PREDEFINIDAS: Final[list[dict]] = [
    {
        "etiqueta": "1. ¿Es la soja apta para Pergamino típico?",
        "query": "apto(lote_pergamino, soja).",
        "esperado": "true.",
    },
    {
        "etiqueta": "2. ¿Cuáles cultivos son recomendados para Pergamino?",
        "query": "findall(C, recomendar(lote_pergamino, C), Cultivos).",
        "esperado": "Cultivos = [soja, maiz, girasol, sorgo, ...] (lista no vacía).",
    },
    {
        "etiqueta": "3. ¿Qué riesgos tiene la soja en Pergamino?",
        "query": "todos_los_riesgos(lote_pergamino, soja, Riesgos).",
        "esperado": "Riesgos = [].",
    },
    {
        "etiqueta": "4. ¿Cuál es el rango óptimo de pH para soja?",
        "query": "rango_optimo(soja, ph, Min, Max).",
        "esperado": "Min ≈ 6.18, Max ≈ 6.96 (P10/P90 de las campañas exitosas).",
    },
    {
        "etiqueta": "5. ¿Es el maíz apto en sequía 2022/23?",
        "query": "apto(lote_sequia, maiz).",
        "esperado": "false. (precipitación bajo el P10 del cultivo).",
    },
    {
        "etiqueta": "6. ¿Cuáles son los 11 cultivos del sistema?",
        "query": "findall(C, cultivo_soportado(C), Cultivos).",
        "esperado": "Cultivos = [soja, maiz, trigo, girasol, cebada, ...] (11 elementos).",
    },
    {
        "etiqueta": "7. ¿Qué riesgos tiene la soja en lote ácido (pH 4.5)?",
        "query": "todos_los_riesgos(lote_acido, soja, Riesgos).",
        "esperado": "Riesgos = [acidez].",
    },
    {
        "etiqueta": "8. ¿Reporte completo del NEA arrocero?",
        "query": "reporte_lote(lote_nea, Recomendados, NoRecomendados, AptosParciales).",
        "esperado": "3 listas: aptos plenos / descartados / parciales.",
    },
]


# ---------------------------------------------------------------------
# Lectura cacheada de archivos .pl
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _leer_archivo_pl(ruta: str) -> str:
    """Lee un archivo .pl. Cacheado para no tocar disco en cada rerun."""
    return Path(ruta).read_text(encoding="utf-8")


def _contar_predicados(contenido: str) -> int:
    """Aproxima cuántos predicados define un archivo .pl.

    Cuenta cláusulas que matchean ``nombre(...) :-`` o hechos sueltos
    al inicio de línea. Subestima en macros raras pero alcanza para un
    caption descriptivo.
    """
    return len(re.findall(r"^[a-z_][a-zA-Z0-9_]*\s*\(", contenido, re.M))


def _filtrar_hechos_por_cultivo(contenido: str, cultivo: str) -> str:
    """Devuelve solo las líneas de hechos_generados.pl referidas a un cultivo.

    Mantiene comentarios contiguos (líneas que empiezan con %) que estén
    inmediatamente arriba de un hecho del cultivo, para que el bloque
    no pierda contexto.
    """
    if cultivo == "todos":
        return contenido

    lineas = contenido.splitlines()
    salida: list[str] = []
    buffer_comentarios: list[str] = []
    patron_cultivo = re.compile(rf"\b{re.escape(cultivo)}\b")

    for linea in lineas:
        stripped = linea.strip()
        if stripped.startswith("%") or not stripped:
            buffer_comentarios.append(linea)
            continue
        if patron_cultivo.search(linea):
            # Adjuntamos los comentarios acumulados (pueden ser cabecera de sección)
            if buffer_comentarios:
                salida.extend(buffer_comentarios)
                buffer_comentarios = []
            salida.append(linea)
        else:
            buffer_comentarios = []  # no era preámbulo de algo nuestro

    if not salida:
        return f"% (no se encontraron hechos para {cultivo})"
    return "\n".join(salida)


# ---------------------------------------------------------------------
# Sección 1 — Reglas del sistema experto
# ---------------------------------------------------------------------
def _render_seccion_reglas() -> None:
    with st.expander("📜 Reglas del sistema experto", expanded=True):
        st.caption(
            "Las reglas razonan sobre el lote combinando los rangos óptimos "
            "(derivados estadísticamente del dataset) con conocimiento "
            "agronómico de manual. Ningún umbral está hardcodeado."
        )
        for archivo, descripcion in ARCHIVOS_REGLAS:
            ruta = PROLOG_DIR / archivo
            if not ruta.exists():
                st.warning(f"No se encontró {archivo} en {PROLOG_DIR}.")
                continue
            contenido = _leer_archivo_pl(str(ruta))
            n_lineas = contenido.count("\n") + 1
            n_predicados = _contar_predicados(contenido)
            st.caption(
                f"**`{archivo}`** — {n_lineas} líneas · "
                f"{n_predicados} predicados/cláusulas. {descripcion}"
            )
            st.code(contenido, language="prolog")


# ---------------------------------------------------------------------
# Sección 2 — Hechos generados desde el dataset
# ---------------------------------------------------------------------
def _render_seccion_hechos() -> None:
    with st.expander("📋 Hechos generados desde el dataset", expanded=False):
        ruta = PROLOG_DIR / "hechos_generados.pl"
        if not ruta.exists():
            st.warning(f"No se encontró hechos_generados.pl en {PROLOG_DIR}.")
            return
        contenido = _leer_archivo_pl(str(ruta))

        st.caption(
            "**265 hechos generados estadísticamente desde el dataset.** "
            "Estos NO son una tabla copiada de un manual: son los "
            "percentiles P10/P90 de las campañas exitosas históricas de "
            "cada cultivo en cada región productiva argentina."
        )

        opciones = ["todos", *CULTIVOS_DISPONIBLES]
        cultivo = st.selectbox(
            "Filtrar hechos por cultivo:",
            opciones,
            key="consola_filtro_cultivo",
            help="'todos' muestra el archivo completo (311 líneas).",
        )

        hechos_filtrados = _filtrar_hechos_por_cultivo(contenido, cultivo)
        st.code(hechos_filtrados, language="prolog")


# ---------------------------------------------------------------------
# Sección 3 — Consultas predefinidas
# ---------------------------------------------------------------------
def _render_consultas_predefinidas(sistema: SistemaAgroSmart) -> None:
    with st.expander("▶️ Consultas predefinidas", expanded=False):
        st.caption(
            "8 consultas pre-armadas que ejecutan el sistema en vivo "
            "contra los 4 lotes pre-cargados (lote_pergamino, lote_sequia, "
            "lote_nea, lote_acido — definidos en `src/prolog/lotes_demo.pl`)."
        )

        opciones = {q["etiqueta"]: q for q in CONSULTAS_PREDEFINIDAS}
        eleccion = st.selectbox(
            "Consulta:",
            list(opciones.keys()),
            key="consola_consulta_predefinida",
        )
        consulta = opciones[eleccion]

        col_codigo, col_btn = st.columns([3, 1])
        with col_codigo:
            st.code(f"?- {consulta['query']}", language="prolog")
        with col_btn:
            st.write("")  # alineación visual con el bloque de código
            ejecutar = st.button(
                "Ejecutar",
                type="primary",
                key="consola_btn_predefinida",
                width="stretch",
            )

        st.caption(f"**Esperado:** {consulta['esperado']}")

        if ejecutar:
            with st.spinner("Consultando Prolog..."):
                # sandboxing=False: las 8 consultas están auditadas y son seguras.
                resultado = sistema.consultar_prolog(
                    consulta["query"], sandboxing=False
                )
            _render_resultado_consulta(resultado)


# ---------------------------------------------------------------------
# Sección 4 — Consola libre (con sandbox)
# ---------------------------------------------------------------------
def _render_consola_libre(sistema: SistemaAgroSmart) -> None:
    with st.expander("💻 Consola libre", expanded=False):
        st.info(
            "**Predicados disponibles:**\n"
            "- Aptitud: `apto/2`, `apto_suelo/2`, `apto_clima/2`, "
            "`apto_parcial_suelo/2`, `apto_parcial_clima/2`\n"
            "- Recomendación: `recomendar/2`, `reporte_lote/4`\n"
            "- Riesgo: `riesgo/3`, `todos_los_riesgos/3`, "
            "`riesgo_sequia/2`, `riesgo_helada/2`, `riesgo_nutricional/2`, "
            "`riesgo_acidez/2`, `riesgo_alcalinidad/2`, "
            "`riesgo_estres_termico/2`, `riesgo_exceso_hidrico/2`\n"
            "- Conocimiento: `cultivo_soportado/1`, `cultivo_en_region/2`, "
            "`rango_optimo/4`, `rendimiento_esperado/4`, `ciclo/2`, "
            "`sensible_helada/1`, `predecesor_recomendado/2`\n"
            "- Meta: `findall/3`, `member/2`, `length/2`, `between/3`\n\n"
            "**Cultivos:** soja · maiz · trigo · girasol · cebada · sorgo · "
            "avena · centeno · arroz · algodon · mani  \n"
            "**Lotes pre-cargados:** lote_pergamino · lote_sequia · "
            "lote_nea · lote_acido  \n"
            "**Sintaxis:** termina la consulta con `.` (la consola lo "
            "agrega solo si lo olvidás)."
        )

        consulta = st.text_area(
            "Consulta Prolog:",
            value=st.session_state.get("consola_libre_input", ""),
            placeholder="apto(lote_pergamino, soja).",
            key="consola_libre_input",
            height=80,
        )

        col_eje, col_lim, _col_pad = st.columns([1, 1, 4])
        with col_eje:
            ejecutar = st.button(
                "Ejecutar",
                type="primary",
                key="consola_libre_btn_eje",
                width="stretch",
            )
        with col_lim:
            limpiar = st.button(
                "Limpiar",
                key="consola_libre_btn_lim",
                width="stretch",
            )

        if limpiar:
            st.session_state["consola_libre_input"] = ""
            st.rerun()

        if ejecutar:
            consulta_str = (consulta or "").strip()
            if not consulta_str:
                st.warning("Escribí una consulta antes de ejecutar.")
                return
            with st.spinner("Consultando Prolog (sandbox + 5s timeout)..."):
                # sandboxing=True: input arbitrario del usuario, defensa total.
                resultado = sistema.consultar_prolog(
                    consulta_str, sandboxing=True, timeout=5.0
                )
            _render_resultado_consulta(resultado)


# ---------------------------------------------------------------------
# Helper: render del resultado de una consulta (predefinida o libre)
# ---------------------------------------------------------------------
def _render_resultado_consulta(resultado: dict) -> None:
    """Renderiza la salida cruda + meta de tiempo/error."""
    if resultado["exitosa"]:
        st.success(
            f"✅ Ejecutada en {resultado['tiempo_ms']:.1f} ms · "
            f"{len(resultado['soluciones'])} solución(es)"
            + (" (truncado)" if resultado["truncado"] else "")
        )
    else:
        st.error(
            f"❌ Error en {resultado['tiempo_ms']:.1f} ms"
            + (f" · {resultado['error']}" if resultado["error"] else "")
        )
    st.code(resultado["output_formateado"], language="text")


# ---------------------------------------------------------------------
# Render principal del tab
# ---------------------------------------------------------------------
def render_consola_prolog(sistema: SistemaAgroSmart) -> None:
    """Punto de entrada del tab '🔍 Consola Prolog'.

    Se renderiza siempre, independientemente de si se evaluó un lote
    o no. La consola es el modo "ver el sistema simbólico" y vive
    paralelo a la cascada de evaluación.
    """
    st.markdown("## 🔍 Consola Prolog del sistema experto")
    st.markdown(
        "Esta consola muestra el sistema simbólico subyacente: las "
        "reglas, los hechos generados y consultas ejecutables en "
        "tiempo real contra la base de conocimiento. Es independiente "
        "de la evaluación de lote del sidebar."
    )

    _render_seccion_reglas()
    _render_seccion_hechos()
    _render_consultas_predefinidas(sistema)
    _render_consola_libre(sistema)
