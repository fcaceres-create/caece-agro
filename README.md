# AgroSmart

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://caece-agrosmart.streamlit.app)

Sistema híbrido de decisión agronómica para Argentina. Dadas la región y
las condiciones edafoclimáticas de un lote, responde en cascada tres
preguntas:

1. **¿Qué cultivos son aptos?** Reglas en SWI-Prolog sobre rangos
   óptimos derivados estadísticamente de datos argentinos reales.
2. **¿Cuánto se estima producir?** Random Forest entrenado por cultivo
   sobre 25 campañas de rendimientos del MAGyP.
3. **¿Qué riesgos enfrenta?** Diagnóstico simbólico de sequía, helada,
   acidez, exceso hídrico, estrés térmico, déficit nutricional y
   alcalinidad.

Combina una capa estadística en Python (pandas + scikit-learn) con una
capa simbólica en SWI-Prolog. La integración real entre ambas capas
—datos ⇄ conocimiento, ML ⇄ lógica— es el núcleo del aporte propio del
trabajo.

Trabajo Final Integrador de la materia *Fundamentos de Inteligencia
Artificial*, Maestría en Gestión y Desarrollo IA, Universidad CAECE.
Entrega: mayo 2026.

## Sistema desplegado

🌐 **App pública:** https://caece-agrosmart.streamlit.app

La app permite:

- Cargar uno de cuatro **lotes pre-configurados** (Pergamino típico,
  Sequía 2022/23, NEA arrocero, Lote ácido) o ajustar los siete
  parámetros del lote con sliders.
- **Clickear sobre un departamento del mapa** para autocompletar el
  sidebar con la mediana histórica del departamento.
- Ver el **reporte completo** en tres pestañas: cultivos recomendados
  (con predicción, intervalo de confianza al 95% y clasificación
  cualitativa contra los percentiles de la zona), no recomendados (con
  motivo) y aptos parciales (mitigables con manejo).
- Inspeccionar el **detalle por cultivo**: tabla de "valor del lote vs
  rango óptimo" variable por variable, y boxplot histórico de
  rendimiento con la predicción del modelo marcada.

## Stack

- **Python 3.11** (3.10+ funciona): pandas + scikit-learn para la capa
  cuantitativa.
- **SWI-Prolog 9.x** (con pyswip): capa simbólica con 265 hechos
  generados desde el dataset + reglas de aptitud, riesgo y
  recomendación.
- **Streamlit + folium + plotly**: app web interactiva.
- **Random Forest** (200 árboles, profundidad 15): un modelo
  independiente por cultivo, con intervalo de confianza derivado de la
  varianza entre árboles.

## Estado del proyecto

| Fase | Estado | Resultado |
|---|---|---|
| I — Exploración de APIs | ✅ Completada | Clientes funcionales para MAGyP, Open-Meteo y SoilGrids. |
| II — Dataset y EDA | ✅ Completada | Dataset de 3.786 filas × 29 columnas; 13 figuras del EDA; rangos óptimos por cultivo. |
| III — Sistema experto Prolog | ✅ Completada | 6 archivos .pl con 265 hechos generados + reglas de aptitud, riesgo y recomendación. |
| IV — Bridge Python ↔ Prolog | ✅ Completada | Cascada en 3 etapas; 11 modelos RF por cultivo; 6 tests pasando. |
| V — App web | ✅ Completada y desplegada | Streamlit Cloud en https://caece-agrosmart.streamlit.app |

## Setup local

### Prerrequisitos

- Python 3.10+ (recomendado 3.11).
- **SWI-Prolog 9.x estable** instalado a nivel sistema:
  - **Windows**: instalador desde https://www.swi-prolog.org/download/stable
    con su carpeta `bin` agregada al `PATH` y la variable de entorno
    `SWI_HOME_DIR` apuntando a la instalación.
  - **Linux**: `sudo apt install swi-prolog-nox` (o paquete equivalente).
  - **macOS**: `brew install swi-prolog`.
