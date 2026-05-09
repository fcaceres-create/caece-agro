% =====================================================================
% AgroSmart - Hechos generados automáticamente desde el dataset
% Generado por: src/procesamiento/generar_hechos_prolog.py
% Fuente: data/processed/rangos_optimos_por_cultivo.csv
%         data/processed/dataset_maestro.csv
% Fecha de generación: 2026-05-09T00:21:36Z
% No editar manualmente. Para regenerar:
%   python -m src.procesamiento.generar_hechos_prolog
% =====================================================================

% ---------------------------------------------------------------------
% Cultivos soportados por el sistema (los 11 cultivos canónicos)
% ---------------------------------------------------------------------
cultivo_soportado(soja).
cultivo_soportado(maiz).
cultivo_soportado(trigo).
cultivo_soportado(girasol).
cultivo_soportado(cebada).
cultivo_soportado(sorgo).
cultivo_soportado(avena).
cultivo_soportado(centeno).
cultivo_soportado(arroz).
cultivo_soportado(algodon).
cultivo_soportado(mani).

% ---------------------------------------------------------------------
% Regiones operacionales del sistema
% (Cuyo y Patagonia quedaron sin cobertura efectiva en MAGyP;
%  ver docs/recuperacion_de_datos.md sección 6)
% ---------------------------------------------------------------------
region_operacional(pampeana).
region_operacional(noa).
region_operacional(nea).

% ---------------------------------------------------------------------
% Cultivo se siembra en región
% Criterio: presencia en el dataset (n>0), sin filtrar por
% rendimiento. Una campaña con rinde 0 igual cuenta como siembra.
% ---------------------------------------------------------------------
cultivo_en_region(soja, pampeana).
cultivo_en_region(soja, noa).
cultivo_en_region(soja, nea).
cultivo_en_region(maiz, pampeana).
cultivo_en_region(maiz, noa).
cultivo_en_region(maiz, nea).
cultivo_en_region(trigo, pampeana).
cultivo_en_region(trigo, noa).
cultivo_en_region(girasol, pampeana).
cultivo_en_region(girasol, noa).
cultivo_en_region(cebada, pampeana).
cultivo_en_region(sorgo, pampeana).
cultivo_en_region(sorgo, noa).
cultivo_en_region(sorgo, nea).
cultivo_en_region(avena, pampeana).
cultivo_en_region(centeno, pampeana).
cultivo_en_region(arroz, nea).
cultivo_en_region(algodon, noa).
cultivo_en_region(algodon, nea).
cultivo_en_region(mani, pampeana).

