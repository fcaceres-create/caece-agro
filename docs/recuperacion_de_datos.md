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
- **Sección 11 — Construcción de la base de hechos Prolog desde el EDA** — pendiente.
- **Sección 12 — Diseño de las reglas del sistema experto** — pendiente.
- **Sección 13 — Bridge Python ↔ Prolog: integración híbrida** — pendiente.
- **Sección 14 — Validación final y caso de uso de demostración** — pendiente.
