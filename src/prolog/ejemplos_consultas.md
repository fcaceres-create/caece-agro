# Ejemplos de consultas a AgroSmart (SWI-Prolog)

Cargar el sistema:

```
swipl src/prolog/agrosmart.pl
```

Las consultas concretas se irán documentando acá a medida que se
escriban las reglas. Esqueleto sugerido:

## Aptitud

```prolog
% ¿Qué cultivos son aptos para un lote con estas condiciones?
% ?- cultivo_apto(Cultivo, lote(ph(6.2), temperatura_media(22.0), precipitacion_anual(900))).
```

## Riesgos

```prolog
% ¿Qué riesgos enfrenta un cultivo dado en este lote?
% ?- riesgo(soja, lote(ph(6.2), temperatura_media(22.0), precipitacion_anual(900)), Riesgo).
```

## Recomendaciones

```prolog
% ¿Qué recomendaciones surgen para mitigar los riesgos detectados?
% ?- recomendacion(soja, lote(ph(6.2), temperatura_media(22.0), precipitacion_anual(900)), Reco).
```
