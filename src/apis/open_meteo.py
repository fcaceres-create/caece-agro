"""
Cliente de Open-Meteo Historical Weather API.

Endpoint: ``https://archive-api.open-meteo.com/v1/archive``

No requiere API key. Cobertura: 1940-presente, ~9 km de resolución
espacial (datos del reanálisis ERA5). Sin paginación: una sola
respuesta JSON por consulta.

Variables daily implementadas
-----------------------------
- ``temperature_2m_mean``       → ``temp_media_c``       (°C)
- ``temperature_2m_max``        → ``temp_max_c``         (°C)
- ``temperature_2m_min``        → ``temp_min_c``         (°C)
- ``precipitation_sum``         → ``precipitacion_mm``   (mm)
- ``relative_humidity_2m_mean`` → ``humedad_relativa``   (%)
- ``shortwave_radiation_sum``   → ``radiacion_solar``    (MJ/m²)

Futuras extensiones (variables disponibles en el endpoint, no usadas hoy)
------------------------------------------------------------------------
Estas variables están al alcance del mismo endpoint sin costo adicional
de ingeniería. Se documentan acá para visibilidad y defensa del trabajo;
implementarlas implica solo agregarlas a ``_VARS_DAILY`` y al mapeo:

- ``et0_fao_evapotranspiration`` (mm/día): evapotranspiración de
  referencia FAO-56 Penman-Monteith. Es la pieza central del balance
  hídrico (precipitación − ET₀) y permitiría que Prolog diagnostique
  estrés hídrico de manera explicable.
- ``soil_moisture_0_to_7cm`` y profundidades superiores: humedad
  volumétrica del suelo modelada. Útil para reglas de aptitud de
  germinación.
- ``soil_temperature_0_to_7cm`` y profundidades superiores: temperatura
  del suelo. Igual aplicación que la anterior.
- GDD (Growing Degree Days): no está pre-calculado en la API. Se
  deriva trivialmente con ``(temp_max + temp_min)/2 − temp_base``
  parametrizado por cultivo. Buen candidato para enriquecer
  ``resumen_campania`` cuando lo evaluemos.

Sin endpoint específico para uso agrícola: todas las variables de arriba
salen del mismo ``/v1/archive``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# === Endpoints y variables ===

_URL_ARCHIVE: str = "https://archive-api.open-meteo.com/v1/archive"

# Variables daily a pedir.
_VARS_DAILY: tuple[str, ...] = (
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "relative_humidity_2m_mean",
    "shortwave_radiation_sum",
)


# === Configuración HTTP y cache ===

_TIMEOUT_S: int = 10
_REINTENTOS_MAX: int = 3
_BACKOFF_BASE_S: int = 1   # 1s, 2s, 4s — para 5xx y errores de red
_BACKOFF_RATE_LIMIT_S: int = 300  # 300s, 600s, 1200s — específico para 429
_DIR_CACHE: Path = Path("data/cache/clima")

# Throttling preventivo: garantiza una pausa mínima entre requests
# reales al endpoint /v1/archive (no afecta cache hits). Open-Meteo
# permite ~600 calls/min en plan free; 750 ms ≈ 80/min, imposible
# llegar al límite por minuto. Conservador a propósito tras un
# incidente previo de saturación de la cuota horaria (5 000/h).
_THROTTLE_MIN_S: float = 0.750
_ultimo_request_ts: float = 0.0

# Si faltan más del 5% de los días esperados en un resumen de campaña,
# se loguea un WARN para visibilidad.
_GAP_TOLERANCIA: float = 0.05

# Decimales a los que se redondean lat/lon para construir la clave de
# cache. 4 decimales ≈ 11 m, muy por debajo de los ~9 km de resolución
# del modelo ERA5. La API recibe los floats originales sin redondear.
_DECIMALES_COORD_CACHE: int = 4


# === Helpers internos ===

def _md5(texto: str) -> str:
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


def _get_con_reintentos(
    url: str, params: dict, contexto: str
) -> requests.Response:
    """
    GET con timeout 10 s y hasta 3 intentos con backoff por categoría:

    - **5xx y errores de red**: backoff base 1s × 2^intento (1, 2, 4 s).
    - **429 Too Many Requests** (rate limiting): backoff 60s × 2^intento
      (60, 120, 240 s). Honra el header ``Retry-After`` si está presente.
    - **Otros 4xx** (400, 401, 403, 404…): NO se reintentan, se propaga
      el error semántico.

    Aplica además un throttling preventivo de 150 ms entre requests
    reales al endpoint, para no disparar el rate limit por nuestra cuenta.
    """
    global _ultimo_request_ts
    ultimo_error: Optional[BaseException] = None
    espera = 0
    for intento in range(_REINTENTOS_MAX):
        # Throttling preventivo: 150 ms mínimo desde el último request real.
        delta = time.monotonic() - _ultimo_request_ts
        if delta < _THROTTLE_MIN_S:
            time.sleep(_THROTTLE_MIN_S - delta)
        _ultimo_request_ts = time.monotonic()

        try:
            resp = requests.get(url, params=params, timeout=_TIMEOUT_S)
        except (requests.Timeout, requests.ConnectionError) as e:
            ultimo_error = e
            espera = _BACKOFF_BASE_S * (2 ** intento)
        else:
            if resp.status_code < 400:
                return resp
            if resp.status_code == 429:
                # Rate limit: backoff largo. Honramos Retry-After si viene.
                retry_after = resp.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    espera = int(retry_after)
                else:
                    espera = _BACKOFF_RATE_LIMIT_S * (2 ** intento)
                ultimo_error = requests.HTTPError(
                    f"HTTP 429 (rate limit) en {contexto}", response=resp,
                )
            elif 400 <= resp.status_code < 500:
                # 4xx no-rate-limit: error semántico, no reintentamos.
                resp.raise_for_status()
            else:
                # 5xx: reintentar con backoff base.
                ultimo_error = requests.HTTPError(
                    f"HTTP {resp.status_code} en {contexto}", response=resp,
                )
                espera = _BACKOFF_BASE_S * (2 ** intento)

        if intento < _REINTENTOS_MAX - 1:
            logger.warning(
                "[Open-Meteo] Fallo en %s (intento %d/%d): %s. "
                "Reintento en %ds.",
                contexto, intento + 1, _REINTENTOS_MAX, ultimo_error, espera,
            )
            time.sleep(espera)

    raise RuntimeError(
        f"[Open-Meteo] Falló la consulta a {contexto} tras "
        f"{_REINTENTOS_MAX} intentos: {ultimo_error}"
    )


def _clave_cache(params: dict) -> str:
    """MD5 sobre los parámetros normalizados (None excluido, claves ordenadas)."""
    norm = {k: str(v) for k, v in params.items() if v is not None}
    return _md5(json.dumps(norm, ensure_ascii=False, sort_keys=True))


def _payload_a_dataframe(payload: dict) -> pd.DataFrame:
    """Convierte el JSON 'daily' devuelto por Open-Meteo a un DataFrame."""
    daily = payload.get("daily", {})
    return pd.DataFrame({
        "fecha": daily.get("time", []),
        "temp_media_c": daily.get("temperature_2m_mean", []),
        "temp_max_c": daily.get("temperature_2m_max", []),
        "temp_min_c": daily.get("temperature_2m_min", []),
        "precipitacion_mm": daily.get("precipitation_sum", []),
        "humedad_relativa": daily.get("relative_humidity_2m_mean", []),
        "radiacion_solar": daily.get("shortwave_radiation_sum", []),
    })


# === API pública ===

def obtener_clima_historico(
    latitud: float,
    longitud: float,
    fecha_inicio: str,
    fecha_fin: str,
) -> pd.DataFrame:
    """
    Devuelve clima histórico diario para un punto y un rango de fechas.

    Parámetros
    ----------
    latitud, longitud
        Coordenadas en grados decimales (WGS84). Open-Meteo "snappea"
        el punto a la celda de grilla más cercana del modelo ERA5
        (~9 km).
    fecha_inicio, fecha_fin
        Fechas en formato ``"YYYY-MM-DD"``, inclusivas en ambos extremos.

    Returns
    -------
    pandas.DataFrame con columnas:
        ``fecha, temp_media_c, temp_max_c, temp_min_c,
        precipitacion_mm, humedad_relativa, radiacion_solar``.
        ``fecha`` es string ISO ``YYYY-MM-DD`` para que el round-trip
        por el cache JSON sea trivial y sin sorpresas de timezone.

    Raises
    ------
    ValueError
        Si ``fecha_fin`` es posterior a hoy, o si ``fecha_inicio``
        es posterior a ``fecha_fin``.
    RuntimeError
        Si la API falla persistentemente tras los reintentos.
    """
    t0 = time.time()
    inicio_d = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
    fin_d = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
    hoy = date.today()
    if fin_d > hoy:
        raise ValueError(
            f"[Open-Meteo] fecha_fin={fecha_fin} es posterior a hoy ({hoy}). "
            f"La API histórica solo cubre datos pasados."
        )
    if inicio_d > fin_d:
        raise ValueError(
            f"[Open-Meteo] fecha_inicio={fecha_inicio} > fecha_fin={fecha_fin}."
        )

    # --- Clave de cache: coords redondeadas a 4 decimales ---
    params_cache = {
        "lat": round(float(latitud), _DECIMALES_COORD_CACHE),
        "lon": round(float(longitud), _DECIMALES_COORD_CACHE),
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "vars": ",".join(_VARS_DAILY),
    }
    _DIR_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = _DIR_CACHE / f"q_{_clave_cache(params_cache)}.json"

    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        df = _payload_a_dataframe(payload)
        elapsed = time.time() - t0
        logger.info(
            "[Open-Meteo] Cache hit (%s): %d filas en %.3fs. "
            "lat=%s lon=%s [%s..%s]",
            cache_path.name, len(df), elapsed,
            params_cache["lat"], params_cache["lon"],
            fecha_inicio, fecha_fin,
        )
        return df

    # --- Cache miss: request a la API con coords originales ---
    params_api = {
        "latitude": float(latitud),
        "longitude": float(longitud),
        "start_date": fecha_inicio,
        "end_date": fecha_fin,
        "daily": ",".join(_VARS_DAILY),
        "timezone": "auto",
    }
    resp = _get_con_reintentos(_URL_ARCHIVE, params_api, "archive (clima histórico)")
    payload = resp.json()
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    df = _payload_a_dataframe(payload)
    elapsed = time.time() - t0
    logger.info(
        "[Open-Meteo] Descarga: %d filas en %.2fs. "
        "lat=%s lon=%s [%s..%s]. Cache: %s",
        len(df), elapsed,
        params_api["latitude"], params_api["longitude"],
        fecha_inicio, fecha_fin, cache_path.name,
    )
    return df


def resumen_campania(
    latitud: float,
    longitud: float,
    anio_campania: int,
    tipo_ciclo: str,
) -> dict[str, Any]:
    """
    Devuelve un resumen agregado del clima durante un ciclo agrícola.

    Convención de fechas
    --------------------
    - ``tipo_ciclo='verano'``: 1-oct del año ``anio_campania`` al 31-mar
      del año siguiente. Cubre cultivos de verano (soja, maíz, sorgo,
      girasol, arroz, algodón, maní).
    - ``tipo_ciclo='invierno'``: 1-abr al 30-nov del mismo año. Cubre
      cultivos de invierno (trigo, cebada, avena, centeno).

    Parámetros
    ----------
    latitud, longitud
        Coordenadas del lote.
    anio_campania
        Año de inicio de la campaña (ej: 2023 para campaña 2023/2024).
    tipo_ciclo
        ``'verano'`` o ``'invierno'``.

    Returns
    -------
    dict con claves:
        - ``temp_media_c`` (°C): promedio simple de la temp media diaria.
        - ``temp_max_promedio_c`` (°C): promedio simple de la temp máxima.
        - ``temp_min_promedio_c`` (°C): promedio simple de la temp mínima.
        - ``precipitacion_total_mm`` (mm): suma de precipitación.
        - ``humedad_relativa_promedio`` (%): promedio de humedad relativa.
        - ``radiacion_solar_total`` (MJ/m²): suma de radiación solar.
        - ``dias_helada`` (int): días con ``temp_min < 0``.
        - ``dias_disponibles`` (int): días con dato real (sin NaN en
          temp_media, temp_max, temp_min, precipitacion).
        - ``dias_esperados`` (int): días que cubre el ciclo. Si
          ``dias_disponibles / dias_esperados < 0.95`` se loguea WARN.

    Raises
    ------
    ValueError
        Si ``tipo_ciclo`` no es 'verano' ni 'invierno', o si la fecha
        final del ciclo es posterior a hoy.
    """
    if tipo_ciclo == "verano":
        fecha_inicio = f"{anio_campania}-10-01"
        fecha_fin = f"{anio_campania + 1}-03-31"
    elif tipo_ciclo == "invierno":
        fecha_inicio = f"{anio_campania}-04-01"
        fecha_fin = f"{anio_campania}-11-30"
    else:
        raise ValueError(
            f"[Open-Meteo] tipo_ciclo='{tipo_ciclo}' inválido. "
            f"Usá 'verano' o 'invierno'."
        )

    df = obtener_clima_historico(latitud, longitud, fecha_inicio, fecha_fin)

    inicio_d = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
    fin_d = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
    dias_esperados = (fin_d - inicio_d).days + 1

    columnas_clave = [
        "temp_media_c", "temp_max_c", "temp_min_c", "precipitacion_mm",
    ]
    dias_disponibles = int(df[columnas_clave].notna().all(axis=1).sum())

    if dias_esperados > 0:
        gap_relativo = 1 - dias_disponibles / dias_esperados
        if gap_relativo > _GAP_TOLERANCIA:
            logger.warning(
                "[Open-Meteo] Gap de cobertura > %.0f%% en campaña "
                "%d/%s (lat=%s, lon=%s): %d/%d días con dato.",
                _GAP_TOLERANCIA * 100, anio_campania, tipo_ciclo,
                latitud, longitud,
                dias_disponibles, dias_esperados,
            )

    resumen: dict[str, Any] = {
        "temp_media_c": float(df["temp_media_c"].mean()),
        "temp_max_promedio_c": float(df["temp_max_c"].mean()),
        "temp_min_promedio_c": float(df["temp_min_c"].mean()),
        "precipitacion_total_mm": float(df["precipitacion_mm"].sum()),
        "humedad_relativa_promedio": float(df["humedad_relativa"].mean()),
        "radiacion_solar_total": float(df["radiacion_solar"].sum()),
        "dias_helada": int((df["temp_min_c"] < 0).sum()),
        "dias_disponibles": dias_disponibles,
        "dias_esperados": dias_esperados,
    }
    logger.info(
        "[Open-Meteo] Resumen %d/%s (lat=%s, lon=%s): %d/%d días, "
        "T_media=%.1f°C, lluvia=%.0fmm, heladas=%d.",
        anio_campania, tipo_ciclo, latitud, longitud,
        dias_disponibles, dias_esperados,
        resumen["temp_media_c"], resumen["precipitacion_total_mm"],
        resumen["dias_helada"],
    )
    return resumen


# === Bloque de prueba ===

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    casos = [
        ("Pergamino verano 2023 (soja)",   -33.89, -60.57, 2023, "verano"),
        ("Pergamino invierno 2023 (trigo)", -33.89, -60.57, 2023, "invierno"),
        ("Río Cuarto verano 2022 (soja)",  -33.13, -64.35, 2022, "verano"),
    ]

    print("\n=== Primera corrida ===")
    resultados: list[tuple[str, dict[str, Any]]] = []
    for etiqueta, lat, lon, anio, ciclo in casos:
        r = resumen_campania(lat, lon, anio, ciclo)
        resultados.append((etiqueta, r))

    df_cmp = pd.DataFrame({et: r for et, r in resultados})
    print("\n=== Comparativa lado a lado ===")
    print(df_cmp.to_string(float_format=lambda x: f"{x:,.2f}"))

    print("\n=== Segunda corrida (debería golpear cache) ===")
    for etiqueta, lat, lon, anio, ciclo in casos:
        resumen_campania(lat, lon, anio, ciclo)
