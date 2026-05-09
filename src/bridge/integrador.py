"""
Bridge Python ↔ Prolog: cascada de decisión integrada (Fase IV).

Este módulo es el núcleo del aporte propio del trabajo. Materializa los
dos puentes entre lo subsímbolico y lo simbólico:

    1. Datos → Conocimiento: las reglas Prolog razonan sobre el lote
       usando rangos óptimos derivados estadísticamente del dataset.
    2. ML ↔ Lógica: la predicción cuantitativa del Random Forest se
       confronta contra los percentiles esperados que ya conoce Prolog
       y se reporta cualquier desacuerdo en lugar de ocultarlo.

Cascada en 3 etapas:

    Etapa 1 — Razonamiento simbólico:  agrosmart.pl :: reporte_lote/4
              decide qué cultivos son recomendados, no recomendados o
              aptos parciales para el lote.
    Etapa 2 — Predicción cuantitativa: para cada cultivo recomendado,
              el regresor por cultivo predice rendimiento + intervalo.
    Etapa 3 — Reporte integrado:       compara la predicción contra el
              rango esperado de la zona (rendimiento_esperado/4) y
              clasifica el resultado.

Pipeline para regenerar todo desde cero, en orden:
    1. notebooks/02_eda_consolidado.ipynb
    2. python -m src.procesamiento.generar_hechos_prolog
    3. python -m src.modelos.regresor_rendimiento --entrenar
    4. python -m src.bridge.integrador --demo
"""

from __future__ import annotations

import argparse
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from src.modelos.regresor_rendimiento import (
    CULTIVOS,
    MODELOS_DIR,
    RegresorRendimiento,
)

logger = logging.getLogger(__name__)

PROLOG_FILE = Path("src/prolog/agrosmart.pl")
REPORTE_DEMO_PATH = MODELOS_DIR / "reporte_demo.json"

# Variables que el lote debe asertar como hechos para que las reglas de
# aptitud / riesgo Prolog puedan razonar. Las claves coinciden con los
# functores que esperan reglas_aptitud.pl y reglas_riesgo.pl.
VARIABLES_LOTE_PROLOG: tuple[str, ...] = (
    "ph",
    "materia_organica_pct",
    "arcilla_pct",
    "arena_pct",
    "precipitacion_total_mm",
    "temp_media_c",
    "humedad_relativa_promedio",
    "radiacion_solar_total",
    "dias_helada",
    "cec",
)


# ---------------------------------------------------------------------
# Modelos de datos
# ---------------------------------------------------------------------
@dataclass
class Lote:
    """Lote bajo análisis. Los campos opcionales toman defaults razonables.

    Si no se aportan temp_max_promedio_c o temp_min_promedio_c se derivan
    como ±5 °C de la media (heurística aceptable para ciclos pampeanos
    típicos; el usuario puede sobrescribirlas).
    """

    region: str  # "pampeana" | "noa" | "nea"
    ph: float
    materia_organica_pct: float
    arcilla_pct: float
    arena_pct: float
    precipitacion_total_mm: float
    temp_media_c: float
    temp_max_promedio_c: float | None = None
    temp_min_promedio_c: float | None = None
    humedad_relativa_promedio: float = 65.0
    radiacion_solar_total: float = 4000.0
    dias_helada: int = 0
    cec: float = 20.0
    nombre: str = "lote_anonimo"

    def __post_init__(self) -> None:
        if self.temp_max_promedio_c is None:
            self.temp_max_promedio_c = self.temp_media_c + 5
        if self.temp_min_promedio_c is None:
            self.temp_min_promedio_c = self.temp_media_c - 5

    def features_para_modelo(self) -> dict[str, float]:
        """Vector de features en el orden documentado para el regresor."""
        return {
            "precipitacion_total_mm": self.precipitacion_total_mm,
            "temp_media_c": self.temp_media_c,
            "temp_max_promedio_c": float(self.temp_max_promedio_c),
            "temp_min_promedio_c": float(self.temp_min_promedio_c),
            "humedad_relativa_promedio": self.humedad_relativa_promedio,
            "radiacion_solar_total": self.radiacion_solar_total,
            "dias_helada": float(self.dias_helada),
            "ph": self.ph,
            "materia_organica_pct": self.materia_organica_pct,
            "arcilla_pct": self.arcilla_pct,
            "arena_pct": self.arena_pct,
            "cec": self.cec,
        }