% ---------------------------------------------------------------------
% Rangos óptimos por cultivo y variable
% Formato: rango_optimo(Cultivo, Variable, P10, P90)
% Derivación: percentiles 10 y 90 sobre campañas con rinde > mediana
% (calculados en notebooks/02_eda_consolidado.ipynb)
% ---------------------------------------------------------------------
rango_optimo(soja, ph, 6.18, 6.96).
rango_optimo(soja, temp_media_c, 20.91, 24.67).
rango_optimo(soja, temp_max_promedio_c, 26.06, 29.65).
rango_optimo(soja, temp_min_promedio_c, 15.84, 20.04).
rango_optimo(soja, precipitacion_total_mm, 477.56, 1115.32).
rango_optimo(soja, humedad_relativa_promedio, 60.55, 73.79).
rango_optimo(soja, arcilla_pct, 18.50, 36.07).
rango_optimo(soja, arena_pct, 9.33, 49.97).
rango_optimo(soja, materia_organica_pct, 2.42, 4.44).
rango_optimo(soja, cec, 15.63, 23.63).
rango_optimo(maiz, ph, 5.85, 6.96).
rango_optimo(maiz, temp_media_c, 20.65, 24.67).
rango_optimo(maiz, temp_max_promedio_c, 25.74, 29.86).
rango_optimo(maiz, temp_min_promedio_c, 15.50, 20.08).
rango_optimo(maiz, precipitacion_total_mm, 442.00, 971.90).
rango_optimo(maiz, humedad_relativa_promedio, 60.20, 71.64).
rango_optimo(maiz, arcilla_pct, 18.50, 36.07).
rango_optimo(maiz, arena_pct, 9.33, 54.60).
rango_optimo(maiz, materia_organica_pct, 2.42, 4.94).
rango_optimo(maiz, cec, 16.15, 24.42).
rango_optimo(trigo, ph, 6.35, 6.96).
rango_optimo(trigo, temp_media_c, 12.77, 16.62).
rango_optimo(trigo, temp_max_promedio_c, 17.71, 21.66).
rango_optimo(trigo, temp_min_promedio_c, 8.21, 12.24).
rango_optimo(trigo, precipitacion_total_mm, 329.92, 727.82).
rango_optimo(trigo, humedad_relativa_promedio, 65.19, 74.33).
rango_optimo(trigo, arcilla_pct, 18.50, 36.07).
rango_optimo(trigo, arena_pct, 9.33, 47.51).
rango_optimo(trigo, materia_organica_pct, 2.45, 4.94).
rango_optimo(trigo, cec, 18.55, 25.09).
rango_optimo(girasol, ph, 6.35, 6.96).
rango_optimo(girasol, temp_media_c, 20.55, 23.71).
rango_optimo(girasol, temp_max_promedio_c, 25.75, 28.91).
rango_optimo(girasol, temp_min_promedio_c, 15.36, 18.57).
rango_optimo(girasol, precipitacion_total_mm, 381.80, 848.75).
rango_optimo(girasol, humedad_relativa_promedio, 58.23, 69.81).
rango_optimo(girasol, arcilla_pct, 18.50, 36.07).
rango_optimo(girasol, arena_pct, 9.33, 47.51).
rango_optimo(girasol, materia_organica_pct, 2.42, 4.69).
rango_optimo(girasol, cec, 17.45, 24.42).
rango_optimo(cebada, ph, 5.85, 6.94).
rango_optimo(cebada, temp_media_c, 12.04, 16.00).
rango_optimo(cebada, temp_max_promedio_c, 16.97, 21.02).
rango_optimo(cebada, temp_min_promedio_c, 7.84, 11.48).
rango_optimo(cebada, precipitacion_total_mm, 367.41, 659.80).
rango_optimo(cebada, humedad_relativa_promedio, 67.59, 74.45).
rango_optimo(cebada, arcilla_pct, 18.50, 40.73).
rango_optimo(cebada, arena_pct, 11.85, 47.51).
rango_optimo(cebada, materia_organica_pct, 2.59, 5.53).
rango_optimo(cebada, cec, 21.08, 25.09).
rango_optimo(sorgo, ph, 5.85, 7.01).
rango_optimo(sorgo, temp_media_c, 20.91, 23.43).
rango_optimo(sorgo, temp_max_promedio_c, 26.06, 28.57).
rango_optimo(sorgo, temp_min_promedio_c, 15.84, 18.79).
rango_optimo(sorgo, precipitacion_total_mm, 448.92, 928.22).
rango_optimo(sorgo, humedad_relativa_promedio, 60.39, 71.03).
rango_optimo(sorgo, arcilla_pct, 18.50, 36.07).
rango_optimo(sorgo, arena_pct, 9.33, 54.60).
rango_optimo(sorgo, materia_organica_pct, 2.42, 4.45).
rango_optimo(sorgo, cec, 17.45, 23.63).
rango_optimo(avena, ph, 6.53, 7.22).
rango_optimo(avena, temp_media_c, 12.06, 15.69).
rango_optimo(avena, temp_max_promedio_c, 17.15, 20.93).
rango_optimo(avena, temp_min_promedio_c, 7.72, 11.06).
rango_optimo(avena, precipitacion_total_mm, 337.82, 659.86).
rango_optimo(avena, humedad_relativa_promedio, 64.73, 73.26).
rango_optimo(avena, arcilla_pct, 18.50, 31.23).
rango_optimo(avena, arena_pct, 9.33, 47.51).
rango_optimo(avena, materia_organica_pct, 2.45, 4.94).
rango_optimo(avena, cec, 20.94, 25.09).
rango_optimo(centeno, ph, 6.70, 7.22).
rango_optimo(centeno, temp_media_c, 13.28, 15.78).
rango_optimo(centeno, temp_max_promedio_c, 18.59, 21.19).
rango_optimo(centeno, temp_min_promedio_c, 8.37, 10.99).
rango_optimo(centeno, precipitacion_total_mm, 291.24, 553.74).
rango_optimo(centeno, humedad_relativa_promedio, 62.45, 70.57).
rango_optimo(centeno, arcilla_pct, 15.34, 31.23).
rango_optimo(centeno, arena_pct, 9.33, 54.60).
rango_optimo(centeno, materia_organica_pct, 2.11, 3.19).
rango_optimo(centeno, cec, 18.47, 22.68).
rango_optimo(arroz, ph, 5.77, 6.18).
rango_optimo(arroz, temp_media_c, 22.83, 25.05).
rango_optimo(arroz, temp_max_promedio_c, 27.57, 30.35).
rango_optimo(arroz, temp_min_promedio_c, 18.12, 20.05).
rango_optimo(arroz, precipitacion_total_mm, 402.32, 938.72).
rango_optimo(arroz, humedad_relativa_promedio, 60.15, 71.69).
rango_optimo(arroz, arcilla_pct, 13.58, 30.43).
rango_optimo(arroz, arena_pct, 30.03, 58.86).
rango_optimo(arroz, materia_organica_pct, 2.69, 4.44).
rango_optimo(arroz, cec, 22.24, 23.63).
rango_optimo(algodon, ph, 6.18, 6.65).
rango_optimo(algodon, temp_media_c, 22.50, 26.18).
rango_optimo(algodon, temp_max_promedio_c, 27.23, 32.47).
rango_optimo(algodon, temp_min_promedio_c, 17.88, 20.93).
rango_optimo(algodon, precipitacion_total_mm, 520.26, 1146.34).
rango_optimo(algodon, humedad_relativa_promedio, 59.36, 76.43).
rango_optimo(algodon, arcilla_pct, 23.45, 36.59).
rango_optimo(algodon, arena_pct, 16.48, 37.27).
rango_optimo(algodon, materia_organica_pct, 2.35, 3.39).
rango_optimo(algodon, cec, 16.17, 25.88).
rango_optimo(mani, ph, 6.78, 7.60).
rango_optimo(mani, temp_media_c, 21.07, 22.70).
rango_optimo(mani, temp_max_promedio_c, 26.34, 28.19).
rango_optimo(mani, temp_min_promedio_c, 15.84, 17.50).
rango_optimo(mani, precipitacion_total_mm, 420.66, 720.02).
rango_optimo(mani, humedad_relativa_promedio, 57.99, 67.77).
rango_optimo(mani, arcilla_pct, 14.40, 31.23).
rango_optimo(mani, arena_pct, 9.33, 61.02).
rango_optimo(mani, materia_organica_pct, 1.51, 2.67).
rango_optimo(mani, cec, 17.45, 21.72).

