% =====================================================================
% AgroSmart - Reglas de recomendación
% ---------------------------------------------------------------------
% Combinan aptitud (reglas_aptitud.pl) y diagnóstico de riesgos
% (reglas_riesgo.pl) para producir recomendaciones de cultivos para un
% lote dado.
%
% Distinción importante:
%   - Riesgo "crítico": descarta la recomendación (sequía, helada,
%     déficit nutricional estructural).
%   - Riesgo "no crítico": el cultivo se recomienda igual pero el
%     riesgo se reporta como observación.
% =====================================================================

% ---------------------------------------------------------------------
% Riesgo crítico: combinación que descarta la recomendación
% ---------------------------------------------------------------------
% Sequía: estrés hídrico de fondo, no se mitiga sin riego.
% Helada: pérdida directa de área cosechable en cultivo sensible.
% Nutricional: déficit estructural del suelo (no se arregla en una
% campaña con fertilización puntual).
% ---------------------------------------------------------------------
riesgo_critico(Lote, Cultivo) :- riesgo_sequia(Lote, Cultivo).
riesgo_critico(Lote, Cultivo) :- riesgo_helada(Lote, Cultivo).
riesgo_critico(Lote, Cultivo) :- riesgo_nutricional(Lote, Cultivo).

% ---------------------------------------------------------------------
% Recomendar: cultivo apto sin riesgos críticos
% ---------------------------------------------------------------------
%   Caso de prueba:
%     ?- recomendar(lote_pergamino, soja).   % true
%     ?- recomendar(lote_seco, soja).        % false (riesgo de sequía)
% ---------------------------------------------------------------------
recomendar(Lote, Cultivo) :-
    apto(Lote, Cultivo),
    \+ riesgo_critico(Lote, Cultivo).

% ---------------------------------------------------------------------
% Recomendar con observaciones: incluye riesgos no críticos detectados
% ---------------------------------------------------------------------
% Devuelve también la lista completa de riesgos (vacía si no hay).
%   Caso de prueba:
%     ?- recomendar_con_observaciones(lote_pergamino, soja, R).
%        % R = []
% ---------------------------------------------------------------------
recomendar_con_observaciones(Lote, Cultivo, Riesgos) :-
    apto(Lote, Cultivo),
    \+ riesgo_critico(Lote, Cultivo),
    todos_los_riesgos(Lote, Cultivo, Riesgos).

% ---------------------------------------------------------------------
% Reporte completo del lote
% ---------------------------------------------------------------------
% reporte_lote(Lote, Recomendados, NoRecomendados, AptosParciales)
% - Recomendados: aptos sin riesgos críticos.
% - NoRecomendados: viables geográficamente pero NO aptos plenos
%   (alguna variable fuera de rango).
% - AptosParciales: aptos solo en suelo o solo en clima (mitigables).
%   Caso de prueba:
%     ?- reporte_lote(lote_pergamino, R, NR, AP).
% ---------------------------------------------------------------------
reporte_lote(Lote, Recomendados, NoRecomendados, AptosParciales) :-
    findall(C, recomendar(Lote, C), Recomendados),
    findall(C,
            ( cultivo_soportado(C),
              viable_geograficamente(Lote, C),
              \+ apto(Lote, C)
            ),
            NoRecomendados),
    findall(C,
            ( apto_parcial_suelo(Lote, C)
            ; apto_parcial_clima(Lote, C)
            ),
            AptosParciales).
