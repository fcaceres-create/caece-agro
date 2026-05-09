% =====================================================================
% AgroSmart - Reglas de riesgo
% ---------------------------------------------------------------------
% Diagnostican riesgos agronómicos específicos para un cultivo en un
% lote dado: estrés hídrico (sequía o exceso), térmico, helada,
% nutricional y de pH (acidez/alcalinidad).
%
% Cada riesgo se expresa con dos formas:
%   - Predicado específico: riesgo_sequia(Lote, Cultivo), etc.
%   - Predicado agregador:  riesgo(Lote, Cultivo, TipoDeRiesgo).
%
% El agregador permite enumerar todos los riesgos vía findall/3.
% =====================================================================

% ---------------------------------------------------------------------
% Riesgo de sequía: lluvia del lote por debajo del p10 del cultivo
% ---------------------------------------------------------------------
% Si la precipitación total del ciclo es menor que el percentil 10 del
% cultivo, hay alta probabilidad de que el rendimiento sea bajo por
% déficit hídrico.
%   Caso de prueba (lote_seco con precip 300, soja P10=477.56):
%     ?- riesgo_sequia(lote_seco, soja).   % true
% ---------------------------------------------------------------------
riesgo_sequia(Lote, Cultivo) :-
    valor_lote(Lote, precipitacion_total_mm, Lluvia),
    rango_optimo(Cultivo, precipitacion_total_mm, P10, _),
    Lluvia < P10.

% ---------------------------------------------------------------------
% Riesgo de exceso hídrico: lluvia por encima del p90 del cultivo
% ---------------------------------------------------------------------
% Demasiada lluvia favorece encharcamiento, anoxia radical y aumento de
% presión de enfermedades fúngicas.
%   Caso de prueba (lote húmedo con precip 1200, soja P90=1115.32):
%     ?- riesgo_exceso_hidrico(lote_humedo, soja).   % true
% ---------------------------------------------------------------------
riesgo_exceso_hidrico(Lote, Cultivo) :-
    valor_lote(Lote, precipitacion_total_mm, Lluvia),
    rango_optimo(Cultivo, precipitacion_total_mm, _, P90),
    Lluvia > P90.

% ---------------------------------------------------------------------
% Riesgo de estrés térmico: temperatura media por encima del p90
% ---------------------------------------------------------------------
% Temperaturas medias por encima del óptimo aceleran ciclo y reducen
% llenado de grano, especialmente en cultivos de invierno.
%   Caso de prueba (lote_calido con temp 30, soja P90=24.67):
%     ?- riesgo_estres_termico(lote_calido, soja).   % true
% ---------------------------------------------------------------------
riesgo_estres_termico(Lote, Cultivo) :-
    valor_lote(Lote, temp_media_c, Temp),
    rango_optimo(Cultivo, temp_media_c, _, P90),
    Temp > P90.

% ---------------------------------------------------------------------
% Riesgo de helada en cultivo sensible
% ---------------------------------------------------------------------
% Más de 5 días con helada en el ciclo es un umbral conservador para
% cultivos de verano sensibles. Los cultivos de invierno no disparan
% este riesgo (la regla exige sensible_helada/1).
%   Caso de prueba (lote_frio con días_helada=10):
%     ?- riesgo_helada(lote_frio, soja).   % true
%     ?- riesgo_helada(lote_frio, trigo).  % false (trigo no sensible)
% ---------------------------------------------------------------------
riesgo_helada(Lote, Cultivo) :-
    sensible_helada(Cultivo),
    valor_lote(Lote, dias_helada, Heladas),
    Heladas > 5.

% ---------------------------------------------------------------------
% Riesgo nutricional: bajo MO + alto contenido de arena
% ---------------------------------------------------------------------
% Suelos arenosos con baja materia orgánica tienen poca CIC, baja
% retención de agua y son pobres en nutrientes (déficit estructural,
% no estacional). El _Cultivo es ignorado: aplica a cualquiera.
%   Caso de prueba (lote_pobre con MO=1.5 y arena=60):
%     ?- riesgo_nutricional(lote_pobre, soja).   % true
% ---------------------------------------------------------------------
riesgo_nutricional(Lote, _Cultivo) :-
    valor_lote(Lote, materia_organica_pct, MO),
    valor_lote(Lote, arena_pct, Arena),
    MO < 2.0,
    Arena > 50.

% ---------------------------------------------------------------------
% Riesgo de acidez: pH muy bajo
% ---------------------------------------------------------------------
% pH < 5.5 limita disponibilidad de P y bases, y puede generar
% toxicidad por Al en muchos cultivos extensivos.
%   Caso de prueba (lote_acido con ph=5.0):
%     ?- riesgo_acidez(lote_acido, soja).   % true
% ---------------------------------------------------------------------
riesgo_acidez(Lote, _Cultivo) :-
    valor_lote(Lote, ph, PH),
    PH < 5.5.

% ---------------------------------------------------------------------
% Riesgo de alcalinidad: pH muy alto
% ---------------------------------------------------------------------
% pH > 8.0 reduce disponibilidad de micronutrientes (Fe, Zn, Mn) y
% puede asociarse a salinidad/sodicidad en suelos áridos.
%   Caso de prueba (lote_alcalino con ph=8.5):
%     ?- riesgo_alcalinidad(lote_alcalino, soja).   % true
% ---------------------------------------------------------------------
riesgo_alcalinidad(Lote, _Cultivo) :-
    valor_lote(Lote, ph, PH),
    PH > 8.0.

% ---------------------------------------------------------------------
% Predicado agregador: riesgo/3 enumera todos los riesgos posibles
% ---------------------------------------------------------------------
% Cada cláusula representa un tipo de riesgo. Usar con findall/3 para
% obtener la lista completa de riesgos de un cultivo en un lote.
% ---------------------------------------------------------------------
riesgo(Lote, Cultivo, sequia)         :- riesgo_sequia(Lote, Cultivo).
riesgo(Lote, Cultivo, exceso_hidrico) :- riesgo_exceso_hidrico(Lote, Cultivo).
riesgo(Lote, Cultivo, estres_termico) :- riesgo_estres_termico(Lote, Cultivo).
riesgo(Lote, Cultivo, helada)         :- riesgo_helada(Lote, Cultivo).
riesgo(Lote, Cultivo, nutricional)    :- riesgo_nutricional(Lote, Cultivo).
riesgo(Lote, Cultivo, acidez)         :- riesgo_acidez(Lote, Cultivo).
riesgo(Lote, Cultivo, alcalinidad)    :- riesgo_alcalinidad(Lote, Cultivo).

% ---------------------------------------------------------------------
% Listado completo de riesgos de un cultivo en un lote
% ---------------------------------------------------------------------
%   Caso de prueba:
%     ?- todos_los_riesgos(lote_pergamino, soja, R).   % R = []
%     ?- todos_los_riesgos(lote_seco, soja, R).        % R = [sequia]
% ---------------------------------------------------------------------
todos_los_riesgos(Lote, Cultivo, Riesgos) :-
    findall(R, riesgo(Lote, Cultivo, R), Riesgos).
