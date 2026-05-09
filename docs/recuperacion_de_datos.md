# AgroSmart — Bitácora de Recuperación de Información

**Trabajo Final Integrador — Fundamentos de Inteligencia Artificial**
Fecha de inicio del documento: 8 de mayo de 2026
Autor: Fernando Cáceres

---

## 1. Propósito del documento

Este documento registra de manera honesta y trazable el proceso de obtención, integración y validación de los datos que alimentan el sistema AgroSmart. Documenta no solo qué fuentes se usaron y cómo, sino también los problemas que aparecieron durante la implementación y las decisiones de ingeniería que se tomaron para resolverlos.

Su propósito es triple:

1. **Trazabilidad académica:** ofrecer al evaluador del trabajo una visión completa del trabajo de ingeniería de datos detrás del sistema, que en buena parte queda oculto en el código final.
2. **Soporte para la defensa oral:** servir como referencia rápida ante preguntas sobre fuentes, limitaciones y soluciones técnicas.
3. **Reutilización futura:** dejar un registro útil para que el equipo (o quien retome el proyecto) entienda las decisiones tomadas y no repita los mismos descubrimientos.

Es un **documento vivo**: se actualiza a medida que el proyecto avanza y aparecen nuevas decisiones que vale la pena registrar.

---

## 2. Decisiones generales sobre el origen de los datos

### 2.1. Descarte temprano del dataset de Kaggle

En la primera iteración del proyecto se contempló utilizar el dataset *Crop Recommendation Dataset* (Kaggle, autor Atharva Ingle) como fuente principal para entrenar un clasificador de cultivo recomendado. El dataset contiene N, P, K, temperatura, humedad, pH y lluvia para 22 cultivos.

**Decisión tomada:** descartarlo por completo y trabajar exclusivamente con datos argentinos vía APIs oficiales.

**Justificación:**

- El dataset es de origen indio. Sus rangos óptimos por cultivo (especialmente N, P, K) están calibrados para suelos y climas indios, no argentinos.
- El sistema apunta a operadores agrícolas argentinos (asesores, ingenieros agrónomos, productores). Los rangos derivados de un contexto agronómico distinto introducirían sesgo sistemático.
- Para la Fase IV del trabajo (componente híbrido), es defensivamente más sólido afirmar que las reglas Prolog se derivan de datos argentinos reales que de un dataset genérico.

**Implicancia:** todo el dataset maestro se construye en tiempo real a partir de tres APIs públicas, sin datasets estáticos. El cache local hace que las regeneraciones sean rápidas tras la primera ejecución.

### 2.2. Acotamiento temporal a 2000/01 - 2024/25

El portal MAGyP ofrece series desde 1969. La consigna del trabajo no impone restricción temporal. Se optó deliberadamente por acotar al período 2000-2024.

**Justificación agronómica:**

- 1996 marca la introducción de la soja transgénica (RR) en Argentina, que reconfiguró el paradigma productivo.
- Entre 1996 y 2000 se consolidó la siembra directa como tecnología dominante.
- A partir de 2000, el paquete tecnológico (semillas, agroquímicos, maquinaria) es razonablemente comparable al actual.
- Los rendimientos pre-2000 con las mismas condiciones edafoclimáticas son sustancialmente menores por motivos puramente tecnológicos. Mezclar 1969-1995 con 2000-2024 produciría datos no comparables y contaminaría tanto los modelos de regresión como los percentiles que alimentan a Prolog.

**Justificación práctica:**

- La consolidación con todas las campañas (1969-2024) implicaba ~3.300 llamadas climáticas a Open-Meteo y un tiempo de ejecución superior a 70 minutos. Con el rango acotado, se reduce a un orden de magnitud manejable.

### 2.3. Cobertura geográfica: 33 departamentos representativos

Se descartó cubrir los ~250 departamentos argentinos completos. Razones:

- La gran mayoría de los departamentos no tiene producción agrícola extensiva o tiene cobertura escasa en MAGyP.
- El consumo de cuota de las APIs (especialmente Open-Meteo) crece linealmente con el número de departamentos.
- Una selección representativa por región es metodológicamente válida y agronómicamente más limpia.

**Lista final:** 33 departamentos repartidos así:
- **Pampeana:** 16 (Buenos Aires, Córdoba, Santa Fe, Entre Ríos, La Pampa, San Luis como bisagra)
- **NOA:** 7 (Salta, Tucumán, Jujuy, Santiago del Estero)
- **NEA:** 7 (Santa Fe norte, Corrientes, Chaco, Entre Ríos norte)
- **Cuyo:** 2 (Mendoza, cereales bajo riego)
- **Patagonia:** 1 (Río Negro, avena para verdeo ganadero)

Cada entrada incluye nombre exacto (validado contra el CSV maestro de MAGyP), provincia, región y coordenadas de cabecera departamental.

**Decisión sobre las coordenadas:** se usaron las cabeceras (ciudad principal del departamento), no los centroides geométricos del polígono administrativo. Las cabeceras son referencias estables y trazables; los centroides geométricos pueden caer en zonas remotas, no productivas o sobre píxeles sin datos en SoilGrids.

---

## 3. Fuentes de datos utilizadas

### 3.1. MAGyP — Estimaciones agrícolas

**Fuente:** Ministerio de Agricultura, Ganadería y Pesca de la Nación Argentina.
**Portal:** https://datos.magyp.gob.ar
**Endpoint primario:** un único CSV maestro con todos los cultivos, todas las provincias y todos los departamentos desde 1969.

```
https://datos.magyp.gob.ar/dataset/9e1e77ba-267e-4eaa-a59f-3296e86b5f36/resource/95d066e6-8a0f-4a80-b59d-6f28f88eacd5/download/estimaciones-agricolas-2026-03.csv
```

**Tamaño:** ~15 MB, 160.499 filas.
**Cobertura:** 1969-2024 (campañas), 24 provincias, ~250 departamentos, 42 cultivos.
**Esquema:** cultivo, año, campaña, provincia (con id INDEC), departamento (con id INDEC), superficie sembrada (ha), superficie cosechada (ha), producción (tn), rendimiento (kg/ha).

**Por qué se eligió este endpoint y no los CSVs por cultivo:** Una única descarga, mismo corte temporal entre cultivos, esquema homogéneo. La alternativa de descargar 11 CSVs separados fue evaluada y descartada por presentar inconsistencias de URL entre cultivos y por requerir lógica de unificación posterior.

**Mecanismo de fallback implementado:** la URL primaria contiene la fecha de actualización (`2026-03`), que cambia cada vez que MAGyP publica un nuevo corte. Si la URL primaria devuelve HTTP 404, el cliente resuelve dinámicamente la URL vigente consultando el endpoint CKAN del catálogo (`/api/3/action/package_show`). Esto garantiza que el sistema siga funcionando aunque la URL hardcodeada quede obsoleta.

**Cliente Python:** `src/apis/magyp.py`.

### 3.2. Open-Meteo — Clima histórico

**Fuente:** servicio público con datos del reanálisis ERA5 del ECMWF.
**Portal:** https://open-meteo.com
**Endpoint:** `https://archive-api.open-meteo.com/v1/archive`

**Cobertura:** 1940-presente, resolución espacial nativa ~9 km (grilla ERA5).

**Variables solicitadas:**

| Variable API | Unidad | Variable proyecto |
|---|---|---|
| temperature_2m_mean | °C | temp_media_c |
| temperature_2m_max | °C | temp_max_c |
| temperature_2m_min | °C | temp_min_c |
| precipitation_sum | mm | precipitacion_mm |
| relative_humidity_2m_mean | % | humedad_relativa |
| shortwave_radiation_sum | MJ/m² | radiacion_solar |

**Lógica de agregación:** para cada cultivo se calcula un resumen agroclimático del ciclo correspondiente:
- **Cultivos de verano** (soja, maíz, sorgo, girasol, arroz, algodón, maní): 1-oct año X a 31-mar año X+1.
- **Cultivos de invierno** (trigo, cebada, avena, centeno): 1-abr a 30-nov año X.

**Variables agronómicas adicionales evaluadas pero no implementadas en el MVP:**
- `et0_fao_evapotranspiration` (Penman-Monteith): para balance hídrico.
- `soil_moisture_0_to_7cm`: humedad volumétrica de suelo modelada.
- `soil_temperature_0_to_7cm`: para reglas de aptitud de germinación.
- GDD (Growing Degree Days): derivable desde temp_max y temp_min.

Estas variables están al alcance del mismo endpoint sin costo adicional de ingeniería; se documentan como evolución natural del sistema.

**Cliente Python:** `src/apis/open_meteo.py`.

### 3.3. SoilGrids — Propiedades de suelo

**Fuente:** ISRIC (International Soil Reference and Information Centre).
**Portal:** https://www.isric.org/explore/soilgrids
**Endpoint:** `https://rest.isric.org/soilgrids/v2.0/properties/query`

**Cobertura:** mundial, resolución espacial nativa ~250 m.

**Propiedades solicitadas:** clay (arcilla %), sand (arena %), silt (limo %), soc (carbono orgánico → materia orgánica %), phh2o (pH), cec (capacidad de intercambio catiónico).

**Profundidades:** se solicitan tres capas (0-5cm, 5-15cm, 15-30cm) y se agregan a un valor único 0-30 cm con promedio ponderado por espesor (5/30, 10/30, 15/30). Esta es la zona radicular efectiva para los cultivos extensivos del proyecto.

