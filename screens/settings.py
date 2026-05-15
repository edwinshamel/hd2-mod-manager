import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

import sys
import os
import mod_manager as mm
import logger
import i18n
from i18n import _


class SettingsWindow(Adw.PreferencesWindow):
    def __init__(self, parent):
        super().__init__(transient_for=parent, modal=True)
        self._parent_win = parent
        self.set_title(_("Settings"))
        self.set_default_size(600, 300)

        page = Adw.PreferencesPage()
        page.set_title(_("General"))
        page.set_icon_name("preferences-system-symbolic")
        self.add(page)

        group = Adw.PreferencesGroup()
        group.set_title(_("Game path"))
        group.set_description(_("Indicates the root folder where Helldivers 2 is installed"))
        page.add(group)

        self.path_row = Adw.ActionRow()
        self.path_row.set_title(_("Installation folder"))
        config = mm.load_config()
        current_path = config.get("game_path", mm.DEFAULT_GAME_PATH)
        self.path_row.set_subtitle(current_path)

        choose_btn = Gtk.Button(label=_("Change"))
        choose_btn.set_valign(Gtk.Align.CENTER)
        choose_btn.add_css_class("flat")
        choose_btn.connect("clicked", self._on_choose_folder)
        self.path_row.add_suffix(choose_btn)
        group.add(self.path_row)

        self.status_row = Adw.ActionRow()
        self.status_row.set_title(_("Status"))
        self._update_status(current_path)
        group.add(self.status_row)

        # ── Language group ─────────────────────────────────────────────────────
        lang_group = Adw.PreferencesGroup()
        lang_group.set_title(_("Language"))
        lang_group.set_description(_("Restart the app to apply the new language"))
        page.add(lang_group)

        lang_codes = [code for _, code in i18n.SUPPORTED_LANGUAGES]
        lang_names = [name for name, _ in i18n.SUPPORTED_LANGUAGES]
        current_lang = mm.get_language()
        current_idx = lang_codes.index(current_lang) if current_lang in lang_codes else 0

        string_list = Gtk.StringList.new(lang_names)
        self._lang_row = Adw.ComboRow()
        self._lang_row.set_title(_("Interface language"))
        self._lang_row.set_model(string_list)
        self._lang_row.set_selected(current_idx)
        self._lang_initial_idx = current_idx
        self._lang_row.connect("notify::selected", self._on_language_changed, lang_codes)
        lang_group.add(self._lang_row)

    def _on_language_changed(self, row, _param, lang_codes):
        idx = row.get_selected()
        if idx == self._lang_initial_idx:
            return
        lang = lang_codes[idx]

        dialog = Adw.AlertDialog.new(
            _("Restart required"),
            _("The app needs to restart to apply the new language. Restart now?"),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("restart", _("Restart"))
        dialog.set_response_appearance("restart", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("restart")
        dialog.set_close_response("cancel")

        def _on_response(d, response):
            if response != "restart":
                self._lang_row.set_selected(self._lang_initial_idx)
                return
            i18n.switch_language(lang)
            app = self._parent_win.get_application()
            python = sys.executable
            main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main.py")
            app.connect("shutdown", lambda _: os.execv(python, [python, main_py]))
            app.quit()

        dialog.connect("response", _on_response)
        dialog.present(self)

    def _update_status(self, path: str):
        from pathlib import Path
        if (Path(path) / "data").exists():
            self.status_row.set_subtitle(_("Valid path — 'data' folder found"))
            self.status_row.remove_css_class("error")
            self.status_row.add_css_class("success")
        else:
            self.status_row.set_subtitle(_("Invalid path — 'data' folder not found"))
            self.status_row.remove_css_class("success")
            self.status_row.add_css_class("error")

    def _on_choose_folder(self, _):
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Select Helldivers 2 folder"))
        dialog.select_folder(self, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            path = folder.get_path()
            mm.set_game_path(path)
            self.path_row.set_subtitle(path)
            self._update_status(path)
        except Exception as e:
            logger.error("Error selecting game folder", exc=e)
