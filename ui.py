import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
import mod_manager as mm
import logger


class ModRow(Adw.ActionRow):
    def __init__(self, mod_info: dict, on_toggle, on_uninstall, on_update, on_verify):
        super().__init__()
        self.mod_info = mod_info
        self.set_title(mod_info["name"])
        installed_at = mod_info.get("installed_at", "")[:10]
        files_count = len(mod_info.get("files", []))
        self.set_subtitle(f"Instalado: {installed_at}  |  Archivos: {files_count}")

        # Toggle switch
        self.switch = Gtk.Switch()
        self.switch.set_active(mod_info.get("enabled", True))
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.connect("state-set", lambda sw, state: on_toggle(mod_info["name"], sw, state))
        self.add_suffix(self.switch)

        # Botón verificar integridad
        verify_btn = Gtk.Button()
        verify_btn.set_icon_name("emblem-ok-symbolic")
        verify_btn.set_tooltip_text("Verificar integridad")
        verify_btn.set_valign(Gtk.Align.CENTER)
        verify_btn.add_css_class("flat")
        verify_btn.connect("clicked", lambda _: on_verify(mod_info["name"]))
        self.add_suffix(verify_btn)

        # Botón actualizar
        update_btn = Gtk.Button()
        update_btn.set_icon_name("software-update-available-symbolic")
        update_btn.set_tooltip_text("Actualizar mod")
        update_btn.set_valign(Gtk.Align.CENTER)
        update_btn.add_css_class("flat")
        update_btn.connect("clicked", lambda _: on_update(mod_info["name"]))
        self.add_suffix(update_btn)

        # Botón desinstalar
        del_btn = Gtk.Button()
        del_btn.set_icon_name("user-trash-symbolic")
        del_btn.set_tooltip_text("Desinstalar mod")
        del_btn.set_valign(Gtk.Align.CENTER)
        del_btn.add_css_class("flat")
        del_btn.add_css_class("destructive-action")
        del_btn.connect("clicked", lambda _: on_uninstall(mod_info["name"]))
        self.add_suffix(del_btn)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("HD2 Mod Manager")
        self.set_default_size(700, 550)

        # Layout principal
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        # Header
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Botón instalar mod
        install_btn = Gtk.Button(label="Instalar mod")
        install_btn.set_icon_name("list-add-symbolic")
        install_btn.add_css_class("suggested-action")
        install_btn.connect("clicked", self.on_install_clicked)
        header.pack_start(install_btn)

        # Botón configuración
        settings_btn = Gtk.Button()
        settings_btn.set_icon_name("preferences-system-symbolic")
        settings_btn.set_tooltip_text("Configuración")
        settings_btn.connect("clicked", self.on_settings_clicked)
        header.pack_end(settings_btn)

        # Contenido con scroll
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        toolbar_view.set_content(scroll)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.main_box.set_margin_top(12)
        self.main_box.set_margin_bottom(12)
        self.main_box.set_margin_start(12)
        self.main_box.set_margin_end(12)
        scroll.set_child(self.main_box)

        # Banner de estado
        self.banner = Adw.Banner()
        self.main_box.append(self.banner)

        # Lista de mods
        self.mods_group = Adw.PreferencesGroup()
        self.mods_group.set_title("Mods instalados")
        self.mods_group.set_description("Activa, desactiva o desinstala tus mods de Helldivers 2")
        self.main_box.append(self.mods_group)

        # Estado vacío
        self.empty_label = Gtk.Label(label="No hay mods instalados.\nHaz clic en 'Instalar mod' para agregar uno.")
        self.empty_label.set_justify(Gtk.Justification.CENTER)
        self.empty_label.add_css_class("dim-label")
        self.empty_label.set_vexpand(True)
        self.empty_label.set_valign(Gtk.Align.CENTER)
        self.main_box.append(self.empty_label)

        self.mod_rows = {}
        self.refresh_mods()

        # Abrir configuración automáticamente si no hay ruta válida configurada
        GLib.idle_add(self._check_first_run)

    def _check_first_run(self):
        config = mm.load_config()
        game_path = config.get("game_path", "")
        from pathlib import Path
        is_default = game_path == mm.DEFAULT_GAME_PATH
        is_missing = not game_path or not (Path(game_path) / "data").exists()

        if is_missing or (is_default and not (Path(game_path) / "data").exists()):
            logger.info("Primera ejecución o ruta no configurada, abriendo configuración automáticamente")
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Bienvenido a HD2 Mod Manager",
                body="No se encontró la carpeta de Helldivers 2.\nConfigura la ruta de instalación del juego para continuar.",
            )
            dialog.add_response("cancel", "Después")
            dialog.add_response("configure", "Configurar ahora")
            dialog.set_response_appearance("configure", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", lambda d, r: self.on_settings_clicked(None) if r == "configure" else None)
            dialog.present()
        return False

    def show_toast(self, message: str, success: bool = True):
        self.banner.set_title(message)
        self.banner.set_revealed(True)
        css = "success" if success else "error"
        self.banner.remove_css_class("success")
        self.banner.remove_css_class("error")
        self.banner.add_css_class(css)
        GLib.timeout_add(3000, lambda: self.banner.set_revealed(False))

    def refresh_mods(self):
        # Limpiar filas existentes
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

    def on_settings_clicked(self, _):
        settings = SettingsWindow(self)
        settings.present()

    def on_install_clicked(self, _):
        dialog = Gtk.FileDialog()
        dialog.set_title("Seleccionar archivo ZIP del mod")
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name("Archivos ZIP")
        filter_zip.add_pattern("*.zip")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_zip)
        dialog.set_filters(filters)
        dialog.open(self, None, self.on_file_selected)

    def on_file_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            zip_path = file.get_path()
            logger.debug(f"Archivo seleccionado para instalación: {zip_path}")
            self.show_install_name_dialog(zip_path)
        except Exception as e:
            logger.error("Error al seleccionar archivo ZIP", exc=e)

    def show_install_name_dialog(self, zip_path: str):
        from pathlib import Path
        default_name = Path(zip_path).stem

        dialog = Adw.MessageDialog(transient_for=self, heading="Nombre del mod")
        dialog.set_body("Puedes personalizar el nombre del mod:")
        entry = Gtk.Entry()
        entry.set_text(default_name)
        entry.set_margin_top(8)
        entry.set_margin_bottom(8)
        entry.set_margin_start(8)
        entry.set_margin_end(8)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("install", "Instalar")
        dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", lambda d, r: self.do_install(zip_path, entry.get_text(), r))
        dialog.present()

    def do_install(self, zip_path: str, mod_name: str, response: str):
        if response != "install":
            logger.debug(f"Instalación cancelada por el usuario: {mod_name}")
            return
        logger.info(f"Usuario inició instalación: {mod_name} | ZIP: {zip_path}")
        ok, msg = mm.install_mod(zip_path, mod_name.strip() or None)
        self.show_toast(msg, ok)
        if ok:
            self.refresh_mods()

    def on_toggle(self, mod_name: str, switch, state):
        logger.info(f"Usuario cambió estado del mod: {mod_name} -> {'activado' if state else 'desactivado'}")
        ok, msg = mm.toggle_mod(mod_name)
        self.show_toast(msg, ok)
        if not ok:
            switch.set_active(not state)
        return False

    def on_verify(self, mod_name: str):
        logger.info(f"Usuario verificó integridad del mod: {mod_name}")
        all_ok, results = mm.verify_mod(mod_name)

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"Integridad: {mod_name}",
        )

        if not results:
            dialog.set_body("No se encontraron archivos registrados para este mod.")
        else:
            lines = []
            for r in results:
                icon = "✓" if r["ok"] else "✗"
                lines.append(f"{icon}  {r['file']}")
            summary = "Todos los archivos están presentes." if all_ok else f"{sum(1 for r in results if not r['ok'])} archivo(s) faltante(s)."
            dialog.set_body(f"{summary}\n\n" + "\n".join(lines))

        dialog.add_response("close", "Cerrar")
        dialog.present()

    def on_uninstall(self, mod_name: str):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Desinstalar mod",
            body=f"¿Deseas desinstalar '{mod_name}'? Los archivos originales del juego serán restaurados.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("uninstall", "Desinstalar")
        dialog.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda d, r: self.do_uninstall(mod_name, r))
        dialog.present()

    def do_uninstall(self, mod_name: str, response: str):
        if response != "uninstall":
            logger.debug(f"Desinstalación cancelada por el usuario: {mod_name}")
            return
        logger.info(f"Usuario inició desinstalación: {mod_name}")
        ok, msg = mm.uninstall_mod(mod_name)
        self.show_toast(msg, ok)
        if ok:
            self.refresh_mods()

    def on_update(self, mod_name: str):
        dialog = Gtk.FileDialog()
        dialog.set_title(f"Seleccionar nueva versión de '{mod_name}'")
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name("Archivos ZIP")
        filter_zip.add_pattern("*.zip")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_zip)
        dialog.set_filters(filters)
        dialog.open(self, None, lambda d, r: self.do_update(mod_name, d, r))

    def do_update(self, mod_name: str, dialog, result):
        try:
            file = dialog.open_finish(result)
            zip_path = file.get_path()
            logger.info(f"Usuario inició actualización: {mod_name} | ZIP: {zip_path}")
            ok, msg = mm.check_for_updates(mod_name, zip_path)
            self.show_toast(msg, ok)
            if ok:
                self.refresh_mods()
        except Exception as e:
            logger.error(f"Error al actualizar mod: {mod_name}", exc=e)