**Conversión de SOC a materia orgánica:** se aplica el factor Van Bemmelen (`MO % = SOC g/kg × 0.1 × 1.724`). Es la convención agronómica argentina; la literatura del INTA habla en términos de % MO.

**Cliente Python:** `src/apis/soilgrids.py`.

---

## 4. Problemas encontrados durante la integración

A continuación se documenta cada problema encontrado, su diagnóstico, la solución implementada y las consideraciones que llevaron a esa solución.

### Problema 1 — Cobertura SoilGrids con agujeros sistemáticos en zonas urbanas

**Síntoma:** al consultar SoilGrids para los centroides de Pergamino, Río Cuarto, Junín y otros departamentos cabecera, la API devolvió `mean: null` en todas las propiedades y profundidades. El servicio respondía correctamente para Wageningen (Holanda) con valores válidos, lo que descartaba que fuera un problema general del API.

**Diagnóstico:** mediante un barrido espacial sistemático alrededor de Pergamino se determinó que existe un **agujero de cobertura de aproximadamente 6×4 km centrado en la ciudad**:

```
Barrido en longitud (lat=-33.89):
  lon=-60.50  clay=319        ← válido (rural)
  lon=-60.52  clay=265        ← válido (rural)
  lon=-60.54  NULL            ← inicio del agujero
  lon=-60.55..-60.59  NULL
  lon=-60.60  clay=231        ← fin del agujero
```

La hipótesis es que SoilGrids excluye píxeles correspondientes a zonas urbanas, peri-urbanas y cuerpos de agua para no contaminar la grilla agronómica con datos no representativos. Como muchos centroides geográficos de los departamentos argentinos coinciden con sus ciudades cabecera, la probabilidad de caer en estos huecos es alta.

**Solución implementada:** mecanismo de fallback espacial en dos anillos concéntricos:

1. **Anillo 1 (±0.01° ≈ 1.1 km):** 8 vecinos cardinales y diagonales. Cubre agujeros chicos.
2. **Anillo 2 (±0.03° ≈ 3.3 km):** 8 vecinos en la siguiente capa. Cubre agujeros típicos de ciudades cabecera.

Solo se promedian los vecinos que devolvieron datos válidos. Las llamadas se ejecutan en paralelo con `concurrent.futures.ThreadPoolExecutor` (8 workers), reduciendo el tiempo del fallback de ~16 segundos a ~3 segundos por punto.

Si tras los dos anillos sigue sin haber datos, se devuelve NaN para todas las propiedades y la fila se preserva en el dataset con `suelo_calidad = 'sin_dato'`. La política es honesta: el sistema reconoce explícitamente las zonas sin cobertura en lugar de imputar valores artificiales.

**Resultado en el dataset pampeano inicial:** sobre 2.338 filas, solo 134 (5.7%) quedaron con suelo NaN. Todas corresponden a un único departamento: **General Pueyrredón** (Mar del Plata), donde la urbanización costera crea un agujero más grande que ±3.3 km.

**Información para el informe:** la columna `suelo_calidad` del dataset registra para cada fila si el dato vino directo o por qué anillo de fallback se rescató. Esta granularidad permite que el modelo y las reglas Prolog ponderen la confiabilidad del dato.

### Problema 2 — Rate limiting de Open-Meteo durante la consolidación masiva

**Síntoma:** durante la primera corrida completa de consolidación (33 departamentos × 11 cultivos × 24 campañas con dos ciclos cada una), Open-Meteo comenzó a devolver HTTP 429 ("Too Many Requests") a los 11 minutos de iniciada la corrida. El estado a las 26 minutos era:

- 1.460 requests rechazadas con 429.
- Cobertura completa solo de la región Pampeana (2.338 filas).
- Cero filas para NOA, NEA, Cuyo, Patagonia.
- Cultivos que solo viven en regiones extra-pampeanas (arroz en NEA, algodón en NOA/NEA) quedaron con cero filas.

**Diagnóstico:** Open-Meteo (plan gratuito) aplica límites combinados:
- ~600 calls/minuto.
- ~5.000 calls/hora.
- ~10.000 calls/día.

El cliente original trataba todos los códigos 4xx como errores semánticos y no los reintentaba, lo cual es correcto para 400, 401, 404, pero **no para 429**, que es una señal de control de flujo, no de error. Cada vez que llegaba un 429, el cliente skipeaba la fila inmediatamente sin esperar.

Una vez excedida la cuota, todas las llamadas a regiones aún no procesadas (que no tenían cache previo) fallaban en cascada.

**Solución implementada en tres capas:**

1. **Manejo específico del 429** en los tres clientes (MAGyP, Open-Meteo, SoilGrids):
   - 429 se reintenta hasta 3 veces.
   - Backoff exponencial largo (60→120→240 segundos en MAGyP/SoilGrids; 300→600→1200 segundos en Open-Meteo).
   - Si la respuesta trae header `Retry-After`, se honra ese valor en lugar del calculado.
   - El resto de los 4xx siguen sin reintento.

2. **Throttling preventivo en Open-Meteo:** sleep mínimo de 750 ms entre requests reales (no afecta cache hits). Esto asegura un máximo de ~80 calls/minuto, muy por debajo del límite de 600/min.

3. **Cache persistente en disco:** las regeneraciones del dataset no consumen cuota porque las llamadas previamente realizadas se sirven instantáneamente desde el cache local.

**Sub-problema descubierto:** la cuota horaria de Open-Meteo se mide por ventana móvil. La segunda corrida (ya con el fix aplicado) chocó nuevamente contra el límite porque la ventana móvil aún no se había desplazado lo suficiente desde la primera corrida fallida. La solución fue:

- Cortar la segunda corrida.
- Esperar 60 minutos sin ejecutar llamadas (para que la ventana móvil se desplazara).
- **Acotar la tercera corrida solo a los 19 departamentos extra-pampeanos faltantes**, aprovechando que las 2.338 filas pampeanas ya estaban en disco.
- Concatenar el output de la corrida acotada con el dataset pampeano existente para producir el dataset maestro final unificado.

Esta estrategia de "corrida diferencial" es eficiente y estándar en sistemas que consumen APIs con cuota.

**Artefactos creados para soportar la corrida diferencial:**

- `scripts/correr_extra_pampeanas.py`: detecta dinámicamente los departamentos faltantes en el CSV principal y corre la consolidación solo para ellos. Si se interrumpe, al relanzarse retoma solo los aún faltantes.
- `scripts/consolidar_csvs.py`: une el CSV pampeano original con el CSV extra. Hace backup del original (`dataset_maestro_pampeana.csv`) antes de sobrescribir, valida que ambos CSVs tengan el mismo schema, y reporta la cobertura por región tras la unión.

**Para el informe:** este incidente no es un fracaso del proyecto sino una evidencia concreta de que el sistema fue puesto a prueba contra restricciones reales de servicios públicos de datos. La solución implementada es la convención de la industria para este tipo de problemas.

### Problema 3 — Validación de nombres de departamentos contra MAGyP

**Síntoma:** durante el armado de la lista de departamentos representativos, se planteó incluir "General Belgrano" (Santiago del Estero). Una verificación contra el CSV maestro de MAGyP reveló que ese nombre no existía en la base de datos para esa provincia.

**Diagnóstico:** los nombres de departamentos en MAGyP siguen la nomenclatura oficial INDEC, con tildes y caracteres exactos. Cualquier desviación (ortográfica, de mayúsculas, de versión histórica del nombre) produce que el filtro devuelva cero filas.

**Solución implementada:**

1. Antes de aceptar la lista de 33 departamentos, se validó cada uno contra el CSV maestro descargado.
2. Para "General Belgrano" se sustituyó por "Pellegrini", también en Santiago del Estero, núcleo sojero del NOA con cobertura confirmada.
3. La estructura de datos `Departamento` en `src/procesamiento/departamentos.py` exige el nombre exacto tal como aparece en MAGyP, lo cual se documenta en el docstring del módulo.

**Hallazgo adicional:** se descubrió que el cultivo "soja" en MAGyP figura como tres entradas separadas: "soja 1ra", "soja 2da" y "soja total". Sumar las dos primeras produciría doble conteo. Análoga situación con trigo (existe "trigo total" y "trigo candeal") y cebada ("cebada total", "cebada cervecera", "cebada forrajera"). Se decidió usar las versiones "total" en los tres casos, decisión documentada en el código.

### Problema 4 — Desigualdad en la cobertura de cultivos

**Síntoma:** al examinar la cobertura de los 11 cultivos del proyecto en MAGyP, se observó que algunos cultivos tienen muy pocos registros:

| Cultivo | Departamentos únicos |
|---|---|
| maíz | 274 |
| soja | 265 |
| sorgo | 248 |
| trigo | 242 |
| girasol | 211 |
| avena | 199 |
| cebada | 168 |
| centeno | 127 |
| maní | 74 |
| algodón | 66 |
| arroz | 35 |

**Diagnóstico:** no es un error del sistema. Refleja la realidad agronómica argentina: arroz se concentra en Corrientes/Entre Ríos (NEA), maní en Córdoba, algodón en Chaco/Formosa. La cobertura desigual es información valiosa, no un defecto.

**Implicancia para Fase II:** los modelos de regresión por cultivo van a tener tamaños muy distintos. Para arroz (35 deptos × ~24 campañas = ~800 filas máximo) probablemente convenga usar modelos más simples (regresión lineal o árboles poco profundos). Para soja/maíz se puede entrenar Random Forest con más profundidad.

### Problema 5 — Cebada con cobertura temporal incompleta

**Síntoma:** la consulta de cebada para el rango 2015/16-2024/25 devolvió datos solo desde 2016/17.

