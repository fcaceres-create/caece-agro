"""
Generador automático de hechos Prolog desde el dataset procesado.

Materializa el primer puente del aporte propio (Datos -> Conocimiento):
calcula percentiles por cultivo sobre el dataset maestro y los exporta
como hechos Prolog en `src/prolog/hechos_generados.pl`.

Las reglas del sistema experto consumen estos hechos en lugar de tener
umbrales hardcodeados, de modo que todo rango óptimo proviene de
evidencia estadística sobre datos argentinos reales.

Se ejecuta como script:
    python -m src.procesamiento.generador_hechos_prolog
"""