@dataclass
class Recomendacion:
    cultivo: str
    rendimiento_predicho_kg_ha: int | None
    intervalo_prediccion: tuple[int, int] | None
    rendimiento_esperado_zona: tuple[int, int, int]  # (p10, p50, p90)
    clasificacion_rendimiento: str  # alto | medio | bajo | muy_bajo | sin_modelo
    riesgos_observados: list[str]


@dataclass
class CultivoNoRecomendado:
    cultivo: str
    motivo: str  # riesgo_sequia | riesgo_helada | riesgo_nutricional |
                 # suelo_fuera_de_rango | clima_fuera_de_rango


@dataclass
class CultivoAptoParcial:
    cultivo: str
    motivo: str  # apto_parcial_suelo | apto_parcial_clima


@dataclass
class ReporteLote:
    lote: dict
    timestamp: str
    recomendaciones: list[Recomendacion] = field(default_factory=list)
    no_recomendados: list[CultivoNoRecomendado] = field(default_factory=list)
    aptos_parciales: list[CultivoAptoParcial] = field(default_factory=list)


# ---------------------------------------------------------------------
# Backend Prolog (pyswip)
# ---------------------------------------------------------------------
class _BackendProlog:
    """Encapsula pyswip y normaliza tipos de retorno.

    El integrador depende solo de esta clase para hablar con Prolog. Si
    en el futuro hace falta cambiar a swipl-via-subprocess (Plan B
    documentado en CLAUDE.md), basta con reemplazar esta clase
    manteniendo la firma de los métodos públicos.
    """

    def __init__(self, archivo_pl: Path = PROLOG_FILE) -> None:
        try:
            from pyswip import Prolog  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pyswip no está disponible. Instalar con `pip install pyswip` y "
                "revisar SWI_HOME_DIR/PATH (ver CLAUDE.md, sección Setup)."
            ) from exc

        if not archivo_pl.exists():
            raise FileNotFoundError(
                f"No se encontró el sistema experto en {archivo_pl}. "
                "Verificar src/prolog/agrosmart.pl."
            )

        self._Prolog = Prolog
        self.prolog = Prolog()
        # SWI-Prolog resuelve consult relativo a su cwd; pasamos el path
        # con forward-slash para evitar problemas en Windows.
        self.prolog.consult(str(archivo_pl).replace("\\", "/"))
        # Declarar dynamics para no recibir errores "unknown procedure"
        # cuando el lote aún no asertó hechos. Los predicados quedan así
        # definidos como bases vacías hasta que el bridge los puebla.
        list(self.prolog.query("dynamic(region_lote/2)"))
        list(self.prolog.query("dynamic(valor_lote/3)"))

    # -- aserción/retracción de hechos del lote --------------------------
    def asertar_lote(self, lote_id: str, lote: Lote) -> None:
        self.prolog.assertz(f"region_lote({lote_id}, {lote.region})")
        valores = lote.features_para_modelo()
        for var in VARIABLES_LOTE_PROLOG:
            valor = valores[var] if var in valores else getattr(lote, var)
            self.prolog.assertz(f"valor_lote({lote_id}, {var}, {valor})")

    def retractar_lote(self, lote_id: str) -> None:
        # retractall no falla si no encuentra hechos; es idempotente.
        list(self.prolog.query(f"retractall(region_lote({lote_id}, _))"))
        list(self.prolog.query(f"retractall(valor_lote({lote_id}, _, _))"))

    # -- consultas de alto nivel ----------------------------------------
    def reporte_lote(
        self, lote_id: str
    ) -> tuple[list[str], list[str], list[str]]:
        """Llama a reporte_lote/4 y devuelve las tres listas de cultivos."""
        q = list(self.prolog.query(
            f"reporte_lote({lote_id}, R, NR, AP)"
        ))
        if not q:
            return [], [], []
        sol = q[0]
        return (
            _normalizar_lista_atomos(sol["R"]),
            _normalizar_lista_atomos(sol["NR"]),
            _normalizar_lista_atomos(sol["AP"]),
        )

    def riesgos_de(self, lote_id: str, cultivo: str) -> list[str]:
        q = list(self.prolog.query(
            f"todos_los_riesgos({lote_id}, {cultivo}, R)"
        ))
        if not q:
            return []
        return _normalizar_lista_atomos(q[0]["R"])

    def rendimiento_esperado(self, cultivo: str) -> tuple[int, int, int] | None:
        q = list(self.prolog.query(
            f"rendimiento_esperado({cultivo}, P10, MED, P90)"
        ))
        if not q:
            return None
        sol = q[0]
        return int(sol["P10"]), int(sol["MED"]), int(sol["P90"])

    def es_apto_suelo(self, lote_id: str, cultivo: str) -> bool:
        return bool(list(self.prolog.query(f"apto_suelo({lote_id}, {cultivo})")))

    def es_apto_clima(self, lote_id: str, cultivo: str) -> bool:
        return bool(list(self.prolog.query(f"apto_clima({lote_id}, {cultivo})")))

    def es_apto_parcial_suelo(self, lote_id: str, cultivo: str) -> bool:
        return bool(list(self.prolog.query(f"apto_parcial_suelo({lote_id}, {cultivo})")))


