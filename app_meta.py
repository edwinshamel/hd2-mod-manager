import json
from pathlib import Path

_META_FILE = Path(__file__).parent / "meta.json"


def get_meta() -> dict:
    """Lee meta.json en cada llamada para reflejar cambios tras git pull."""
    with open(_META_FILE, "r") as f:
        return json.load(f)


def get_version() -> str:
    return get_meta()["version"]


def get_repo() -> str:
    return get_meta()["repo"]
