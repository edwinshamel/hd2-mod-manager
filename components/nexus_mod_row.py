import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Pango, GdkPixbuf

from i18n import _
import logger


class NexusModRow(Gtk.ListBoxRow):
    """
    Fila de un mod del catálogo de Nexus Mods en la pestaña Explorar.
    Usa Gtk.ListBoxRow en lugar de Adw.ActionRow para soportar descripción
    multilínea sin romper el layout interno de ActionRow.
    """

    def __init__(self, mod: dict, on_install, on_open):
        super().__init__()
        self.mod = mod
        self._thumb_loaded = False

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(12)
        outer.set_margin_end(8)
        self.set_child(outer)

        # ── Thumbnail ────────────────────────────────────────────────────────
        self._thumb = Gtk.Image.new_from_icon_name("image-loading-symbolic")
        self._thumb.set_size_request(72, 72)
        self._thumb.set_valign(Gtk.Align.START)
        self._thumb.set_pixel_size(48)
        self._thumb.add_css_class("rounded")
        outer.append(self._thumb)

        # ── Content (title + subtitle + description) ─────────────────────────
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        content.set_hexpand(True)
        content.set_valign(Gtk.Align.CENTER)
        outer.append(content)

        title_lbl = Gtk.Label(label=mod["name"])
        title_lbl.set_xalign(0)
        title_lbl.set_wrap(True)
        title_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_lbl.add_css_class("heading")
        content.append(title_lbl)

        subtitle_lbl = Gtk.Label(
            label=f"{mod['author']}  ·  v{mod['version']}  ·  "
                  f"★ {mod['endorsement_count']:,}  ·  ↓ {mod['mod_unique_downloads']:,}"
        )
        subtitle_lbl.set_xalign(0)
        subtitle_lbl.add_css_class("caption")
        subtitle_lbl.add_css_class("dim-label")
        content.append(subtitle_lbl)

        if mod.get("summary"):
            summary = mod["summary"]
            if len(summary) > 140:
                summary = summary[:140].rstrip() + "…"
            desc_lbl = Gtk.Label(label=summary)
            desc_lbl.set_xalign(0)
            desc_lbl.set_wrap(True)
            desc_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            desc_lbl.add_css_class("caption")
            desc_lbl.set_margin_top(4)
            content.append(desc_lbl)

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        btn_box.set_valign(Gtk.Align.CENTER)
        outer.append(btn_box)

        open_btn = Gtk.Button()
        open_btn.set_icon_name("web-browser-symbolic")
        open_btn.set_tooltip_text(_("View on Nexus Mods"))
        open_btn.add_css_class("flat")
        open_btn.connect("clicked", lambda _: on_open(mod["mod_id"]))
        btn_box.append(open_btn)

        install_btn = Gtk.Button()
        install_btn.set_icon_name("list-add-symbolic")
        install_btn.set_tooltip_text(_("Install mod"))
        install_btn.add_css_class("flat")
        install_btn.add_css_class("suggested-action")
        install_btn.connect("clicked", lambda _: on_install(mod))
        btn_box.append(install_btn)

    def set_thumbnail_bytes(self, data: bytes):
        """Carga la miniatura desde bytes. Debe llamarse desde el hilo principal via GLib.idle_add."""
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            w, h = pixbuf.get_width(), pixbuf.get_height()
            side = min(w, h)
            x = (w - side) // 2
            y = (h - side) // 2
            cropped = pixbuf.new_subpixbuf(x, y, side, side)
            scaled = cropped.scale_simple(72, 72, GdkPixbuf.InterpType.BILINEAR)
            self._thumb.set_from_pixbuf(scaled)
        except Exception as e:
            logger.error(f"Error loading thumbnail: {e}")
