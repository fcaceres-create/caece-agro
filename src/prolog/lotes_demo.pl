% =====================================================================
% AgroSmart - Lotes pre-cargados para demos y consultas
% ---------------------------------------------------------------------
% Este archivo materializa los 4 lotes que también aparecen en el
% selector "Cargar ejemplo" del sidebar de la app (app/componentes/
% sidebar.py, dict EJEMPLOS). Permite que las consultas predefinidas y
% la consola libre del tab "🔍 Consola Prolog" puedan referenciarlos
% directamente sin necesidad de instanciar un Lote desde Python primero.
%
% Convenciones (ver reglas_aptitud.pl):
%   - region_lote(LoteId, Region).
%   - valor_lote(LoteId, Variable, Valor).  % una por variable
%
% Si los valores de EJEMPLOS cambian en sidebar.py, hay que actualizar
% acá manualmente. Es la única duplicación tolerada por el sistema:
% el costo de mantenerla es menor que el de generar este archivo desde
% Python para cuatro lotes que casi no cambian.
% =====================================================================

% Agrupamos los hechos por lote (no por predicado) para que la lectura
% sea natural. Le avisamos a SWI-Prolog para que no nos warneé.
:- discontiguous region_lote/2.
:- discontiguous valor_lote/3.

% ---------------------------------------------------------------------
% lote_pergamino — Pergamino típico, condiciones óptimas pampeanas
% ---------------------------------------------------------------------
region_lote(lote_pergamino, pampeana).
valor_lote(lote_pergamino, ph, 6.5).
valor_lote(lote_pergamino, materia_organica_pct, 3.2).
valor_lote(lote_pergamino, arcilla_pct, 26).
valor_lote(lote_pergamino, arena_pct, 12).
valor_lote(lote_pergamino, precipitacion_total_mm, 750).
valor_lote(lote_pergamino, temp_media_c, 22.0).
valor_lote(lote_pergamino, dias_helada, 0).
valor_lote(lote_pergamino, humedad_relativa_promedio, 65.0).
valor_lote(lote_pergamino, radiacion_solar_total, 4000.0).
valor_lote(lote_pergamino, cec, 20.0).

% ---------------------------------------------------------------------
% lote_sequia — Misma base pampeana, lluvia derrumbada (campaña 2022/23)
% ---------------------------------------------------------------------
region_lote(lote_sequia, pampeana).
valor_lote(lote_sequia, ph, 6.5).
valor_lote(lote_sequia, materia_organica_pct, 3.2).
valor_lote(lote_sequia, arcilla_pct, 26).
valor_lote(lote_sequia, arena_pct, 12).
valor_lote(lote_sequia, precipitacion_total_mm, 320).
valor_lote(lote_sequia, temp_media_c, 22.0).
valor_lote(lote_sequia, dias_helada, 0).
valor_lote(lote_sequia, humedad_relativa_promedio, 65.0).
valor_lote(lote_sequia, radiacion_solar_total, 4000.0).
valor_lote(lote_sequia, cec, 20.0).

% ---------------------------------------------------------------------
% lote_nea — NEA arrocero (Corrientes/Entre Ríos)
% ---------------------------------------------------------------------
region_lote(lote_nea, nea).
valor_lote(lote_nea, ph, 6.1).
valor_lote(lote_nea, materia_organica_pct, 2.7).
valor_lote(lote_nea, arcilla_pct, 30).
valor_lote(lote_nea, arena_pct, 20).
valor_lote(lote_nea, precipitacion_total_mm, 850).
valor_lote(lote_nea, temp_media_c, 24.0).
valor_lote(lote_nea, dias_helada, 0).
valor_lote(lote_nea, humedad_relativa_promedio, 65.0).
valor_lote(lote_nea, radiacion_solar_total, 4000.0).
valor_lote(lote_nea, cec, 20.0).

% ---------------------------------------------------------------------
% lote_acido — Pampeana con pH derrumbado (riesgo_acidez se dispara)
% ---------------------------------------------------------------------
region_lote(lote_acido, pampeana).
valor_lote(lote_acido, ph, 4.5).
valor_lote(lote_acido, materia_organica_pct, 3.2).
valor_lote(lote_acido, arcilla_pct, 26).
valor_lote(lote_acido, arena_pct, 12).
valor_lote(lote_acido, precipitacion_total_mm, 750).
valor_lote(lote_acido, temp_media_c, 22.0).
valor_lote(lote_acido, dias_helada, 0).
valor_lote(lote_acido, humedad_relativa_promedio, 65.0).
valor_lote(lote_acido, radiacion_solar_total, 4000.0).
valor_lote(lote_acido, cec, 20.0).
