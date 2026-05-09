"""
Suite de tests de AgroSmart.

Los tests usan pytest y no deberían depender de internet: las llamadas a
APIs externas se mockean. Se priorizan los módulos críticos: cascada de
decisión (`src.bridge.integrador`), generación de hechos
(`src.procesamiento.generar_hechos_prolog`) y los clientes de APIs.
"""