- Git.

### Instalación

```bash
# clonar repo y crear venv
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements-dev.txt    # desarrollo local (notebook, tests, informe)
# o
pip install -r requirements.txt        # solo runtime de la app
```

Para correr la app localmente:

```bash
streamlit run app/streamlit_app.py
```

URL: http://localhost:8501.

El detalle paso a paso del setup en Windows (incluida la verificación de
que pyswip puede cargar la DLL) está en [`CLAUDE.md`](CLAUDE.md), sección
"Setup local (Windows nativo)".

## Regenerar artefactos desde cero

El repositorio ya incluye los artefactos versionados que la app necesita
para arrancar (~16 MB: dataset maestro, 11 modelos joblib, hechos
Prolog generados). Para regenerarlos desde las fuentes originales:

```bash
# 1. Reconstruir el dataset desde las APIs (puede tardar; respeta cache)
python -m src.procesamiento.consolidacion

# 2. Correr el notebook de EDA hasta el final (genera figuras y CSV de rangos)
jupyter notebook notebooks/02_eda_consolidado.ipynb

# 3. Generar los hechos Prolog desde los rangos
python -m src.procesamiento.generar_hechos_prolog

# 4. Entrenar los 11 modelos Random Forest
python -m src.modelos.regresor_rendimiento --entrenar

# 5. Validar con la demo de los 3 lotes
python scripts/demo_agrosmart.py

# 6. (Opcional) Regenerar el informe TFI en .docx
python scripts/generar_informe.py
```

## Estructura del repo

```
caece-agro/
├── app/                        # aplicación Streamlit (entrypoint del deploy)
│   ├── streamlit_app.py
│   └── componentes/            # sidebar, mapa, reporte, detalle por cultivo
├── src/
│   ├── apis/                   # clientes MAGyP, Open-Meteo, SoilGrids
│   ├── procesamiento/          # consolidación + generador de hechos Prolog
│   ├── modelos/                # regresor Random Forest por cultivo
│   ├── prolog/                 # 6 archivos del sistema experto
│   └── bridge/                 # cascada Python ↔ Prolog (núcleo Fase IV)
├── data/
│   ├── processed/              # dataset maestro y rangos óptimos
│   └── modelos/                # 11 joblibs + reporte JSON de entrenamiento
├── notebooks/
│   └── 02_eda_consolidado.ipynb
├── scripts/
│   ├── demo_agrosmart.py       # cascada end-to-end de 3 lotes
│   └── generar_informe.py      # genera docs/informe.docx
├── tests/
│   └── test_bridge.py          # 6 tests pytest del bridge
├── docs/
│   ├── informe.docx            # informe TFI académico (entregable formal)
│   ├── recuperacion_de_datos.md  # bitácora extendida (14 secciones)
│   └── figuras/                # 13 PNGs del EDA
├── .streamlit/config.toml      # configuración de la app (tema dark)
├── packages.txt                # paquetes apt para Streamlit Cloud
├── requirements.txt            # deps de runtime (deploy)
├── requirements-dev.txt        # deps de desarrollo local
├── CLAUDE.md                   # marco general y setup detallado
└── README.md                   # este archivo
```

## Documentos del proyecto

- **Informe TFI académico** (entregable formal a la cátedra):
  [`docs/informe.docx`](docs/informe.docx). 25-32 páginas, 8
  capítulos, 6 figuras embebidas.
- **Bitácora extendida** (decisiones técnicas y resolución de problemas):
  [`docs/recuperacion_de_datos.md`](docs/recuperacion_de_datos.md).
- **Marco general y setup local detallado**: [`CLAUDE.md`](CLAUDE.md).

## Autores

- Fernando Cáceres
- Ezequiel Díaz Fernández

Universidad CAECE — Maestría en Gestión y Desarrollo IA — Mayo 2026.
