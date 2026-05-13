import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Adw, Gio, GLib, GdkPixbuf
import mod_manager as mm
import logger
import updater
import nexus_api
from nexus_api import KeyNotConfiguredError, NexusApiError
from app_meta import get_version


# ══════════════════════════════════════════════════════════════════════════════
# Pestaña: Mis Mods
# ══════════════════════════════════════════════════════════════════════════════

class ModRow(Adw.ActionRow):
    def __init__(self, mod_info: dict, on_toggle, on_uninstall, on_update, on_verify):
        super().__init__()
        self.mod_info = mod_info
        self.set_title(mod_info["name"])
        installed_at = mod_info.get("installed_at", "")[:10]
        files_count = len(mod_info.get("files", []))
        self.set_subtitle(f"Instalado: {installed_at}  |  Archivos: {files_count}")

        self.switch = Gtk.Switch()
        self.switch.set_active(mod_info.get("enabled", True))
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.connect("state-set", lambda sw, state: on_toggle(mod_info["name"], sw, state))
        self.add_suffix(self.switch)

        verify_btn = Gtk.Button()
        verify_btn.set_icon_name("emblem-ok-symbolic")
        verify_btn.set_tooltip_text("Verificar integridad")
        verify_btn.set_valign(Gtk.Align.CENTER)
        verify_btn.add_css_class("flat")
        verify_btn.connect("clicked", lambda _: on_verify(mod_info["name"]))
        self.add_suffix(verify_btn)

        update_btn = Gtk.Button()
        update_btn.set_icon_name("software-update-available-symbolic")
        update_btn.set_tooltip_text("Actualizar mod")
        update_btn.set_valign(Gtk.Align.CENTER)
        update_btn.add_css_class("flat")
        update_btn.connect("clicked", lambda _: on_update(mod_info["name"]))
        self.add_suffix(update_btn)

        del_btn = Gtk.Button()
        del_btn.set_icon_name("user-trash-symbolic")
        del_btn.set_tooltip_text("Desinstalar mod")
        del_btn.set_valign(Gtk.Align.CENTER)
        del_btn.add_css_class("flat")
        del_btn.add_css_class("destructive-action")
        del_btn.connect("clicked", lambda _: on_uninstall(mod_info["name"]))
        self.add_suffix(del_btn)


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
        self.mods_group.set_title("Mods instalados")
        self.mods_group.set_description("Activa, desactiva o desinstala tus mods de Helldivers 2")
        self.main_box.append(self.mods_group)

        self.empty_label = Gtk.Label(
            label="No hay mods instalados.\nUsa 'Instalar mod' o explora el catálogo en la pestaña Explorar."
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
        logger.info(f"Usuario cambió estado del mod: {mod_name} -> {'activado' if state else 'desactivado'}")
        ok, msg = mm.toggle_mod(mod_name)
        self.show_toast(msg, ok)
        if not ok:
            switch.set_active(not state)
        return False

    def on_verify(self, mod_name: str):
        logger.info(f"Usuario verificó integridad del mod: {mod_name}")
        all_ok, results = mm.verify_mod(mod_name)

        dialog = Adw.MessageDialog(transient_for=self.window, heading=f"Integridad: {mod_name}")
        if not results:
            dialog.set_body("No se encontraron archivos registrados para este mod.")
        else:
            lines = [("✓" if r["ok"] else "✗") + f"  {r['file']}" for r in results]
            summary = "Todos los archivos están presentes." if all_ok else \
                      f"{sum(1 for r in results if not r['ok'])} archivo(s) faltante(s)."
            dialog.set_body(f"{summary}\n\n" + "\n".join(lines))

        dialog.add_response("close", "Cerrar")
        dialog.present()

    def on_uninstall(self, mod_name: str):
        dialog = Adw.MessageDialog(
            transient_for=self.window,
            heading="Desinstalar mod",
            body=f"¿Deseas desinstalar '{mod_name}'? Los archivos originales del juego serán restaurados.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("uninstall", "Desinstalar")
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
        dialog.set_title(f"Seleccionar nueva versión de '{mod_name}'")
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name("Archivos ZIP")
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
            logger.error(f"Error al actualizar mod: {mod_name}", exc=e)


# ══════════════════════════════════════════════════════════════════════════════
# Pestaña: Explorar
# ══════════════════════════════════════════════════════════════════════════════

class NexusModRow(Gtk.ListBoxRow):
    """
    Fila de un mod del catálogo de Nexus Mods.
    Usa Gtk.ListBoxRow en lugar de Adw.ActionRow para poder incluir
    una descripción multilínea sin romper el layout interno de ActionRow.
    """

    def __init__(self, mod: dict, on_install, on_open):
        super().__init__()
        self.mod = mod

        # Contenedor raíz de la fila
        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(12)
        outer.set_margin_end(8)
        self.set_child(outer)

        # ── Miniatura ────────────────────────────────────────────────────────
        self._thumb = Gtk.Image()
        self._thumb.set_size_request(72, 72)
        self._thumb.set_valign(Gtk.Align.START)
        self._thumb.set_icon_name("image-loading-symbolic")
        self._thumb.set_icon_size(Gtk.IconSize.LARGE)
        self._thumb.add_css_class("rounded")
        outer.append(self._thumb)

        # ── Contenido central (título + subtítulo + descripción) ─────────────
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        content.set_hexpand(True)
        content.set_valign(Gtk.Align.CENTER)
        outer.append(content)

        title_lbl = Gtk.Label(label=mod["name"])
        title_lbl.set_xalign(0)
        title_lbl.set_wrap(True)
        title_lbl.set_wrap_mode(gi.repository.Pango.WrapMode.WORD_CHAR)
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
            desc_lbl.set_wrap_mode(gi.repository.Pango.WrapMode.WORD_CHAR)
            desc_lbl.add_css_class("caption")
            desc_lbl.set_margin_top(4)
            content.append(desc_lbl)

        # ── Botones ──────────────────────────────────────────────────────────
        btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        btn_box.set_valign(Gtk.Align.CENTER)
        outer.append(btn_box)

        open_btn = Gtk.Button()
        open_btn.set_icon_name("web-browser-symbolic")
        open_btn.set_tooltip_text("Ver en Nexus Mods")
        open_btn.add_css_class("flat")
        open_btn.connect("clicked", lambda _: on_open(mod["mod_id"]))
        btn_box.append(open_btn)

        install_btn = Gtk.Button()
        install_btn.set_icon_name("list-add-symbolic")
        install_btn.set_tooltip_text("Instalar mod")
        install_btn.add_css_class("flat")
        install_btn.add_css_class("suggested-action")
        install_btn.connect("clicked", lambda _: on_install(mod))
        btn_box.append(install_btn)

    def set_thumbnail_bytes(self, data: bytes):
        """Carga la miniatura desde bytes. Llamado desde el hilo principal via GLib.idle_add."""
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            # Recortar al centro y escalar a 72x72
            w, h = pixbuf.get_width(), pixbuf.get_height()
            side = min(w, h)
            x = (w - side) // 2
            y = (h - side) // 2
            cropped = pixbuf.new_subpixbuf(x, y, side, side)
            scaled = cropped.scale_simple(72, 72, GdkPixbuf.InterpType.BILINEAR)
            self._thumb.set_from_pixbuf(scaled)
        except Exception as e:
            logger.error(f"Error cargando miniatura: {e}")


class ExplorePage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.window = window
        self._current_mods: list[dict] = []
        self._mod_rows: dict[int, NexusModRow] = {}

        # ── Barra de herramientas ────────────────────────────────────────────
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        self.append(toolbar)

        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text("Buscar mods…")
        self._search.set_hexpand(True)
        self._search.connect("search-changed", self._on_search_changed)
        toolbar.append(self._search)

        # Selector de modo: Trending / Actualizados
        self._mode_btn = Gtk.DropDown.new_from_strings(["Trending", "Actualizados"])
        self._mode_btn.connect("notify::selected", self._on_mode_changed)
        toolbar.append(self._mode_btn)

        # Botón refrescar
        refresh_btn = Gtk.Button()
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refrescar lista")
        refresh_btn.connect("clicked", self._on_refresh)
        toolbar.append(refresh_btn)

        # ── ViewStack: loading / error / lista ───────────────────────────────
        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self.append(self._stack)

        # Estado: cargando
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        loading_box.set_valign(Gtk.Align.CENTER)
        loading_box.set_halign(Gtk.Align.CENTER)
        spinner = Gtk.Spinner()
        spinner.set_size_request(48, 48)
        spinner.start()
        loading_label = Gtk.Label(label="Cargando mods desde Nexus Mods…")
        loading_label.add_css_class("dim-label")
        loading_box.append(spinner)
        loading_box.append(loading_label)
        self._stack.add_named(loading_box, "loading")

        # Estado: sin API key
        self._key_status_page = Adw.StatusPage()
        self._key_status_page.set_icon_name("dialog-password-symbolic")
        self._key_status_page.set_title("API Key requerida")
        self._key_status_page.set_description(
            "Para explorar mods necesitas una API key de Nexus Mods.\n\n"
            "1. Ve a nexusmods.com → Preferencias → API Access\n"
            "2. Copia tu Personal API Key\n"
            "3. Crea el archivo ~/hd2-mod-manager/key.json:\n"
            '   { "api_key": "TU_KEY_AQUI" }\n'
            "4. Reinicia la app"
        )
        open_nexus_btn = Gtk.Button(label="Abrir nexusmods.com")
        open_nexus_btn.set_halign(Gtk.Align.CENTER)
        open_nexus_btn.add_css_class("suggested-action")
        open_nexus_btn.add_css_class("pill")
        open_nexus_btn.connect("clicked", lambda _: Gtk.show_uri(None, "https://www.nexusmods.com/helldivers2/mods", 0))
        self._key_status_page.set_child(open_nexus_btn)
        self._stack.add_named(self._key_status_page, "no_key")

        # Estado: error de red
        self._error_status_page = Adw.StatusPage()
        self._error_status_page.set_icon_name("network-error-symbolic")
        self._error_status_page.set_title("Error de conexión")
        retry_btn = Gtk.Button(label="Reintentar")
        retry_btn.set_halign(Gtk.Align.CENTER)
        retry_btn.add_css_class("pill")
        retry_btn.connect("clicked", self._on_refresh)
        self._error_status_page.set_child(retry_btn)
        self._stack.add_named(self._error_status_page, "error")

        # Estado: lista de mods con scroll infinito
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self._stack.add_named(scroll, "list")

        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        list_box.set_margin_top(12)
        list_box.set_margin_bottom(12)
        list_box.set_margin_start(12)
        list_box.set_margin_end(12)
        scroll.set_child(list_box)

        # Título del grupo
        group_title = Gtk.Label(label="Mods de Helldivers 2")
        group_title.set_xalign(0)
        group_title.add_css_class("heading")
        group_title.set_margin_bottom(4)
        list_box.append(group_title)

        self._group_description = Gtk.Label(label="")
        self._group_description.set_xalign(0)
        self._group_description.add_css_class("dim-label")
        self._group_description.add_css_class("caption")
        self._group_description.set_margin_bottom(8)
        list_box.append(self._group_description)

        self._mods_group = Gtk.ListBox()
        self._mods_group.set_selection_mode(Gtk.SelectionMode.NONE)
        self._mods_group.add_css_class("boxed-list")
        list_box.append(self._mods_group)

        # Pie de lista — aviso API personal
        notice = Gtk.Label(
            label="ℹ Usando API key personal en modo testing. "
                  "Los mods se descargan manualmente desde Nexus Mods."
        )
        notice.set_wrap(True)
        notice.set_xalign(0.5)
        notice.add_css_class("dim-label")
        notice.set_margin_top(8)
        list_box.append(notice)

        # Cargar al inicio
        self._load_mods()

    # ── Carga de mods ────────────────────────────────────────────────────────

    def _load_mods(self):
        self._stack.set_visible_child_name("loading")
        mode = "trending" if self._mode_btn.get_selected() == 0 else "updated"

        nexus_api.fetch_mods_async(
            mode,
            on_success=lambda mods: GLib.idle_add(self._on_mods_loaded, mods),
            on_error=lambda err: GLib.idle_add(self._on_mods_error, err),
        )

    def _on_mods_loaded(self, mods: list[dict]):
        self._current_mods = mods
        self._render_mods(mods)
        self._stack.set_visible_child_name("list")
        self._load_thumbnails(mods)
        return False

    def _on_mods_error(self, err: tuple):
        kind, msg = err
        if kind == "key_missing":
            self._stack.set_visible_child_name("no_key")
        else:
            self._error_status_page.set_description(msg)
            self._stack.set_visible_child_name("error")
        return False

    def _render_mods(self, mods: list[dict]):
        # Limpiar filas actuales
        for row in self._mod_rows.values():
            self._mods_group.remove(row)
        self._mod_rows.clear()

        for mod in mods:
            row = NexusModRow(mod, self._on_install, self._on_open_mod)
            self._mods_group.append(row)
            self._mod_rows[mod["mod_id"]] = row

        title_mode = "Trending" if self._mode_btn.get_selected() == 0 else "Actualizados esta semana"
        self._group_description.set_label(f"{title_mode} · {len(mods)} mods")

    def _load_thumbnails(self, mods: list[dict]):
        """Descarga miniaturas en hilos separados y las aplica via GLib.idle_add."""
        import threading

        def _fetch(mod):
            url = mod.get("picture_url", "")
            if not url:
                return
            data = nexus_api.download_thumbnail(url)
            if data:
                row = self._mod_rows.get(mod["mod_id"])
                if row:
                    GLib.idle_add(row.set_thumbnail_bytes, data)

        for mod in mods:
            threading.Thread(target=_fetch, args=(mod,), daemon=True).start()

    # ── Eventos ──────────────────────────────────────────────────────────────

    def _on_search_changed(self, entry):
        query = entry.get_text().lower().strip()
        if not query:
            filtered = self._current_mods
        else:
            filtered = [
                m for m in self._current_mods
                if query in m["name"].lower() or query in m["summary"].lower()
                or query in m["author"].lower()
            ]
        self._render_mods(filtered)

    def _on_mode_changed(self, dropdown, _param):
        self._search.set_text("")
        self._load_mods()

    def _on_refresh(self, *_):
        # Limpiar caché para forzar nueva consulta
        nexus_api._cache.clear()
        self._search.set_text("")
        self._load_mods()

    def _on_open_mod(self, mod_id: int):
        logger.info(f"Abriendo página del mod {mod_id} en el navegador")
        nexus_api.open_mod_page(mod_id)

    def _on_install(self, mod: dict):
        """Abre el navegador y luego el FileDialog para instalar el mod."""
        logger.info(f"Usuario inició instalación desde Explorar: {mod['name']} (id={mod['mod_id']})")
        # 1. Abrir navegador
        nexus_api.open_mod_page(mod["mod_id"])
        # 2. Pequeña pausa para que el navegador abra, luego el FileDialog
        GLib.timeout_add(800, self._open_install_dialog, mod)

    def _open_install_dialog(self, mod: dict):
        dialog = Gtk.FileDialog()
        dialog.set_title(f"Seleccionar ZIP descargado de '{mod['name']}'")
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name("Archivos ZIP")
        filter_zip.add_pattern("*.zip")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_zip)
        dialog.set_filters(filters)
        dialog.open(self.window, None, lambda d, r: self._on_file_selected(d, r, mod))
        return False  # no repetir el timeout

    def _on_file_selected(self, dialog, result, mod: dict):
        try:
            file = dialog.open_finish(result)
            zip_path = file.get_path()
            logger.debug(f"ZIP seleccionado: {zip_path}")
            self._show_name_dialog(zip_path, mod["name"])
        except Exception as e:
            logger.error(f"Error seleccionando archivo: {e}")

    def _show_name_dialog(self, zip_path: str, default_name: str):
        dialog = Adw.MessageDialog(transient_for=self.window, heading="Nombre del mod")
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
        dialog.connect("response", lambda d, r: self._do_install(zip_path, entry.get_text(), r))
        dialog.present()

    def _do_install(self, zip_path: str, mod_name: str, response: str):
        if response != "install":
            return
        ok, msg = mm.install_mod(zip_path, mod_name.strip() or None)
        # Notificar a la ventana principal para refrescar la pestaña Mis Mods
        self.window.notify_install(msg, ok)


# ══════════════════════════════════════════════════════════════════════════════
# Ventana principal
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("HD2 Mod Manager")
        self.set_default_size(750, 600)

        # ── Layout raíz ──────────────────────────────────────────────────────
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root_box)

        # ── HeaderBar ────────────────────────────────────────────────────────
        self._header = Adw.HeaderBar()
        root_box.append(self._header)

        self._install_btn = Gtk.Button(label="Instalar mod")
        self._install_btn.set_icon_name("list-add-symbolic")
        self._install_btn.add_css_class("suggested-action")
        self._install_btn.connect("clicked", self._on_install_clicked)
        self._header.pack_start(self._install_btn)

        settings_btn = Gtk.Button()
        settings_btn.set_icon_name("preferences-system-symbolic")
        settings_btn.set_tooltip_text("Configuración")
        settings_btn.connect("clicked", self._on_settings_clicked)
        self._header.pack_end(settings_btn)

        # ── ViewStack (contenido) ─────────────────────────────────────────────
        self._view_stack = Adw.ViewStack()
        self._view_stack.set_vexpand(True)
        root_box.append(self._view_stack)

        self._my_mods_page = MyModsPage(self)
        self._view_stack.add_titled_with_icon(
            self._my_mods_page, "my_mods", "Mis Mods", "drive-harddisk-symbolic"
        )

        self._explore_page = ExplorePage(self)
        self._view_stack.add_titled_with_icon(
            self._explore_page, "explore", "Explorar", "web-browser-symbolic"
        )

        # ── ViewSwitcherBar (barra inferior) ──────────────────────────────────
        switcher_bar = Adw.ViewSwitcherBar()
        switcher_bar.set_stack(self._view_stack)
        switcher_bar.set_reveal(True)
        root_box.append(switcher_bar)

        # Ocultar/mostrar botón "Instalar mod" según pestaña activa
        self._view_stack.connect("notify::visible-child", self._on_tab_changed)

        # ── Inicialización ────────────────────────────────────────────────────
        GLib.idle_add(self._check_first_run)
        updater.check_for_app_update(self._on_update_available)

    # ── Cambio de pestaña ─────────────────────────────────────────────────────
    def _on_tab_changed(self, stack, _param):
        visible = stack.get_visible_child_name()
        self._install_btn.set_visible(visible == "my_mods")

    # ── Instalar mod (desde header, pestaña Mis Mods) ─────────────────────────
    def _on_install_clicked(self, _):
        dialog = Gtk.FileDialog()
        dialog.set_title("Seleccionar archivo ZIP del mod")
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name("Archivos ZIP")
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
            logger.error("Error al seleccionar archivo ZIP", exc=e)

    def _show_install_name_dialog(self, zip_path: str):
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
        dialog.connect("response", lambda d, r: self._do_install(zip_path, entry.get_text(), r))
        dialog.present()

    def _do_install(self, zip_path: str, mod_name: str, response: str):
        if response != "install":
            return
        ok, msg = mm.install_mod(zip_path, mod_name.strip() or None)
        self.notify_install(msg, ok)

    def notify_install(self, msg: str, ok: bool):
        """Notifica resultado de instalación y refresca la lista de mods."""
        self._my_mods_page.show_toast(msg, ok)
        if ok:
            self._my_mods_page.refresh_mods()

    # ── Configuración ─────────────────────────────────────────────────────────
    def _on_settings_clicked(self, _):
        SettingsWindow(self).present()

    # ── Primera ejecución ─────────────────────────────────────────────────────
    def _check_first_run(self):
        from pathlib import Path
        config = mm.load_config()
        game_path = config.get("game_path", "")
        is_missing = not game_path or not (Path(game_path) / "data").exists()

        if is_missing:
            logger.info("Primera ejecución o ruta no configurada")
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Bienvenido a HD2 Mod Manager",
                body="No se encontró la carpeta de Helldivers 2.\nConfigura la ruta de instalación del juego para continuar.",
            )
            dialog.add_response("cancel", "Después")
            dialog.add_response("configure", "Configurar ahora")
            dialog.set_response_appearance("configure", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", lambda d, r: self._on_settings_clicked(None) if r == "configure" else None)
            dialog.present()
        return False

    # ── Actualizaciones de la app ─────────────────────────────────────────────
    def _on_update_available(self, latest_tag: str):
        logger.info(f"Mostrando diálogo de actualización: {latest_tag}")
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Actualización disponible",
            body=f"Hay una nueva versión de HD2 Mod Manager.\n\n"
                 f"Versión actual: {get_version()}\nNueva versión: {latest_tag}\n\n"
                 f"¿Deseas actualizar ahora?",
        )
        dialog.add_response("later", "Después")
        dialog.add_response("update", "Actualizar ahora")
        dialog.set_response_appearance("update", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_update_response)
        dialog.present()
        return False

    def _on_update_response(self, dialog, response: str):
        if response != "update":
            return
        self._my_mods_page.show_toast("Actualizando… por favor espera.", success=True)
        updater.apply_update(
            on_success=self._on_update_success,
            on_failure=self._on_update_failure,
        )

    def _on_update_success(self):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Actualización completada",
            body="La app se actualizó correctamente. Se reiniciará ahora.",
        )
        dialog.add_response("restart", "Reiniciar")
        dialog.set_response_appearance("restart", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", lambda d, r: updater.restart())
        dialog.present()

    def _on_update_failure(self, msg: str):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Error al actualizar",
            body=f"No se pudo actualizar la app:\n\n{msg}",
        )
        dialog.add_response("close", "Cerrar")
        dialog.present()


