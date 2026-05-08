% =============================================================================
% agrosmart.pl
% -----------------------------------------------------------------------------
% Archivo principal del sistema experto AgroSmart. Carga la base de hechos
% (los generados automáticamente desde el EDA y los expertos manuales) y
% los tres módulos de reglas: aptitud, riesgo y recomendación.
%
% Punto de entrada para consultas interactivas:
%     swipl src/prolog/agrosmart.pl
%
% Ejemplos de consultas se documentan en ejemplos_consultas.md.
% =============================================================================

:- [hechos_generados].
:- [hechos_expertos].
:- [reglas_aptitud].
:- [reglas_riesgo].
:- [reglas_recomendacion].
