# AgroSmart

Sistema híbrido de decisión agronómica para Argentina. Dadas las
coordenadas geográficas de un lote, responde en cascada:

1. ¿Qué cultivos son aptos? (reglas Prolog sobre datos reales)
2. ¿Cuánto se estima producir? (regresión Random Forest sobre históricos)
3. ¿Qué riesgos enfrenta y cómo mitigarlos? (diagnóstico simbólico)

Combina una capa estadística en Python (pandas + scikit-learn) con una
capa simbólica en SWI-Prolog. La integración real entre ambas capas es el
núcleo del aporte propio del trabajo (Fase IV).

Cobertura: 11 cultivos extensivos (soja, maíz, trigo, girasol, cebada,
sorgo, avena, centeno, arroz, algodón, maní) sobre las 5 regiones
agrícolas argentinas (pampeana, NOA, NEA, Cuyo, Patagonia).

Trabajo Final Integrador de "Fundamentos de Inteligencia Artificial"
(maestría). Entrega: 22/05/2026.

## Setup

Resumen para Windows. El detalle paso a paso (incluyendo configuración de
pyswip, plan B si la DLL falla y verificación con SWI-Prolog) está en
`CLAUDE.md`, sección "Setup local (Windows nativo)".

```bat
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Requisitos previos:

- Python 3.10+ (recomendado 3.11).
- SWI-Prolog 9.x estable, con su carpeta `bin` en el PATH y la variable
  `SWI_HOME_DIR` apuntando a la instalación.
- Git para Windows.

## Estructura

```
agrosmart/
├── data/
│   ├── raw/                    # respuestas crudas de APIs
│   ├── processed/              # dataset maestro y rangos por cultivo
│   └── cache/                  # cache de respuestas (gitignored)
│       ├── magyp/
│       ├── clima/
│       └── suelo/
├── notebooks/
│   ├── 01_exploracion_apis.ipynb
│   ├── 02_eda_consolidado.ipynb
│   └── 03_modelado.ipynb
├── src/
│   ├── apis/                   # clientes de APIs externas
│   │   ├── magyp.py
│   │   ├── open_meteo.py
│   │   └── soilgrids.py
│   ├── procesamiento/          # consolidación y generación de hechos
│   │   ├── departamentos.py
│   │   ├── consolidacion.py
│   │   └── generar_hechos_prolog.py
│   ├── modelos/                # modelos estadísticos
│   │   └── regresion_rendimiento.py
│   ├── prolog/                 # capa simbólica
│   │   ├── hechos_generados.pl
│   │   ├── hechos_expertos.pl
│   │   ├── reglas_aptitud.pl
│   │   ├── reglas_riesgo.pl
│   │   ├── reglas_recomendacion.pl
│   │   └── agrosmart.pl
│   └── bridge/                 # cascada de decisión Python <-> Prolog
│       └── integrador.py
├── tests/
├── docs/
│   ├── informe.md
│   ├── presentacion.md
│   └── figuras/
├── requirements.txt
├── CLAUDE.md
├── README.md
└── .gitignore
```

## Estado del proyecto

**Fase 0 — Inicialización.** Estructura del repositorio creada,
dependencias declaradas en `requirements.txt`. Todavía no se descargaron
datos ni se escribió código funcional.

Próximos pasos previstos:

- Fase I: exploración de APIs (MAGyP, Open-Meteo, SoilGrids) y diseño del
  esquema del dataset maestro.
- Fase II: clientes de API con cache y reintentos, consolidación del
  dataset, EDA y modelo de regresión.
- Fase III: hechos generados desde el EDA + hechos expertos + reglas de
  aptitud, riesgo y recomendación.
- Fase IV: integrador en cascada con validación cruzada ML <-> reglas.