% ---------------------------------------------------------------------
% Mediana óptima por cultivo y variable
% Formato: mediana_optima(Cultivo, Variable, Mediana)
% Útil para reglas de 'condición ideal' (centro del rango).
% ---------------------------------------------------------------------
mediana_optima(soja, ph, 6.72).
mediana_optima(soja, temp_media_c, 22.48).
mediana_optima(soja, temp_max_promedio_c, 27.57).
mediana_optima(soja, temp_min_promedio_c, 17.62).
mediana_optima(soja, precipitacion_total_mm, 714.10).
mediana_optima(soja, humedad_relativa_promedio, 67.08).
mediana_optima(soja, arcilla_pct, 26.47).
mediana_optima(soja, arena_pct, 31.87).
mediana_optima(soja, materia_organica_pct, 2.69).
mediana_optima(soja, cec, 21.72).
mediana_optima(maiz, ph, 6.74).
mediana_optima(maiz, temp_media_c, 22.29).
mediana_optima(maiz, temp_max_promedio_c, 27.41).
mediana_optima(maiz, temp_min_promedio_c, 17.38).
mediana_optima(maiz, precipitacion_total_mm, 680.90).
mediana_optima(maiz, humedad_relativa_promedio, 66.03).
mediana_optima(maiz, arcilla_pct, 26.47).
mediana_optima(maiz, arena_pct, 31.87).
mediana_optima(maiz, materia_organica_pct, 2.83).
mediana_optima(maiz, cec, 21.72).
mediana_optima(trigo, ph, 6.74).
mediana_optima(trigo, temp_media_c, 14.86).
mediana_optima(trigo, temp_max_promedio_c, 20.05).
mediana_optima(trigo, temp_min_promedio_c, 10.25).
mediana_optima(trigo, precipitacion_total_mm, 469.30).
mediana_optima(trigo, humedad_relativa_promedio, 69.77).
mediana_optima(trigo, arcilla_pct, 26.99).
mediana_optima(trigo, arena_pct, 25.78).
mediana_optima(trigo, materia_organica_pct, 3.11).
mediana_optima(trigo, cec, 22.13).
mediana_optima(girasol, ph, 6.78).
mediana_optima(girasol, temp_media_c, 21.83).
mediana_optima(girasol, temp_max_promedio_c, 27.16).
mediana_optima(girasol, temp_min_promedio_c, 16.74).
mediana_optima(girasol, precipitacion_total_mm, 586.25).
mediana_optima(girasol, humedad_relativa_promedio, 64.22).
mediana_optima(girasol, arcilla_pct, 26.47).
mediana_optima(girasol, arena_pct, 25.78).
mediana_optima(girasol, materia_organica_pct, 2.83).
mediana_optima(girasol, cec, 21.72).
mediana_optima(cebada, ph, 6.74).
mediana_optima(cebada, temp_media_c, 14.70).
mediana_optima(cebada, temp_max_promedio_c, 19.66).
mediana_optima(cebada, temp_min_promedio_c, 10.01).
mediana_optima(cebada, precipitacion_total_mm, 474.50).
mediana_optima(cebada, humedad_relativa_promedio, 70.69).
mediana_optima(cebada, arcilla_pct, 26.90).
mediana_optima(cebada, arena_pct, 25.78).
mediana_optima(cebada, materia_organica_pct, 3.19).
mediana_optima(cebada, cec, 22.13).
mediana_optima(sorgo, ph, 6.72).
mediana_optima(sorgo, temp_media_c, 22.25).
mediana_optima(sorgo, temp_max_promedio_c, 27.33).
mediana_optima(sorgo, temp_min_promedio_c, 17.29).
mediana_optima(sorgo, precipitacion_total_mm, 670.90).
mediana_optima(sorgo, humedad_relativa_promedio, 66.05).
mediana_optima(sorgo, arcilla_pct, 26.99).
mediana_optima(sorgo, arena_pct, 25.78).
mediana_optima(sorgo, materia_organica_pct, 2.83).
mediana_optima(sorgo, cec, 21.72).
mediana_optima(avena, ph, 6.78).
mediana_optima(avena, temp_media_c, 14.54).
mediana_optima(avena, temp_max_promedio_c, 19.66).
mediana_optima(avena, temp_min_promedio_c, 9.92).
mediana_optima(avena, precipitacion_total_mm, 436.80).
mediana_optima(avena, humedad_relativa_promedio, 68.95).
mediana_optima(avena, arcilla_pct, 26.90).
mediana_optima(avena, arena_pct, 32.48).
mediana_optima(avena, materia_organica_pct, 3.11).
mediana_optima(avena, cec, 22.13).
mediana_optima(centeno, ph, 6.96).
mediana_optima(centeno, temp_media_c, 14.56).
mediana_optima(centeno, temp_max_promedio_c, 20.21).
mediana_optima(centeno, temp_min_promedio_c, 10.01).
mediana_optima(centeno, precipitacion_total_mm, 423.10).
mediana_optima(centeno, humedad_relativa_promedio, 67.79).
mediana_optima(centeno, arcilla_pct, 20.53).
mediana_optima(centeno, arena_pct, 37.54).
mediana_optima(centeno, materia_organica_pct, 2.45).
mediana_optima(centeno, cec, 20.94).
mediana_optima(arroz, ph, 5.77).
mediana_optima(arroz, temp_media_c, 23.62).
mediana_optima(arroz, temp_max_promedio_c, 28.74).
mediana_optima(arroz, temp_min_promedio_c, 18.68).
mediana_optima(arroz, precipitacion_total_mm, 655.30).
mediana_optima(arroz, humedad_relativa_promedio, 66.09).
mediana_optima(arroz, arcilla_pct, 21.85).
mediana_optima(arroz, arena_pct, 58.04).
mediana_optima(arroz, materia_organica_pct, 4.44).
mediana_optima(arroz, cec, 23.03).
mediana_optima(algodon, ph, 6.65).
mediana_optima(algodon, temp_media_c, 24.03).
mediana_optima(algodon, temp_max_promedio_c, 29.12).
mediana_optima(algodon, temp_min_promedio_c, 19.42).
mediana_optima(algodon, precipitacion_total_mm, 844.60).
mediana_optima(algodon, humedad_relativa_promedio, 70.50).
mediana_optima(algodon, arcilla_pct, 23.45).
mediana_optima(algodon, arena_pct, 37.27).
mediana_optima(algodon, materia_organica_pct, 2.85).
mediana_optima(algodon, cec, 16.17).
mediana_optima(mani, ph, 6.96).
mediana_optima(mani, temp_media_c, 21.88).
mediana_optima(mani, temp_max_promedio_c, 27.25).
mediana_optima(mani, temp_min_promedio_c, 16.70).
mediana_optima(mani, precipitacion_total_mm, 570.30).
mediana_optima(mani, humedad_relativa_promedio, 63.80).
mediana_optima(mani, arcilla_pct, 19.56).
mediana_optima(mani, arena_pct, 37.54).
mediana_optima(mani, materia_organica_pct, 2.42).
mediana_optima(mani, cec, 18.55).

% ---------------------------------------------------------------------
% Rendimiento esperado por cultivo (kg/ha)
% Formato: rendimiento_esperado(Cultivo, P10, Mediana, P90)
% Derivación: percentiles del dataset COMPLETO (no solo campañas
% exitosas). Útil para diagnosticar si un cultivo está rindiendo
% por debajo de lo esperado para esa zona.
% ---------------------------------------------------------------------
rendimiento_esperado(soja, 1421, 2500, 3500).
rendimiento_esperado(maiz, 3000, 5900, 9000).
rendimiento_esperado(trigo, 1000, 2433, 4300).
rendimiento_esperado(girasol, 1453, 2143, 2800).
rendimiento_esperado(cebada, 1240, 3200, 4720).
rendimiento_esperado(sorgo, 2435, 4500, 6400).
rendimiento_esperado(avena, 0, 1800, 3300).
rendimiento_esperado(centeno, 0, 1300, 2630).
rendimiento_esperado(arroz, 5299, 6632, 7560).
rendimiento_esperado(algodon, 868, 1414, 2960).
rendimiento_esperado(mani, 2000, 3000, 3800).