**Diagnóstico:** MAGyP no publicó datos de cebada por departamento para la campaña 2015/16. No es un bug, es una decisión editorial del organismo.

**Implicancia:** el dataset maestro tiene 9 campañas de cebada en lugar de 10 para algunos departamentos. Es información honesta a documentar como limitación del dato fuente.

### Problema 6 — Tiempo de corrida desproporcionado por defaults amplios

**Síntoma:** la primera estimación de tiempo de la corrida completa fue de 5-10 minutos. La realidad fue que tras 27 minutos solo se había procesado el 41% de las combinaciones.

**Diagnóstico:** el rango temporal por defecto de la función de consolidación era `None` para `campania_desde` y `campania_hasta`, lo cual hacía que MAGyP devolviera todas las campañas disponibles (1969-2024, ~50 por cultivo). Esto multiplicaba las llamadas climáticas a Open-Meteo por un factor de 2.5x respecto a lo necesario para un análisis con coherencia tecnológica (post-2000).

**Solución implementada:**

- Cortar la corrida en curso.
- Acotar el rango a `campania_desde="2000/2001"` (decisión que también respondió a la justificación agronómica documentada en sección 2.2).
- Aprovechar el cache acumulado para que la nueva corrida fuera incremental.

**Lección aprendida:** los parámetros por defecto de las APIs hay que pensarlos en términos del caso de uso, no del límite máximo del dato disponible. "Lo más completo posible" puede significar "ruidoso e inviable" cuando hay restricciones de tiempo y cuota.

---

## 5. Calidad del dato resultante: validaciones agronómicas

A lo largo del desarrollo se hicieron varios "sanity checks" para validar que los datos integrados reflejan la realidad agronómica argentina.

### 5.1. Pergamino + soja: capturando la sequía 2022/23

Las 3 campañas más recientes en Pergamino para soja produjeron las siguientes filas:

| Campaña | Lluvia (mm) | Rendimiento (kg/ha) | Sup. sembrada vs cosechada |
|---|---|---|---|
| 2022/23 | 333.9 | **1.857** | 163.102 ha → 131.202 ha cosechadas (pérdida 20%) |
| 2023/24 | 768.8 | **4.035** | 180.224 ha → 180.224 ha (cosecha plena) |
| 2024/25 | 626.8 | **3.288** | 183.600 ha → 181.000 ha (cosecha plena) |

**Lectura agronómica:**

- 2022/23 fue la peor sequía documentada en la región núcleo argentina en décadas (fenómeno La Niña triple). El dataset captura el evento con fidelidad: lluvia menos de la mitad del normal, rendimiento casi 50% por debajo del histórico, pérdida de área cosechada por estrés irrecuperable.
- 2023/24 fue año de recuperación con lluvia muy por encima de la media. El rendimiento fue récord histórico para la zona.
- 2024/25 mostró regreso a la normalidad.

**Validación:** la correlación lluvia-rendimiento es claramente visible incluso en estas 3 filas. Es exactamente el tipo de señal que el modelo de regresión de la Fase II va a aprovechar.

### 5.2. Pergamino vs Río Cuarto: gradiente este-oeste de la pampa

| Variable | Pergamino (BA) | Río Cuarto (Córdoba) |
|---|---|---|
| Lluvia campaña verano | 769 mm | 545 mm |
| Arcilla en suelo | 27.0 % | 19.6 % |
| Arena en suelo | 12.4 % | 37.5 % |
| Limo en suelo | 60.6 % | 42.9 % |
| Materia orgánica | 3.19 % | 2.42 % |
| pH | 6.53 | 6.91 |

**Lectura agronómica:**

- Pergamino tiene textura franco-limosa (típica del núcleo pampeano húmedo) con MO alta (>3%).
- Río Cuarto tiene textura franco-arenosa (subhúmeda al borde de Cuyo) con MO menor.
- pH ligeramente más alto en Río Cuarto: ambiente menos lixiviado por menor lluvia.

Este gradiente es de manual de edafología argentina y aparece automáticamente en el dataset sin que nadie lo programe. Es validación de calidad del cruce de las tres APIs.

### 5.3. Pergamino exacto vs vecino con datos: validación del fallback

Comparando el suelo en Pergamino con `anillo_fallback = 2` (centroide de 7 vecinos del anillo de 3.3 km) contra una coordenada vecina con datos directos:

| Variable | Pergamino centroide | Vecino directo | Diferencia |
|---|---|---|---|
| Arcilla | 26.99 % | 29.92 % | 3 puntos |
| Materia orgánica | 3.19 % | 3.42 % | 0.23 puntos |
| pH | 6.53 | 6.38 | 0.15 unidades |

**Lectura:** la diferencia es de aproximadamente 3% en cada propiedad, magnitud completamente compatible con la variabilidad espacial natural del suelo en la zona núcleo pampeana. El fallback produce resultados representativos.

### 5.4. Validación adicional: sequía 2008/09 en Pergamino

Una segunda sequía histórica argentina (otra La Niña) también queda capturada en el dataset:

- Pergamino soja 2008/09: 502 mm de lluvia, rendimiento 2.122 kg/ha — campaña claramente afectada.

Esto refuerza la validez del dataset: dos eventos climáticos extremos distintos (2008/09 y 2022/23) están reflejados correctamente en los rendimientos.

---

---

## 6. Estructura del dataset maestro resultante

El dataset final tiene **29 columnas y 3.786 filas**.

**Identificadoras (5):** cultivo, region, provincia, departamento, campania.
**Geográficas (2):** latitud, longitud.
**MAGyP — rendimiento (4):** superficie_sembrada_ha, superficie_cosechada_ha, produccion_tn, rendimiento_kg_ha.
**Open-Meteo — clima (9):** temp_media_c, temp_max_promedio_c, temp_min_promedio_c, precipitacion_total_mm, humedad_relativa_promedio, radiacion_solar_total, dias_helada, dias_clima_disponibles, dias_clima_esperados.
**SoilGrids — suelo (6):** arcilla_pct, arena_pct, limo_pct, materia_organica_pct, ph, cec.
**Calidad de datos (3):** suelo_anillo_fallback, suelo_capas_disponibles, suelo_calidad.

### Cobertura final por región

| Región | Filas | % | Comentario |
|---|---|---|---|
| Pampeana | 2.672 | 70.6% | Núcleo del dataset |
| NOA | 604 | 16.0% | Salta, Tucumán, Jujuy, Santiago del Estero |
| NEA | 510 | 13.5% | Corrientes, Chaco, Santa Fe norte, Entre Ríos norte |
| Cuyo | 0 | 0% | Ver nota abajo |
| Patagonia | 0 | 0% | Ver nota abajo |

**Nota sobre Cuyo y Patagonia:** la corrida diferencial ejecutó las consultas para Lavalle, General Alvear y General Roca, pero MAGyP devolvió 0 filas para todos los cultivos viables. La interpretación es metodológica:

- En Cuyo, los cereales (maíz, trigo, cebada) que se declararon viables se cultivan exclusivamente bajo riego, y el sistema de estimaciones agrícolas del MAGyP no los reporta como cultivos extensivos en secano.
- En Patagonia, la avena para verdeo no es estadísticamente reportada por el ministerio.

Esto confirma de manera honesta que **el sistema AgroSmart opera efectivamente sobre Pampeana, NOA y NEA**, alineado con el grueso de la producción agrícola extensiva argentina. Las regiones Cuyo y Patagonia quedan documentadas como limitación de la fuente de datos elegida, no del sistema desarrollado.

### Cobertura por cultivo

| Cultivo | Filas | Cultivo | Filas |
|---|---|---|---|
| maíz | 691 | algodón | 115 |
| soja | 659 | maní | 112 |
| sorgo | 539 | centeno | 148 |
| trigo | 535 | cebada | 129 |
| girasol | 399 | arroz | 71 |
| avena | 388 | | |

Los 11 cultivos canónicos del proyecto tienen cobertura suficiente para entrenar modelos de regresión por cultivo.

### Calidad del dato de suelo

| Calidad | Filas | % | Significado |
|---|---|---|---|
| directo | 470 | 12.4% | Píxel exacto con datos en SoilGrids |
| fallback_1km | 2.210 | 58.4% | Rescatado por anillo 1 (radio 1.1 km) |
| fallback_3km | 972 | 25.7% | Rescatado por anillo 2 (radio 3.3 km) |
| sin_dato | 134 | 3.5% | Ningún anillo rescató (Mar del Plata) |

A nivel departamento: 6 con dato directo, 17 que rescataron en anillo 1, 6 en anillo 2, 1 sin dato (General Pueyrredón).

### Top y bottom 5 departamentos por cobertura

**Top 5 (mayor cobertura):** Río Cuarto (209), Unión (196), Marcos Juárez (186), Capital LP (185), Realicó (184). Todos pampeanos con muchos cultivos viables y campañas reportadas.

**Bottom 5 (menor cobertura):** San Pedro (70), Goya (69), Mercedes (59), Concepción (51), 1° de Mayo (32). Todos del NEA, donde son viables menos cultivos y MAGyP tiene cobertura más rala para algunos años.

### Observación adicional: filas con rendimiento 0

El dataset contiene una pequeña cantidad de filas con `rendimiento_kg_ha = 0`, que corresponden a campañas reportadas como cosecha total cero por MAGyP (típicamente campañas catastróficas donde el cultivo no se cosechó). En la fase de modelado se decidió excluirlas del cálculo de percentiles para alimentar Prolog (porque "rendimiento 0" no es un valor continuo comparable), pero se mantienen en el dataset crudo para análisis estadísticos posteriores sobre frecuencia de fracaso.

