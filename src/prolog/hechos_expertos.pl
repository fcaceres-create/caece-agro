% =====================================================================
% AgroSmart - Hechos expertos (conocimiento agronómico cargado a mano)
% ---------------------------------------------------------------------
% Estos hechos NO se derivan del dataset: representan conocimiento
% agronómico de manual (INTA, FAO, bibliografía de cátedra) que el
% sistema necesita para razonar correctamente sobre los cultivos.
%
% Son complementarios a los hechos generados automáticamente en
% hechos_generados.pl, que contiene los rangos estadísticos por cultivo
% y variable agronómica derivados del dataset argentino.
%
% Editar este archivo es seguro: no se sobrescribe automáticamente.
% Cada bloque trae un comentario corto con la justificación agronómica.
% =====================================================================

% ---------------------------------------------------------------------
% Ciclo del cultivo: invierno o verano
% ---------------------------------------------------------------------
% Determina la ventana de siembra y cosecha y, por extensión, qué
% datos climáticos son relevantes (verano: oct-mar; invierno: abr-nov).
% Fuente: prácticas de manejo extensivo en Argentina (INTA).
% ---------------------------------------------------------------------
ciclo(soja, verano).
ciclo(maiz, verano).
ciclo(sorgo, verano).
ciclo(girasol, verano).
ciclo(arroz, verano).
ciclo(algodon, verano).
ciclo(mani, verano).
ciclo(trigo, invierno).
ciclo(cebada, invierno).
ciclo(avena, invierno).
ciclo(centeno, invierno).

% ---------------------------------------------------------------------
% Cultivos sensibles a heladas durante el ciclo crítico
% ---------------------------------------------------------------------
% Típicamente cultivos de verano que se ven afectados por heladas
% tempranas en otoño durante el llenado de grano. Los cultivos de
% invierno NO se incluyen acá: tolerancia al frío es parte de su
% fisiología normal.
% ---------------------------------------------------------------------
sensible_helada(maiz).
sensible_helada(soja).
sensible_helada(sorgo).
sensible_helada(girasol).
sensible_helada(arroz).
sensible_helada(algodon).
sensible_helada(mani).

% ---------------------------------------------------------------------
% Cultivos que necesitan vernalización
% ---------------------------------------------------------------------
% Vernalización: proceso fisiológico que requiere acumulación de horas
% de frío para inducir floración correctamente. Aplica a cereales de
% invierno; la avena puede prescindir según variedad.
% ---------------------------------------------------------------------
necesita_vernalizacion(trigo).
necesita_vernalizacion(cebada).
necesita_vernalizacion(centeno).

% ---------------------------------------------------------------------
% Categorización agronómica del cultivo
% ---------------------------------------------------------------------
% Útil para clasificar los outputs del sistema y agruparlos en reportes
% (cultivos principales primero, alternativos como sugerencias, etc.).
% ---------------------------------------------------------------------
cultivo_principal(soja).
cultivo_principal(maiz).
cultivo_principal(trigo).
cultivo_principal(girasol).
cultivo_alternativo(sorgo).
cultivo_alternativo(arroz).
cultivo_alternativo(algodon).
cultivo_alternativo(mani).
cultivo_forrajero(avena).
cultivo_forrajero(centeno).
cultivo_industrial(cebada).

% ---------------------------------------------------------------------
% Predecesores recomendados (rotaciones)
% ---------------------------------------------------------------------
% Formato: predecesor_recomendado(Cultivo, CultivoPredecesor).
% Las rotaciones mejoran sanidad del suelo, ciclan nutrientes y
% rompen ciclos de plagas/enfermedades. Las recomendaciones siguen el
% manual de buenas prácticas del INTA para la región pampeana.
% ---------------------------------------------------------------------
% Soja después de gramínea (rotación mejor que monocultivo de soja).
predecesor_recomendado(soja, maiz).
predecesor_recomendado(soja, trigo).
predecesor_recomendado(soja, sorgo).
% Maíz después de leguminosa (aprovecha N residual fijado por la soja).
predecesor_recomendado(maiz, soja).
% Trigo después de cualquier cultivo de verano.
predecesor_recomendado(trigo, soja).
predecesor_recomendado(trigo, maiz).
predecesor_recomendado(trigo, girasol).
% Girasol después de cereal de invierno.
predecesor_recomendado(girasol, trigo).
predecesor_recomendado(girasol, cebada).
