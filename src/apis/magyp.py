"""
Cliente de la API del MAGyP (Ministerio de Agricultura, Ganadería y Pesca
de la Nación Argentina).

Expone funciones para descargar series históricas de superficie sembrada,
superficie cosechada, producción y rendimiento por cultivo, provincia y
departamento. Usa cache en disco bajo data/cache/magyp/ con clave MD5
derivada de los parámetros de consulta.

Endpoint
--------
- CSV maestro de "estimaciones agrícolas" en datos.magyp.gob.ar (un único
  archivo con todos los cultivos, provincias y departamentos desde 1969).
- Fallback vía CKAN package_show si la URL primaria queda obsoleta.

Granularidad geográfica
-----------------------
La API expone "departamento" como nombre genérico de la unidad geográfica
intra-provincial. En Buenos Aires popularmente se llama "partido" pero
en el resto del país es "departamento". El módulo respeta el nombre
universal: la columna devuelta es ``departamento``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import unicodedata
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# === Constantes públicas ===

CULTIVOS_SOPORTADOS: tuple[str, ...] = (
    "soja",
    "maiz",
    "trigo",
    "girasol",
    "cebada",
    "sorgo",
    "avena",
    "centeno",
    "arroz",
    "algodon",
    "mani",
)
"""Lista canónica de cultivos extensivos cubiertos por AgroSmart."""


# === Mapeo cultivo canónico ↔ nombre real en la API ===

# Justificación de las variantes "total":
#   - "soja total" agrega "soja 1ra" + "soja 2da". Usar 1ra/2da por
#     separado produciría doble conteo cuando ambas se siembran en el
#     mismo departamento durante la misma campaña.
#   - "trigo total" incluye "trigo candeal" (cultivo minoritario, ~1%
#     del área). El proyecto trabaja con trigo como cultivo único.
#   - "cebada total" agrega "cebada cervecera" + "cebada forrajera".
#     Se usa el agregado por consistencia con los otros 10 cultivos.
_CULTIVO_API: dict[str, str] = {
    "soja": "soja total",
    "maiz": "maíz",
    "trigo": "trigo total",
    "girasol": "girasol",
    "cebada": "cebada total",
    "sorgo": "sorgo",
    "avena": "avena",
    "centeno": "centeno",
    "arroz": "arroz",
    "algodon": "algodón",
    "mani": "maní",
}
_API_A_CANONICO: dict[str, str] = {v: k for k, v in _CULTIVO_API.items()}


# === Endpoints ===

# URL primaria del CSV maestro. Incluye año-mes en el nombre del archivo,
# que cambia cuando MAGyP publica un nuevo corte. Si esta URL devuelve
# 404, se resuelve dinámicamente vía CKAN (package_show).
_URL_CSV_PRIMARIA: str = (
    "https://datos.magyp.gob.ar/dataset/"
    "9e1e77ba-267e-4eaa-a59f-3296e86b5f36/resource/"
    "95d066e6-8a0f-4a80-b59d-6f28f88eacd5/download/"
    "estimaciones-agricolas-2026-03.csv"
)
_URL_CKAN_PACKAGE_SHOW: str = (
    "https://datos.magyp.gob.ar/api/3/action/package_show"
    "?id=estimaciones-agricolas"
)
# ID estable del recurso "estimaciones agrícolas serie completa" en CKAN.
_RESOURCE_ID_MAESTRO: str = "95d066e6-8a0f-4a80-b59d-6f28f88eacd5"


# === Configuración HTTP y cache ===

_TIMEOUT_S: int = 10
_REINTENTOS_MAX: int = 3
_BACKOFF_BASE_S: int = 1  # 1s, 2s, 4s — para 5xx y errores de red
_BACKOFF_RATE_LIMIT_S: int = 60  # 60s, 120s, 240s — específico para 429
_DIR_CACHE: Path = Path("data/cache/magyp")


# === Helpers internos ===

def _md5(texto: str) -> str:
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


def _normalizar_str(s: str) -> str:
    """Minúsculas, sin tildes, strip — para comparaciones tolerantes."""
    s = s.strip().lower()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _get_con_reintentos(url: str, contexto: str) -> requests.Response:
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
            resp = requests.get(url, timeout=_TIMEOUT_S)
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
                # 4xx no-rate-limit: error semántico, no reintentamos.
                resp.raise_for_status()
            else:
                ultimo_error = requests.HTTPError(
                    f"HTTP {resp.status_code} en {contexto}", response=resp,
                )
                espera = _BACKOFF_BASE_S * (2 ** intento)

        if intento < _REINTENTOS_MAX - 1:
            logger.warning(
                "[MAGyP] Fallo en %s (intento %d/%d): %s. Reintento en %ds.",
                contexto, intento + 1, _REINTENTOS_MAX, ultimo_error, espera,
            )
            time.sleep(espera)

    raise RuntimeError(
        f"[MAGyP] Falló la consulta a {contexto} tras {_REINTENTOS_MAX} "
        f"intentos: {ultimo_error}"
    )


def _resolver_url_csv_maestro() -> str:
    """
    Resuelve la URL vigente del CSV maestro consultando el catálogo CKAN.
    Se invoca como fallback cuando la URL primaria devuelve 404.
    """
    logger.warning(
        "[MAGyP] URL primaria devolvió 404, resolviendo URL vigente vía CKAN: %s",
        _URL_CKAN_PACKAGE_SHOW,
    )
    resp = _get_con_reintentos(_URL_CKAN_PACKAGE_SHOW, "CKAN package_show")
    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError("[MAGyP] CKAN devolvió success=false al resolver el dataset.")
    for recurso in payload["result"]["resources"]:
        if recurso.get("id") == _RESOURCE_ID_MAESTRO:
            url = recurso.get("url")
            if not url:
                raise RuntimeError("[MAGyP] Recurso CKAN sin URL.")
            logger.info("[MAGyP] URL vigente del CSV maestro: %s", url)
            return url
    raise RuntimeError(
        f"[MAGyP] No se encontró el recurso {_RESOURCE_ID_MAESTRO} en CKAN."
    )


def _leer_csv_maestro(path: Path) -> pd.DataFrame:
    """Lee el CSV maestro preservando como string las columnas categóricas."""
    return pd.read_csv(
        path,
        dtype={
            "cultivo": "string",
            "anio": "string",
            "campania": "string",
            "provincia": "string",
            "provincia_id": "string",
            "departamento": "string",
            "departamento_id": "string",
        },
    )


def _descargar_csv_maestro() -> pd.DataFrame:
    """
    Descarga (o lee del cache) el CSV maestro y lo devuelve como DataFrame.
    Cache: data/cache/magyp/maestro_<md5_url>.csv. Si la URL primaria
    devuelve 404, se resuelve dinámicamente vía CKAN y la nueva URL se
    cachea bajo su propio MD5.
    """
    _DIR_CACHE.mkdir(parents=True, exist_ok=True)

    # Intento de cache hit con la URL primaria.
    url_efectiva = _URL_CSV_PRIMARIA
    cache_path = _DIR_CACHE / f"maestro_{_md5(url_efectiva)}.csv"
    if cache_path.exists():
        logger.info("[MAGyP] CSV maestro desde cache: %s", cache_path.name)
        return _leer_csv_maestro(cache_path)

    t0 = time.time()
    try:
        resp = _get_con_reintentos(_URL_CSV_PRIMARIA, "CSV maestro (URL primaria)")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            url_efectiva = _resolver_url_csv_maestro()
            cache_path = _DIR_CACHE / f"maestro_{_md5(url_efectiva)}.csv"
            if cache_path.exists():
                logger.info(
                    "[MAGyP] CSV maestro desde cache (URL CKAN): %s",
                    cache_path.name,
                )
                return _leer_csv_maestro(cache_path)
            resp = _get_con_reintentos(url_efectiva, "CSV maestro (URL CKAN)")
        else:
            raise

    cache_path.write_bytes(resp.content)
    df = _leer_csv_maestro(cache_path)
    elapsed = time.time() - t0
    logger.info(
        "[MAGyP] CSV maestro descargado: %d filas en %.2fs.",
        len(df), elapsed,
    )
    return df


def _clave_cache_consulta(params: dict) -> str:
    """MD5 sobre los parámetros normalizados (None excluido, claves ordenadas)."""
    norm = {k: str(v) for k, v in params.items() if v is not None}
    return _md5(json.dumps(norm, ensure_ascii=False, sort_keys=True))


# === API pública ===

def obtener_estimaciones(
    cultivo: str,
    provincia: Optional[str] = None,
    departamento: Optional[str] = None,
    campania_desde: Optional[str] = None,
    campania_hasta: Optional[str] = None,
) -> pd.DataFrame:
    """
    Devuelve estimaciones agrícolas para un cultivo, opcionalmente
    filtradas por provincia, departamento y rango de campañas.

    Parámetros
    ----------
    cultivo
        Nombre canónico del cultivo (ver ``CULTIVOS_SOPORTADOS``,
        ej: ``"soja"``) o el nombre real de la API (ej: ``"soja total"``).
        El módulo acepta ambos.
    provincia, departamento
        Filtros opcionales (case-insensitive y sin tildes). Si son None,
        no se filtra por esa dimensión.
    campania_desde, campania_hasta
        Rango de campañas en formato ``"YYYY/YYYY"`` (ej: ``"2015/2016"``),
        inclusivos en ambos extremos. Si son None, no se filtra.

    Returns
    -------
    pandas.DataFrame con columnas:
        ``cultivo, provincia, departamento, campania,
        superficie_sembrada_ha, superficie_cosechada_ha,
        produccion_tn, rendimiento_kg_ha``

    Raises
    ------
    ValueError
        Si ``cultivo`` no está soportado.
    RuntimeError
        Si todas las fuentes (URL primaria + CKAN) fallan.
    """
    t0 = time.time()

    # --- Resolver cultivo: aceptamos canónico o nombre completo de API. ---
    cultivo_norm = cultivo.strip().lower()
    if cultivo_norm in _CULTIVO_API:
        cultivo_canonico = cultivo_norm
        cultivo_api = _CULTIVO_API[cultivo_norm]
    elif cultivo_norm in _API_A_CANONICO:
        cultivo_canonico = _API_A_CANONICO[cultivo_norm]
        cultivo_api = cultivo_norm
    else:
        raise ValueError(
            f"[MAGyP] Cultivo '{cultivo}' no soportado. "
            f"Usá uno de: {', '.join(CULTIVOS_SOPORTADOS)}"
        )

    params = {
        "cultivo": cultivo_canonico,
        "provincia": provincia,
        "departamento": departamento,
        "campania_desde": campania_desde,
        "campania_hasta": campania_hasta,
    }

    # --- Cache por consulta (JSON) ---
    _DIR_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = _DIR_CACHE / f"q_{_clave_cache_consulta(params)}.json"

    if cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        df = pd.DataFrame(data)
        elapsed = time.time() - t0
        logger.info(
            "[MAGyP] Consulta desde cache (%s): %d filas en %.3fs. Params=%s",
            cache_path.name, len(df), elapsed, params,
        )
        return df

    # --- Cache miss: descargar maestro + filtrar en memoria ---
    df_m = _descargar_csv_maestro()
    df = df_m[df_m["cultivo"] == cultivo_api].copy()

    if provincia is not None:
        clave = _normalizar_str(provincia)
        df = df[df["provincia"].astype(str).map(_normalizar_str) == clave]
    if departamento is not None:
        clave = _normalizar_str(departamento)
        df = df[df["departamento"].astype(str).map(_normalizar_str) == clave]
    if campania_desde is not None:
        df = df[df["campania"] >= campania_desde]
    if campania_hasta is not None:
        df = df[df["campania"] <= campania_hasta]

    df = df.rename(columns={
        "produccion_tm": "produccion_tn",
        "rendimiento_kgxha": "rendimiento_kg_ha",
    })
    # Reemplazo del nombre interno de la API por el canónico del proyecto.
    df["cultivo"] = cultivo_canonico
    df = df[[
        "cultivo", "provincia", "departamento", "campania",
        "superficie_sembrada_ha", "superficie_cosechada_ha",
        "produccion_tn", "rendimiento_kg_ha",
    ]].reset_index(drop=True)

    cache_path.write_text(
        df.to_json(orient="records", force_ascii=False),
        encoding="utf-8",
    )
    elapsed = time.time() - t0
    logger.info(
        "[MAGyP] Consulta nueva: %d filas en %.2fs. Params=%s. Cacheada en %s.",
        len(df), elapsed, params, cache_path.name,
    )
    return df


# === Bloque de prueba ===

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Detectamos las últimas 10 campañas reales del maestro.
    df_m = _descargar_csv_maestro()
    campanias = sorted(c for c in df_m["campania"].dropna().unique())
    ultimas_10 = campanias[-10:]
    desde, hasta = ultimas_10[0], ultimas_10[-1]
    print(f"\nÚltimas 10 campañas detectadas: {ultimas_10}")
    print(f"Filtrando con desde={desde} hasta={hasta}\n")

    resumen: list[dict] = []
    sin_datos: list[str] = []
    df_soja: Optional[pd.DataFrame] = None

    for cultivo in CULTIVOS_SOPORTADOS:
        df_c = obtener_estimaciones(
            cultivo=cultivo,
            campania_desde=desde,
            campania_hasta=hasta,
        )
        if df_c.empty:
            sin_datos.append(cultivo)
            continue
        resumen.append({
            "cultivo": cultivo,
            "registros": len(df_c),
            "departamentos_unicos": df_c["departamento"].nunique(),
            "campania_min": df_c["campania"].min(),
            "campania_max": df_c["campania"].max(),
        })
        if cultivo == "soja":
            df_soja = df_c

    df_resumen = pd.DataFrame(resumen)
    print("\n=== Resumen por cultivo (rango: últimas 10 campañas) ===")
    print(df_resumen.to_string(index=False))
    print(f"\nRegistros totales: {df_resumen['registros'].sum()}")

    if sin_datos:
        print(f"\n[!] Cultivos SIN datos en el rango: {sin_datos}")
    else:
        print("\nTodos los cultivos canónicos devolvieron datos.")

    if df_soja is not None:
        print("\n=== Soja: 5 primeras filas ===")
        print(df_soja.head().to_string(index=False))
