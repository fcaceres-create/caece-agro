% =====================================================================
% AgroSmart - Punto de entrada del sistema experto
% ---------------------------------------------------------------------
% Este archivo carga toda la base de conocimiento (hechos generados
% automáticamente desde el EDA + hechos expertos cargados a mano) y los
% tres módulos de reglas: aptitud, riesgo y recomendación.
%
% Es el único archivo que Python necesita consultar; el resto se carga
% en cascada vía las directivas :- consult/1 de abajo.
%
% Modos de uso:
%   - Consulta interactiva: swipl src/prolog/agrosmart.pl
%   - Desde Python: pyswip carga este archivo y queries directas.
%
% Ver ejemplos_consultas.md para casos de uso típicos.
% =====================================================================

:- consult('hechos_generados').
:- consult('hechos_expertos').
:- consult('reglas_aptitud').
:- consult('reglas_riesgo').
:- consult('reglas_recomendacion').

% ---------------------------------------------------------------------
% API pública del sistema experto
% ---------------------------------------------------------------------
% Los predicados están definidos en los archivos cargados arriba; se
% listan acá como contrato del sistema para consulta desde Python o
% desde la línea de comandos de SWI-Prolog.
%
% Información sobre cultivos:
%   cultivo_soportado(Cultivo).
%   ciclo(Cultivo, Ciclo).                          % verano | invierno
%   sensible_helada(Cultivo).
%   necesita_vernalizacion(Cultivo).
%   cultivo_principal(Cultivo) | cultivo_alternativo | cultivo_forrajero | cultivo_industrial
%   cultivo_en_region(Cultivo, Region).             % pampeana | noa | nea
%   predecesor_recomendado(Cultivo, Predecesor).
%
% Datos del rango óptimo y rendimientos esperados:
%   rango_optimo(Cultivo, Variable, P10, P90).
%   mediana_optima(Cultivo, Variable, Mediana).
%   rendimiento_esperado(Cultivo, P10, Mediana, P90).
%
% Evaluación de un lote (requiere region_lote/2 y valor_lote/3):
%   apto(Lote, Cultivo).
%   apto_suelo(Lote, Cultivo).
%   apto_clima(Lote, Cultivo).
%   apto_parcial_suelo(Lote, Cultivo).
%   apto_parcial_clima(Lote, Cultivo).
%   viable_geograficamente(Lote, Cultivo).
%   en_rango_optimo(Lote, Cultivo, Variable).
%
% Diagnóstico de riesgos:
%   riesgo_sequia(Lote, Cultivo).
%   riesgo_exceso_hidrico(Lote, Cultivo).
%   riesgo_estres_termico(Lote, Cultivo).
%   riesgo_helada(Lote, Cultivo).
%   riesgo_nutricional(Lote, Cultivo).
%   riesgo_acidez(Lote, Cultivo).
%   riesgo_alcalinidad(Lote, Cultivo).
%   riesgo(Lote, Cultivo, Tipo).                    % agregador
%   todos_los_riesgos(Lote, Cultivo, Riesgos).
%
% Recomendaciones:
%   recomendar(Lote, Cultivo).
%   recomendar_con_observaciones(Lote, Cultivo, Riesgos).
%   reporte_lote(Lote, Recomendados, NoRecomendados, AptosParciales).
% ---------------------------------------------------------------------
