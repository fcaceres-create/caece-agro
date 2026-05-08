"""
Cliente de SoilGrids v2.0 (ISRIC).

Endpoint: ``https://rest.isric.org/soilgrids/v2.0/properties/query``

No requiere API key. Sin paginación: una sola respuesta JSON por
consulta. Resolución espacial nativa: ~250 m (pero la profundidad y la
agregación se manejan acá).

Variables solicitadas a la API
------------------------------
- ``clay``  (g/kg, divisor 10 → %)
- ``sand``  (g/kg, divisor 10 → %)
- ``silt``  (g/kg, divisor 10 → %)
- ``soc``   (dg/kg, divisor 10 → g/kg)  — Soil Organic Carbon
- ``phh2o`` (pH·10, divisor 10 → pH)
- ``cec``   (mmol(c)/kg, divisor 10 → cmol(c)/kg)

Profundidades pedidas: ``0-5cm``, ``5-15cm``, ``15-30cm``. Se agregan
con un promedio ponderado por espesor (5/30, 10/30, 15/30) a un valor
único 0-30 cm, que es la zona radicular efectiva relevante para los
cultivos extensivos cubiertos por AgroSmart. Si una capa está sin dato,
los pesos se renormalizan sobre las capas disponibles.

Conversiones API → proyecto
---------------------------
- ``arcilla_pct = clay_API / 10``                    (g/kg → %)
- ``arena_pct  = sand_API / 10``
- ``limo_pct   = silt_API / 10``
- ``ph         = phh2o_API / 10``
- ``cec        = cec_API / 10``                      (mmol/kg → cmol/kg)
- ``materia_organica_pct = soc_API × 0.01724``       (ver abajo)

Materia orgánica
----------------
La API entrega Soil Organic Carbon (SOC) escalado en dg/kg
(``valor_API``). Para llevarlo a porcentaje de materia orgánica del
suelo se aplica el factor de Van Bemmelen 1.724:

    SOC_g_por_kg = valor_API / 10
    SOC_pct      = SOC_g_por_kg / 10              (g/kg → %)
    MO_pct       = SOC_pct × 1.724

Combinado: ``MO_pct = valor_API × 0.01724``. Si en el futuro hace falta
el SOC crudo, conviene derivarlo desde el cache (que guarda el valor ya
convertido a SOC g/kg en ``_obtener_capas_brutas`` antes del agregado)
o llamar al endpoint directo.

Manejo de coordenadas sin datos (fallback en dos anillos)
---------------------------------------------------------
La grilla SoilGrids tiene "agujeros" sin datos en zonas urbanas,
peri-urbanas, agua, roca expuesta, etc. Caracterización empírica:
en el caso de Pergamino (-33.89, -60.57) el agujero mide ~6×4 km
(probable exclusión de la zona urbana). Si la coordenada exacta
solicitada cae adentro, la API devuelve ``mean: null`` para todas
las propiedades.

El fallback opera en dos anillos concéntricos consultados en paralelo
con ``ThreadPoolExecutor`` (8 hilos), para mantener latencia razonable
incluso si hay que iterar muchos puntos en la consolidación:

- **Anillo 1** (≈ 1.1 km): jitter ±0.01° en N/S/E/O y 4 diagonales.
  Cubre coordenadas que caen en píxeles "no data" aislados o en bordes
  de agujeros chicos.
- **Anillo 2** (≈ 3.3 km): jitter ±0.03°. Se activa solo si el anillo 1
  vino entero null. Cubre agujeros más grandes, típicamente alrededor
  de ciudades intermedias como Pergamino o Río Cuarto.

En ambos anillos se promedian SOLO los vecinos que devuelven datos
válidos. Si tras el anillo 2 sigue todo null, se devuelve NaN en todas
las propiedades y se loguea un WARN.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import logging
import math
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# === Endpoint y vocabulario API ===

_URL_QUERY: str = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# Propiedades a pedir, en el orden que aparecen en la lista interna.
_PROPIEDADES_API: tuple[str, ...] = (
    "clay", "sand", "silt", "soc", "phh2o", "cec",
)

# Profundidades a pedir y sus espesores (cm) para el promedio ponderado.
_DEPTHS_API: tuple[str, ...] = ("0-5cm", "5-15cm", "15-30cm")
_PESO_DEPTH_CM: dict[str, int] = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}

# Mapeo API → claves del dict resultado y factor de conversión a unidad
# del proyecto. La conversión se aplica DESPUÉS del agregado por capas.
# Para SOC el factor combina divisor d_factor=10 + g/kg→% + Van Bemmelen.
_CONVERSION: dict[str, tuple[str, float]] = {
    "clay":  ("arcilla_pct",            1 / 10),
    "sand":  ("arena_pct",              1 / 10),
    "silt":  ("limo_pct",               1 / 10),
    "soc":   ("materia_organica_pct",   0.01724),
    "phh2o": ("ph",                     1 / 10),
    "cec":   ("cec",                    1 / 10),
}


# === Configuración HTTP, cache y fallback ===

_TIMEOUT_S: int = 10
_REINTENTOS_MAX: int = 3
_BACKOFF_BASE_S: int = 1  # 1s, 2s, 4s — para 5xx y errores de red
_BACKOFF_RATE_LIMIT_S: int = 60  # 60s, 120s, 240s — específico para 429
_DIR_CACHE: Path = Path("data/cache/suelo")

# Decimales a los que se redondean lat/lon para construir la clave de
# cache. La grilla nativa de SoilGrids es ~250 m (~0.0025°), así que
# 4 decimales (~11 m) capturan el píxel sin colisiones espurias.
_DECIMALES_COORD_CACHE: int = 4

# Offsets de los anillos del fallback, en grados decimales.
#   Anillo 1 ≈ 1.1 km, primer intento si la coord exacta da null.
#   Anillo 2 ≈ 3.3 km, solo si el anillo 1 viene entero vacío.
_OFFSET_ANILLO_1: float = 0.01
_OFFSET_ANILLO_2: float = 0.03

# Hilos de paralelización en cada anillo (un hilo por vecino).
_MAX_WORKERS: int = 8

# Versión del esquema del dict cacheado. Se incluye en la clave MD5; al
# bumpearla, los caches viejos quedan ignorados sin necesidad de borrar.
_CACHE_SCHEMA_VERSION: int = 2


def _offsets_anillo(offset: float) -> tuple[tuple[float, float], ...]:
    """Devuelve los 8 offsets (N, S, E, O + diagonales) para un radio dado."""
    return (
        ( offset,    0.0),   # E
        (-offset,    0.0),   # O
        (   0.0,  offset),   # N
        (   0.0, -offset),   # S
        ( offset,  offset),  # NE
        ( offset, -offset),  # SE
        (-offset,  offset),  # NO
        (-offset, -offset),  # SO
    )


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
    """
    ultimo_error: Optional[BaseException] = None
    espera = 0
    for intento in range(_REINTENTOS_MAX):
        try:
            resp = requests.get(url, params=params, timeout=_TIMEOUT_S)
        except (requests.Timeout, requests.ConnectionError) as e:
            ultimo_error = e
            espera = _BACKOFF_BASE_S * (2 ** intento)
        else:
            if resp.status_code < 400:
                return resp
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    espera = int(retry_after)
                else:
                    espera = _BACKOFF_RATE_LIMIT_S * (2 ** intento)
                ultimo_error = requests.HTTPError(
                    f"HTTP 429 (rate limit) en {contexto}", response=resp,
                )
            elif 400 <= resp.status_code < 500:
                resp.raise_for_status()
            else:
                ultimo_error = requests.HTTPError(
                    f"HTTP {resp.status_code} en {contexto}", response=resp,
                )
                espera = _BACKOFF_BASE_S * (2 ** intento)

        if intento < _REINTENTOS_MAX - 1:
            logger.warning(
                "[SoilGrids] Fallo en %s (intento %d/%d): %s. "
                "Reintento en %ds.",
                contexto, intento + 1, _REINTENTOS_MAX, ultimo_error, espera,
            )
            time.sleep(espera)

    raise RuntimeError(
        f"[SoilGrids] Falló la consulta a {contexto} tras "
        f"{_REINTENTOS_MAX} intentos: {ultimo_error}"
    )


