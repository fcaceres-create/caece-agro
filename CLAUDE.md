# Contexto del proyecto

Trabajo Final Integrador de la materia "Fundamentos de Inteligencia
Artificial" de una maestría. Entrega: 22/05/2026. Equipo de 2 personas.
Defensa oral individual.

## Proyecto

"AgroSmart: Sistema Híbrido de Decisión Agronómica para Argentina"

Sistema que, dadas coordenadas geográficas de un lote en cualquier región
productiva argentina, responde en cascada tres preguntas:

1. ¿Qué cultivos son aptos? (evaluación simbólica + reglas)
2. ¿Cuánto se estima producir? (regresión sobre históricos reales)
3. ¿Qué riesgos enfrenta y cómo mitigarlos? (diagnóstico simbólico)

Cobertura: 11 cultivos extensivos (soja, maíz, trigo, girasol, cebada,
sorgo, avena, centeno, arroz, algodón, maní) en las 5 regiones agrícolas
argentinas (pampeana, NOA, NEA, Cuyo, Patagonia).

## Arquitectura híbrida

- **Capa de datos (Python):** consume APIs oficiales argentinas (MAGyP)
  y globales (Open-Meteo, SoilGrids) para construir un dataset maestro
  georreferenciado.
- **Capa estadística (Python):** EDA completo + modelo de regresión
  Random Forest por cultivo para estimar rendimiento.
- **Capa simbólica (SWI-Prolog):** base de hechos generada
  automáticamente desde el EDA + hechos expertos cargados manualmente
  + reglas de aptitud, riesgo y recomendación.
- **Capa de integración:** cascada de decisión que orquesta todas las
  anteriores y produce recomendaciones explicables. Esta capa es el
  núcleo del aporte propio de la Fase IV.

## Aporte propio (Fase IV — requisito excluyente)

El trabajo demuestra dos puentes concretos entre lo subsímbolico y lo
simbólico:

1. **Datos → Conocimiento:** el EDA en Python calcula percentiles por
   cultivo y los exporta automáticamente como hechos Prolog. Las reglas
   no usan umbrales hardcodeados: todos los rangos óptimos provienen de
   evidencia estadística sobre datos argentinos reales.
2. **ML ↔ Lógica:** la predicción de rendimiento (Python) se valida
   contra reglas agronómicas (Prolog). Si hay desacuerdo, el sistema lo
   reporta en lugar de aceptar ciegamente la predicción.

## Fuentes de datos (todas vía API, sin datasets estáticos)

- **MAGyP** — rendimientos históricos por cultivo, provincia y departamento.
  https://datos.magyp.gob.ar/series/api
  https://datosestimaciones.magyp.gob.ar
- **Open-Meteo** — clima histórico por coordenadas, sin API key.
  https://archive-api.open-meteo.com/v1/archive
- **SoilGrids (ISRIC)** — propiedades de suelo por coordenadas.
  https://rest.isric.org/soilgrids/v2.0/
- **NASA POWER** (opcional, fallback de clima) — datos agronómicos.
  https://power.larc.nasa.gov/api/
- **INTA / FAO** — literatura agronómica para validar y enriquecer
  hechos expertos manuales (sensibilidades, mitigaciones, ciclos).

