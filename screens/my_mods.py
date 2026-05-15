import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

import mod_manager as mm
import logger
from i18n import _
from components.mod_row import ModRow


class MyModsPage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self.append(scroll)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.main_box.set_margin_top(12)
        self.main_box.set_margin_bottom(12)
        self.main_box.set_margin_start(12)
        self.main_box.set_margin_end(12)
        scroll.set_child(self.main_box)

        self.banner = Adw.Banner()
        self.main_box.append(self.banner)

        self.mods_group = Adw.PreferencesGroup()
        self.mods_group.set_title(_("Installed mods"))
        self.mods_group.set_description(_("Enable, disable or uninstall your Helldivers 2 mods"))
        self.main_box.append(self.mods_group)

        self.empty_label = Gtk.Label(
            label=_("No mods installed.\nUse 'Install mod' or browse the catalog in the Explore tab.")
        )
        self.empty_label.set_justify(Gtk.Justification.CENTER)
        self.empty_label.add_css_class("dim-label")
        self.empty_label.set_vexpand(True)
        self.empty_label.set_valign(Gtk.Align.CENTER)
        self.main_box.append(self.empty_label)

        self.mod_rows = {}
        self.refresh_mods()

    def show_toast(self, message: str, success: bool = True):
        self.banner.set_title(message)
        self.banner.set_revealed(True)
        self.banner.remove_css_class("success")
        self.banner.remove_css_class("error")
        self.banner.add_css_class("success" if success else "error")
        GLib.timeout_add(3000, lambda: self.banner.set_revealed(False))

    def refresh_mods(self):
        for row in self.mod_rows.values():
            self.mods_group.remove(row)
        self.mod_rows.clear()

        mods = mm.get_mods()
        self.empty_label.set_visible(len(mods) == 0)
        self.mods_group.set_visible(len(mods) > 0)

        for mod in mods:
            row = ModRow(mod, self.on_toggle, self.on_uninstall, self.on_update, self.on_verify)
            self.mods_group.add(row)
            self.mod_rows[mod["name"]] = row

    def on_toggle(self, mod_name: str, switch, state):
        logger.info(f"User changed mod state: {mod_name} -> {'enabled' if state else 'disabled'}")
        ok, msg = mm.toggle_mod(mod_name)
        self.show_toast(msg, ok)
        if not ok:
            switch.set_active(not state)
        return False

    def on_verify(self, mod_name: str):
        logger.info(f"User verified mod integrity: {mod_name}")
        all_ok, results = mm.verify_mod(mod_name)

        dialog = Adw.MessageDialog(
            transient_for=self.window,
            heading=_("Integrity: {name}").format(name=mod_name),
        )
        if not results:
            dialog.set_body(_("No registered files found for this mod."))
        else:
            lines = [("✓" if r["ok"] else "✗") + f"  {r['file']}" for r in results]
            missing = sum(1 for r in results if not r["ok"])
            summary = (
                _("All files are present.")
                if all_ok
                else _("{n} missing file(s).").format(n=missing)
            )
            dialog.set_body(f"{summary}\n\n" + "\n".join(lines))

        dialog.add_response("close", _("Close"))
        dialog.present()

    def on_uninstall(self, mod_name: str):
        dialog = Adw.MessageDialog(
            transient_for=self.window,
            heading=_("Uninstall mod"),
            body=_("Are you sure you want to uninstall '{name}'? Original game files will be restored.").format(
                name=mod_name
            ),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("uninstall", _("Uninstall"))
        dialog.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda d, r: self._do_uninstall(mod_name, r))
        dialog.present()

    def _do_uninstall(self, mod_name: str, response: str):
        if response != "uninstall":
            return
        ok, msg = mm.uninstall_mod(mod_name)
        self.show_toast(msg, ok)
        if ok:
            self.refresh_mods()

    def on_update(self, mod_name: str):
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Select new version of '{name}'").format(name=mod_name))
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name(_("ZIP Files"))
        filter_zip.add_pattern("*.zip")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_zip)
        dialog.set_filters(filters)
        dialog.open(self.window, None, lambda d, r: self._do_update(mod_name, d, r))

    def _do_update(self, mod_name: str, dialog, result):
        try:
            file = dialog.open_finish(result)
            zip_path = file.get_path()
            ok, msg = mm.check_for_updates(mod_name, zip_path)
            self.show_toast(msg, ok)
            if ok:
                self.refresh_mods()
        except Exception as e:
            logger.error(f"Error updating mod: {mod_name}", exc=e)