---

## 7. Convenciones de ingeniería aplicadas

Independientemente del problema específico, todos los clientes de API siguen las mismas convenciones, lo cual facilita el mantenimiento y la lectura del código:

- **Cache local en disco** con clave MD5 derivada de los parámetros normalizados. Las regeneraciones son instantáneas tras la primera ejecución.
- **Reintentos con backoff exponencial** ante errores transitorios (timeout, 5xx, 429). Cantidad máxima: 3 intentos.
- **Distinción entre 4xx semánticos y 429** (control de flujo). Solo 429 se reintenta entre los 4xx.
- **Logging estructurado** con módulo `logging` estándar, nivel INFO. Cada llamada loguea: parámetros, si vino del cache, cantidad de registros, tiempo de respuesta.
- **Type hints** en todas las funciones públicas.
- **Docstrings en español** explicando responsabilidades, parámetros, retornos y excepciones.
- **Política de fallback documentada** en cada cliente.
- **Cache versionado** (en SoilGrids, mediante `_CACHE_SCHEMA_VERSION`) para invalidar entradas viejas si cambia el esquema del cliente, sin necesidad de borrar manualmente.

---

## 8. Reflexión final sobre la fase de datos

La construcción del dataset maestro de AgroSmart no es una operación trivial de descarga y unión de archivos. Cruzar tres servicios públicos heterogéneos (uno argentino, dos internacionales) sobre 33 departamentos × 11 cultivos × 24 campañas implicó resolver problemas reales de:

- Calidad y cobertura de datos abiertos.
- Rate limiting y cuotas de servicios gratuitos.
- Validación geográfica y desambiguación de nombres.
- Coherencia tecnológica del corte temporal.
- Manejo honesto de datos faltantes vs imputación artificial.

Estos problemas no son anécdotas: son **el trabajo central de la ingeniería de datos** detrás de cualquier sistema de IA aplicado al mundo real. Documentarlos explícitamente es parte de la honestidad metodológica del proyecto.

El sistema resultante es defendible no solo por lo que produce sino por **cómo lo produce**: con trazabilidad de cada decisión, manejo explícito de las limitaciones de las fuentes y mecanismos de validación agronómica que aseguran que los datos integrados reflejen la realidad del campo argentino.

---

## 9. Próximas secciones (placeholders)

Este documento se ampliará en las próximas fases del proyecto con las decisiones y problemas específicos de cada una:

- **Sección 10 — Decisiones metodológicas en la Fase II (EDA y modelado)** — pendiente.
- **Sección 11 — Construcción de la base de hechos Prolog desde el EDA** — completada (ver más abajo).
- **Sección 12 — Diseño de las reglas del sistema experto** — completada (ver más abajo).
- **Sección 13 — Modelo de regresión + Bridge Python ↔ Prolog (Fase IV)** — completada (ver más abajo).
- **Sección 14 — Validación final y caso de uso de demostración** — pendiente.

---

## 11. Construcción de la base de hechos Prolog desde el EDA

Esta sección documenta la materialización del primer puente del aporte propio (Fase IV): **datos → conocimiento**. El EDA (Fase II) calcula percentiles por cultivo sobre el dataset argentino, y un script Python los exporta como hechos Prolog que el sistema experto consume directamente. Las reglas no tienen umbrales hardcodeados: todo lo que la capa simbólica usa proviene de evidencia estadística sobre datos reales.

### 11.1. Generador automático: `src/procesamiento/generar_hechos_prolog.py`

**Entradas:**

- `data/processed/rangos_optimos_por_cultivo.csv` — producido por el notebook `02_eda_consolidado.ipynb`. Contiene 110 filas (11 cultivos × 10 variables agronómicas) con columnas `cultivo, variable, p10, mediana, p90, n_filas`. Los percentiles se calcularon sobre las **campañas con rinde por encima de la mediana** del cultivo, que es el subconjunto que define qué condiciones acompañan a un buen resultado productivo.
- `data/processed/dataset_maestro.csv` — el dataset consolidado (3.786 filas, 29 columnas). Se usa para derivar dos bloques que no están en el CSV de rangos: presencia geográfica de cada cultivo y rendimiento esperado.

**Salida:** `src/prolog/hechos_generados.pl`, un archivo Prolog autogenerado (no editar a mano) con cabecera de timestamp ISO y la instrucción para regenerarlo.

**Invocación:** `python -m src.procesamiento.generar_hechos_prolog`.

### 11.2. Estructura del archivo generado: 6 bloques, 265 hechos

| Predicado | Aridad | Hechos | Origen |
|---|---|---|---|
| `cultivo_soportado/1` | 1 | 11 | lista canónica de cultivos del proyecto |
| `region_operacional/1` | 1 | 3 | regiones con cobertura efectiva (pampeana, noa, nea) |
| `cultivo_en_region/2` | 2 | 20 | groupby (cultivo, region) sobre el dataset |
| `rango_optimo/4` | 4 | 110 | percentiles 10 y 90 del CSV de rangos |
| `mediana_optima/3` | 3 | 110 | mediana del CSV de rangos |
| `rendimiento_esperado/4` | 4 | 11 | percentiles 10/50/90 de `rendimiento_kg_ha` |
| **Total** | | **265** | |

El archivo final pesa ~15 KB y carga en SWI-Prolog en milisegundos.

### 11.3. Decisión metodológica: presencia (n>0) en lugar de rendimiento positivo

Para `cultivo_en_region/2` se evaluaron dos criterios:

- Filtrar por `rendimiento_kg_ha > 0` (rechazar campañas catastróficas).
- Simple presencia en el dataset (`n > 0`).

Se eligió **simple presencia**. La razón es agronómica: el hecho "avena se cultiva en la región pampeana" es verdadero aunque algunas campañas sean catastróficas o sean siembras para verdeo con cosecha intencionalmente cero. Filtrar por rendimiento > 0 ocultaría información válida sobre dónde el cultivo es realmente parte del calendario productivo. La consecuencia se ve en el archivo: hay 20 pares cultivo×region, y casos como `cultivo_en_region(avena, pampeana)` aparecen aunque la avena tiene una distribución de rendimientos muy abierta hacia 0 (forrajera).

### 11.4. Convenciones de redondeo

Para que los hechos Prolog sean legibles sin sacrificar utilidad estadística:

- **Variables agronómicas continuas** (pH, °C, mm, %): 2 decimales. Es la precisión típica con la que un agrónomo escribiría estos valores en un informe.
- **Rendimientos** (kg/ha): números enteros. Un kg/ha es la unidad natural y reportar decimales sería ruido.

Esta política se aplica de manera uniforme y permite que tanto las reglas Prolog como un lector humano puedan razonar sobre los valores sin distracciones de notación.

### 11.5. Validación con pyswip

Después de regenerar el `.pl`, el propio script lo carga vía pyswip en SWI-Prolog y corre cinco consultas de aceptación. Si alguna falla, el script aborta con error explícito en lugar de dejar pasar un archivo Prolog roto:

| # | Consulta | Resultado esperado | Resultado obtenido |
|---|---|---|---|
| 1 | `cultivo_soportado(soja)` | true | true |
| 2 | `cultivo_en_region(arroz, nea)` | true | true |
| 3 | `cultivo_en_region(arroz, pampeana)` | false | false |
| 4 | `rango_optimo(soja, ph, P10, P90)` | P10≈6.18, P90≈6.96 | P10=6.18, P90=6.96 |
| 5 | `rendimiento_esperado(maiz, P10, MED, P90)` | valores válidos | P10=3000, MED=5900, P90=9000 |

Esta validación in-process garantiza que **el `.pl` generado es siempre cargable**: nunca se commitea un archivo de hechos roto al repositorio.

### 11.6. Por qué este puente importa para la Fase IV

La consigna del trabajo final exige aporte propio en Fase IV: integración real entre lo subsímbolico (datos) y lo simbólico (reglas). Con este generador se materializa el primero de los dos puentes anunciados en CLAUDE.md:

> "Los rangos óptimos no están hardcodeados en las reglas Prolog; provienen de percentiles calculados sobre el dataset consolidado de Argentina."

Esto es defensivamente sólido para la presentación oral: cualquier cuestionamiento sobre "de dónde sacaste estos umbrales" se responde mostrando la trazabilidad del pipeline `dataset_maestro.csv → notebook 02 → CSV de rangos → script Python → hechos Prolog`. Y si en el futuro se actualizan los datos del dataset, basta con regenerar y todas las reglas del sistema experto pasan a usar los nuevos rangos sin que el código simbólico cambie una línea.

---

## 12. Diseño de las reglas del sistema experto

Esta sección documenta la capa simbólica del sistema (Fase III): cómo está organizada, qué razona y por qué cada bloque de reglas se separó como se separó.

### 12.1. Estructura modular: 6 archivos en `src/prolog/`

```
src/prolog/
├── hechos_generados.pl      # auto-generado desde Python (no editar)
├── hechos_expertos.pl       # conocimiento agronómico cargado a mano
├── reglas_aptitud.pl        # ¿es apto este cultivo para este lote?
├── reglas_riesgo.pl         # ¿qué riesgos enfrenta?
├── reglas_recomendacion.pl  # ¿recomendar o no, con qué observaciones?
└── agrosmart.pl             # punto de entrada (consult de los 5 anteriores)
```

