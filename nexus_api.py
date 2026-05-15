import subprocess
import threading
import time

import requests

import logger
from app_meta import get_version

# ── Constantes ────────────────────────────────────────────────────────────────
_GRAPHQL_URL = "https://api.nexusmods.com/v2/graphql"
_GAME_DOMAIN = "helldivers2"
_MOD_PAGE_URL = "https://www.nexusmods.com/{domain}/mods/{mod_id}"
_CACHE_TTL = 300  # segundos (5 minutos)
_MAX_MODS = 20


# ── Excepciones ───────────────────────────────────────────────────────────────
class KeyNotConfiguredError(Exception):
    """Mantenida por compatibilidad con ui.py; ya no se lanza en consultas de exploración."""


class NexusApiError(Exception):
    """Error en la comunicación con la API de Nexus Mods."""


# ── Caché en memoria (por sesión) ─────────────────────────────────────────────
_cache: dict[str, dict] = {}

# ── Estado de paginación por fuente ──────────────────────────────────────────
_page_state: dict[str, dict] = {
    "trending": {"offset": 0, "exhausted": False},
    "latest":   {"offset": 0, "exhausted": False},
    "updated":  {"offset": 0, "exhausted": False},
}

_SORTS: dict[str, list[dict]] = {
    "trending": [{"endorsements": {"direction": "DESC"}}],
    "latest":   [{"createdAt": {"direction": "DESC"}}],
    "updated":  [{"updatedAt": {"direction": "DESC"}}],
}


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        logger.debug(f"nexus_api: cache hit '{key}'")
        return entry["data"]
    return None


def _cache_set(key: str, data):
    _cache[key] = {"data": data, "ts": time.time()}


# ── GraphQL helper ────────────────────────────────────────────────────────────
def _graphql(query: str, variables: dict | None = None) -> dict:
    """Ejecuta una query GraphQL contra la API v2 de Nexus Mods."""
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables

    headers = {
        "Content-Type": "application/json",
        "Application-Name": "hd2-mod-manager",
        "Application-Version": get_version(),
    }

    logger.debug("nexus_api: GraphQL POST")
    try:
        r = requests.post(_GRAPHQL_URL, json=payload, headers=headers, timeout=15)
        logger.debug(f"nexus_api: HTTP {r.status_code}")
        r.raise_for_status()
        body = r.json()
        if "errors" in body:
            msgs = "; ".join(e.get("message", str(e)) for e in body["errors"])
            raise NexusApiError(f"GraphQL error: {msgs}")
        return body.get("data", {})
    except (NexusApiError,):
        raise
    except requests.exceptions.ConnectionError:
        raise NexusApiError("Sin conexión a internet.")
    except requests.exceptions.Timeout:
        raise NexusApiError("Tiempo de espera agotado al conectar con Nexus Mods.")
    except Exception as e:
        raise NexusApiError(f"Error inesperado: {e}")


# ── Query compartida de mods ──────────────────────────────────────────────────
_MODS_QUERY = """
query GetMods($filter: ModsFilter, $sort: [ModsSort!], $count: Int, $offset: Int) {
  mods(filter: $filter, sort: $sort, count: $count, offset: $offset) {
    nodes {
      modId
      name
      summary
      version
      author
      pictureUrl
      thumbnailUrl
      downloads
      endorsements
      adultContent
      updatedAt
      status
    }
    totalCount
  }
}
"""

_BASE_FILTER = {
    "op": "AND",
    "filter": [
        {"gameDomainName": [{"value": "helldivers2", "op": "EQUALS"}]},
        {"status": [{"value": "published", "op": "EQUALS"}]},
    ],
}


def _fetch_mods(sort: list[dict], cache_key: str, offset: int = 0) -> list[dict]:
    if offset == 0:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    data = _graphql(_MODS_QUERY, {
        "filter": _BASE_FILTER,
        "sort": sort,
        "count": _MAX_MODS,
        "offset": offset,
    })
    nodes = data.get("mods", {}).get("nodes", [])
    mods = _normalize_mods(nodes)
    if offset == 0:
        _cache_set(cache_key, mods)
    logger.info(f"nexus_api: {len(mods)} mods obtenidos ({cache_key}, offset={offset})")
    return mods


# ── Funciones públicas ────────────────────────────────────────────────────────
def get_trending_mods() -> list[dict]:
    """Retorna hasta _MAX_MODS mods más endorsados de Helldivers 2."""
    return _fetch_mods(
        sort=_SORTS["trending"],
        cache_key="trending",
    )


