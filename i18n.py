"""
i18n.py — Internacionalización con gettext.

Detecta el idioma del sistema y carga la traducción correspondiente.
Instala _() en builtins para que esté disponible globalmente.

Idiomas soportados: en (base), es
"""
import gettext
import locale
import builtins
from pathlib import Path

_DOMAIN = "hd2-mod-manager"
_LOCALEDIR = Path(__file__).parent / "locale"

# Supported languages: (display_name, lang_code)
SUPPORTED_LANGUAGES = [
    ("English", "en"),
    ("Español", "es"),
]


def setup():
    """
    Detecta el idioma del sistema (o el guardado en config) y activa la traducción.
    Debe llamarse antes de importar cualquier módulo que use _().
    """
    # Prefer saved config language, fall back to system locale
    try:
        import mod_manager as _mm
        lang_code = _mm.get_language()
    except Exception:
        lang_code = locale.getlocale()[0] or "en"
    _apply(lang_code)


def switch_language(lang_code: str):
    """
    Cambia el idioma en caliente. Recarga la traducción de gettext.
    Los strings ya renderizados en la UI NO se actualizarán automáticamente;
    se muestra un aviso al usuario para reiniciar la app.
    """
    import mod_manager as _mm
    _mm.set_language(lang_code)
    _apply(lang_code)


def _apply(lang_code: str):
    """Load and install the translation for lang_code."""
    langs = [lang_code, lang_code[:2], "en"]
    t = gettext.translation(
        _DOMAIN,
        localedir=_LOCALEDIR,
        languages=langs,
        fallback=True,
    )
    t.install()


def _(text: str) -> str:
    """
    Re-exportado para que IDEs reconozcan el tipo y xgettext lo detecte.
    En runtime, builtins._() ya está instalado por setup().
    """
    return builtins.__dict__.get("_", lambda x: x)(text)
