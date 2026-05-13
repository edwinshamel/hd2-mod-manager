import os
import json
import shutil
import zipfile
import hashlib
from pathlib import Path
from datetime import datetime
import logger
from i18n import _

APP_DIR = Path.home() / "hd2-mod-manager"
MODS_DIR = APP_DIR / "mods"
BACKUPS_DIR = APP_DIR / "backups"
DISABLED_DIR = APP_DIR / "disabled"
INDEX_FILE = APP_DIR / "mods_index.json"
CONFIG_FILE = APP_DIR / "config.json"

DEFAULT_GAME_PATH = "/mnt/storage/SteamLibrary/steamapps/common/Helldivers 2"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"game_path": DEFAULT_GAME_PATH}


def save_config(config: dict):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_language() -> str:
    """Returns the saved language code, e.g. 'en' or 'es'. Defaults to 'en'."""
    return load_config().get("language", "en")


def set_language(lang_code: str):
    """Persists the chosen language code to config."""
    config = load_config()
    config["language"] = lang_code
    save_config(config)


def get_game_data_dir() -> Path:
    config = load_config()
    return Path(config.get("game_path", DEFAULT_GAME_PATH)) / "data"


def set_game_path(path: str) -> tuple[bool, str]:
    p = Path(path)
    logger.debug(f"Trying to set game path: {p}")
    if not p.exists():
        msg = _("The path does not exist.")
        logger.error(f"set_game_path: {msg} | Path: {p}")
        return False, msg
    if not (p / "data").exists():
        msg = _("The 'data' folder was not found inside the specified path. Make sure it is the game's root folder.")
        logger.error(f"set_game_path: {msg} | Path: {p}")
        return False, msg
    config = load_config()
    config["game_path"] = str(p)
    save_config(config)
    logger.info(f"Game path set: {p}")
    return True, _("Path saved: {path}").format(path=p)


def load_index() -> dict:
    if INDEX_FILE.exists():
        with open(INDEX_FILE, "r") as f:
            return json.load(f)
    return {}


def save_index(index: dict):
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)


def file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def install_mod(zip_path: str, mod_name: str = None) -> tuple[bool, str]:
    zip_path = Path(zip_path)
    logger.debug(f"Starting mod install | File: {zip_path} | Name: {mod_name}")

    if not zip_path.exists():
        msg = _("The file does not exist.")
        logger.error(f"install_mod: {msg} | Path: {zip_path}")
        return False, msg

    if not zipfile.is_zipfile(zip_path):
        msg = _("The file is not a valid ZIP.")
        logger.error(f"install_mod: {msg} | Path: {zip_path}")
        return False, msg

    game_data_dir = get_game_data_dir()
    logger.debug(f"Game data folder: {game_data_dir}")

    if not game_data_dir.exists():
        msg = _("Game folder not found. Check the path in Settings.")
        logger.error(f"install_mod: {msg} | Path: {game_data_dir}")
        return False, msg

    mod_name = mod_name or zip_path.stem
    mod_dir = MODS_DIR / mod_name

    if mod_dir.exists():
        msg = _("Mod '{name}' is already installed.").format(name=mod_name)
        logger.error(f"install_mod: {msg}")
        return False, msg

    mod_dir.mkdir(parents=True)
    backup_dir = BACKUPS_DIR / mod_name
    backup_dir.mkdir(parents=True)

    installed_files = []
    backed_up_files = []

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            members = z.namelist()
            logger.debug(f"Files in ZIP: {len(members)}")
            for member in members:
                target = game_data_dir / member
                if target.exists():
                    backup_target = backup_dir / member
                    backup_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup_target)
                    backed_up_files.append(member)
                    logger.debug(f"Backup created: {member}")

                target.parent.mkdir(parents=True, exist_ok=True)
                z.extract(member, game_data_dir)
                installed_files.append(member)
                logger.debug(f"File installed: {member}")

    except Exception as e:
        logger.error(f"install_mod: Error during installation of '{mod_name}'", exc=e)
        for f in installed_files:
            target = game_data_dir / f
            if target.exists():
                target.unlink()
        shutil.rmtree(mod_dir, ignore_errors=True)
        shutil.rmtree(backup_dir, ignore_errors=True)
        return False, _("Error installing: {error}").format(error=e)

    index = load_index()
    index[mod_name] = {
        "name": mod_name,
        "installed_at": datetime.now().isoformat(),
        "files": installed_files,
        "backed_up": backed_up_files,
        "enabled": True,
        "zip_hash": file_hash(zip_path),
        "version": "1.0",
    }
    save_index(index)

    msg = _("Mod '{name}' installed successfully ({n} files).").format(
        name=mod_name, n=len(installed_files)
    )
    logger.info(msg)
    return True, msg