## Estructura del repositorio

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
│   ├── apis/
│   │   ├── __init__.py
│   │   ├── magyp.py
│   │   ├── open_meteo.py
│   │   ├── soilgrids.py
│   │   └── README.md
│   ├── procesamiento/
│   │   ├── __init__.py
│   │   ├── departamento.py         # constantes geográficas
│   │   ├── consolidacion.py    # construye dataset maestro
│   │   └── generador_hechos_prolog.py
│   ├── modelos/
│   │   ├── __init__.py
│   │   └── regresion_rendimiento.py
│   ├── prolog/
│   │   ├── hechos_generados.pl # auto-generado desde Python
│   │   ├── hechos_expertos.pl  # cargados manualmente
│   │   ├── reglas_aptitud.pl
│   │   ├── reglas_riesgo.pl
│   │   ├── reglas_recomendacion.pl
│   │   ├── agrosmart.pl        # archivo principal
│   │   └── ejemplos_consultas.md
│   └── bridge/
│       ├── __init__.py
│       └── integrador.py       # cascada de decisión Python ↔ Prolog
├── tests/
│   └── __init__.py
├── docs/
│   ├── informe.md
│   ├── presentacion.md
│   └── figuras/                # PNG exportados del EDA
├── requirements.txt
├── CLAUDE.md                   # este archivo
├── README.md
└── .gitignore
```

## Restricciones obligatorias de la consigna

- **Fase II:** Python obligatorio (pandas, scikit-learn, matplotlib,
  seaborn).
- **Fase III:** SWI-Prolog obligatorio.
- **Fase IV:** aporte propio que evidencie integración real entre la
  capa estadística y la simbólica. No se acepta que sean dos sistemas
  paralelos.

## Criterios de calidad

- Código limpio, modular, comentado en español.
- Cada decisión técnica justificada en docstring o comentario.
- Visualizaciones exportables a PNG (300 dpi) en docs/figuras/ para la
  presentación.
- Reglas Prolog legibles, comentadas, con ejemplo de consulta al lado.
- Tests mínimos para los módulos críticos: cascada de decisión,
  generación de hechos, clientes de API.
- Sin secretos en el código (las APIs usadas no requieren key, pero si
  en algún momento se suma una, va en .env).

## Convenciones técnicas

- **Logging:** usar el módulo `logging` estándar, nivel INFO por
  defecto. Cada cliente de API loguea: parámetros de consulta, si vino
  del cache, cantidad de registros y tiempo de respuesta.
- **Manejo de errores:** las llamadas a APIs externas siempre tienen
  reintentos (máximo 3, con backoff exponencial: 1s, 2s, 4s) y timeouts
  explícitos (10s).
- **Cache:** todas las respuestas de API se cachean en disco. Clave del
  cache derivada de los parámetros (hash MD5). El cache nunca expira
  automáticamente; si hace falta refrescarlo, se borra la carpeta
  manualmente.
- **Tipos:** usar type hints en todas las funciones públicas.
- **Tests:** pytest. Los tests no deberían depender de internet (mockear
  las APIs).

## Política de fallback

- Si una API responde mal en una llamada puntual durante la construcción
  del dataset maestro, se loguea, se skipea ese registro y se continúa.
  Al final se reporta la cantidad de skipeos.
- Si una API está caída completa al construir el dataset, se aborta con
  mensaje claro indicando cuál falló.
- En tiempo de inferencia (cuando un usuario consulta un lote), si una
  API está caída, se intenta usar el cache. Si no hay cache para esas
  coordenadas, se devuelve un error explicativo al usuario.

## Estilo de trabajo con Claude Code

- Antes de programar, explicame qué vas a hacer y por qué.
- Si una decisión tiene varios caminos válidos, ofreceme las
  alternativas con pros y contras y esperá mi confirmación.
- No introduzcas librerías nuevas sin consultarme. Las permitidas son
  las que están en requirements.txt.
- Cuando termines un bloque, dame un resumen de qué quedó hecho y qué
  sigue.
- Si encontrás un problema en los datos o en mi planteo, decímelo en
  lugar de "arreglarlo" silenciosamente.
- No mezcles tareas: si te pido el cliente del MAGyP, no toques el de
  Open-Meteo aunque veas algo para mejorar. Anotá la sugerencia y
  seguimos después.

## Idioma

Todo en español: comentarios, docstrings, mensajes al usuario, nombres
de variables (cuando sea razonable y no choque con convenciones
técnicas) y reglas Prolog. Los identificadores de librerías y
frameworks se mantienen en inglés.

## Tarea actual

[PEGAR ACÁ LA TAREA PUNTUAL DE LA SESIÓN]

## Setup local (Windows nativo)

### Requisitos

- Python 3.10 o superior (recomendado 3.11).
- SWI-Prolog 9.x (estable).
- Git para Windows.
- VS Code con la extensión de Python y, opcionalmente, una extensión de
  Prolog (VSC-Prolog de Arthur Wang sirve bien).

### Instalación paso a paso

**1. Python**
Descargar desde https://www.python.org/downloads/windows/ e instalar
marcando "Add Python to PATH". Verificar con:
```
python --version
pip --version
```

**2. SWI-Prolog**
Descargar el instalador estable de 64 bits desde
https://www.swi-prolog.org/download/stable e instalar con las opciones
por defecto. Verificar:
```
swipl --version
```
Si swipl no se reconoce en la terminal, agregar manualmente al PATH:
`C:\Program Files\swipl\bin`.

**3. Variables de entorno para pyswip**
pyswip necesita encontrar la DLL de SWI-Prolog. Asegurarse de tener
estas variables de entorno:
- `SWI_HOME_DIR` apuntando a `C:\Program Files\swipl`
- En el PATH: `C:\Program Files\swipl\bin`

**4. Entorno virtual e instalación de dependencias**
Desde la raíz del proyecto:
```
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

