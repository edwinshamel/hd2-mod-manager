import json
import subprocess
import threading
import time
from pathlib import Path

import requests

import logger
from app_meta import get_version

# ── Constantes ────────────────────────────────────────────────────────────────
_KEY_FILE = Path(__file__).parent / "key.json"
_GAME_DOMAIN = "helldivers2"
_BASE_URL = "https://api.nexusmods.com/v1"
_MOD_PAGE_URL = "https://www.nexusmods.com/{domain}/mods/{mod_id}"
_CACHE_TTL = 300  # segundos (5 minutos)
_MAX_MODS = 20


# ── Excepciones ───────────────────────────────────────────────────────────────
class KeyNotConfiguredError(Exception):
    """key.json no existe o no contiene una api_key válida."""


class NexusApiError(Exception):
    """Error en la comunicación con la API de Nexus Mods."""


# ── Caché en memoria (por sesión) ─────────────────────────────────────────────
_cache: dict[str, dict] = {}


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        logger.debug(f"nexus_api: cache hit '{key}'")
        return entry["data"]
    return None


def _cache_set(key: str, data):
    _cache[key] = {"data": data, "ts": time.time()}


# ── API key ───────────────────────────────────────────────────────────────────
def get_api_key() -> str:
    """Lee key.json y retorna la api_key. Lanza KeyNotConfiguredError si falla."""
    if not _KEY_FILE.exists():
        raise KeyNotConfiguredError(f"No se encontró {_KEY_FILE}")
    try:
        with open(_KEY_FILE, "r") as f:
            data = json.load(f)
        key = data.get("api_key", "").strip()
        if not key:
            raise KeyNotConfiguredError("api_key está vacía en key.json")
        return key
    except json.JSONDecodeError as e:
        raise KeyNotConfiguredError(f"key.json no es JSON válido: {e}")


def _headers() -> dict:
    return {
        "apikey": get_api_key(),
        "Application-Name": "hd2-mod-manager",
        "Application-Version": get_version(),
    }


def _get(endpoint: str) -> dict | list:
    """Realiza un GET a la API de Nexus Mods con manejo de errores."""
    url = f"{_BASE_URL}{endpoint}"
    logger.debug(f"nexus_api GET: {url}")
    try:
        r = requests.get(url, headers=_headers(), timeout=10)
        remaining = r.headers.get("x-rl-hourly-remaining", "?")
        logger.debug(f"nexus_api: HTTP {r.status_code} | hourly remaining: {remaining}")
        if r.status_code == 401:
            raise KeyNotConfiguredError("API key inválida o expirada (HTTP 401)")
        if r.status_code == 429:
            raise NexusApiError("Rate limit alcanzado. Intenta en una hora.")
        r.raise_for_status()
        return r.json()
    except (KeyNotConfiguredError, NexusApiError):
        raise
    except requests.exceptions.ConnectionError:
        raise NexusApiError("Sin conexión a internet.")
    except requests.exceptions.Timeout:
        raise NexusApiError("Tiempo de espera agotado al conectar con Nexus Mods.")
    except Exception as e:
        raise NexusApiError(f"Error inesperado: {e}")


# ── Funciones públicas ────────────────────────────────────────────────────────
def get_trending_mods() -> list[dict]:
    """
    Retorna hasta _MAX_MODS mods trending de Helldivers 2.
    Usa caché de sesión (5 minutos).
    """
    cached = _cache_get("trending")
    if cached is not None:
        return cached

    data = _get(f"/games/{_GAME_DOMAIN}/mods/trending.json")
    mods = _normalize_mods(data[:_MAX_MODS])
    _cache_set("trending", mods)
    logger.info(f"nexus_api: {len(mods)} mods trending obtenidos")
    return mods


def get_updated_mods() -> list[dict]:
    """
    Retorna hasta _MAX_MODS mods actualizados en la última semana.
    Obtiene la lista de IDs y luego el detalle de cada uno.
    Usa caché de sesión (5 minutos).
    """
    cached = _cache_get("updated")
    if cached is not None:
        return cached

    updated = _get(f"/games/{_GAME_DOMAIN}/mods/updated.json?period=1w")
    # Ordenar por latest_mod_activity desc y tomar los primeros _MAX_MODS
    updated_sorted = sorted(updated, key=lambda x: x.get("latest_mod_activity", 0), reverse=True)
    mod_ids = [m["mod_id"] for m in updated_sorted[:_MAX_MODS]]

    mods = []
    for mod_id in mod_ids:
        try:
            detail = _get(f"/games/{_GAME_DOMAIN}/mods/{mod_id}.json")
            if detail.get("available") and detail.get("status") == "published":
                mods.append(_normalize_mod(detail))
        except NexusApiError as e:
            logger.error(f"nexus_api: error obteniendo mod {mod_id}: {e}")
            continue

    _cache_set("updated", mods)
    logger.info(f"nexus_api: {len(mods)} mods actualizados obtenidos")
    return mods


