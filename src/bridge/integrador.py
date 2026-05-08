"""
Cascada de decisión Python <-> Prolog.

Núcleo del aporte propio (Fase IV). Dada una coordenada y un año
objetivo:
1. Consulta clima y suelo para esa coordenada (clientes de APIs).
2. Pide a Prolog la lista de cultivos aptos según las reglas y los
   hechos generados desde el EDA.
3. Para cada cultivo apto, predice rendimiento con el modelo de Python.
4. Vuelve a consultar Prolog para diagnóstico de riesgos y
   recomendaciones de mitigación.
5. Confronta la predicción del modelo contra las reglas: si hay
   desacuerdo (segundo puente del aporte propio: ML <-> Lógica), lo
   reporta en lugar de ocultarlo.

El backend de Prolog se inyecta a través de una abstracción para poder
intercambiar pyswip por subprocess sin afectar al resto del sistema (ver
"Plan B si pyswip no funciona en Windows" en CLAUDE.md).
"""