**5. Verificación de pyswip (crítica)**
Antes de avanzar con el código, correr este test mínimo:
```python
from pyswip import Prolog
prolog = Prolog()
prolog.assertz("padre(juan, pedro)")
print(list(prolog.query("padre(X, pedro)")))
```
Debería imprimir `[{'X': 'juan'}]`. Si falla con un error de DLL,
revisar las variables de entorno del paso 3.

### Plan B si pyswip no funciona en Windows

Si después de configurar las variables `pyswip` sigue fallando, tenemos
dos alternativas, en orden de preferencia:

1. **Usar SWI-Prolog vía subprocess**: invocar `swipl` como proceso
   externo desde Python, pasarle el archivo .pl y un goal, y parsear la
   salida. Es más lento pero independiente de la DLL.
2. **Mover el desarrollo a WSL2**: instalar WSL2 con Ubuntu, donde
   `pyswip` anda sin problemas. Implica versionar el repo dentro de WSL.

La decisión la tomamos cuando aparezca el problema, no antes. El
integrador en src/bridge/integrador.py debe estar diseñado con una
abstracción que permita cambiar el backend (pyswip o subprocess) sin
afectar al resto del sistema.

### Setup de Git

El repo se versiona desde el primer commit. Convenciones:

- Branch principal: `main`.
- Branches de trabajo: `feature/<descripcion-corta>` (ej:
  `feature/cliente-magyp`).
- Commits en español, en imperativo: "agrega cliente MAGyP", "corrige
  cache de SoilGrids".
- Un commit por cada bloque funcional terminado y probado, no commits
  gigantes con todo mezclado.

Archivos sensibles que NO se versionan (ya cubiertos en .gitignore):
- `.venv/`
- `__pycache__/` y `*.pyc`
- `.ipynb_checkpoints/`
- `data/cache/` (regenerable)
- `data/raw/` y `data/processed/` (los regenera el pipeline; si pesan
  mucho conviene no versionarlos; si son livianos, se puede versionar
  solo `data/processed/dataset_maestro.csv` para tener trazabilidad)
- `*.pkl` (modelos serializados, regenerables)
- `.env` (si en algún momento se suma)

### Comandos útiles del proyecto

Documentar acá los comandos frecuentes a medida que se construyen:
- Activar entorno: `.venv\Scripts\activate`
- Construir dataset maestro: `python -m src.procesamiento.consolidacion`
- Generar hechos Prolog: `python -m src.procesamiento.generador_hechos_prolog`
- Lanzar Jupyter: `jupyter notebook`
- Correr tests: `pytest tests/`
- Consultar el sistema experto: `swipl src/prolog/agrosmart.pl`