def _normalizar_lista_atomos(prolog_list: Any) -> list[str]:
    """Convierte una lista de átomos pyswip a strings Python."""
    return [_atomo_a_str(x) for x in prolog_list]


def _atomo_a_str(x: Any) -> str:
    """Robusto contra Atom, bytes y str (varía con la versión de pyswip)."""
    if isinstance(x, bytes):
        return x.decode("utf-8")
    s = str(x)
    # pyswip a veces formatea átomos como "Atom('soja')"; normalizamos.
    if s.startswith("Atom(") and s.endswith(")"):
        s = s[5:-1].strip("'\"")
    return s


# ---------------------------------------------------------------------
# Sistema integrado
# ---------------------------------------------------------------------
class SistemaAgroSmart:
    """Cascada de decisión completa: símbolico + cuantitativo.

    En el __init__ carga los 11 modelos joblib y consulta el archivo
    Prolog. Una vez instanciado, evaluar_lote(lote) devuelve un
    ReporteLote completo y se puede llamar repetidamente.
    """

    def __init__(
        self,
        modelos_dir: Path = MODELOS_DIR,
        archivo_prolog: Path = PROLOG_FILE,
    ) -> None:
        self.regresor = RegresorRendimiento(modelos_dir=modelos_dir)
        self._precargar_modelos()
        self.backend = _BackendProlog(archivo_pl=archivo_prolog)

    def _precargar_modelos(self) -> None:
        self._modelos_disponibles: set[str] = set()
        for cultivo in CULTIVOS:
            if self.regresor.cargar_modelo(cultivo) is not None:
                self._modelos_disponibles.add(cultivo)
        if not self._modelos_disponibles:
            logger.warning(
                "No hay ningún modelo entrenado en %s. La cascada va a "
                "funcionar solo con la parte simbólica.",
                self.regresor.modelos_dir,
            )

    # ------------------------------------------------------------------
    # Cascada principal
    # ------------------------------------------------------------------
    def evaluar_lote(self, lote: Lote) -> ReporteLote:
        """Ejecuta las 3 etapas y devuelve el reporte integrado."""
        # ID único por evaluación: evita colisiones si el sistema se usa
        # concurrentemente y permite limpiar al final sin tocar otros lotes.
        lote_id = f"lote_runtime_{uuid.uuid4().hex[:8]}"
        logger.info("Evaluando lote %s (%s)", lote.nombre, lote_id)

        try:
            self.backend.asertar_lote(lote_id, lote)

            # Etapa 1 — razonamiento simbólico
            recomendados, no_recomendados, aptos_parciales = (
                self.backend.reporte_lote(lote_id)
            )
            logger.info(
                "Prolog: %d recomendados, %d no recomendados, %d aptos parciales",
                len(recomendados), len(no_recomendados), len(aptos_parciales),
            )

            reporte = ReporteLote(
                lote=asdict(lote),
                timestamp=datetime.now().isoformat(timespec="seconds"),
            )

            # Etapa 2 — predicción cuantitativa (solo para recomendados)
            for cultivo in recomendados:
                reporte.recomendaciones.append(
                    self._construir_recomendacion(lote, lote_id, cultivo)
                )

            # Etapa 3 — anotación de no recomendados y aptos parciales
            for cultivo in no_recomendados:
                reporte.no_recomendados.append(
                    self._motivo_no_recomendado(lote_id, cultivo)
                )
            for cultivo in aptos_parciales:
                reporte.aptos_parciales.append(
                    self._motivo_apto_parcial(lote_id, cultivo)
                )

            return reporte
        finally:
            # Siempre limpiar los hechos del lote, incluso si hubo error.
            self.backend.retractar_lote(lote_id)

    def _construir_recomendacion(
        self, lote: Lote, lote_id: str, cultivo: str
    ) -> Recomendacion:
        riesgos = self.backend.riesgos_de(lote_id, cultivo)
        esperado = self.backend.rendimiento_esperado(cultivo) or (0, 0, 0)

        if cultivo not in self._modelos_disponibles:
            logger.warning(
                "Cultivo %s recomendado pero sin modelo entrenado: "
                "se omite la predicción cuantitativa.", cultivo,
            )
            return Recomendacion(
                cultivo=cultivo,
                rendimiento_predicho_kg_ha=None,
                intervalo_prediccion=None,
                rendimiento_esperado_zona=esperado,
                clasificacion_rendimiento="sin_modelo",
                riesgos_observados=riesgos,
            )

        pred = self.regresor.predecir(cultivo, lote.features_para_modelo())
        clasificacion = _clasificar_rendimiento(pred["prediccion_kg_ha"], esperado)

        # Segundo puente del aporte propio: si el modelo predice por
        # debajo del p10 esperado, lo reportamos como observación
        # explícita en lugar de aceptarlo en silencio.
        if clasificacion == "muy_bajo" and "rendimiento_bajo_lo_esperado" not in riesgos:
            riesgos = [*riesgos, "rendimiento_bajo_lo_esperado"]

        return Recomendacion(
            cultivo=cultivo,
            rendimiento_predicho_kg_ha=pred["prediccion_kg_ha"],
            intervalo_prediccion=(pred["low_kg_ha"], pred["high_kg_ha"]),
            rendimiento_esperado_zona=esperado,
            clasificacion_rendimiento=clasificacion,
            riesgos_observados=riesgos,
        )

    def _motivo_no_recomendado(self, lote_id: str, cultivo: str) -> CultivoNoRecomendado:
        """Determina por qué un cultivo viable geográficamente quedó descartado.

        Prioriza riesgos críticos (más informativos) sobre razones de
        aptitud genérica.
        """
        riesgos = self.backend.riesgos_de(lote_id, cultivo)
        for critico in ("sequia", "helada", "nutricional"):
            if critico in riesgos:
                return CultivoNoRecomendado(cultivo=cultivo, motivo=f"riesgo_{critico}")
        if not self.backend.es_apto_suelo(lote_id, cultivo):
            return CultivoNoRecomendado(cultivo=cultivo, motivo="suelo_fuera_de_rango")
        return CultivoNoRecomendado(cultivo=cultivo, motivo="clima_fuera_de_rango")

    def _motivo_apto_parcial(self, lote_id: str, cultivo: str) -> CultivoAptoParcial:
        if self.backend.es_apto_parcial_suelo(lote_id, cultivo):
            return CultivoAptoParcial(cultivo=cultivo, motivo="apto_parcial_suelo")
        return CultivoAptoParcial(cultivo=cultivo, motivo="apto_parcial_clima")

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------
    def exportar_json(self, reporte: ReporteLote) -> str:
        """Serializa el reporte a JSON. Las tuplas se vuelven listas."""
        return json.dumps(asdict(reporte), indent=2, ensure_ascii=False)


