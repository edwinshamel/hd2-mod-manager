import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from pathlib import Path
import mod_manager as mm
import logger
import updater
from app_meta import get_version
from i18n import _
from screens.my_mods import MyModsPage
from screens.explore import ExplorePage
from screens.settings import SettingsWindow


# ══════════════════════════════════════════════════════════════════════════════
# Main window
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title(_("HD2 Mod Manager"))
        self.set_default_size(750, 600)

        # Icono de ventana — usa el nombre instalado en hicolor por install.sh
        self.set_icon_name("hd2-mod-manager")

        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root_box)

        self._header = Adw.HeaderBar()
        root_box.append(self._header)

        self._install_btn = Gtk.Button(label=_("Install mod"))
        self._install_btn.set_icon_name("list-add-symbolic")
        self._install_btn.add_css_class("suggested-action")
        self._install_btn.connect("clicked", self._on_install_clicked)
        self._header.pack_start(self._install_btn)

        settings_btn = Gtk.Button()
        settings_btn.set_icon_name("preferences-system-symbolic")
        settings_btn.set_tooltip_text(_("Settings"))
        settings_btn.connect("clicked", self._on_settings_clicked)
        self._header.pack_end(settings_btn)

        self._view_stack = Adw.ViewStack()
        self._view_stack.set_vexpand(True)
        root_box.append(self._view_stack)

        self._my_mods_page = MyModsPage(self)
        self._view_stack.add_titled_with_icon(
            self._my_mods_page, "my_mods", _("My Mods"), "drive-harddisk-symbolic"
        )

        self._explore_page = ExplorePage(self)
        self._view_stack.add_titled_with_icon(
            self._explore_page, "explore", _("Explore"), "web-browser-symbolic"
        )

        switcher_bar = Adw.ViewSwitcherBar()
        switcher_bar.set_stack(self._view_stack)
        switcher_bar.set_reveal(True)
        root_box.append(switcher_bar)

        self._view_stack.connect("notify::visible-child", self._on_tab_changed)

        GLib.idle_add(self._check_first_run)
        updater.check_for_app_update(self._on_update_available)

    def _on_tab_changed(self, stack, _param):
        visible = stack.get_visible_child_name()
        self._install_btn.set_visible(visible == "my_mods")

    def _on_install_clicked(self, _):
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Select mod ZIP file"))
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name(_("ZIP Files"))
        filter_zip.add_pattern("*.zip")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_zip)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_file_selected)

    def _on_file_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            zip_path = file.get_path()
            self._show_install_name_dialog(zip_path)
        except Exception as e:
            logger.error("Error selecting ZIP file", exc=e)

    def _show_install_name_dialog(self, zip_path: str):
        default_name = Path(zip_path).stem

        dialog = Adw.MessageDialog(transient_for=self, heading=_("Mod name"))
        dialog.set_body(_("You can customize the mod name:"))
        entry = Gtk.Entry()
        entry.set_text(default_name)
        entry.set_margin_top(8)
        entry.set_margin_bottom(8)
        entry.set_margin_start(8)
        entry.set_margin_end(8)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("install", _("Install"))
        dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", lambda d, r: self._do_install(zip_path, entry.get_text(), r))
        dialog.present()

    def _do_install(self, zip_path: str, mod_name: str, response: str):
        if response != "install":
            return
        ok, msg = mm.install_mod(zip_path, mod_name.strip() or None)
        self.notify_install(msg, ok)

    def notify_install(self, msg: str, ok: bool):
        self._my_mods_page.show_toast(msg, ok)
        if ok:
            self._my_mods_page.refresh_mods()

    def _on_settings_clicked(self, _):
        SettingsWindow(self).present()

    def _check_first_run(self):
        config = mm.load_config()
        game_path = config.get("game_path", "")
        is_missing = not game_path or not (Path(game_path) / "data").exists()

        if is_missing:
            logger.info("First run or path not configured")
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=_("Welcome to HD2 Mod Manager"),
                body=_("Game path not found.\nConfigure the game installation path to continue."),
            )
            dialog.add_response("cancel", _("Later"))
            dialog.add_response("configure", _("Configure now"))
            dialog.set_response_appearance("configure", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", lambda d, r: self._on_settings_clicked(None) if r == "configure" else None)
            dialog.present()
        return False

    def _on_update_available(self, latest_tag: str):
        logger.info(f"Showing update dialog: {latest_tag}")
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Update available"),
            body=_("A new version of HD2 Mod Manager is available.\n\n"
                   "Current version: {current}\nNew version: {latest}\n\n"
                   "Do you want to update now?").format(
                current=get_version(), latest=latest_tag
            ),
        )
        dialog.add_response("later", _("Later"))
        dialog.add_response("update", _("Update now"))
        dialog.set_response_appearance("update", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_update_response)
        dialog.present()
        return False

    def _on_update_response(self, dialog, response: str):
        if response != "update":
            return
        self._my_mods_page.show_toast(_("Updating… please wait."), success=True)
        updater.apply_update(
            on_success=self._on_update_success,
            on_failure=self._on_update_failure,
        )

    def _on_update_success(self):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Update completed"),
            body=_("The app updated successfully. It will restart now."),
        )
        dialog.add_response("restart", _("Restart"))
        dialog.set_response_appearance("restart", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", lambda d, r: updater.restart())
        dialog.present()

    def _on_update_failure(self, msg: str):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Error updating"),
            body=_("Could not update the app:\n\n{msg}").format(msg=msg),
        )
        dialog.add_response("close", _("Close"))
        dialog.present()


# ══════════════════════════════════════════════════════════════════════════════
# Application
# ══════════════════════════════════════════════════════════════════════════════

class HD2ModManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.edd.hd2modmanager")

    def do_activate(self):
        logger.info(f"HD2 Mod Manager started (version {get_version()})")
        win = MainWindow(self)
        win.present()
