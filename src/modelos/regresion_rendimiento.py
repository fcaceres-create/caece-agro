"""
Modelo de regresión de rendimiento por cultivo.

Entrena un Random Forest Regressor sobre el dataset maestro para estimar
rendimiento (kg/ha) en función de variables de clima y suelo. Se entrena
un modelo por cultivo para capturar respuestas agronómicas específicas.

El módulo expone funciones para entrenar, evaluar y persistir los
modelos en `data/processed/` (formato joblib), y para cargarlos a
demanda durante la inferencia desde el integrador.
"""