def _clasificar_rendimiento(pred: int, esperado: tuple[int, int, int]) -> str:
    """Compara la predicción contra los percentiles esperados de la zona.

    - alto:      pred >= p90
    - medio:     p50 <= pred < p90
    - bajo:      p10 <= pred < p50
    - muy_bajo:  pred < p10
    """
    p10, p50, p90 = esperado
    if p90 == 0 and p50 == 0 and p10 == 0:
        # Sin datos esperados (cultivo sin rendimiento_esperado/4): el
        # lector ve la predicción cruda sin etiqueta cualitativa.
        return "sin_referencia"
    if pred >= p90:
        return "alto"
    if pred >= p50:
        return "medio"
    if pred >= p10:
        return "bajo"
    return "muy_bajo"


# ---------------------------------------------------------------------
# Demo / CLI
# ---------------------------------------------------------------------
def _lote_demo_pampeano() -> Lote:
    """Pergamino típico, condiciones óptimas. Ver docs/recuperacion_de_datos.md §12.7."""
    return Lote(
        region="pampeana",
        ph=6.5,
        materia_organica_pct=3.2,
        arcilla_pct=26.0,
        arena_pct=12.0,
        precipitacion_total_mm=750.0,
        temp_media_c=22.0,
        dias_helada=0,
        nombre="pergamino_demo",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bridge Python ↔ Prolog: cascada de decisión AgroSmart."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Evalúa un lote pampeano de demostración y exporta el reporte a JSON.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.demo:
        sistema = SistemaAgroSmart()
        lote = _lote_demo_pampeano()
        reporte = sistema.evaluar_lote(lote)
        salida = sistema.exportar_json(reporte)
        print(salida)
        REPORTE_DEMO_PATH.write_text(salida, encoding="utf-8")
        print(f"\nReporte guardado en {REPORTE_DEMO_PATH}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
