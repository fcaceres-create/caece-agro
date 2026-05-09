"""
Tab "📚 Documentación" — vidriera estática del proyecto AgroSmart.

Reúne en una sola superficie todo el material que un evaluador
necesita: manual de usuario, descripción de la arquitectura, fuentes
de datos, resultados del TFI con R² reales por cultivo, glosario y
recursos. Incluye un botón para descargar el informe TFI .docx.

A diferencia de los otros componentes, este es 100% estático: no
toca el sistema experto ni los modelos. Solo lee archivos de docs/
y data/modelos/. Por eso no recibe el `sistema` como argumento.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import streamlit as st


# ---------------------------------------------------------------------
# Rutas y constantes del proyecto
# ---------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[2]
DOCS_DIR = RAIZ / "docs"
FIGURAS_DIR = DOCS_DIR / "figuras"
INFORME_DOCX = DOCS_DIR / "informe.docx"
REPORTE_ENTRENAMIENTO_JSON = (
    RAIZ / "data" / "modelos" / "reporte_entrenamiento.json"
)

URL_REPO = "https://github.com/fcaceres-create/caece-agro"
URL_NOTEBOOK_EDA = (
    f"{URL_REPO}/blob/main/notebooks/02_eda_consolidado.ipynb"
)
URL_BITACORA = (
    f"{URL_REPO}/blob/main/docs/recuperacion_de_datos.md"
)
URL_INFORME_GH = f"{URL_REPO}/blob/main/docs/informe.docx"
URL_APP_DESPLEGADA = "https://caece-agrosmart.streamlit.app"

# Las 13 figuras del EDA (la 14 es captura de la propia app y se omite
# por ser meta-circular). Los títulos legibles son curados a mano para
# que la galería se vea como una figura indexada de informe.
TITULOS_FIGURAS_EDA: Final[list[tuple[str, str]]] = [
    ("01", "Boxplot de rendimiento por cultivo"),
    ("02", "Boxplot de rendimiento por región (4 cultivos principales)"),
    ("03", "Histogramas de variables agronómicas"),
    ("04", "Evolución temporal del rendimiento de soja en Pampeana"),
    ("05", "Evolución temporal del rendimiento de maíz en Pampeana"),
    ("06", "Heatmap de correlación general"),
    ("07", "Top 5 correlaciones rendimiento↔variable por cultivo"),
    ("08", "Boxplot de soja por región"),
    ("09", "Distribución de calidad del suelo"),
    ("10", "Validación del fallback de suelo (SoilGrids)"),
    ("11", "Campañas fallidas por cultivo y campaña"),
    ("12", "Avena: fracasos por año y departamento"),
    ("13", "Heatmap de rangos óptimos por cultivo"),
]


# ---------------------------------------------------------------------
# Lectura cacheada de archivos pesados
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _cargar_informe_bytes() -> bytes | None:
    """Lee el .docx una sola vez por sesión. None si no existe."""
    if not INFORME_DOCX.exists():
        return None
    return INFORME_DOCX.read_bytes()


@st.cache_data(show_spinner=False)
def _cargar_reporte_entrenamiento() -> dict | None:
    """Carga el JSON con métricas de los 11 modelos. None si no existe."""
    if not REPORTE_ENTRENAMIENTO_JSON.exists():
        return None
    try:
        return json.loads(
            REPORTE_ENTRENAMIENTO_JSON.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return None


def _categoria_r2(r2: float) -> str:
    """Etiqueta cualitativa según el R² del cultivo (criterio del TFI)."""
    if r2 >= 0.6:
        return "🟢 Buen ajuste"
    if r2 >= 0.3:
        return "🟡 Ajuste moderado"
    return "🔴 Drivers fuera del dataset"


# ---------------------------------------------------------------------
# Botón de descarga del informe
# ---------------------------------------------------------------------
def _render_descarga_informe() -> None:
    bytes_informe = _cargar_informe_bytes()
    if bytes_informe is None:
        st.warning(
            "📥 El informe TFI (.docx) no está disponible en este deploy. "
            f"Se puede consultar en el [repositorio en GitHub]({URL_INFORME_GH})."
        )
        return
    st.download_button(
        "📥 Descargar informe TFI (.docx)",
        data=bytes_informe,
        file_name="AgroSmart_TFI_Caceres_DiazFernandez.docx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        type="primary",
        help=(
            "Documento formal del trabajo final integrador "
            "(25–32 páginas, 8 capítulos, 6 figuras embebidas)."
        ),
    )


# ---------------------------------------------------------------------
# Sección 1 — 🎯 Sobre el proyecto (manual de usuario)
# ---------------------------------------------------------------------
def _render_seccion_proyecto() -> None:
    with st.expander("🎯 Sobre el proyecto", expanded=True):
        st.markdown(
            "### ¿Qué es AgroSmart?\n"
            "\n"
            "AgroSmart es un sistema híbrido de decisión agronómica para "
            "Argentina. Dadas las características de un lote, responde "
            "tres preguntas en cascada:\n"
            "\n"
            "1. **¿Qué cultivos son aptos?** Reglas Prolog sobre rangos "
            "óptimos derivados estadísticamente del dataset argentino.\n"
            "2. **¿Cuánto se estima producir?** Random Forest entrenado "
            "por cultivo sobre 25 campañas reales del MAGyP.\n"
            "3. **¿Qué riesgos enfrenta?** Diagnóstico simbólico de "
            "sequía, helada, acidez, exceso hídrico, estrés térmico, "
            "déficit nutricional y alcalinidad.\n"
            "\n"
            "### ¿Cómo se usa la app?\n"
            "\n"
            "1. **Cargá un lote**: en el sidebar, elegí un ejemplo "
            "pre-configurado (Pergamino típico, Sequía 2022/23, NEA "
            "arrocero, Lote ácido) o ajustá manualmente los 7 parámetros "
            "con sliders.\n"
            "2. **Opcional — Click en mapa**: clickeá un departamento "
            "del mapa interactivo de Argentina. Los sliders se "
            "autocompletan con la mediana histórica de ese departamento.\n"
            "3. **Apretá *Evaluar lote***: la cascada Prolog + Random "
            "Forest procesa el lote. Tarda menos de 2 segundos.\n"
            "4. **Leé el reporte**: aparece debajo del mapa con tres "
            "pestañas:\n"
            "   - **Recomendados**: cultivos aptos sin riesgos críticos, "
            "con predicción de rendimiento e intervalo de confianza al 95%.\n"
            "   - **No recomendados**: cultivos descartados con motivo "
            "explícito.\n"
            "   - **Aptos parciales**: cultivos viables solo con manejo "
            "correctivo.\n"
            "5. **Explorá el detalle por cultivo**: el expander al final "
            "muestra una tabla *Valor del lote vs rango óptimo* variable "
            "por variable y un boxplot de la distribución histórica con "
            "la predicción del modelo marcada.\n"
            "6. **Tab Consola Prolog**: para ver el sistema simbólico "
            "subyacente, ejecutar consultas predefinidas o escribir "
            "consultas libres."
        )


# ---------------------------------------------------------------------
# Sección 2 — 🔬 Arquitectura técnica
# ---------------------------------------------------------------------
def _render_seccion_arquitectura() -> None:
    with st.expander("🔬 Arquitectura técnica", expanded=False):
        st.markdown(
            "### Stack tecnológico\n"
            "\n"
            "- **Python 3.11**: pandas, scikit-learn, joblib para la "
            "capa cuantitativa.\n"
            "- **SWI-Prolog 9.x con pyswip**: capa simbólica.\n"
            "- **Streamlit + folium + plotly**: interfaz web interactiva.\n"
            "- **Random Forest** (200 árboles, profundidad 15): un modelo "
            "independiente por cultivo.\n"
            "\n"
            "### El bridge en cascada (núcleo del aporte propio)\n"
            "\n"
            "El sistema NO consulta un modelo que diga *\"soja con "
            "probabilidad 0.87\"*. Combina razonamiento simbólico y "
            "predicción cuantitativa en tres etapas:\n"
            "\n"
            "**Etapa 1 — Aptitud simbólica (Prolog).**  \n"
            "Se asertan los hechos del lote en la base de conocimiento. "
            "Las reglas Prolog evalúan si cada cultivo es apto verificando "
            "que las variables del lote (pH, MO, arcilla, arena, "
            "precipitación, temperatura, días de helada) caigan dentro "
            "del rango óptimo del cultivo. Los rangos NO son hardcodeados: "
            "son los percentiles P10/P90 calculados sobre las campañas "
            "exitosas históricas del cultivo en el dataset.\n"
            "\n"
            "**Etapa 2 — Predicción cuantitativa (Random Forest).**  \n"
            "Solo para los cultivos que pasaron la etapa 1, se ejecuta el "
            "modelo entrenado para ese cultivo. Devuelve la predicción "
            "puntual más un intervalo de confianza al 95% derivado de la "
            "varianza entre los árboles del bosque.\n"
            "\n"
            "**Etapa 3 — Diagnóstico de riesgos y reporte (Prolog).**  \n"
            "Se evalúan los 7 tipos de riesgo definidos. Si hay riesgo "
            "crítico, el cultivo se mueve de *recomendado* a *apto "
            "parcial*. Se genera el reporte final con clasificación "
            "cualitativa (rendimiento alto/medio/bajo según percentiles "
            "zonales).\n"
            "\n"
            "### ¿Por qué un sistema híbrido?\n"
            "\n"
            "Un Random Forest puro daría predicciones opacas: *\"soja, "
            "3.359 kg/ha, 87% de confianza\"*. No permite responder por "
            "qué soja, qué hace que sea apta, qué riesgos enfrenta.\n"
            "\n"
            "Un sistema experto puro Prolog razonaría sobre aptitud y "
            "riesgo pero no podría cuantificar el rendimiento esperado.\n"
            "\n"
            "Combinar ambos da una decisión que es simultáneamente "
            "**explicable** (las reglas son auditables) y **cuantificable** "
            "(los modelos predicen rendimientos). Los desacuerdos entre "
            "ambas capas se reportan como observaciones explícitas, no "
            "se ocultan."
        )


# ---------------------------------------------------------------------
# Sección 3 — 📊 Datos y EDA
# ---------------------------------------------------------------------
def _render_seccion_datos_eda() -> None:
    with st.expander("📊 Datos y EDA", expanded=False):
        st.markdown(
            "### Las 4 fuentes de datos\n"
            "\n"
            "El dataset maestro consolida cuatro fuentes oficiales y de "
            "cátedra:\n"
            "\n"
            "| Fuente | Variable | Cobertura |\n"
            "|---|---|---|\n"
            "| **MAGyP** | Producción y rendimientos por departamento | "
            "11 cultivos × 30 deptos × 25 campañas |\n"
            "| **Open-Meteo (ERA5)** | Clima histórico de reanálisis | "
            "Precipitación, temperatura media, días de helada |\n"
            "| **SoilGrids** | Propiedades edáficas | "
            "pH, materia orgánica, arcilla, arena |\n"
            "| **Cátedra/INTA/FAO** | Conocimiento agronómico | "
            "Cargado a mano en `hechos_expertos.pl` |\n"
            "\n"
            "El resultado son **3.786 registros georreferenciados**.\n"
            "\n"
            "### ¿Cómo se derivaron los rangos óptimos?\n"
            "\n"
            "Los **265 hechos** generados en `hechos_generados.pl` NO son "
            "una tabla copiada de un manual. Son los percentiles P10/P90 "
            "calculados sobre las campañas exitosas históricas de cada "
            "cultivo en cada región productiva. Por ejemplo, para soja:"
        )
        st.code(
            "rango_optimo(soja, ph, 6.18, 6.96).\n"
            "rango_optimo(soja, materia_organica_pct, 2.42, 4.44).\n"
            "rango_optimo(soja, arcilla_pct, 18.50, 36.07).\n"
            "...",
            language="prolog",
        )
        st.markdown(
            "Estos números provienen de las 25 campañas argentinas "
            "reales en las que la soja produjo rendimientos por encima "
            "del P25 zonal. Al estar derivados estadísticamente del "
            "propio dataset, las reglas pueden auditarse contra los "
            "datos: cualquier evaluador puede correr el notebook de EDA "
            "y verificar que los rangos son los percentiles 10/90 de las "
            "campañas exitosas.\n"
            "\n"
            "### Cobertura efectiva\n"
            "\n"
            "El sistema cubre **3 regiones productivas argentinas**:\n"
            "\n"
            "- **Pampeana** (Buenos Aires, Santa Fe, Córdoba, Entre Ríos, "
            "La Pampa)\n"
            "- **NOA** (Salta, Tucumán, Santiago del Estero, Catamarca, "
            "Jujuy)\n"
            "- **NEA** (Corrientes, Chaco, Formosa, Misiones)\n"
            "\n"
            "Cuyo y Patagonia quedaron sin filas: MAGyP no reporta como "
            "cultivos extensivos los cereales bajo riego en Mendoza ni "
            "la avena para verdeo patagónica. Es una limitación de la "
            "fuente, no del sistema."
        )

        # Galería completa de figuras del EDA — sub-expander para no
        # cargar 13 imágenes pesadas hasta que el usuario las pida.
        with st.expander(
            "📊 Ver las 13 figuras del análisis exploratorio",
            expanded=False,
        ):
            faltantes: list[str] = []
            for prefijo, titulo in TITULOS_FIGURAS_EDA:
                # Las figuras tienen nombres tipo "01_boxplot_…png".
                # Glob por prefijo permite tolerar pequeños cambios
                # del slug sin romper la galería.
                candidatos = sorted(FIGURAS_DIR.glob(f"{prefijo}_*.png"))
                if not candidatos:
                    faltantes.append(prefijo)
                    continue
                st.markdown(f"**Figura {prefijo}** — {titulo}")
                st.image(str(candidatos[0]), width="stretch")
            if faltantes:
                st.caption(
                    f"⚠ Figuras no encontradas en `docs/figuras/`: "
                    f"{', '.join(faltantes)}."
                )


# ---------------------------------------------------------------------
# Sección 4 — 🎓 TFI académico
# ---------------------------------------------------------------------
def _render_tabla_r2() -> None:
    """Tabla de R² reales por cultivo, ordenada de mayor a menor.

    Lee `data/modelos/reporte_entrenamiento.json`. Si el archivo no
    está disponible, muestra un placeholder en lugar de inventar números.
    """
    reporte = _cargar_reporte_entrenamiento()
    if reporte is None or "cultivos" not in reporte:
        st.info(
            "Tabla de R² disponible en "
            "`data/modelos/reporte_entrenamiento.json` del repositorio."
        )
        return

    filas: list[dict[str, str]] = []
    items = sorted(
        reporte["cultivos"].values(),
        key=lambda c: c.get("r2", 0.0),
        reverse=True,
    )
    for c in items:
        n_total = c.get("n_train", 0) + c.get("n_test", 0)
        filas.append(
            {
                "Cultivo": c["cultivo"].capitalize(),
                "R²": f"{c['r2']:.3f}",
                "MAE (kg/ha)": f"{c['mae_kg_ha']:.0f}",
                "n (train + test)": str(n_total),
                "Categoría": _categoria_r2(c["r2"]),
            }
        )
    st.table(filas)


def _render_seccion_tfi() -> None:
    with st.expander("🎓 TFI académico", expanded=False):
        st.markdown(
            "### Datos del Trabajo Final Integrador\n"
            "\n"
            "- **Universidad:** CAECE — Modalidad E-distancia\n"
            "- **Carrera:** Maestría en Gestión y Desarrollo de IA\n"
            "- **Materia:** Fundamentos de Inteligencia Artificial\n"
            "- **Profesor:** Juan Miguel Azcurra\n"
            "- **Cuatrimestre:** 1° Cuatrimestre 2026\n"
            "- **Fecha de entrega:** 22 de mayo de 2026\n"
            "- **Autores:** Fernando Cáceres, Ezequiel Díaz Fernández\n"
            "\n"
            "### Objetivos del trabajo\n"
            "\n"
            "El objetivo fue implementar un sistema híbrido que combine "
            "las dos paradigmas centrales de IA cubiertos en la materia: "
            "**razonamiento simbólico** (sistema experto en Prolog) y "
            "**aprendizaje automático** (Random Forest). Aplicado a un "
            "dominio relevante en Argentina (recomendación de cultivos "
            "extensivos), con datos públicos reales, y validado mediante "
            "una app web interactiva.\n"
            "\n"
            "### Metodología\n"
            "\n"
            "El proyecto siguió 5 fases:\n"
            "\n"
            "1. **Exploración de APIs**: clientes para MAGyP, Open-Meteo "
            "y SoilGrids.\n"
            "2. **Dataset y EDA**: consolidación a 3.786 registros y "
            "análisis exploratorio.\n"
            "3. **Sistema experto Prolog**: 5 archivos de reglas + 265 "
            "hechos generados estadísticamente.\n"
            "4. **Bridge Python ↔ Prolog**: 11 modelos Random Forest + "
            "cascada en 3 etapas + 6 tests automatizados.\n"
            "5. **App web**: interfaz Streamlit con mapa interactivo, "
            "evaluación de lotes y consola Prolog.\n"
            "\n"
            "### Resultados — R² por cultivo\n"
            "\n"
            "Los 11 modelos fueron entrenados y validados "
            "independientemente. Los R² se reportan honestamente, sin "
            "maquillar:"
        )
        _render_tabla_r2()
        st.markdown(
            "### Limitaciones reconocidas\n"
            "\n"
            "El sistema reconoce honestamente sus propios límites:\n"
            "\n"
            "1. **Cobertura geográfica**: solo Pampeana, NOA y NEA. "
            "Cuyo y Patagonia quedaron sin datos por limitación de la "
            "fuente.\n"
            "2. **R² bajo en cultivos minoritarios**: maní y otros "
            "cultivos con pocos registros tienen R² < 0.1 porque sus "
            "drivers reales (variedad, fecha de siembra, calcio del "
            "suelo) no están en el dataset. El sistema documenta esta "
            "limitación en lugar de disimularla.\n"
            "3. **Escenarios extremos**: ante campañas catastróficas "
            "como la sequía 2022/23 (320 mm de lluvia, debajo del P10 "
            "de todos los cultivos extensivos pampeanos), el sistema "
            "responde con la lista de recomendados vacía. Es "
            "agronómicamente correcto y prácticamente conservador.\n"
            "\n"
            "### Descargar informe completo\n"
            "\n"
            "El informe TFI completo (25–32 páginas, 8 capítulos, 6 "
            "figuras embebidas, 7 tablas) se puede descargar con el "
            "botón al inicio de esta sección de documentación."
        )


# ---------------------------------------------------------------------
# Sección 5 — 📖 Glosario
# ---------------------------------------------------------------------
def _render_seccion_glosario() -> None:
    with st.expander("📖 Glosario de términos", expanded=False):
        st.markdown(
            "- **AgroSmart**: nombre del sistema desarrollado para este TFI.\n"
            "- **Aptitud parcial**: cultivo viable pero solo con manejo "
            "correctivo (riego suplementario, encalado, drenaje, etc.).\n"
            "- **Bridge**: módulo Python que coordina la cascada de 3 "
            "etapas entre la capa cuantitativa (scikit-learn) y la "
            "simbólica (Prolog).\n"
            "- **Campaña agrícola**: ciclo productivo de un cultivo. "
            "Las campañas se nombran por los dos años calendario que "
            "abarcan (ej: 2024/25).\n"
            "- **Cascada de decisión**: arquitectura del bridge donde "
            "el output de cada etapa alimenta a la siguiente, y la "
            "presencia de riesgo crítico puede mover un cultivo de "
            "*recomendado* a *apto parcial*.\n"
            "- **EDA**: análisis exploratorio de datos. Etapa preliminar "
            "donde se inspeccionan distribuciones, correlaciones y "
            "outliers para entender la estructura del dataset antes de "
            "modelar.\n"
            "- **Hechos generados**: 265 cláusulas Prolog (tipo "
            "`rango_optimo(soja, ph, 6.18, 6.96)`) derivadas "
            "estadísticamente del dataset. Se generan automáticamente; "
            "no se cargan a mano.\n"
            "- **Intervalo de confianza al 95%**: rango dentro del cual "
            "cae el rendimiento real con 95% de probabilidad. Se calcula "
            "a partir de la varianza entre los árboles del bosque.\n"
            "- **MAGyP**: Ministerio de Agricultura, Ganadería y Pesca "
            "de Argentina. Fuente principal de datos productivos.\n"
            "- **Percentiles P10/P90**: el 10% de las observaciones "
            "está debajo del P10 y el 90% debajo del P90. Definen el "
            "rango óptimo de cada variable para cada cultivo.\n"
            "- **pyswip**: librería Python que provee bindings a "
            "SWI-Prolog, permitiendo ejecutar consultas Prolog desde "
            "Python.\n"
            "- **Random Forest**: algoritmo de aprendizaje automático "
            "que promedia las predicciones de muchos árboles de decisión "
            "entrenados sobre subconjuntos aleatorios de los datos.\n"
            "- **Rangos óptimos**: para cada cultivo y cada variable, "
            "el intervalo (P10, P90) dentro del cual el cultivo prosperó "
            "históricamente.\n"
            "- **SoilGrids**: base de datos global de propiedades del "
            "suelo (pH, materia orgánica, textura) producida por ISRIC.\n"
            "- **Sistema experto**: programa que aplica reglas lógicas "
            "sobre una base de conocimiento para inferir conclusiones, "
            "simulando el razonamiento de un experto humano.\n"
            "- **SWI-Prolog**: implementación open-source de Prolog. La "
            "que se usa en este proyecto, versión 9.x."
        )


# ---------------------------------------------------------------------
# Sección 6 — 📚 Recursos del proyecto
# ---------------------------------------------------------------------
def _render_seccion_recursos() -> None:
    with st.expander("📚 Recursos del proyecto", expanded=False):
        st.markdown(
            f"### Repositorio\n"
            f"\n"
            f"- 📂 **[GitHub: fcaceres-create/caece-agro]({URL_REPO})**  \n"
            f"  Repositorio público con todo el código fuente, datos, "
            f"modelos serializados y documentación.\n"
            f"\n"
            f"### Documentos del proyecto\n"
            f"\n"
            f"- 📄 **[Informe TFI académico (.docx)]({URL_INFORME_GH})**  \n"
            f"  Documento formal de 25–32 páginas con la descripción "
            f"completa del trabajo. (También descargable con el botón "
            f"al inicio.)\n"
            f"- 📓 **[Bitácora extendida del proyecto]({URL_BITACORA})**  \n"
            f"  Documento de 15 secciones con cada decisión técnica, "
            f"problema encontrado y solución aplicada durante el "
            f"desarrollo.\n"
            f"- 📊 **[Notebook de EDA]({URL_NOTEBOOK_EDA})**  \n"
            f"  Análisis exploratorio reproducible con código + gráficos.\n"
            f"\n"
            f"### Sistema desplegado\n"
            f"\n"
            f"- 🌐 **[App pública]({URL_APP_DESPLEGADA})**  \n"
            f"  Estás aquí."
        )


# ---------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------
def render_documentacion() -> None:
    """Punto de entrada del tab '📚 Documentación'.

    Estática y autocontenida: no toca el sistema experto ni los modelos,
    solo lee archivos de docs/ y data/modelos/. Todas las secciones son
    expandibles; la primera (manual de usuario) abre por default.
    """
    st.markdown("## 📚 Documentación del proyecto")
    st.markdown(
        "Manual de usuario, descripción de la arquitectura, fuentes de "
        "datos, resultados del TFI y glosario. Toda la documentación "
        "del proyecto, accesible sin salir de la app."
    )

    _render_descarga_informe()
    _render_seccion_proyecto()
    _render_seccion_arquitectura()
    _render_seccion_datos_eda()
    _render_seccion_tfi()
    _render_seccion_glosario()
    _render_seccion_recursos()
