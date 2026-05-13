import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Adw, Gio, GLib, GdkPixbuf, Pango
import mod_manager as mm
import logger
import updater
import nexus_api
from nexus_api import KeyNotConfiguredError, NexusApiError
from app_meta import get_version
from i18n import _
import i18n


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


# ══════════════════════════════════════════════════════════════════════════════
# Pestaña: Explorar
# ══════════════════════════════════════════════════════════════════════════════

class NexusModRow(Gtk.ListBoxRow):
    """
    Row for a mod from the Nexus Mods catalog.
    Uses Gtk.ListBoxRow instead of Adw.ActionRow to support
    multiline description without breaking ActionRow's internal layout.
    """

    def __init__(self, mod: dict, on_install, on_open):
        super().__init__()
        self.mod = mod

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
        """Load thumbnail from bytes. Called from main thread via GLib.idle_add."""
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


class ExplorePage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.window = window
        self._pool: list[dict] = []
        self._visible_mods: list[dict] = []
        self._mod_rows: dict[int, NexusModRow] = {}

        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        self.append(toolbar)

        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text(_("Search all mods…"))
        self._search.set_hexpand(True)
        self._search.connect("search-changed", self._on_search_changed)
        toolbar.append(self._search)

        self._sort_btn = Gtk.DropDown.new_from_strings([
            _("Trending first"),
            _("Most recent"),
            _("Most downloaded"),
            _("A–Z"),
        ])
        self._sort_btn.connect("notify::selected", self._on_sort_changed)
        toolbar.append(self._sort_btn)

        refresh_btn = Gtk.Button()
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh list"))
        refresh_btn.connect("clicked", self._on_refresh)
        toolbar.append(refresh_btn)

        # ── Stack ─────────────────────────────────────────────────────────────
        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self.append(self._stack)

        # Loading state
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        loading_box.set_valign(Gtk.Align.CENTER)
        loading_box.set_halign(Gtk.Align.CENTER)
        spinner = Gtk.Spinner()
        spinner.set_size_request(48, 48)
        spinner.start()
        loading_label = Gtk.Label(label=_("Loading mods from Nexus Mods…"))
        loading_label.add_css_class("dim-label")
        loading_box.append(spinner)
        loading_box.append(loading_label)
        self._stack.add_named(loading_box, "loading")

        # No API key state
        self._key_status_page = Adw.StatusPage()
        self._key_status_page.set_icon_name("dialog-password-symbolic")
        self._key_status_page.set_title(_("API Key required"))
        self._key_status_page.set_description(
            _("To browse mods you need a Nexus Mods API key.\n\n"
              "1. Go to nexusmods.com → Preferences → API Access\n"
              "2. Copy your Personal API Key\n"
              "3. Create the file ~/hd2-mod-manager/key.json:\n"
              "   { \"api_key\": \"YOUR_KEY_HERE\" }\n"
              "4. Restart the app")
        )
        open_nexus_btn = Gtk.Button(label=_("Open nexusmods.com"))
        open_nexus_btn.set_halign(Gtk.Align.CENTER)
        open_nexus_btn.add_css_class("suggested-action")
        open_nexus_btn.add_css_class("pill")
        open_nexus_btn.connect("clicked", lambda _: Gtk.show_uri(None, "https://www.nexusmods.com/helldivers2/mods", 0))
        self._key_status_page.set_child(open_nexus_btn)
        self._stack.add_named(self._key_status_page, "no_key")

        # No results state
        self._empty_status_page = Adw.StatusPage()
        self._empty_status_page.set_icon_name("system-search-symbolic")
        self._empty_status_page.set_title(_("No results"))
        self._empty_status_page.set_description(
            _("No mod matches your search.\nTry a different term or refresh the list.")
        )
        self._stack.add_named(self._empty_status_page, "empty")

        # Connection error state
        self._error_status_page = Adw.StatusPage()
        self._error_status_page.set_icon_name("network-error-symbolic")
        self._error_status_page.set_title(_("Connection error"))
        retry_btn = Gtk.Button(label=_("Retry"))
        retry_btn.set_halign(Gtk.Align.CENTER)
        retry_btn.add_css_class("pill")
        retry_btn.connect("clicked", self._on_refresh)
        self._error_status_page.set_child(retry_btn)
        self._stack.add_named(self._error_status_page, "error")

        # Mod list state
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self._stack.add_named(scroll, "list")

        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        list_box.set_margin_top(12)
        list_box.set_margin_bottom(12)
        list_box.set_margin_start(12)
        list_box.set_margin_end(12)
        scroll.set_child(list_box)

        self._group_description = Gtk.Label(label="")
        self._group_description.set_xalign(0)
        self._group_description.add_css_class("dim-label")
        self._group_description.add_css_class("caption")
        self._group_description.set_margin_bottom(4)
        list_box.append(self._group_description)

        self._mods_group = Gtk.ListBox()
        self._mods_group.set_selection_mode(Gtk.SelectionMode.NONE)
        self._mods_group.add_css_class("boxed-list")
        list_box.append(self._mods_group)

        notice = Gtk.Label(
            label=_("Search is over loaded mods (trending + recent + updated). "
                    "Visit nexusmods.com to see the full catalog.")
        )
        notice.set_wrap(True)
        notice.set_xalign(0.5)
        notice.add_css_class("dim-label")
        notice.add_css_class("caption")
        notice.set_margin_top(8)
        list_box.append(notice)

        self._load_pool()

    # ── Pool loading ─────────────────────────────────────────────────────────

    def _load_pool(self):
        self._stack.set_visible_child_name("loading")
        nexus_api.fetch_pool_async(
            on_success=lambda mods: GLib.idle_add(self._on_pool_loaded, mods),
            on_error=lambda err: GLib.idle_add(self._on_mods_error, err),
        )

    def _on_pool_loaded(self, pool: list[dict]):
        self._pool = pool
        self._apply_filter_and_sort()
        return False

    def _on_mods_error(self, err: tuple):
        kind, msg = err
        if kind == "key_missing":
            self._stack.set_visible_child_name("no_key")
        else:
            self._error_status_page.set_description(msg)
            self._stack.set_visible_child_name("error")
        return False

    # ── Filter + sort ────────────────────────────────────────────────────────

    def _apply_filter_and_sort(self):
        query = self._search.get_text().lower().strip()

        if query:
            mods = [
                m for m in self._pool
                if query in m["name"].lower()
                or query in (m.get("summary") or "").lower()
                or query in m["author"].lower()
            ]
        else:
            mods = list(self._pool)

        sort_idx = self._sort_btn.get_selected()
        if sort_idx == 0:
            pass  # Trending first — keep pool insertion order
        elif sort_idx == 1:
            mods.sort(key=lambda m: m.get("updated_time", ""), reverse=True)
        elif sort_idx == 2:
            mods.sort(key=lambda m: m.get("mod_unique_downloads", 0), reverse=True)
        elif sort_idx == 3:
            mods.sort(key=lambda m: m["name"].lower())

        self._visible_mods = mods

        if not mods and query:
            self._stack.set_visible_child_name("empty")
        else:
            self._render_mods(mods)
            self._stack.set_visible_child_name("list")
            self._load_thumbnails(mods)

    def _render_mods(self, mods: list[dict]):
        for row in self._mod_rows.values():
            self._mods_group.remove(row)
        self._mod_rows.clear()

        for mod in mods:
            row = NexusModRow(mod, self._on_install, self._on_open_mod)
            self._mods_group.append(row)
            self._mod_rows[mod["mod_id"]] = row

        total = len(self._pool)
        shown = len(mods)
        query = self._search.get_text().strip()
        if query:
            self._group_description.set_label(
                _("{n} result(s) of {total} loaded mods").format(n=shown, total=total)
            )
        else:
            self._group_description.set_label(
                _("{total} mods loaded from Nexus Mods").format(total=total)
            )

    def _load_thumbnails(self, mods: list[dict]):
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

    # ── Events ───────────────────────────────────────────────────────────────

    def _on_search_changed(self, entry):
        if self._pool:
            self._apply_filter_and_sort()

    def _on_sort_changed(self, dropdown, _param):
        if self._pool:
            self._apply_filter_and_sort()

    def _on_refresh(self, *_):
        nexus_api._cache.clear()
        self._search.set_text("")
        self._pool = []
        self._load_pool()

    def _on_open_mod(self, mod_id: int):
        logger.info(f"Opening mod page {mod_id} in browser")
        nexus_api.open_mod_page(mod_id)

    def _on_install(self, mod: dict):
        logger.info(f"User started install from Explore: {mod['name']} (id={mod['mod_id']})")
        nexus_api.open_mod_page(mod["mod_id"])
        GLib.timeout_add(800, self._open_install_dialog, mod)

    def _open_install_dialog(self, mod: dict):
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Select downloaded ZIP for '{name}'").format(name=mod["name"]))
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name(_("ZIP Files"))
        filter_zip.add_pattern("*.zip")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_zip)
        dialog.set_filters(filters)
        dialog.open(self.window, None, lambda d, r: self._on_file_selected(d, r, mod))
        return False

    def _on_file_selected(self, dialog, result, mod: dict):
        try:
            file = dialog.open_finish(result)
            zip_path = file.get_path()
            logger.debug(f"ZIP selected: {zip_path}")
            self._show_name_dialog(zip_path, mod["name"])
        except Exception as e:
            logger.error(f"Error selecting file: {e}")

    def _show_name_dialog(self, zip_path: str, default_name: str):
        dialog = Adw.MessageDialog(transient_for=self.window, heading=_("Mod name"))
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
        self.window.notify_install(msg, ok)


# ══════════════════════════════════════════════════════════════════════════════
# Main window
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title(_("HD2 Mod Manager"))
        self.set_default_size(750, 600)

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
        from pathlib import Path
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
        from pathlib import Path
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
# Settings window
# ══════════════════════════════════════════════════════════════════════════════

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
        # Ignore the signal fired during __init__ when set_selected() is called
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
                # Revert the combo back to the original selection
                self._lang_row.set_selected(self._lang_initial_idx)
                return
            import sys, os
            i18n.switch_language(lang)
            app = self._parent_win.get_application()
            python = sys.executable
            main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
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
