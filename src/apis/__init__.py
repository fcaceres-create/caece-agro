"""
Clientes de APIs externas usadas por AgroSmart.

Cada submódulo encapsula el acceso a una fuente de datos y se encarga de:
- construir las URLs y parámetros de la consulta,
- aplicar reintentos con backoff exponencial y timeouts explícitos,
- cachear las respuestas en disco para evitar llamadas repetidas,
- loguear parámetros, hits de cache, cantidad de registros y latencia.

El resto del proyecto consume datos a través de estos clientes y nunca
hace requests crudos a las APIs externas.
"""