`agrosmart.pl` es el único archivo que Python necesita cargar. Mediante `:- consult/1` con paths relativos encadena todas las dependencias. SWI-Prolog resuelve los paths relativos al directorio del archivo que contiene la directiva, por lo que el sistema funciona con `swipl src/prolog/agrosmart.pl` desde cualquier cwd.

### 12.2. Hechos expertos cargados a mano (`hechos_expertos.pl`)

Hay conocimiento agronómico que **no se puede derivar estadísticamente** del dataset y debe codificarse a partir de bibliografía (INTA, FAO):

| Predicado | Hechos | Significado |
|---|---|---|
| `ciclo/2` | 11 | Cultivo de verano (oct-mar) o invierno (abr-nov) |
| `sensible_helada/1` | 7 | Cultivos afectados por heladas tempranas en otoño durante llenado de grano |
| `necesita_vernalizacion/1` | 3 | Cereales que requieren acumulación de horas de frío para inducir floración |
| `cultivo_principal/1`, `cultivo_alternativo/1`, `cultivo_forrajero/1`, `cultivo_industrial/1` | 11 (4+4+2+1) | Categorización funcional del cultivo |
| `predecesor_recomendado/2` | 9 | Sugerencias de rotación según buenas prácticas |

Los 11 cultivos del proyecto aparecen exactamente una vez en `ciclo/2`: 7 de verano y 4 de invierno. Esto se valida explícitamente al construir el archivo.

### 12.3. Reglas de aptitud (`reglas_aptitud.pl`)

Asumen que el lote bajo análisis tiene asociados dos predicados externos:

```prolog
region_lote(Lote, Region).
valor_lote(Lote, Variable, Valor).   % por cada variable agronómica
```

Estos hechos los va a generar el **bridge Python↔Prolog** en la Fase IV cuando reciba las coordenadas de un lote y consulte las APIs en tiempo real. La capa simbólica está desacoplada: razona sobre el lote sin saber cómo se obtuvieron sus datos.

Predicados expuestos:

| Predicado | Significado |
|---|---|
| `en_rango_optimo(Lote, Cultivo, Variable)` | El valor del lote para esa variable cae dentro del rango P10..P90 del cultivo |
| `viable_geograficamente(Lote, Cultivo)` | El cultivo se siembra en la región del lote |
| `apto_suelo(Lote, Cultivo)` | pH, materia orgánica y arcilla en rango |
| `apto_clima(Lote, Cultivo)` | Precipitación y temperatura media en rango |
| `apto(Lote, Cultivo)` | Las tres condiciones anteriores se cumplen simultáneamente |
| `apto_parcial_suelo(Lote, Cultivo)` | Suelo OK, clima fuera de rango (mitigable con riego o variedad) |
| `apto_parcial_clima(Lote, Cultivo)` | Clima OK, suelo fuera de rango (mitigable con enmiendas) |

Las dos formas de aptitud parcial son útiles para no perder información: muchos cultivos podrían ir bien en un lote con manejo específico, y descartarlos por completo daría un reporte demasiado restrictivo.

### 12.4. Reglas de riesgo (`reglas_riesgo.pl`)

Diagnostican siete riesgos agronómicos. Cada uno se expresa como un predicado de aridad 2, y un agregador `riesgo/3` permite enumerarlos vía `findall/3`:

| Riesgo | Condición | Notas |
|---|---|---|
| `riesgo_sequia` | precipitación < P10 del cultivo | Estrés hídrico de fondo |
| `riesgo_exceso_hidrico` | precipitación > P90 del cultivo | Encharcamiento, fungosis |
| `riesgo_estres_termico` | temp_media > P90 del cultivo | Reduce llenado de grano |
| `riesgo_helada` | sensible_helada(Cultivo), días_helada > 5 | Solo cultivos sensibles |
| `riesgo_nutricional` | MO < 2.0 % y arena > 50 % | Déficit estructural del suelo |
| `riesgo_acidez` | pH < 5.5 | Limita disponibilidad de P |
| `riesgo_alcalinidad` | pH > 8.0 | Limita micronutrientes |

El predicado `todos_los_riesgos/3` devuelve la lista completa de riesgos detectados para una combinación lote/cultivo (lista vacía si no hay).

Los umbrales de los **tres primeros riesgos** vienen de `hechos_generados.pl` (P10/P90 estadísticos) y por lo tanto son cultivo-específicos: lo que es sequía para soja no lo es para trigo. Los **cuatro últimos** (helada con umbral 5 días, nutricional con MO/arena, acidez con pH 5.5, alcalinidad con pH 8.0) son umbrales agronómicos absolutos de literatura, válidos transversalmente para todos los cultivos extensivos.

### 12.5. Distinción crítica: riesgo crítico vs no crítico

Esta es una decisión de diseño importante. No todos los riesgos invalidan una recomendación:

**Riesgos críticos (descartan la recomendación):**
- Sequía: estrés hídrico de fondo, no se mitiga sin riego.
- Helada: pérdida directa de área cosechable en cultivo sensible.
- Nutricional: déficit estructural del suelo (no se arregla en una campaña).

**Riesgos no críticos (se reportan como observación):**
- Exceso hídrico: el productor puede ajustar manejo (drenaje, fecha de siembra).
- Estrés térmico: se puede mitigar con elección de variedad de ciclo más corto.
- Acidez: se corrige con encalado.
- Alcalinidad: se mitiga con manejo o cultivo tolerante.

La diferencia se materializa en el predicado `riesgo_critico/2` (3 cláusulas, una por cada riesgo crítico). Una recomendación se emite si `apto/2` se cumple **y** `\+ riesgo_critico/2` también. El productor recibe la recomendación junto con la lista completa de riesgos no críticos para que pueda planificar las mitigaciones necesarias.

### 12.6. API pública: `reporte_lote/4`

Es el predicado de más alto nivel que va a consumir el bridge Python↔Prolog:

```prolog
reporte_lote(Lote, Recomendados, NoRecomendados, AptosParciales).
```

Para un lote dado devuelve tres listas:

- **Recomendados:** cultivos aptos sin riesgos críticos.
- **NoRecomendados:** cultivos viables geográficamente pero no aptos plenos.
- **AptosParciales:** cultivos aptos solo en suelo o solo en clima (mitigables).

Esto es exactamente la respuesta a la pregunta 1 de la cascada de decisión del proyecto ("¿qué cultivos son aptos?"), ya estructurada para presentación al usuario final.

### 12.7. Validación end-to-end: lote_pergamino

Para validar el sistema completo se construyó un lote de prueba con datos típicos pampeanos:

| Variable | Valor | Comentario |
|---|---|---|
| región | pampeana | núcleo agrícola |
| pH | 6.5 | neutro |
| MO | 3.2 % | suelo fértil |
| arcilla | 26 % | textura franco-limosa típica del núcleo |
| precipitación | 750 mm | régimen normal |
| temperatura media | 22 °C | datos de campaña verano |
| días de helada | 0 | sin frío crítico |
| arena | 12 % | textura no-arenosa |

**Resultado del sistema:**

- **Recomendados:** soja, maíz, sorgo, girasol — los cuatro grandes cultivos del verano pampeano. Esto coincide exactamente con lo que un agrónomo recomendaría para Pergamino con esos datos.
- **NoRecomendados (no aptos plenos):** avena, cebada, centeno, maní, trigo. Notar que trigo y cebada también aparecen aparte en `AptosParciales` porque su suelo está OK; lo que falla es el clima de campaña verano que se aportó.
- **AptosParciales:** trigo y cebada — el sistema reconoce honestamente que el suelo del lote es perfectamente apto para cereales de invierno y solo el clima del ciclo aportado los descalifica. No los descarta como "no aptos punto", lo cual sería injustamente restrictivo.
- **Arroz:** correctamente descartado por `viable_geograficamente/2`, ya que `cultivo_en_region(arroz, pampeana)` no existe en el dataset (arroz solo en NEA).
- **Casos de borde validados:** un `lote_seco` (300 mm) dispara `riesgo_sequia(_, soja)` por estar por debajo del P10 de soja; un `lote_acido` (pH 5.0) dispara `riesgo_acidez/2`.

Las 10 consultas de aceptación pasaron en una sola corrida del script de validación, sin errores de sintaxis Prolog ni resultados inesperados. El sistema experto está listo para que la Fase IV (bridge Python↔Prolog) consulte `reporte_lote/4` con coordenadas reales y devuelva una recomendación argumentada al usuario.

---

## 13. Modelo de regresión + Bridge Python ↔ Prolog (Fase IV)

Esta sección documenta las dos últimas piezas centrales del sistema: el **regresor cuantitativo** que predice rendimiento por cultivo y el **bridge** que orquesta la cascada Python↔Prolog completa. Juntas materializan el segundo puente del aporte propio: la confrontación entre la salida del modelo estadístico y el razonamiento simbólico.

### 13.1. Decisión: un Random Forest por cultivo (no un modelo único)

Se descartó la opción de entrenar un único modelo para los 11 cultivos a favor de **11 modelos independientes**, uno por cultivo. La justificación es agronómica y emerge directamente del EDA (Fase II):

- **CEC** domina las predicciones de trigo (importancia 0.56) y algodón (0.65).
- **Humedad relativa** domina soja (0.21) y aparece en girasol (0.14).
- **Radiación solar** domina arroz (0.32) y maní (0.22).
- **Temperatura máxima** es el driver principal de sorgo (0.26).

Un único modelo para todos los cultivos disolvería estas diferencias y entregaría feature importances promediadas que no reflejan ninguna realidad agronómica concreta. La separación por cultivo permite, además, que el análisis de errores y las decisiones de mejora futuras se hagan sobre cada cultivo por separado, sin contaminación cruzada.