def get_mod_files(mod_id: int) -> list[dict]:
    """
    Retorna los archivos principales de un mod (MAIN o is_primary).
    """
    data = _get(f"/games/{_GAME_DOMAIN}/mods/{mod_id}/files.json")
    files = data.get("files", [])
    # Priorizar archivos MAIN o marcados como primarios
    main_files = [
        f for f in files
        if f.get("is_primary") or f.get("category_name") in ("MAIN", "Main")
    ]
    return main_files if main_files else files[-1:] if files else []


def open_mod_page(mod_id: int):
    """Abre la página del mod en el navegador del sistema."""
    url = _MOD_PAGE_URL.format(domain=_GAME_DOMAIN, mod_id=mod_id)
    logger.info(f"nexus_api: abriendo página del mod {mod_id}: {url}")
    try:
        subprocess.Popen(["xdg-open", url])
    except Exception as e:
        logger.error(f"nexus_api: no se pudo abrir el navegador: {e}")


def download_thumbnail(url: str) -> bytes | None:
    """
    Descarga la miniatura de un mod desde el CDN de Nexus.
    Retorna los bytes de la imagen o None si falla.
    No consume rate limit de la API (CDN externo).
    """
    cached = _cache_get(f"thumb:{url}")
    if cached is not None:
        return cached

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        _cache_set(f"thumb:{url}", r.content)
        return r.content
    except Exception as e:
        logger.error(f"nexus_api: error descargando miniatura {url}: {e}")
        return None


def get_latest_added_mods() -> list[dict]:
    """
    Retorna los 10 mods más recientes de Helldivers 2.
    Usa caché de sesión (5 minutos).
    """
    cached = _cache_get("latest_added")
    if cached is not None:
        return cached

    data = _get(f"/games/{_GAME_DOMAIN}/mods/latest_added.json")
    mods = _normalize_mods(data)
    _cache_set("latest_added", mods)
    logger.info(f"nexus_api: {len(mods)} mods recientes obtenidos")
    return mods


def fetch_pool_async(on_success, on_error):
    """
    Carga en paralelo trending + updated + latest_added y los combina
    en un único pool deduplicado (por mod_id).
    on_success(pool): lista de dicts, llamado desde hilo secundario — usar GLib.idle_add
    on_error(err):   tupla (kind, msg), llamado desde hilo secundario
    """
    def _run():
        try:
            pool: dict[int, dict] = {}

            # Cargar las tres fuentes; updated es la más lenta (muchos requests)
            for getter in (get_trending_mods, get_latest_added_mods, get_updated_mods):
                try:
                    for mod in getter():
                        mid = mod["mod_id"]
                        if mid not in pool:
                            pool[mid] = mod
                except NexusApiError as e:
                    logger.error(f"nexus_api: error parcial en pool: {e}")
                    # No abortar: continuar con las otras fuentes

            if not pool:
                raise NexusApiError("No se pudieron obtener mods de ninguna fuente.")

            result = list(pool.values())
            logger.info(f"nexus_api: pool combinado = {len(result)} mods únicos")
            on_success(result)
        except KeyNotConfiguredError as e:
            on_error(("key_missing", str(e)))
        except NexusApiError as e:
            on_error(("api_error", str(e)))

    threading.Thread(target=_run, daemon=True).start()



# ── Helpers internos ──────────────────────────────────────────────────────────
def _normalize_mod(raw: dict) -> dict:
    """Normaliza un dict de mod de la API a la estructura interna."""
    return {
        "mod_id": raw.get("mod_id"),
        "name": raw.get("name", "Sin nombre"),
        "summary": raw.get("summary", ""),
        "version": raw.get("version", ""),
        "author": raw.get("author", ""),
        "picture_url": raw.get("picture_url", ""),
        "mod_downloads": raw.get("mod_downloads", 0),
        "mod_unique_downloads": raw.get("mod_unique_downloads", 0),
        "endorsement_count": raw.get("endorsement_count", 0),
        "updated_time": raw.get("updated_time", ""),
        "contains_adult_content": raw.get("contains_adult_content", False),
    }


def _normalize_mods(raw_list: list) -> list[dict]:
    return [
        _normalize_mod(m) for m in raw_list
        if m.get("available") and m.get("status") == "published"
    ]
