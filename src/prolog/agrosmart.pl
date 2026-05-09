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

% ---------------------------------------------------------------------
% Sandboxing para la consola libre del tab "🔍 Consola Prolog" (app)
% ---------------------------------------------------------------------
% library(sandbox) provee safe_goal/1, que decide si una consulta del
% usuario es segura para ejecutar (rechaza halt, assert/retract,
% consult, shell, open, etc.). library(time) provee call_with_time_limit/2.
%
% Como sandbox bloquea por defecto cualquier predicado de usuario, hay
% que declarar explícitamente como "safe_primitive" los predicados de
% nuestro dominio que queremos exponer en la consola libre. Hacerlo en
% un archivo cargado por agrosmart.pl garantiza que estén disponibles
% tanto para los tests como para la app.
% ---------------------------------------------------------------------
:- use_module(library(sandbox)).
:- use_module(library(time)).

:- consult('hechos_generados').
:- consult('hechos_expertos').
:- consult('reglas_aptitud').
:- consult('reglas_riesgo').
:- consult('reglas_recomendacion').
:- consult('lotes_demo').

% ---------------------------------------------------------------------
% Declaración de predicados seguros para library(sandbox)
% ---------------------------------------------------------------------
% Solo los predicados públicos del sistema experto + los hechos del
% lote/cultivo. Los predicados internos (auxiliares en las reglas)
% son alcanzados transitivamente por sandbox a través de meta_predicates;
% no hace falta declararlos uno por uno.
% ---------------------------------------------------------------------
sandbox:safe_primitive(user:cultivo_soportado(_)).
sandbox:safe_primitive(user:cultivo_en_region(_, _)).
sandbox:safe_primitive(user:region_operacional(_)).
sandbox:safe_primitive(user:ciclo(_, _)).
sandbox:safe_primitive(user:sensible_helada(_)).
sandbox:safe_primitive(user:necesita_vernalizacion(_)).
sandbox:safe_primitive(user:cultivo_principal(_)).
sandbox:safe_primitive(user:cultivo_alternativo(_)).
sandbox:safe_primitive(user:cultivo_forrajero(_)).
sandbox:safe_primitive(user:cultivo_industrial(_)).
sandbox:safe_primitive(user:predecesor_recomendado(_, _)).
sandbox:safe_primitive(user:rango_optimo(_, _, _, _)).
sandbox:safe_primitive(user:mediana_optima(_, _, _)).
sandbox:safe_primitive(user:rendimiento_esperado(_, _, _, _)).
sandbox:safe_primitive(user:region_lote(_, _)).
sandbox:safe_primitive(user:valor_lote(_, _, _)).
sandbox:safe_primitive(user:en_rango_optimo(_, _, _)).
sandbox:safe_primitive(user:viable_geograficamente(_, _)).
sandbox:safe_primitive(user:apto(_, _)).
sandbox:safe_primitive(user:apto_suelo(_, _)).
sandbox:safe_primitive(user:apto_clima(_, _)).
sandbox:safe_primitive(user:apto_parcial_suelo(_, _)).
sandbox:safe_primitive(user:apto_parcial_clima(_, _)).
sandbox:safe_primitive(user:riesgo_sequia(_, _)).
sandbox:safe_primitive(user:riesgo_exceso_hidrico(_, _)).
sandbox:safe_primitive(user:riesgo_estres_termico(_, _)).
sandbox:safe_primitive(user:riesgo_helada(_, _)).
sandbox:safe_primitive(user:riesgo_nutricional(_, _)).
sandbox:safe_primitive(user:riesgo_acidez(_, _)).
sandbox:safe_primitive(user:riesgo_alcalinidad(_, _)).
sandbox:safe_primitive(user:riesgo(_, _, _)).
sandbox:safe_primitive(user:todos_los_riesgos(_, _, _)).
sandbox:safe_primitive(user:riesgo_critico(_, _)).
sandbox:safe_primitive(user:recomendar(_, _)).
sandbox:safe_primitive(user:recomendar_con_observaciones(_, _, _)).
sandbox:safe_primitive(user:reporte_lote(_, _, _, _)).

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