def _clave_cache(lat: float, lon: float) -> str:
    """MD5 estable a partir de la coord ORIGINAL redondeada a 4 decimales."""
    payload = json.dumps({
        "v": _CACHE_SCHEMA_VERSION,
        "lat": round(float(lat), _DECIMALES_COORD_CACHE),
        "lon": round(float(lon), _DECIMALES_COORD_CACHE),
        "props": list(_PROPIEDADES_API),
        "depths": list(_DEPTHS_API),
    }, sort_keys=True)
    return _md5(payload)


def _obtener_capas_brutas(
    lat: float, lon: float,
) -> dict[tuple[str, str], Optional[float]]:
    """
    Pega un GET a SoilGrids para un punto y devuelve un mapping
    ``(property, depth_label) → mean`` (None si la API devolvió null).

    Esta función está aislada y bien definida para que en el futuro,
    si hace falta exponer los datos crudos por capa, baste con
    promoverla a la API pública.
    """
    params = {
        "lon": float(lon),
        "lat": float(lat),
        "property": list(_PROPIEDADES_API),
        "depth": list(_DEPTHS_API),
        "value": "mean",
    }
    resp = _get_con_reintentos(
        _URL_QUERY, params, f"properties/query lat={lat:.4f} lon={lon:.4f}",
    )
    payload = resp.json()

    out: dict[tuple[str, str], Optional[float]] = {}
    for layer in payload.get("properties", {}).get("layers", []):
        prop = layer.get("name")
        for d in layer.get("depths", []):
            label = d.get("label")
            mean = d.get("values", {}).get("mean")
            out[(prop, label)] = mean
    return out