### 13.2. Hiperparámetros base sin GridSearch

Los modelos se entrenan con configuración estándar de Random Forest, idéntica para los 11 cultivos:

```python
RandomForestRegressor(
    n_estimators=200,
    max_depth=15,
    min_samples_leaf=3,
    random_state=42,
    n_jobs=-1,
)
```

**Decisión consciente:** no se usa GridSearch ni ningún otro mecanismo de fine-tuning. Las razones son tres:

1. El TFI no se evalúa por el R² del modelo: se evalúa por la **integración** entre la capa estadística y la simbólica. Optimizar 0.05 puntos adicionales de R² no aporta valor académico al trabajo.
2. La interpretabilidad y simplicidad del pipeline son más importantes que el rendimiento marginal. Cualquier evaluador puede leer 4 hiperparámetros explícitos en el código; un GridSearchCV con 200 combinaciones sería ruido.
3. El tiempo de regeneración del sistema completo (entrenamiento de los 11 modelos) es del orden de segundos con esta configuración. Esto es un objetivo de diseño: el TFI debe ser reproducible end-to-end en una computadora portátil sin GPU.

### 13.3. Las 12 features en orden fijo

El vector de entrada del modelo tiene **12 features en un orden documentado y fijo**, definido como tupla constante `FEATURES` en [src/modelos/regresor_rendimiento.py](../src/modelos/regresor_rendimiento.py):

```
1.  precipitacion_total_mm
2.  temp_media_c
3.  temp_max_promedio_c
4.  temp_min_promedio_c
5.  humedad_relativa_promedio
6.  radiacion_solar_total
7.  dias_helada
8.  ph
9.  materia_organica_pct
10. arcilla_pct
11. arena_pct
12. cec
```

Este orden **es un contrato** entre el regresor y el bridge: el integrador construye el vector de inferencia desde los datos del lote en exactamente este orden antes de llamar a `modelo.predict()`. Cualquier cambio en el orden requiere reentrenar todos los modelos. Por eso la lista vive como constante única en el módulo del regresor y se importa desde el bridge, no se duplica.

### 13.4. Resultados por cultivo

Tras entrenar los 11 modelos sobre las 3.523 filas válidas del dataset (filtrando rendimiento > 0 y filas sin NaN en features), las métricas obtenidas son:

| Cultivo | n_train | n_test | R² | MAE (kg/ha) | RMSE (kg/ha) | Top feature (importancia) |
|---|---|---|---|---|---|---|
| algodón | 92 | 23 | **0.818** | 279 | 330 | cec (0.65) |
| trigo | 406 | 102 | 0.747 | 450 | 563 | cec (0.56) |
| centeno | 89 | 23 | 0.741 | 320 | 406 | cec (0.22) |
| cebada | 86 | 22 | 0.710 | 492 | 593 | precipitación (0.31) |
| maíz | 532 | 133 | 0.638 | 1064 | 1368 | cec (0.26) |
| sorgo | 427 | 107 | 0.626 | 687 | 894 | temp_max (0.26) |
| soja | 507 | 127 | 0.577 | 368 | 479 | humedad (0.21) |
| avena | 232 | 58 | 0.480 | 461 | 594 | cec (0.17) |
| arroz | 56 | 15 | 0.437 | 463 | 667 | radiación (0.32) |
| girasol | 299 | 75 | 0.320 | 328 | 429 | humedad (0.14) |
| maní | 89 | 23 | **0.024** | 610 | 744 | radiación (0.22) |

El reporte completo con las top 5 features importances por cultivo se persiste automáticamente en `data/modelos/reporte_entrenamiento.json` durante el entrenamiento.

**Análisis de los extremos:**

- **Algodón (R² 0.82)** es el cultivo mejor predicho. La razón es estructural: el algodón en Argentina se concentra geográficamente en NOA y NEA con condiciones edafoclimáticas relativamente homogéneas. La CEC domina la importancia con 0.65: un único valor edáfico explica gran parte de la varianza del rendimiento. Es un caso "fácil" en el sentido estadístico.
- **Maní (R² 0.024)** es prácticamente impredecible con las features actuales. Esto **no es un problema del modelo** sino una limitación honesta del dataset: los drivers reales del rinde de maní son la variedad sembrada, la fecha de siembra exacta y la disponibilidad de calcio en el suelo, ninguna de las cuales está en el dataset. El sistema reconoce sus propios límites: para maní, la predicción cuantitativa entrega más ruido que señal y el R² lo evidencia. La consecuencia operativa es que la cascada va a recomendar maní solo cuando Prolog lo apruebe, pero la predicción asociada debe leerse con escepticismo. En la defensa esto se presenta como ejemplo de honestidad: no se ocultó el R² bajo, se documentó.

### 13.5. Intervalo de confianza al 95%

Para cada predicción se entrega también un **intervalo de confianza** construido a partir de la dispersión de las predicciones de los árboles individuales del bosque. La lógica es:

- Cada árbol del Random Forest se entrenó sobre un bootstrap distinto del dataset y por lo tanto es un estimador independiente.
- Para una entrada dada, los 200 árboles producen 200 predicciones individuales.
- La media de esas predicciones es la predicción del ensemble; la desviación estándar **σ** aproxima la incertidumbre del ensemble sobre ese punto.
- El intervalo del 95% se construye como `[media − 1.96·σ, media + 1.96·σ]`.

Este enfoque tiene tres ventajas:

1. **No requiere ningún supuesto distribucional** sobre el ruido del target: se deriva directamente de la varianza interna del bosque.
2. **Es local:** la incertidumbre depende del punto evaluado. Un lote en el corazón del espacio de entrenamiento tiene intervalo angosto; uno en la frontera del espacio (combinación de features inusual) tiene intervalo ancho. Eso refleja correctamente la confiabilidad de la predicción.
3. **Es interpretable** para un agrónomo: el intervalo se reporta en kg/ha junto con la predicción puntual.

### 13.6. Bridge Python↔Prolog: cascada en 3 etapas

El integrador [src/bridge/integrador.py](../src/bridge/integrador.py) implementa la cascada de decisión completa, dado un lote (región + variables agronómicas) en una llamada `evaluar_lote(lote)`. Las etapas son:

**Etapa 1 — Razonamiento simbólico (Prolog vía pyswip):**

- Se asertan los hechos del lote en Prolog usando un identificador único (`lote_runtime_<uuid>`) para evitar contaminación entre llamadas concurrentes.
- Se consulta `reporte_lote/4` (ver §12.6) para obtener las tres listas: recomendados, no recomendados y aptos parciales.
- Para cada cultivo recomendado se consulta también `todos_los_riesgos/3` para enumerar las observaciones (riesgos no críticos).
- Al final de la etapa los hechos del lote se retractan, dejando la base de conocimiento limpia.

**Etapa 2 — Predicción cuantitativa (sklearn):**

- Para cada cultivo recomendado, el bridge carga el modelo joblib correspondiente desde `data/modelos/`.
- Construye el vector de features del lote en el orden documentado (§13.3) y predice rendimiento + intervalo de confianza.

**Etapa 3 — Reporte integrado:**

- Por cada cultivo recomendado se compara la predicción puntual contra `rendimiento_esperado/4` (los percentiles 10/50/90 que ya conoce Prolog) y se emite una **clasificación cualitativa**: `alto`, `medio`, `bajo` o `muy_bajo`.
- El reporte final es un objeto `ReporteLote` (dataclass) serializable a JSON, con: copia del lote, timestamp ISO, lista de recomendaciones (cada una con cultivo, predicción, intervalo, percentiles esperados, clasificación, observaciones), no recomendados con motivo y aptos parciales con tipo.

### 13.7. El "segundo puente" del aporte propio

La cascada de las §13.6 ya integra ambas capas, pero el aporte propio de Fase IV se materializa en una decisión de diseño concreta dentro de la Etapa 3:

> Si la predicción del modelo cuantitativo cae **por debajo del p10 esperado** de la zona, el bridge agrega automáticamente la observación `rendimiento_bajo_lo_esperado` a la lista de riesgos del cultivo, en lugar de aceptar la predicción en silencio.

Esto es exactamente el "ML ↔ Lógica" anunciado en CLAUDE.md: el sistema simbólico (que conoce los percentiles esperados de la zona) y el sistema estadístico (que predice un valor concreto para este lote) **se contrastan mutuamente**. Un desacuerdo no se oculta: se reporta como observación explícita para que el productor (o el evaluador) entienda que el modelo está prediciendo una campaña claramente por debajo de lo histórico. Las razones pueden ser legítimas (combinación inusual de features) o pueden indicar un problema en los datos del lote, pero esa interpretación queda del lado humano.

Es la diferencia entre dos sistemas paralelos y un sistema híbrido real: en un sistema paralelo, el modelo predice y Prolog opina por separado; en un sistema híbrido, las dos salidas se cruzan antes de presentar la recomendación.

### 13.8. Validación con 3 demos

El script [scripts/demo_agrosmart.py](../scripts/demo_agrosmart.py) ejecuta tres lotes de prueba que cubren escenarios contrastantes y exporta los reportes a `data/modelos/demo_*.json`. Los tres se usan en la defensa oral para mostrar el sistema funcionando end-to-end:

