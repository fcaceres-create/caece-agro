% =============================================================================
% reglas_aptitud.pl
% -----------------------------------------------------------------------------
% Reglas que evalúan si un cultivo es apto para un lote dado, en función
% de los rangos óptimos (hechos generados desde el EDA) y de los hechos
% expertos sobre sensibilidades específicas.
%
% Convenciones:
% - Toda regla debe llevar un comentario explicando la lógica agronómica.
% - Junto a cada regla, dejar al menos un caso de prueba como comentario
%   con su resultado esperado.
% - Las reglas no deben tener umbrales hardcodeados: los rangos vienen de
%   hechos_generados.pl.
% =============================================================================