def _agregar_capas_a_0_30cm(
    valores_capas: dict[str, Optional[float]],
) -> Optional[float]:
    """
    Promedio ponderado por espesor de capa, normalizado sobre las capas
    con dato. Devuelve None si todas las capas están vacías.
    """
    pesos_validos = {
        d: _PESO_DEPTH_CM[d]
        for d, v in valores_capas.items()
        if v is not None
    }
    if not pesos_validos:
        return None
    num = sum(_PESO_DEPTH_CM[d] * v for d, v in valores_capas.items() if v is not None)
    den = sum(pesos_validos.values())
    return num / den


def _consolidar_por_punto(
    crudos: dict[tuple[str, str], Optional[float]],
) -> tuple[dict[str, Optional[float]], int]:
    """
    Agrega los valores por capa a un único valor 0-30 cm por propiedad.
    Devuelve también ``capas_disponibles``: cuántas de las 3 capas
    tenían al menos una propiedad con dato válido.
    """
    capas_con_dato: set[str] = set()
    consolidado: dict[str, Optional[float]] = {}
    for prop in _PROPIEDADES_API:
        capas = {d: crudos.get((prop, d)) for d in _DEPTHS_API}
        for d, v in capas.items():
            if v is not None:
                capas_con_dato.add(d)
        consolidado[prop] = _agregar_capas_a_0_30cm(capas)
    return consolidado, len(capas_con_dato)


def _todos_null(consolidado: dict[str, Optional[float]]) -> bool:
    return all(v is None for v in consolidado.values())


def _centroide(
    coords: list[tuple[float, float]],
) -> Optional[tuple[float, float]]:
    """Centroide aritmético redondeado, o None si la lista está vacía."""
    if not coords:
        return None
    return (
        round(sum(c[0] for c in coords) / len(coords), _DECIMALES_COORD_CACHE),
        round(sum(c[1] for c in coords) / len(coords), _DECIMALES_COORD_CACHE),
    )