def uninstall_mod(mod_name: str) -> tuple[bool, str]:
    logger.debug(f"Starting mod uninstall: {mod_name}")
    index = load_index()
    if mod_name not in index:
        msg = _("Mod '{name}' is not in the index.").format(name=mod_name)
        logger.error(f"uninstall_mod: {msg}")
        return False, msg

    game_data_dir = get_game_data_dir()
    mod_info = index[mod_name]
    backup_dir = BACKUPS_DIR / mod_name

    for f in mod_info.get("files", []):
        target = game_data_dir / f
        if target.exists():
            target.unlink()
            logger.debug(f"Mod file removed: {f}")

    for f in mod_info.get("backed_up", []):
        backup_file = backup_dir / f
        target = game_data_dir / f
        if backup_file.exists():
            shutil.copy2(backup_file, target)
            logger.debug(f"Original file restored: {f}")

    shutil.rmtree(BACKUPS_DIR / mod_name, ignore_errors=True)
    shutil.rmtree(MODS_DIR / mod_name, ignore_errors=True)
    shutil.rmtree(DISABLED_DIR / mod_name, ignore_errors=True)

    del index[mod_name]
    save_index(index)

    msg = _("Mod '{name}' uninstalled and original files restored.").format(name=mod_name)
    logger.info(msg)
    return True, msg


def toggle_mod(mod_name: str) -> tuple[bool, str]:
    logger.debug(f"Toggling mod state: {mod_name}")
    index = load_index()
    if mod_name not in index:
        msg = _("Mod '{name}' is not in the index.").format(name=mod_name)
        logger.error(f"toggle_mod: {msg}")
        return False, msg

    game_data_dir = get_game_data_dir()
    mod_info = index[mod_name]
    enabled = mod_info.get("enabled", True)
    backup_dir = BACKUPS_DIR / mod_name
    disabled_dir = DISABLED_DIR / mod_name

    if enabled:
        disabled_dir.mkdir(parents=True, exist_ok=True)
        for f in mod_info.get("files", []):
            target = game_data_dir / f
            if target.exists():
                dst = disabled_dir / f
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, dst)
            backup_file = backup_dir / f
            if backup_file.exists():
                shutil.copy2(backup_file, target)
        index[mod_name]["enabled"] = False
        save_index(index)
        msg = _("Mod '{name}' disabled.").format(name=mod_name)
        logger.info(msg)
        return True, msg
    else:
        for f in mod_info.get("files", []):
            src = disabled_dir / f
            target = game_data_dir / f
            if src.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
        shutil.rmtree(disabled_dir, ignore_errors=True)
        index[mod_name]["enabled"] = True
        save_index(index)
        msg = _("Mod '{name}' enabled.").format(name=mod_name)
        logger.info(msg)
        return True, msg


def verify_mod(mod_name: str) -> tuple[bool, list[dict]]:
    """
    Verifies that all mod files are present in the game folder.
    Returns (all_ok, list_of_results).
    Each result is {"file": str, "ok": bool}.
    """
    logger.debug(f"Verifying mod integrity: {mod_name}")
    index = load_index()
    if mod_name not in index:
        logger.error(f"verify_mod: mod '{mod_name}' not in index.")
        return False, []

    game_data_dir = get_game_data_dir()
    mod_info = index[mod_name]
    results = []

    for f in mod_info.get("files", []):
        target = game_data_dir / f
        ok = target.exists()
        results.append({"file": f, "ok": ok})
        if ok:
            logger.debug(f"verify_mod: OK - {f}")
        else:
            logger.error(f"verify_mod: MISSING - {f}")

    all_ok = all(r["ok"] for r in results)
    if all_ok:
        logger.info(f"Verification of '{mod_name}': all files present ({len(results)})")
    else:
        missing = sum(1 for r in results if not r["ok"])
        logger.error(f"Verification of '{mod_name}': {missing} missing files out of {len(results)}")

    return all_ok, results


def get_mods() -> list[dict]:
    logger.debug("Loading installed mods list")
    index = load_index()
    return list(index.values())


def check_for_updates(mod_name: str, new_zip_path: str) -> tuple[bool, str]:
    logger.debug(f"Checking for mod update: {mod_name} | ZIP: {new_zip_path}")
    index = load_index()
    if mod_name not in index:
        msg = _("Mod '{name}' is not installed.").format(name=mod_name)
        logger.error(f"check_for_updates: {msg}")
        return False, msg

    new_hash = file_hash(Path(new_zip_path))
    old_hash = index[mod_name].get("zip_hash", "")

    if new_hash == old_hash:
        msg = _("The mod is already on the latest version.")
        logger.info(f"check_for_updates: {mod_name} - {msg}")
        return False, msg

    logger.info(f"Update detected for '{mod_name}', reinstalling...")
    uninstall_mod(mod_name)
    return install_mod(new_zip_path, mod_name)