# ══════════════════════════════════════════════════════════════════════════════
# Ventana de configuración
# ══════════════════════════════════════════════════════════════════════════════

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

        self.path_row = Adw.ActionRow()
        self.path_row.set_title("Carpeta de instalación")
        config = mm.load_config()
        current_path = config.get("game_path", mm.DEFAULT_GAME_PATH)
        self.path_row.set_subtitle(current_path)

        choose_btn = Gtk.Button(label="Cambiar")
        choose_btn.set_valign(Gtk.Align.CENTER)
        choose_btn.add_css_class("flat")
        choose_btn.connect("clicked", self._on_choose_folder)
        self.path_row.add_suffix(choose_btn)
        group.add(self.path_row)

        self.status_row = Adw.ActionRow()
        self.status_row.set_title("Estado")
        self._update_status(current_path)
        group.add(self.status_row)

    def _update_status(self, path: str):
        from pathlib import Path
        if (Path(path) / "data").exists():
            self.status_row.set_subtitle("Ruta válida — carpeta 'data' encontrada")
            self.status_row.remove_css_class("error")
            self.status_row.add_css_class("success")
        else:
            self.status_row.set_subtitle("Ruta inválida — no se encontró carpeta 'data'")
            self.status_row.remove_css_class("success")
            self.status_row.add_css_class("error")

    def _on_choose_folder(self, _):
        dialog = Gtk.FileDialog()
        dialog.set_title("Seleccionar carpeta de Helldivers 2")
        dialog.select_folder(self, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            path = folder.get_path()
            mm.set_game_path(path)
            self.path_row.set_subtitle(path)
            self._update_status(path)
        except Exception as e:
            logger.error("Error al seleccionar carpeta del juego", exc=e)


# ══════════════════════════════════════════════════════════════════════════════
# Aplicación
# ══════════════════════════════════════════════════════════════════════════════

class HD2ModManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.edd.hd2modmanager")

    def do_activate(self):
        logger.info(f"HD2 Mod Manager iniciado (versión {get_version()})")
        win = MainWindow(self)
        win.present()