class SettingsWindow(Adw.PreferencesWindow):
    def __init__(self, parent):
        super().__init__(transient_for=parent, modal=True)
        self.set_title("Configuración")
        self.set_default_size(600, 300)

        page = Adw.PreferencesPage()
        page.set_title("General")
        page.set_icon_name("preferences-system-symbolic")
        self.add(page)

        group = Adw.PreferencesGroup()
        group.set_title("Ruta del juego")
        group.set_description("Indica la carpeta raíz donde está instalado Helldivers 2")
        page.add(group)

        # Fila con la ruta actual
        self.path_row = Adw.ActionRow()
        self.path_row.set_title("Carpeta de instalación")
        config = mm.load_config()
        current_path = config.get("game_path", mm.DEFAULT_GAME_PATH)
        self.path_row.set_subtitle(current_path)

        # Botón para elegir carpeta
        choose_btn = Gtk.Button(label="Cambiar")
        choose_btn.set_valign(Gtk.Align.CENTER)
        choose_btn.add_css_class("flat")
        choose_btn.connect("clicked", self.on_choose_folder)
        self.path_row.add_suffix(choose_btn)
        group.add(self.path_row)

        # Fila de estado de validación
        self.status_row = Adw.ActionRow()
        self.status_row.set_title("Estado")
        self._update_status(current_path)
        group.add(self.status_row)

    def _update_status(self, path: str):
        from pathlib import Path
        data_path = Path(path) / "data"
        if data_path.exists():
            self.status_row.set_subtitle("Ruta valida - carpeta 'data' encontrada")
            self.status_row.remove_css_class("error")
            self.status_row.add_css_class("success")
        else:
            self.status_row.set_subtitle("Ruta invalida - no se encontro carpeta 'data'")
            self.status_row.remove_css_class("success")
            self.status_row.add_css_class("error")

    def on_choose_folder(self, _):
        dialog = Gtk.FileDialog()
        dialog.set_title("Seleccionar carpeta de Helldivers 2")
        dialog.select_folder(self, None, self.on_folder_selected)

    def on_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            path = folder.get_path()
            logger.info(f"Usuario seleccionó nueva ruta del juego: {path}")
            ok, msg = mm.set_game_path(path)
            self.path_row.set_subtitle(path)
            self._update_status(path)
        except Exception as e:
            logger.error("Error al seleccionar carpeta del juego", exc=e)


class HD2ModManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.edd.hd2modmanager")

    def do_activate(self):
        logger.info("HD2 Mod Manager iniciado")
        win = MainWindow(self)
        win.present()