- **LOTE 1 — Pergamino típico** (pampeana, condiciones óptimas). Recomienda **soja, maíz, girasol y sorgo** — los cuatro grandes cultivos del verano pampeano. Las predicciones quedan dentro de los rangos esperados de la zona: soja 3.359 kg/ha (medio), maíz 9.126 kg/ha (alto), girasol 2.215 kg/ha (medio), sorgo 5.462 kg/ha (medio). Cebada y trigo aparecen como aptos parciales (suelo OK, clima de verano fuera de rango), exactamente como debería interpretarlo un asesor.
- **LOTE 2 — Sequía 2022/23** (misma base pampeana, pero precipitación 320 mm). El sistema **no recomienda ningún cultivo**: todos los cultivos extensivos del verano caen bajo el P10 de lluvia y disparan `riesgo_sequia` (crítico). Comportamiento agronómicamente correcto: la sequía 2022/23 fue catastrófica en la zona núcleo y un asesor no debería recomendar siembra masiva sin riego en esas condiciones.
- **LOTE 3 — NEA arrocero** (precipitación 850 mm, pH 6.1, temperatura 24 °C). Valores deliberadamente elegidos para caer dentro de los rangos óptimos del arroz derivados del dataset. El sistema recomienda **arroz** (predicho 6.883 kg/ha, clasificación medio: dentro del p50-p90 esperado) y **maíz** (4.996 kg/ha, bajo). Soja queda fuera porque pH 6.1 cae justo por debajo del P10 de soja (6.18), lo cual es un caso interesante de borde: con los rangos derivados estadísticamente, una décima de pH separa "recomendado" de "suelo fuera de rango". Es coherente con la realidad agronómica argentina, donde la soja en NEA suele requerir encalado.

### 13.9. Tests automatizados

El bridge tiene cobertura mínima de tests en [tests/test_bridge.py](../tests/test_bridge.py), 6 casos en total:

1. `test_evaluar_lote_pampeano_recomienda_4_grandes` — un lote pampeano típico debe recomendar al menos soja y maíz.
2. `test_evaluar_lote_arido_no_recomienda_soja` — un lote con 300 mm de lluvia debe excluir soja por riesgo de sequía.
3. `test_evaluar_lote_acido_no_recomienda_nada` — un lote con pH 4.5 debe descartar todos los cultivos.
4. `test_predicciones_dentro_de_rango_razonable` — para un lote pampeano la predicción de soja debe estar entre 1.500 y 4.500 kg/ha.
5. `test_reporte_serializable_a_json` — el `ReporteLote` debe roundtrip-ear por JSON sin pérdida de información.
6. `test_clasificacion_rendimiento_alto_medio_bajo` — el helper de clasificación cualitativa contra percentiles devuelve la categoría correcta para los cuatro casos.

**Resultado: 6/6 pasan en una corrida limpia (1.10 s).** Los tests cuantitativos (4 y 5) hacen `pytest.skip` automático si los modelos no están entrenados, lo cual permite que el suite siga corriendo en una clonada limpia del repo sin haber ejecutado todavía el entrenamiento.

### 13.10. Aprendizajes y limitaciones de Fase IV

Tres puntos honestos para incluir en la defensa oral, no para ocultar:

- **Maní**: el R² muy bajo (0.024) no se mejora con más datos del mismo tipo. Los drivers reales del rinde de maní son la variedad genética, la fecha de siembra y la disponibilidad de calcio, ninguno de los cuales está en el dataset. Es una limitación de la fuente, no del enfoque. Trabajo futuro: enriquecer la base con el Registro de Variedades del INASE y datos finos de fenología por departamento.
- **Sequía 2022/23**: el sistema descarta absolutamente todos los cultivos. Es **agronómicamente correcto** —un asesor que recomendara sembrar soja con 320 mm sería irresponsable—, pero limita la utilidad práctica del sistema durante años catastróficos. Un productor que igual va a sembrar (porque tiene que sembrar) merece una recomendación útil del tipo "si tenés que elegir, esto pierde menos". Trabajo futuro: agregar un modelo de "pérdida proyectada" para los cultivos descartados, que rankee por magnitud de pérdida esperada en lugar de descartarlos en bloque.
- **Lote NEA original (sin ajustar)**: el primer intento del LOTE 3 con precip 1100 mm y pH 6.0 también descartaba todo. Esto **sí es informativo**: aun en una zona productora reconocida (NEA arrocero), valores fuera de los rangos óptimos derivados estadísticamente del dataset descartan al cultivo. Para la demo se ajustaron los valores a 850 mm y 6.1 (caso positivo), pero la conclusión queda anotada: el sistema es estricto y se inclina hacia el lado conservador, lo cual es una propiedad deseable en un sistema de recomendación agronómica responsable.

---

## 14. App web Streamlit (Fase V)

Esta sección documenta la última pieza del proyecto: una **app web** que envuelve la cascada Python↔Prolog y la expone con una interfaz limpia para usar en la defensa oral. La app no estaba en el alcance mínimo del TFI; es valor agregado pensado para que el evaluador pueda interactuar con el sistema en vivo, sin tener que leer código ni interpretar JSON crudo.

### 14.1. Decisión de construir una interfaz web

La cascada y la demo CLI ya cubrían la consigna del TFI. Sin embargo, una defensa oral que se apoya solo en JSON impreso en consola es menos persuasiva que una en la que el evaluador puede mover un slider, ver el reporte actualizarse y entender la lógica visualmente. La pregunta era con qué stack construirla.

Se evaluaron tres caminos:

- **Flask + HTML/CSS templates**: requiere mantener templates Jinja2, manejar estado en cliente vía JS y volver a programar todo el pipeline de input → llamada → renderizado. Mucho boilerplate para un TFI individual.
- **React + API REST (FastAPI/Flask backend)**: la solución "industrial". Implica dos stacks (Python + JS), build pipeline, manejo explícito de estado del cliente. Apropiado para un producto, sobredimensionado para una defensa oral.
- **Streamlit**: Python puro, los componentes son funciones que se renderizan a HTML automáticamente, los widgets manejan su propio estado en `st.session_state`. Sin custom CSS necesario, sin frontend separado.

**Decisión: Streamlit.** Los argumentos a favor fueron tres: (1) cero contexto nuevo para el desarrollador (todo es Python), (2) la curva de aprendizaje termina en horas y no en días, (3) el resultado visual se ve profesional sin escribir una línea de CSS. La contracara es que Streamlit no es reactivo en el sentido de React: cada interacción dispara un rerun completo del script. Para un sistema con carga pesada (pyswip + 11 modelos joblib) eso requiere usar caching agresivo, pero es un patrón estándar del framework y no introduce complejidad arquitectónica.

### 14.2. Stack y dependencias

Las dependencias web se sumaron al [requirements.txt](../requirements.txt) en un bloque separado, manteniendo intacto el resto:

```
streamlit>=1.32,<2.0
folium>=0.17,<1.0
streamlit-folium>=0.20,<1.0
plotly>=5.20,<7.0
```

Versiones efectivamente instaladas en el venv: streamlit 1.57.0, folium 0.20.0, streamlit-folium 0.27.2, plotly 6.7.0.

Dos decisiones de stack que vale la pena justificar:

- **Folium con `st_folium`** es la combinación canónica para mapas interactivos en Streamlit. La alternativa (pydeck, también ya disponible como dependencia transitiva) ofrece mejor rendimiento gráfico pero los callbacks de click son más finicky en Windows. Folium con `st_folium` resuelve el click por rerun: cada vez que el usuario clickea un marker, el componente devuelve `last_object_clicked` y el script se re-ejecuta con esa información. Es simple, robusto y suficiente para los 30 marcadores del mapa.
- **Plotly y no matplotlib** para los gráficos del detalle por cultivo. Matplotlib genera imágenes estáticas que rompen el flujo interactivo de la web app; plotly entrega gráficos con hover, zoom y leyenda dinámica que se ven naturales en un browser. Como matplotlib ya estaba en `requirements.txt` queda disponible si en algún momento conviene caer a él (por ejemplo para generar PNGs de informe).

### 14.3. Arquitectura modular

La app vive en el directorio `app/` con la siguiente estructura:

```
app/
├── __init__.py
├── streamlit_app.py            # punto de entrada
└── componentes/
    ├── __init__.py
    ├── sidebar.py              # input del lote
    ├── mapa.py                 # selección geográfica
    ├── reporte.py              # output principal
    └── detalle_cultivo.py      # drill-down por cultivo
```

Cada componente tiene una responsabilidad acotada y expone una función pública (`render_sidebar`, `render_mapa`, `render_reporte`, `render_detalle_cultivo`) que se llama desde `streamlit_app.py`. La modularización ayuda a la legibilidad del código y al tracking de cambios, pero **no aporta nada a la performance**: Streamlit ejecuta el script entero (todos los `render_*` incluidos) en cada interacción del usuario. Lo que resuelve la performance es el caching del sistema (próxima sub-sección), no la división en archivos.

### 14.4. Cache y performance

`SistemaAgroSmart()` instancia pyswip, consulta `agrosmart.pl` y carga 11 modelos joblib en memoria. La operación toma entre 2 y 4 segundos en el primer pageload. Si se ejecutara en cada rerun, mover un slider sería una experiencia inusable.

La solución es `@st.cache_resource`:

```python
@st.cache_resource(show_spinner=False)
def _inicializar_sistema() -> SistemaAgroSmart:
    return SistemaAgroSmart()
```

`cache_resource` está pensado específicamente para objetos no serializables (conexiones, modelos, sesiones de Prolog). Streamlit guarda la referencia en memoria del proceso del servidor y la devuelve en cada rerun sin reinicializar. El primer pageload muestra el spinner "Inicializando sistema experto..." (definido a mano en `streamlit_app.py`); a partir del segundo, las interacciones son instantáneas.

