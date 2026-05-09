"""
Regresor de rendimiento por cultivo (Random Forest).

Entrena un modelo independiente para cada uno de los 11 cultivos del
proyecto sobre el dataset maestro consolidado. La motivación de tener
un modelo por cultivo es agronómica: en el EDA quedó claro que cada
cultivo responde a drivers distintos (maíz dominado por temperatura,
soja por humedad, sorgo y girasol por suelo). Un único modelo "para
todos los cultivos" disolvería esas diferencias.

Pipeline para regenerar todo desde cero, en orden:
    1. notebooks/02_eda_consolidado.ipynb  (genera rangos por cultivo)
    2. python -m src.procesamiento.generar_hechos_prolog
    3. python -m src.modelos.regresor_rendimiento --entrenar

Persistencia: cada modelo se guarda como joblib en data/modelos/ junto
con un reporte JSON de métricas (R², MAE, RMSE, top 5 features). Esos
artefactos no se versionan (data/modelos/ está en .gitignore).
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)

# Lista canónica de cultivos del proyecto. El orden no importa: el modelo
# por cultivo se entrena de forma independiente.
CULTIVOS: tuple[str, ...] = (
    "soja", "maiz", "trigo", "girasol", "cebada", "sorgo",
    "avena", "centeno", "arroz", "algodon", "mani",
)

# Orden fijo y documentado de las 12 features. NO cambiar sin regenerar
# todos los modelos: el bridge construye el vector de inferencia en este
# mismo orden.
FEATURES: tuple[str, ...] = (
    "precipitacion_total_mm",
    "temp_media_c",
    "temp_max_promedio_c",
    "temp_min_promedio_c",
    "humedad_relativa_promedio",
    "radiacion_solar_total",
    "dias_helada",
    "ph",
    "materia_organica_pct",
    "arcilla_pct",
    "arena_pct",
    "cec",
)

TARGET = "rendimiento_kg_ha"

DATASET_PATH = Path("data/processed/dataset_maestro.csv")
MODELOS_DIR = Path("data/modelos")
REPORTE_PATH = MODELOS_DIR / "reporte_entrenamiento.json"

# Por debajo de este umbral, train_test_split estratificado por región
# se vuelve poco confiable (algunas regiones quedan con 0 o 1 ejemplo).
# Se cae a un split simple sin estratificar, con warning.
UMBRAL_FILAS_ESTRATIFICAR: int = 50

# Hiperparámetros base, sin GridSearch deliberadamente: el TFI no busca
# fine-tuning sino demostrar que la cascada simbólica + cuantitativa
# funciona end-to-end con un modelo razonable.
HIPERPARAMS: dict = {
    "n_estimators": 200,
    "max_depth": 15,
    "min_samples_leaf": 3,
    "random_state": 42,
    "n_jobs": -1,
}


@dataclass
class MetricasCultivo:
    """Métricas del modelo entrenado para un cultivo concreto."""

    cultivo: str
    n_train: int
    n_test: int
    r2: float
    mae_kg_ha: float
    rmse_kg_ha: float
    top_5_features: list[dict]
    estratificado: bool

    def to_dict(self) -> dict:
        return {
            "cultivo": self.cultivo,
            "n_train": int(self.n_train),
            "n_test": int(self.n_test),
            "r2": round(float(self.r2), 4),
            "mae_kg_ha": round(float(self.mae_kg_ha), 1),
            "rmse_kg_ha": round(float(self.rmse_kg_ha), 1),
            "estratificado_por_region": self.estratificado,
            "top_5_features": self.top_5_features,
        }


class RegresorRendimiento:
    """Random Forest por cultivo, con persistencia en joblib.

    Uso típico:
        reg = RegresorRendimiento()
        reg.entrenar_todos()                 # entrena los 11 modelos
        modelo = reg.cargar_modelo("soja")
        pred = reg.predecir("soja", features_dict)
    """

    def __init__(
        self,
        modelos_dir: Path = MODELOS_DIR,
        dataset_path: Path = DATASET_PATH,
    ) -> None:
        self.modelos_dir = Path(modelos_dir)
        self.dataset_path = Path(dataset_path)
        self.modelos_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, RandomForestRegressor] = {}

    # ------------------------------------------------------------------
    # Entrenamiento
    # ------------------------------------------------------------------
    def entrenar_todos(self) -> dict[str, dict]:
        """Entrena un modelo por cultivo y devuelve un dict de métricas.

        Persiste cada modelo a disco y un reporte JSON consolidado en
        data/modelos/reporte_entrenamiento.json.
        """
        logger.info("Cargando dataset desde %s", self.dataset_path)
        df = pd.read_csv(self.dataset_path)
        logger.info("Dataset cargado: %d filas, %d columnas", *df.shape)

        df = self._filtrar_dataset(df)
        logger.info(
            "Tras filtrar rendimiento>0 y NaN en features: %d filas", len(df)
        )

        reporte: dict[str, dict] = {}
        for cultivo in CULTIVOS:
            df_cultivo = df[df["cultivo"] == cultivo].copy()
            if df_cultivo.empty:
                logger.warning("Cultivo %s sin filas tras filtrar; se omite", cultivo)
                continue

            modelo, metricas = self._entrenar_cultivo(cultivo, df_cultivo)
            self._guardar_modelo(cultivo, modelo)
            reporte[cultivo] = metricas.to_dict()
            logger.info(
                "[%s] n_train=%d n_test=%d R2=%.3f MAE=%.0f RMSE=%.0f",
                cultivo,
                metricas.n_train,
                metricas.n_test,
                metricas.r2,
                metricas.mae_kg_ha,
                metricas.rmse_kg_ha,
            )

        self._guardar_reporte(reporte)
        return reporte

    def _filtrar_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aplica los filtros de calidad acordados en el EDA."""
        # Excluir campañas catastróficas (rendimiento 0). Decisión documentada
        # en docs/recuperacion_de_datos.md sección 6.
        df = df[df[TARGET] > 0]
        # Excluir filas con NaN en features (excluye principalmente
        # General Pueyrredón, los 134 registros sin suelo).
        df = df.dropna(subset=list(FEATURES))
        return df

    def _entrenar_cultivo(
        self, cultivo: str, df: pd.DataFrame
    ) -> tuple[RandomForestRegressor, MetricasCultivo]:
        """Entrena un único modelo para el cultivo dado."""
        X = df[list(FEATURES)].to_numpy(dtype=float)
        y = df[TARGET].to_numpy(dtype=float)

        estratificar = self._puede_estratificar(df)
        if estratificar:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42,
                stratify=df["region"].to_numpy(),
            )
        else:
            logger.warning(
                "Cultivo %s con %d filas: split simple (sin estratificar por región)",
                cultivo, len(df),
            )
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42,
            )

        modelo = RandomForestRegressor(**HIPERPARAMS)
        modelo.fit(X_train, y_train)

        y_pred = modelo.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

        importancias = modelo.feature_importances_
        orden = np.argsort(importancias)[::-1][:5]
        top_5 = [
            {"feature": FEATURES[i], "importance": round(float(importancias[i]), 4)}
            for i in orden
        ]

        metricas = MetricasCultivo(
            cultivo=cultivo,
            n_train=len(X_train),
            n_test=len(X_test),
            r2=r2,
            mae_kg_ha=mae,
            rmse_kg_ha=rmse,
            top_5_features=top_5,
            estratificado=estratificar,
        )
        return modelo, metricas

    def _puede_estratificar(self, df: pd.DataFrame) -> bool:
        """True si conviene estratificar por región.

        Requiere al menos UMBRAL_FILAS_ESTRATIFICAR filas y que cada
        región tenga al menos 2 ejemplos (sklearn lo exige).
        """
        if len(df) < UMBRAL_FILAS_ESTRATIFICAR:
            return False
        # bool() explícito: pandas devuelve numpy.bool_, que no es
        # serializable por json.dumps cuando llega al reporte.
        return bool((df["region"].value_counts() >= 2).all())

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------
    def _ruta_modelo(self, cultivo: str) -> Path:
        return self.modelos_dir / f"{cultivo}.joblib"

    def _guardar_modelo(self, cultivo: str, modelo: RandomForestRegressor) -> None:
        ruta = self._ruta_modelo(cultivo)
        joblib.dump(modelo, ruta)
        logger.info("Modelo %s guardado en %s", cultivo, ruta)

    def _guardar_reporte(self, reporte: dict[str, dict]) -> None:
        contenido = {
            "fecha_entrenamiento": datetime.now().isoformat(timespec="seconds"),
            "n_cultivos": len(reporte),
            "hiperparametros": HIPERPARAMS,
            "features_orden_fijo": list(FEATURES),
            "target": TARGET,
            "cultivos": reporte,
        }
        REPORTE_PATH.write_text(
            json.dumps(contenido, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Reporte de entrenamiento guardado en %s", REPORTE_PATH)

    # ------------------------------------------------------------------
    # Inferencia
    # ------------------------------------------------------------------
    def cargar_modelo(self, cultivo: str) -> RandomForestRegressor | None:
        """Carga el modelo del disco y lo cachea. None si no fue entrenado."""
        if cultivo in self._cache:
            return self._cache[cultivo]

        ruta = self._ruta_modelo(cultivo)
        if not ruta.exists():
            logger.warning(
                "Modelo de %s no encontrado en %s. ¿Falta correr --entrenar?",
                cultivo, ruta,
            )
            return None

        modelo = joblib.load(ruta)
        self._cache[cultivo] = modelo
        return modelo

    def predecir(self, cultivo: str, features: dict[str, float]) -> dict:
        """Predice rendimiento e intervalo de confianza al 95%.

        El intervalo se construye a partir de la dispersión de las
        predicciones de los árboles individuales del bosque: cada árbol
        es un estimador independiente sobre un bootstrap distinto, así
        que su std es una buena aproximación a la incertidumbre del
        ensemble.

        Devuelve un dict con:
            prediccion_kg_ha (int), low_kg_ha (int), high_kg_ha (int),
            std_kg_ha (float).
        """
        modelo = self.cargar_modelo(cultivo)
        if modelo is None:
            raise FileNotFoundError(f"Modelo de {cultivo} no entrenado.")

        # Vector en el orden documentado en FEATURES.
        x = np.array(
            [[features[col] for col in FEATURES]],
            dtype=float,
        )
        # Predicciones de cada árbol del bosque para estimar varianza.
        preds_arboles = np.array([est.predict(x)[0] for est in modelo.estimators_])
        media = float(preds_arboles.mean())
        std = float(preds_arboles.std())

        return {
            "prediccion_kg_ha": int(round(media)),
            "low_kg_ha": max(0, int(round(media - 1.96 * std))),
            "high_kg_ha": int(round(media + 1.96 * std)),
            "std_kg_ha": round(std, 1),
        }


# ----------------------------------------------------------------------
# Entrypoint CLI
# ----------------------------------------------------------------------
def _configurar_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Entrenamiento del regresor de rendimiento por cultivo."
    )
    parser.add_argument(
        "--entrenar",
        action="store_true",
        help="Entrena los 11 modelos y persiste un reporte JSON con métricas.",
    )
    args = parser.parse_args(argv)
    _configurar_logging()

    if args.entrenar:
        reg = RegresorRendimiento()
        reporte = reg.entrenar_todos()
        print(
            f"\nEntrenamiento finalizado. {len(reporte)} modelos guardados en "
            f"{MODELOS_DIR}/. Reporte: {REPORTE_PATH}"
        )
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
