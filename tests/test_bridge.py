"""
Tests del bridge Python ↔ Prolog (src/bridge/integrador.py).

Estos tests validan la cascada de decisión completa, incluyendo el
razonamiento simbólico (Prolog) y la integración con el regresor.
Requieren:
    - SWI-Prolog instalado y pyswip configurado.
    - Modelos entrenados en data/modelos/ (correr antes:
      `python -m src.modelos.regresor_rendimiento --entrenar`).

Si los modelos no están, los tests cuantitativos hacen skip; los
simbólicos siguen corriendo porque no dependen del regresor.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bridge.integrador import (
    Lote,
    ReporteLote,
    SistemaAgroSmart,
    _clasificar_rendimiento,
)
from src.modelos.regresor_rendimiento import MODELOS_DIR


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def sistema() -> SistemaAgroSmart:
    """Una sola instancia compartida: cargar Prolog y modelos es caro."""
    return SistemaAgroSmart()


@pytest.fixture
def lote_pampeano_tipico() -> Lote:
    """Pergamino-style: condiciones óptimas pampeanas (ver §12.7 docs)."""
    return Lote(
        region="pampeana",
        ph=6.5,
        materia_organica_pct=3.2,
        arcilla_pct=26.0,
        arena_pct=12.0,
        precipitacion_total_mm=750.0,
        temp_media_c=22.0,
        dias_helada=0,
        nombre="lote_pampeano_test",
    )


@pytest.fixture
def lote_arido() -> Lote:
    """Misma base pampeana pero con sequía severa (campaña 2022/23)."""
    return Lote(
        region="pampeana",
        ph=6.5,
        materia_organica_pct=3.2,
        arcilla_pct=26.0,
        arena_pct=12.0,
        precipitacion_total_mm=300.0,
        temp_media_c=22.0,
        dias_helada=0,
        nombre="lote_arido_test",
    )


@pytest.fixture
def lote_acido() -> Lote:
    """pH muy bajo: el suelo queda fuera de rango óptimo para todos."""
    return Lote(
        region="pampeana",
        ph=4.5,
        materia_organica_pct=3.2,
        arcilla_pct=26.0,
        arena_pct=12.0,
        precipitacion_total_mm=750.0,
        temp_media_c=22.0,
        dias_helada=0,
        nombre="lote_acido_test",
    )


def _hay_modelos_entrenados() -> bool:
    return any(Path(MODELOS_DIR).glob("*.joblib"))


# ---------------------------------------------------------------------
# Tests simbólicos (no requieren modelos entrenados)
# ---------------------------------------------------------------------
def test_evaluar_lote_pampeano_recomienda_4_grandes(
    sistema: SistemaAgroSmart, lote_pampeano_tipico: Lote
) -> None:
    """Un lote pampeano típico debe recomendar al menos soja y maíz."""
    reporte = sistema.evaluar_lote(lote_pampeano_tipico)
    cultivos = {r.cultivo for r in reporte.recomendaciones}
    assert "soja" in cultivos, f"Esperaba soja en recomendados; obtuve {cultivos}"
    assert "maiz" in cultivos, f"Esperaba maíz en recomendados; obtuve {cultivos}"


def test_evaluar_lote_arido_no_recomienda_soja(
    sistema: SistemaAgroSmart, lote_arido: Lote
) -> None:
    """Con precipitación 300 mm la soja debe quedar fuera de recomendados.

    Por debajo del p10 de lluvia para soja, riesgo_sequia se dispara y
    riesgo_critico la elimina de recomendados. Debe aparecer como
    no_recomendado con motivo riesgo_sequia.
    """
    reporte = sistema.evaluar_lote(lote_arido)
    cultivos_recomendados = {r.cultivo for r in reporte.recomendaciones}
    assert "soja" not in cultivos_recomendados

    motivos_soja = [
        nr.motivo for nr in reporte.no_recomendados if nr.cultivo == "soja"
    ]
    assert motivos_soja, "Soja debería estar en no_recomendados"
    assert motivos_soja[0] == "riesgo_sequia"


def test_evaluar_lote_acido_no_recomienda_nada(
    sistema: SistemaAgroSmart, lote_acido: Lote
) -> None:
    """Con pH 4.5 ningún cultivo califica como apto pleno.

    El pH cae fuera del p10 de todos los cultivos, así que apto_suelo
    falla universalmente y la lista de recomendados queda vacía. El
    riesgo de acidez además se reportaría como observación si algún
    cultivo lograra colarse.
    """
    reporte = sistema.evaluar_lote(lote_acido)
    assert reporte.recomendaciones == [], (
        f"Esperaba lista vacía; obtuve {[r.cultivo for r in reporte.recomendaciones]}"
    )


# ---------------------------------------------------------------------
# Tests cuantitativos (requieren modelos entrenados)
# ---------------------------------------------------------------------
@pytest.mark.skipif(
    not _hay_modelos_entrenados(),
    reason="No hay modelos entrenados en data/modelos/. "
           "Correr `python -m src.modelos.regresor_rendimiento --entrenar` primero.",
)
def test_predicciones_dentro_de_rango_razonable(
    sistema: SistemaAgroSmart, lote_pampeano_tipico: Lote
) -> None:
    """Para un lote pampeano típico, soja debe predecir entre 1500-4500 kg/ha.

    Es un sanity check amplio: el rango cubre desde campañas malas
    hasta excelentes en la zona núcleo. Una predicción fuera de este
    rango indicaría un problema de scaling, features cruzadas o
    contaminación entre modelos.
    """
    reporte = sistema.evaluar_lote(lote_pampeano_tipico)
    soja = next(
        (r for r in reporte.recomendaciones if r.cultivo == "soja"), None
    )
    assert soja is not None, "Soja debería estar en recomendados"
    assert soja.rendimiento_predicho_kg_ha is not None
    assert 1500 <= soja.rendimiento_predicho_kg_ha <= 4500, (
        f"Predicción de soja fuera de rango razonable: "
        f"{soja.rendimiento_predicho_kg_ha} kg/ha"
    )


def test_reporte_serializable_a_json(
    sistema: SistemaAgroSmart, lote_pampeano_tipico: Lote
) -> None:
    """ReporteLote debe roundtrip-ear por JSON sin pérdida de campos.

    No tiene que reconstruir las dataclasses (asdict ya las aplana a
    dicts), pero el contenido textual debe ser idéntico.
    """
    reporte = sistema.evaluar_lote(lote_pampeano_tipico)
    serializado = sistema.exportar_json(reporte)

    deserializado = json.loads(serializado)

    assert deserializado["lote"]["region"] == "pampeana"
    assert deserializado["timestamp"]
    assert "recomendaciones" in deserializado
    assert "no_recomendados" in deserializado
    assert "aptos_parciales" in deserializado

    # Roundtrip: re-serializar el dict deserializado y comparar como dicts.
    re_serializado = json.dumps(deserializado, ensure_ascii=False)
    assert json.loads(re_serializado) == deserializado


# ---------------------------------------------------------------------
# Tests del helper de clasificación
# ---------------------------------------------------------------------
def test_clasificacion_rendimiento_alto_medio_bajo() -> None:
    esperado = (2000, 3500, 5000)  # (p10, p50, p90) hipotético
    assert _clasificar_rendimiento(5500, esperado) == "alto"
    assert _clasificar_rendimiento(4000, esperado) == "medio"
    assert _clasificar_rendimiento(2500, esperado) == "bajo"
    assert _clasificar_rendimiento(1500, esperado) == "muy_bajo"


# ---------------------------------------------------------------------
# Tests de consultar_prolog (consola Prolog del tab de la app)
# ---------------------------------------------------------------------
# El método se prueba con sandboxing en sus dos modos: False para las
# 8 consultas predefinidas (que ya auditamos), True para todo lo que
# entre por la consola libre del usuario.
def test_consulta_solucion_unica_true(sistema: SistemaAgroSmart) -> None:
    """Una consulta sin variables que tiene éxito devuelve 'true.'."""
    r = sistema.consultar_prolog(
        "apto(lote_pergamino, soja).", sandboxing=False
    )
    assert r["exitosa"] is True
    assert r["error"] is None
    assert r["output_formateado"] == "true."
    assert r["soluciones"] == [{}]


def test_consulta_sin_soluciones_false(sistema: SistemaAgroSmart) -> None:
    """Sin soluciones devuelve 'false.' (estilo SWI-Prolog clásico)."""
    r = sistema.consultar_prolog(
        "apto(lote_pergamino, arroz).", sandboxing=False
    )
    assert r["exitosa"] is True
    assert r["soluciones"] == []
    assert r["output_formateado"] == "false."


def test_consulta_multiples_soluciones_se_truncan(
    sistema: SistemaAgroSmart,
) -> None:
    """between/3 con 100 soluciones se debe cortar en max_soluciones."""
    r = sistema.consultar_prolog(
        "between(1, 100, X).", sandboxing=False, max_soluciones=5
    )
    assert r["exitosa"] is True
    assert len(r["soluciones"]) == 5
    assert r["truncado"] is True
    # Formato esperado: 5 bindings separados por " ;\n" + sufijo de truncado
    assert "X = 1" in r["output_formateado"]
    assert "X = 5" in r["output_formateado"]
    assert "más soluciones" in r["output_formateado"]


def test_consulta_sintaxis_invalida_devuelve_error(
    sistema: SistemaAgroSmart,
) -> None:
    """Una consulta mal formada no debe romper Python; debe quedar exitosa=False."""
    r = sistema.consultar_prolog("esto no es prolog", sandboxing=True)
    assert r["exitosa"] is False
    assert r["error"] is not None
    assert r["output_formateado"].startswith("ERROR:")


def test_consulta_predicado_bloqueado_por_regex(
    sistema: SistemaAgroSmart,
) -> None:
    """halt y asserta deben ser rechazados antes incluso de llegar a sandbox."""
    for consulta_peligrosa, predicado in [
        ("halt.", "halt"),
        ("asserta(cultivo_soportado(troll)).", "asserta"),
        ("retract(cultivo_soportado(soja)).", "retract"),
    ]:
        r = sistema.consultar_prolog(consulta_peligrosa, sandboxing=True)
        assert r["exitosa"] is False, f"{consulta_peligrosa} no se rechazó"
        assert r["error"] is not None
        assert predicado in r["error"], (
            f"Esperaba '{predicado}' en r['error']; obtuve {r['error']!r}"
        )


def test_consulta_predicado_bloqueado_por_sandbox(
    sistema: SistemaAgroSmart,
) -> None:
    """Predicados peligrosos que el regex no atrapa deben caer en sandbox.

    `print/1` no está en nuestra lista negra explícita pero sandbox lo
    rechaza por escribir a un stream global. Es nuestra red de contención.
    """
    r = sistema.consultar_prolog("print(hola).", sandboxing=True)
    assert r["exitosa"] is False
    assert r["error"] is not None
    assert r["error"].startswith("sandbox:"), (
        f"Esperaba prefijo 'sandbox:'; obtuve {r['error']!r}"
    )


def test_consulta_timeout_excedido(sistema: SistemaAgroSmart) -> None:
    """Si una consulta no termina en `timeout` segundos, se aborta.

    Usamos `between(1, 1e9, _)` que genera mil millones de soluciones
    rápidas. Con timeout 0.1s y max_soluciones >> 0, el bucle
    interno acumula soluciones hasta que el chequeo de tiempo decide
    cortar y devolver error == 'timeout'.
    """
    r = sistema.consultar_prolog(
        "between(1, 1000000000, _).",
        sandboxing=False,
        timeout=0.1,
        max_soluciones=10**9,
    )
    assert r["exitosa"] is False
    assert r["error"] == "timeout"
    assert "tiempo límite" in r["output_formateado"]


def test_consulta_sin_punto_final_se_normaliza(
    sistema: SistemaAgroSmart,
) -> None:
    """Si el usuario olvida el '.' final, debe ejecutarse igual."""
    r = sistema.consultar_prolog("apto(lote_pergamino, soja)", sandboxing=False)
    assert r["exitosa"] is True
    assert r["output_formateado"] == "true."