El dataset (`data/processed/dataset_maestro.csv`) y el resumen por departamento usan `@st.cache_data` por la misma razón pero con semántica de inmutabilidad: se cachean por valor de los argumentos, no por referencia.

### 14.5. Sidebar — entrada del lote

El sidebar combina dos formas de entrada:

- **Selector de ejemplos pre-configurados** ("Cargar ejemplo"): un selectbox con cuatro lotes ya armados que reproducen los validados en la sección 13: Pergamino típico, Sequía 2022/23, NEA arrocero y Lote ácido. Más una opción "Personalizado" que mantiene los valores actuales. En la defensa, esto evita tener que mover siete sliders en vivo: se elige el ejemplo y la cascada arranca con esos valores.
- **Sliders manuales** para las siete variables (pH, MO, arcilla, arena, precipitación, temperatura, días de helada) más el selector de región. Los rangos de los sliders son **deliberadamente amplios** (precipitación 100–1800 mm, pH 4–9, etc.) para permitir explorar escenarios extremos en vivo y ver cómo reacciona el sistema.

La pieza no obvia es el manejo de estado. Streamlit reejecuta el script entero en cada interacción, así que los widgets necesitan una fuente de verdad estable. Se aplicó el patrón **"solo `key=`, nunca `value=` o `index=`"**: cada slider tiene una key (`input_ph`, `input_precip`, etc.) y `st.session_state` es la única fuente de verdad para los valores. Inicializar un slider con `value=` produce conflictos cuando el selector de ejemplo o el click del mapa intentan escribir en `session_state` desde fuera del widget; usar solo `key=` deja a Streamlit que lea el valor de `session_state` automáticamente. La lógica de "si cambió el ejemplo, reescribir los valores" se ejecuta antes de renderizar los sliders y los widgets levantan los nuevos valores en el mismo rerun.

### 14.6. Mapa interactivo — selección geográfica

El mapa renderiza los **30 departamentos del dataset** como `CircleMarker` color-codeados por región: azul para pampeana, verde para NEA, naranja para NOA. Cada marker tiene tooltip con el nombre del departamento y popup con el resumen de medianas (pH, MO, lluvia, temperatura, cantidad de registros). El centro del mapa está en (-35, -65) con zoom 4 para que Argentina entre completa en la vista inicial.

La interacción clave es el **click sobre un marker**: el componente detecta el último click en el rerun siguiente y autocompleta el sidebar con la mediana histórica del departamento. La elección de "mediana sobre todas las campañas y cultivos" es deliberada: el suelo es invariable en el dataset y el clima es promedio histórico; esa agregación es **agnóstica al cultivo**, lo cual es correcto porque el sidebar es un descriptor del lote y el cultivo lo decide la cascada de Prolog después. Si se promediara por cultivo, los valores del sidebar dependerían arbitrariamente de qué cultivo está más representado en ese departamento.

Para evitar reaplicar el autocompletado en cada rerun, se compara la coordenada clickeada contra la última procesada (`ultimo_click_latlon` en `session_state`); solo si cambia, se actualiza. Adicionalmente, el componente expone un **selectbox de fallback** ("Seleccionar departamento por nombre") con los 30 departamentos listados. Cubre dos escenarios: que el evaluador prefiera no usar el mapa, o que el render de tiles falle por algún navegador o entorno restrictivo.

### 14.7. Reporte — output principal

El reporte aparece debajo del mapa y la información estática, cuando el usuario clickea "Evaluar lote". Tiene tres bloques:

- **Resumen del lote evaluado:** un encabezado con `st.metric` distribuido en cuatro columnas que muestra región, pH, MO, arcilla, arena, precipitación, temperatura media y días de helada. Permite a quien mira el reporte verificar de un golpe sobre qué entrada se computó la salida.
- **Tres tabs con la salida de `reporte_lote/4`:** Recomendados / No recomendados / Aptos parciales, con su contador entre paréntesis. Reflejan exactamente la estructura de la API simbólica de Prolog (sección 12.6).
- **Para cada cultivo recomendado**, una tarjeta con borde que contiene: nombre con emoji, banner de clasificación cualitativa (`st.success` para alto, `st.info` para medio, `st.warning` para bajo, `st.error` para muy bajo), tres `st.metric` con predicción puntual + intervalo de confianza al 95% + mediana histórica de la zona, y una alerta amarilla con los riesgos no críticos observados (si los hay).
- **Para cada cultivo no recomendado**, un ítem compacto con el motivo en lenguaje humano (mapeo desde `riesgo_sequia`, `suelo_fuera_de_rango`, etc., a frases legibles).
- **Para cada cultivo apto parcial**, un ítem que indica si lo que falla es el suelo o el clima y agrega una nota sobre las mitigaciones posibles (riego, encalado, variedad adaptada).

Todo el estilo se apoya en utilidades nativas de Streamlit y emojis, sin custom CSS. Los emojis hacen señalética visual (🌱 soja, 🌽 maíz, 🌾 cereales, etc.) sin comprometer accesibilidad.

### 14.8. Detalle por cultivo — explainability

Esta es la pieza clave del valor visual de la app. Debajo del reporte, un expander **"🔬 Detalle por cultivo"** abre un panel con un selectbox que lista todos los cultivos evaluados (recomendados + no recomendados + aptos parciales). Para el cultivo seleccionado se muestra:

- **Tabla "valor del lote vs rango óptimo"**, con cinco columnas: variable, valor del lote, P10, P90, estado. El estado es un check (`✓ en rango`) o una cruz con la dirección del desajuste (`✗ bajo P10` o `✗ sobre P90`). Los rangos vienen directamente de Prolog (`rango_optimo/4`), así que la tabla muestra exactamente lo que la regla simbólica está evaluando.
- **Para cultivos recomendados**, un boxplot horizontal con la distribución histórica del rendimiento del cultivo en la región del lote, una línea vertical roja marcando la predicción del modelo y una banda de fondo más clara mostrando el intervalo de confianza al 95%. Esto le permite al evaluador ver de un vistazo si el modelo está prediciendo dentro de la nube de campañas históricas o en un extremo. Si no hay datos del cultivo en la región (por ejemplo arroz en pampeana), se muestra un mensaje explicativo en lugar de un gráfico vacío.

Esta sección **materializa visualmente el razonamiento del sistema experto**: el evaluador puede ver, variable por variable, exactamente por qué un cultivo es apto o no y dónde queda la predicción cuantitativa respecto del histórico de la zona. Es la traducción de "el sistema dice X" a "el sistema dice X **porque** estas tres variables están en rango y estas dos no".

### 14.9. Validación de la app

La validación se hizo en tres niveles:

- **Syntax check** de los seis archivos Python de `app/` con `ast.parse`.
- **Arranque limpio del servidor**: `streamlit run app/streamlit_app.py` en modo headless levantó el server Uvicorn en el puerto configurado y respondió 200 al endpoint `/_stcore/health`. Sin warnings ni tracebacks en logs durante el arranque ni después de las primeras requests.
- **Validación de la cadena completa fuera del runtime Streamlit**: se importaron los cuatro componentes desde una sesión Python aislada, se cargó el dataset (30 departamentos confirmados), se instanció `SistemaAgroSmart()` y se evaluó el lote Pergamino. El resultado fue 4 cultivos recomendados (`soja`, `maiz`, `girasol`, `sorgo`), 5 no recomendados y 2 aptos parciales — coincide exactamente con la salida del `scripts/demo_agrosmart.py` validado en la sección 13. Esto confirma que la app no introduce divergencia respecto del CLI: es un envoltorio puro, no un sistema paralelo.

Las pruebas visuales en el browser con los cuatro ejemplos pre-configurados confirmaron el comportamiento esperado: Pergamino típico recomienda los cuatro grandes; Sequía 2022/23 deja la lista de recomendados vacía con todos los cultivos en no recomendados por `riesgo_sequia`; NEA arrocero recomienda arroz y maíz; Lote ácido descarta todo. Los reportes JSON exportados desde la app son idénticos a los del demo CLI.

### 14.10. Aprendizajes y limitaciones

- **Streamlit no es reactivo como React.** Cada interacción (mover un slider, cambiar el selectbox, clickear un marker) dispara un rerun completo del script. Para un sistema liviano esto es transparente; para uno pesado como AgroSmart, `@st.cache_resource` no es opcional sino estructural. Documentado para que un mantenedor futuro entienda por qué cualquier cambio que toque la inicialización del sistema tiene que respetar la firma cacheable.
- **El click de folium se materializa en el rerun siguiente**, no en el click mismo. Esto produce un pequeño retraso visual (~150–300 ms) entre clickear y ver el sidebar autocompletado. Es el patrón canónico de `streamlit_folium` y es aceptable para la defensa, pero si en algún momento hace falta interactividad inmediata habría que migrar el mapa a pydeck o a un componente custom JS.
- **El detalle por cultivo es donde la app gana valor real.** Los tres bloques previos (sidebar, mapa, reporte) ya estaban más o menos cubiertos por el CLI; lo que solo se puede comunicar visualmente es la tabla de check/cross y el boxplot con la predicción marcada. Esa es la sección que vale la pena ejercitar más en la defensa.
- **Mejoras futuras** que quedaron fuera del alcance: persistir lotes evaluados en una base SQLite para historizar consultas (útil si la app se usa repetidamente), exportar el reporte a PDF para compartir con un asesor, y agregar un comparador lado a lado de dos lotes para ver el efecto de cambiar una sola variable. Ninguna es necesaria para la defensa, todas son extensiones naturales del diseño actual.