def get_updated_mods() -> list[dict]:
    """Retorna hasta _MAX_MODS mods actualizados recientemente."""
    return _fetch_mods(
        sort=_SORTS["updated"],
        cache_key="updated",
    )


def get_latest_added_mods() -> list[dict]:
    """Retorna hasta _MAX_MODS mods más recientes de Helldivers 2."""
    return _fetch_mods(
        sort=_SORTS["latest"],
        cache_key="latest_added",
    )


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


def fetch_pool_async(on_success, on_error):
    """
    Carga la primera página (trending + latest + updated) y resetea el estado
    de paginación. Llama on_success(pool) o on_error((kind, msg)) desde hilo
    secundario — usar GLib.idle_add en los callbacks.
    """
    # Resetear estado de paginación
    for key in _page_state:
        _page_state[key]["offset"] = 0
        _page_state[key]["exhausted"] = False

    def _run():
        try:
            pool: dict[int, dict] = {}
            sources = [
                ("trending", get_trending_mods),
                ("latest",   get_latest_added_mods),
                ("updated",  get_updated_mods),
            ]
            for key, getter in sources:
                try:
                    mods = getter()
                    _page_state[key]["offset"] = len(mods)
                    if len(mods) < _MAX_MODS:
                        _page_state[key]["exhausted"] = True
                    for mod in mods:
                        mid = mod["mod_id"]
                        if mid not in pool:
                            pool[mid] = mod
                except NexusApiError as e:
                    logger.error(f"nexus_api: error parcial en pool ({key}): {e}")

            if not pool:
                raise NexusApiError("No se pudieron obtener mods de ninguna fuente.")

            result = list(pool.values())
            logger.info(f"nexus_api: pool inicial = {len(result)} mods únicos")
            on_success(result)
        except NexusApiError as e:
            on_error(("api_error", str(e)))

    threading.Thread(target=_run, daemon=True).start()


def fetch_more_async(on_success, on_error):
    """
    Carga la siguiente página de cada fuente no agotada y devuelve los mods
    nuevos (deduplicados contra existing_ids).
    on_success(new_mods, all_exhausted): lista de dicts nuevos + bool si ya no hay más
    on_error((kind, msg))
    """
    def _run():
        try:
            new_mods: dict[int, dict] = {}
            any_active = False

            sources = [
                ("trending", _SORTS["trending"]),
                ("latest",   _SORTS["latest"]),
                ("updated",  _SORTS["updated"]),
            ]
            for key, sort in sources:
                state = _page_state[key]
                if state["exhausted"]:
                    continue
                any_active = True
                try:
                    mods = _fetch_mods(sort=sort, cache_key=key, offset=state["offset"])
                    state["offset"] += len(mods)
                    if len(mods) < _MAX_MODS:
                        state["exhausted"] = True
                    for mod in mods:
                        mid = mod["mod_id"]
                        if mid not in new_mods:
                            new_mods[mid] = mod
                except NexusApiError as e:
                    logger.error(f"nexus_api: error en fetch_more ({key}): {e}")

            all_exhausted = all(s["exhausted"] for s in _page_state.values())
            result = list(new_mods.values())
            logger.info(f"nexus_api: {len(result)} mods nuevos cargados (exhausted={all_exhausted})")
            on_success(result, all_exhausted)
        except Exception as e:
            on_error(("api_error", str(e)))

    threading.Thread(target=_run, daemon=True).start()


def all_sources_exhausted() -> bool:
    """Retorna True si todas las fuentes de paginación ya fueron cargadas completamente."""
    return all(s["exhausted"] for s in _page_state.values())


# ── Helpers internos ──────────────────────────────────────────────────────────
def _normalize_mod(raw: dict) -> dict:
    """Normaliza un nodo Mod de la API GraphQL v2 a la estructura interna."""
    downloads = raw.get("downloads", 0) or 0
    return {
        "mod_id": raw.get("modId"),
        "name": raw.get("name", "Sin nombre"),
        "summary": raw.get("summary", ""),
        "version": raw.get("version", ""),
        "author": raw.get("author", ""),
        "picture_url": raw.get("pictureUrl", "") or "",
        "thumbnail_url": raw.get("thumbnailUrl", "") or "",
        "mod_downloads": downloads,
        "mod_unique_downloads": downloads,  # V2 no expone uniqueDownloads en Mod; usamos total
        "endorsement_count": raw.get("endorsements", 0) or 0,
        "updated_time": raw.get("updatedAt", ""),
        "contains_adult_content": raw.get("adultContent", False),
    }


def _normalize_mods(raw_list: list) -> list[dict]:
    return [
        _normalize_mod(m) for m in raw_list
        if m.get("status") == "published"
    ]
