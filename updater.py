import threading
import subprocess
import os
import sys
import requests
from packaging.version import Version
from gi.repository import GLib
import logger
from app_meta import get_version, get_repo

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _parse_version(tag: str) -> str:
    """Elimina el prefijo 'v' del tag para comparar versiones."""
    return tag.lstrip("v")


def _fetch_latest_tag() -> str | None:
    """Consulta la API de GitHub y retorna el tag más reciente o None si falla."""
    url = f"https://api.github.com/repos/{get_repo()}/tags"
    try:
        logger.debug(f"Consultando tags en: {url}")
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        tags = response.json()
        if not tags:
            logger.info("No se encontraron tags en el repositorio.")
            return None
        latest = tags[0]["name"]
        logger.debug(f"Tag más reciente en GitHub: {latest}")
        return latest
    except requests.exceptions.ConnectionError:
        logger.error("Sin conexión a internet al verificar actualizaciones.")
        return None
    except Exception as e:
        logger.error("Error al consultar tags de GitHub", exc=e)
        return None


def _do_update() -> tuple[bool, str]:
    """Ejecuta git pull en la carpeta de la app."""
    try:
        logger.info("Iniciando git pull para actualizar la app...")
        result = subprocess.run(
            ["git", "pull", "origin", "master"],
            cwd=APP_DIR,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info(f"git pull exitoso:\n{result.stdout}")
            return True, result.stdout
        else:
            logger.error(f"git pull falló:\n{result.stderr}")
            return False, result.stderr
    except Exception as e:
        logger.error("Error ejecutando git pull", exc=e)
        return False, str(e)


def _restart_app():
    """Reinicia la app reemplazando el proceso actual."""
    logger.info("Reiniciando la app tras actualización...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


def check_for_app_update(on_update_available):
    """
    Verifica si hay una versión nueva en un hilo separado.
    Si hay actualización, llama a on_update_available(latest_tag) en el hilo principal de GTK.
    """
    def _run():
        latest_tag = _fetch_latest_tag()
        if not latest_tag:
            return

        latest_version = _parse_version(latest_tag)
        current_version = get_version()

        try:
            if Version(latest_version) > Version(current_version):
                logger.info(f"Nueva versión disponible: {latest_tag} (actual: {current_version})")
                GLib.idle_add(on_update_available, latest_tag)
            else:
                logger.info(f"La app está actualizada (versión {current_version})")
        except Exception as e:
            logger.error("Error comparando versiones", exc=e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def apply_update(on_success, on_failure):
    """
    Ejecuta git pull en un hilo separado.
    Llama a on_success() o on_failure(msg) en el hilo principal de GTK al terminar.
    """
    def _run():
        ok, msg = _do_update()
        if ok:
            GLib.idle_add(on_success)
        else:
            GLib.idle_add(on_failure, msg)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def restart():
    _restart_app()
