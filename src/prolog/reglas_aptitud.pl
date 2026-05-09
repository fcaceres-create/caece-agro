% =====================================================================
% AgroSmart - Reglas de aptitud
% ---------------------------------------------------------------------
% Evalúan si un cultivo es apto para un lote dado, combinando los
% rangos óptimos derivados del EDA (hechos_generados.pl) con las
% condiciones agronómicas del lote concreto.
%
% Convenciones:
% - Las reglas asumen que el lote tiene asociados:
%     region_lote(Lote, Region).
%     valor_lote(Lote, Variable, Valor).   % por cada variable
% - Junto a cada regla se deja un caso de prueba como comentario con su
%   resultado esperado (ver tests en _test_sistema_experto.py para los
%   casos validados programáticamente).
% - Las reglas NO tienen umbrales hardcodeados: todos los rangos
%   provienen de hechos_generados.pl.
% =====================================================================

% ---------------------------------------------------------------------
% Predicado auxiliar: una variable del lote está dentro del rango óptimo
% ---------------------------------------------------------------------
% Verdadero si el valor del lote para esa variable cae dentro del
% rango óptimo (P10..P90) del cultivo.
%   Caso de prueba (con lote pampeano típico):
%     ?- en_rango_optimo(lote_pergamino, soja, ph).   % true
%     ?- en_rango_optimo(lote_pergamino, soja, temp_media_c). % true
% ---------------------------------------------------------------------
en_rango_optimo(Lote, Cultivo, Variable) :-
    valor_lote(Lote, Variable, Valor),
    rango_optimo(Cultivo, Variable, Min, Max),
    Valor >= Min,
    Valor =< Max.

% ---------------------------------------------------------------------
% Predicado auxiliar: cultivo viable en la región del lote
% ---------------------------------------------------------------------
% Combina dos hechos generados: que el cultivo esté soportado por el
% sistema y que efectivamente se siembre en la región del lote.
%   Caso de prueba:
%     ?- viable_geograficamente(lote_pergamino, soja).   % true
%     ?- viable_geograficamente(lote_pergamino, arroz).  % false (NEA only)
% ---------------------------------------------------------------------
viable_geograficamente(Lote, Cultivo) :-
    cultivo_soportado(Cultivo),
    region_lote(Lote, Region),
    cultivo_en_region(Cultivo, Region).

% ---------------------------------------------------------------------
% Aptitud edáfica: pH, materia orgánica y textura (arcilla)
% ---------------------------------------------------------------------
% Las tres variables describen las condiciones de suelo que más impactan
% en la disponibilidad de nutrientes y en la retención de agua.
%   Caso de prueba (Pergamino, ph 6.5 / MO 3.2 / arcilla 26):
%     ?- apto_suelo(lote_pergamino, soja).   % true
% ---------------------------------------------------------------------
apto_suelo(Lote, Cultivo) :-
    en_rango_optimo(Lote, Cultivo, ph),
    en_rango_optimo(Lote, Cultivo, materia_organica_pct),
    en_rango_optimo(Lote, Cultivo, arcilla_pct).

% ---------------------------------------------------------------------
% Aptitud climática: precipitación y temperatura media del ciclo
% ---------------------------------------------------------------------
% Resumen agroclimático mínimo del ciclo del cultivo. Los valores del
% lote ya deben venir agregados al ciclo correcto (verano/invierno).
%   Caso de prueba (Pergamino, precip 750 / temp 22):
%     ?- apto_clima(lote_pergamino, soja).   % true
%     ?- apto_clima(lote_pergamino, trigo).  % false (temp=22 fuera de 12.77-16.62)
% ---------------------------------------------------------------------
apto_clima(Lote, Cultivo) :-
    en_rango_optimo(Lote, Cultivo, precipitacion_total_mm),
    en_rango_optimo(Lote, Cultivo, temp_media_c).

% ---------------------------------------------------------------------
% Aptitud completa
% ---------------------------------------------------------------------
% Un cultivo es apto si: (1) es viable geográficamente en la región del
% lote, (2) las condiciones edáficas están en el rango óptimo y (3) las
% condiciones climáticas también lo están.
%   Caso de prueba:
%     ?- apto(lote_pergamino, soja).   % true
%     ?- apto(lote_pergamino, arroz).  % false (no viable en pampeana)
% ---------------------------------------------------------------------
apto(Lote, Cultivo) :-
    viable_geograficamente(Lote, Cultivo),
    apto_suelo(Lote, Cultivo),
    apto_clima(Lote, Cultivo).

% ---------------------------------------------------------------------
% Aptitud parcial: suelo OK, clima fuera de rango
% ---------------------------------------------------------------------
% Útil para reportar cultivos que podrían funcionar con riego o
% selección de variedad pero hoy no califican como aptos plenos.
%   Caso de prueba (trigo en datos de campaña de verano):
%     ?- apto_parcial_suelo(lote_pergamino, trigo).   % true
% ---------------------------------------------------------------------
apto_parcial_suelo(Lote, Cultivo) :-
    viable_geograficamente(Lote, Cultivo),
    apto_suelo(Lote, Cultivo),
    \+ apto_clima(Lote, Cultivo).

% ---------------------------------------------------------------------
% Aptitud parcial: clima OK, suelo fuera de rango
% ---------------------------------------------------------------------
% Caso simétrico: el clima acompaña pero el suelo (ph, MO o textura)
% está fuera del óptimo del cultivo. Se puede mitigar con enmiendas.
%   Caso de prueba (lote ácido con ph=5.0):
%     ?- apto_parcial_clima(lote_acido, soja).   % depende del resto
% ---------------------------------------------------------------------
apto_parcial_clima(Lote, Cultivo) :-
    viable_geograficamente(Lote, Cultivo),
    apto_clima(Lote, Cultivo),
    \+ apto_suelo(Lote, Cultivo).