def _consultar_anillo(
    lat_origen: float, lon_origen: float, offset: float,
) -> tuple[
    dict[tuple[str, str], Optional[float]],
    list[tuple[float, float]],
]:
    """
    Consulta los 8 vecinos de un anillo a ``offset`` grados, en paralelo
    con un ThreadPoolExecutor. Promedia por (propiedad, profundidad)
    sobre los vecinos que devolvieron datos válidos.

    Returns
    -------
    crudos_promediados
        ``(prop, depth) → mean | None``. None si ningún vecino aportó
        dato para esa combinación.
    coords_validos
        Coordenadas de los vecinos que tuvieron al menos un dato.
        Sirve para calcular ``coordenadas_efectivas``.
    """
    puntos = [
        (lat_origen + dlat, lon_origen + dlon)
        for dlat, dlon in _offsets_anillo(offset)
    ]

    agregados: dict[tuple[str, str], list[float]] = {}
    coords_validos: list[tuple[float, float]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        futures = {
            ex.submit(_obtener_capas_brutas, lat_v, lon_v): (lat_v, lon_v)
            for lat_v, lon_v in puntos
        }
        for fut in concurrent.futures.as_completed(futures):
            lat_v, lon_v = futures[fut]
            try:
                crudos_v = fut.result()
            except RuntimeError as e:
                logger.warning(
                    "[SoilGrids] Vecino (%.4f, %.4f) falló y se omite: %s",
                    lat_v, lon_v, e,
                )
                continue
            tuvo_dato = False
            for k, v in crudos_v.items():
                if v is not None:
                    agregados.setdefault(k, []).append(v)
                    tuvo_dato = True
            if tuvo_dato:
                coords_validos.append((lat_v, lon_v))

    crudos_promediados: dict[tuple[str, str], Optional[float]] = {}
    for prop in _PROPIEDADES_API:
        for depth in _DEPTHS_API:
            vs = agregados.get((prop, depth), [])
            crudos_promediados[(prop, depth)] = (
                sum(vs) / len(vs) if vs else None
            )
    return crudos_promediados, coords_validos


# === API pública ===

def obtener_propiedades_suelo(
    latitud: float, longitud: float,
) -> dict[str, Any]:
    """
    Devuelve propiedades de suelo agregadas a 0-30 cm para una coordenada.

    Parámetros
    ----------
    latitud, longitud
        Coordenadas en grados decimales (WGS84).

    Returns
    -------
    dict con claves:
        - ``arcilla_pct`` (%)
        - ``arena_pct`` (%)
        - ``limo_pct`` (%)
        - ``materia_organica_pct`` (%)  — derivada como SOC × 1.724
          (factor Van Bemmelen). Ver docstring del módulo para detalle.
        - ``ph`` (-)
        - ``cec`` (cmol(c)/kg)
        - ``profundidad_cm``: ``"0-30"``
        - ``coordenadas_solicitadas``: tupla ``(lat, lon)`` original.
        - ``coordenadas_efectivas``: tupla ``(lat, lon)``. Si no hubo
          fallback, igual a ``coordenadas_solicitadas``. Si hubo
          fallback, es el centroide de los vecinos que aportaron datos.
        - ``fallback_usado`` (bool): True si la coord original no
          tenía datos y se activó alguno de los dos anillos.
        - ``anillo_fallback`` (int):
            * ``0``  → sin fallback, datos vinieron de la coord exacta;
            * ``1``  → rescató el anillo 1 (±0.01°, ~1.1 km);
            * ``2``  → rescató el anillo 2 (±0.03°, ~3.3 km);
            * ``-1`` → ningún anillo rescató (todas las propiedades NaN).
        - ``capas_disponibles`` (int 0..3): cuántas de las 3 capas
          (0-5, 5-15, 15-30 cm) tuvieron al menos un dato válido.

    Cualquier propiedad sin dato (ni en la coord original ni en los
    vecinos del fallback) se devuelve como ``NaN`` y se loguea un WARN.

    Raises
    ------
    RuntimeError
        Si la API falla persistentemente tras los reintentos.
    """
    t0 = time.time()
    coord_orig = (round(float(latitud), _DECIMALES_COORD_CACHE),
                  round(float(longitud), _DECIMALES_COORD_CACHE))

    # --- Cache hit ---
    _DIR_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = _DIR_CACHE / f"q_{_clave_cache(latitud, longitud)}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        # Tuplas se serializan como listas en JSON; las restauro.
        cached["coordenadas_solicitadas"] = tuple(cached["coordenadas_solicitadas"])
        cached["coordenadas_efectivas"] = tuple(cached["coordenadas_efectivas"])
        elapsed = time.time() - t0
        logger.info(
            "[SoilGrids] Cache hit (%s): lat=%s lon=%s en %.3fs. "
            "fallback_usado=%s, capas_disponibles=%d.",
            cache_path.name, coord_orig[0], coord_orig[1], elapsed,
            cached["fallback_usado"], cached["capas_disponibles"],
        )
        return cached

    # --- Query original ---
    crudos = _obtener_capas_brutas(latitud, longitud)
    consolidado, capas_disponibles = _consolidar_por_punto(crudos)
    fallback_usado = False
    anillo_fallback = 0  # 0 = sin fallback; 1 ó 2 = anillo que rescató; -1 = ninguno
    coord_efectiva: tuple[float, float] = coord_orig

    # --- Fallback en dos anillos paralelos si todo vino null ---
    if _todos_null(consolidado):
        fallback_usado = True

        # Anillo 1
        logger.info(
            "[SoilGrids] Coord (%s, %s) sin datos; intentando anillo 1 "
            "(±%g°, %d vecinos en paralelo).",
            latitud, longitud, _OFFSET_ANILLO_1, _MAX_WORKERS,
        )
        crudos_a1, coords_a1 = _consultar_anillo(
            latitud, longitud, _OFFSET_ANILLO_1,
        )
        cons_a1, capas_a1 = _consolidar_por_punto(crudos_a1)

        if not _todos_null(cons_a1):
            consolidado = cons_a1
            capas_disponibles = capas_a1
            anillo_fallback = 1
            centro = _centroide(coords_a1)
            if centro is not None:
                coord_efectiva = centro
            logger.info(
                "[SoilGrids] Anillo 1 rescató: %d/%d vecinos válidos.",
                len(coords_a1), _MAX_WORKERS,
            )
        else:
            # Anillo 2
            logger.info(
                "[SoilGrids] Anillo 1 vacío; probando anillo 2 "
                "(±%g°, %d vecinos en paralelo).",
                _OFFSET_ANILLO_2, _MAX_WORKERS,
            )
            crudos_a2, coords_a2 = _consultar_anillo(
                latitud, longitud, _OFFSET_ANILLO_2,
            )
            cons_a2, capas_a2 = _consolidar_por_punto(crudos_a2)

            if not _todos_null(cons_a2):
                consolidado = cons_a2
                capas_disponibles = capas_a2
                anillo_fallback = 2
                centro = _centroide(coords_a2)
                if centro is not None:
                    coord_efectiva = centro
                logger.info(
                    "[SoilGrids] Anillo 2 rescató: %d/%d vecinos válidos.",
                    len(coords_a2), _MAX_WORKERS,
                )
            else:
                anillo_fallback = -1
                consolidado = cons_a2  # todo None
                capas_disponibles = 0
                coord_efectiva = coord_orig
                logger.warning(
                    "[SoilGrids] Ningún anillo rescató para coord (%s, %s). "
                    "Devolviendo NaN en todas las propiedades.",
                    coord_orig[0], coord_orig[1],
                )

    # --- Conversión a unidades del proyecto ---
    resultado: dict[str, Any] = {}
    propiedades_faltantes: list[str] = []
    for prop_api, (clave_proyecto, factor) in _CONVERSION.items():
        v = consolidado.get(prop_api)
        if v is None:
            resultado[clave_proyecto] = math.nan
            propiedades_faltantes.append(clave_proyecto)
        else:
            resultado[clave_proyecto] = v * factor

    resultado["profundidad_cm"] = "0-30"
    resultado["coordenadas_solicitadas"] = coord_orig
    resultado["coordenadas_efectivas"] = coord_efectiva
    resultado["fallback_usado"] = fallback_usado
    resultado["anillo_fallback"] = anillo_fallback
    resultado["capas_disponibles"] = capas_disponibles

    if propiedades_faltantes:
        logger.warning(
            "[SoilGrids] Propiedades sin dato tras fallback en (%s, %s): %s.",
            coord_orig[0], coord_orig[1], propiedades_faltantes,
        )

    # --- Cache (clave: coord ORIGINAL) ---
    cache_path.write_text(
        json.dumps(resultado, ensure_ascii=False), encoding="utf-8",
    )
    elapsed = time.time() - t0
    logger.info(
        "[SoilGrids] Consulta nueva (%s, %s) en %.2fs. "
        "fallback_usado=%s, capas_disponibles=%d, faltantes=%d. Cache: %s",
        coord_orig[0], coord_orig[1], elapsed,
        fallback_usado, capas_disponibles, len(propiedades_faltantes),
        cache_path.name,
    )
    return resultado


# === Bloque de prueba ===

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    casos = [
        ("Pergamino exacto (-33.89, -60.57)", -33.89, -60.57),
        ("Pergamino jitter (-33.9, -60.5)",   -33.9,  -60.5),
        ("Río Cuarto (-33.13, -64.35)",       -33.13, -64.35),
    ]

    print("\n=== Primera corrida ===")
    resultados: list[tuple[str, dict[str, Any]]] = []
    for et, lat, lon in casos:
        r = obtener_propiedades_suelo(lat, lon)
        resultados.append((et, r))

    campos_num = [
        "arcilla_pct", "arena_pct", "limo_pct",
        "materia_organica_pct", "ph", "cec",
    ]
    df_num = pd.DataFrame(
        {et: {k: r[k] for k in campos_num} for et, r in resultados}
    )
    print("\n=== Comparativa de propiedades (0-30 cm) ===")
    print(df_num.to_string(float_format=lambda x: f"{x:,.2f}"))

    print("\n=== Metadatos ===")
    for et, r in resultados:
        print(f"\n{et}:")
        print(f"  coordenadas_solicitadas: {r['coordenadas_solicitadas']}")
        print(f"  coordenadas_efectivas:   {r['coordenadas_efectivas']}")
        print(f"  fallback_usado:          {r['fallback_usado']}")
        print(f"  anillo_fallback:         {r['anillo_fallback']}")
        print(f"  capas_disponibles:       {r['capas_disponibles']}")

    print("\n=== Segunda corrida (debería golpear cache) ===")
    for et, lat, lon in casos:
        obtener_propiedades_suelo(lat, lon)
