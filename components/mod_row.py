import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from i18n import _
import logger


class ModRow(Adw.ActionRow):
    """Fila de un mod instalado en la pestaña Mis Mods."""

    def __init__(self, mod_info: dict, on_toggle, on_uninstall, on_update, on_verify):
        super().__init__()
        self.mod_info = mod_info
        self.set_title(mod_info["name"])
        installed_at = mod_info.get("installed_at", "")[:10]
        files_count = len(mod_info.get("files", []))
        self.set_subtitle(_("Installed: {date}  |  Files: {n}").format(
            date=installed_at, n=files_count
        ))

        self.switch = Gtk.Switch()
        self.switch.set_active(mod_info.get("enabled", True))
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.connect("state-set", lambda sw, state: on_toggle(mod_info["name"], sw, state))
        self.add_suffix(self.switch)

        verify_btn = Gtk.Button()
        verify_btn.set_icon_name("emblem-ok-symbolic")
        verify_btn.set_tooltip_text(_("Verify integrity"))
        verify_btn.set_valign(Gtk.Align.CENTER)
        verify_btn.add_css_class("flat")
        verify_btn.connect("clicked", lambda _: on_verify(mod_info["name"]))
        self.add_suffix(verify_btn)

        update_btn = Gtk.Button()
        update_btn.set_icon_name("software-update-available-symbolic")
        update_btn.set_tooltip_text(_("Update mod"))
        update_btn.set_valign(Gtk.Align.CENTER)
        update_btn.add_css_class("flat")
        update_btn.connect("clicked", lambda _: on_update(mod_info["name"]))
        self.add_suffix(update_btn)

        del_btn = Gtk.Button()
        del_btn.set_icon_name("user-trash-symbolic")
        del_btn.set_tooltip_text(_("Uninstall mod"))
        del_btn.set_valign(Gtk.Align.CENTER)
        del_btn.add_css_class("flat")
        del_btn.add_css_class("destructive-action")
        del_btn.connect("clicked", lambda _: on_uninstall(mod_info["name"]))
        self.add_suffix(del_btn)
