import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

import threading
import mod_manager as mm
import nexus_api
import logger
from i18n import _
from components.nexus_mod_row import NexusModRow


class ExplorePage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.window = window
        self._pool: list[dict] = []
        self._pool_ids: set[int] = set()
        self._visible_mods: list[dict] = []
        self._mod_rows: dict[int, NexusModRow] = {}
        self._loading_more = False
        self._search_timer_id: int | None = None

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
        scroll.connect("edge-reached", self._on_edge_reached)
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

        # Spinner inline para "cargando más"
        self._more_spinner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._more_spinner_box.set_halign(Gtk.Align.CENTER)
        self._more_spinner_box.set_margin_top(8)
        self._more_spinner_box.set_margin_bottom(8)
        self._more_spinner = Gtk.Spinner()
        self._more_spinner.set_size_request(24, 24)
        _more_lbl = Gtk.Label(label=_("Loading more…"))
        _more_lbl.add_css_class("dim-label")
        self._more_spinner_box.append(self._more_spinner)
        self._more_spinner_box.append(_more_lbl)
        self._more_spinner_box.set_visible(False)
        list_box.append(self._more_spinner_box)

        # Label "fin del catálogo"
        self._end_label = Gtk.Label(label=_("You've reached the end of the catalog."))
        self._end_label.add_css_class("dim-label")
        self._end_label.add_css_class("caption")
        self._end_label.set_margin_top(8)
        self._end_label.set_margin_bottom(8)
        self._end_label.set_visible(False)
        list_box.append(self._end_label)

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
        self._pool_ids = {m["mod_id"] for m in pool}
        self._loading_more = False
        self._end_label.set_visible(False)
        self._apply_filter_and_sort()
        return False

    def _on_mods_error(self, err: tuple):
        kind, msg = err
        self._error_status_page.set_description(msg)
        self._stack.set_visible_child_name("error")
        return False

    # ── Scroll infinito ───────────────────────────────────────────────────────

    def _on_edge_reached(self, _scroll, pos):
        if pos != Gtk.PositionType.BOTTOM:
            return
        if self._search.get_text().strip():
            return
        if self._loading_more:
            return
        if nexus_api.all_sources_exhausted():
            return
        self._loading_more = True
        self._more_spinner_box.set_visible(True)
        self._more_spinner.start()
        nexus_api.fetch_more_async(
            on_success=lambda mods, done: GLib.idle_add(self._on_more_loaded, mods, done),
            on_error=lambda err: GLib.idle_add(self._on_more_error, err),
        )

    def _on_more_loaded(self, new_mods: list[dict], all_exhausted: bool):
        self._more_spinner.stop()
        self._more_spinner_box.set_visible(False)
        self._loading_more = False

        deduped = [m for m in new_mods if m["mod_id"] not in self._pool_ids]
        if deduped:
            for mod in deduped:
                self._pool.append(mod)
                self._pool_ids.add(mod["mod_id"])
            for mod in deduped:
                row = NexusModRow(mod, self._on_install, self._on_open_mod)
                self._mods_group.append(row)
                self._mod_rows[mod["mod_id"]] = row
            self._update_group_label()
            self._load_thumbnails(deduped)

        if all_exhausted:
            self._end_label.set_visible(True)

        return False

    def _on_more_error(self, err: tuple):
        self._more_spinner.stop()
        self._more_spinner_box.set_visible(False)
        self._loading_more = False
        logger.error(f"nexus_api: error cargando más mods: {err[1]}")
        return False

    # ── Filter + sort ────────────────────────────────────────────────────────

    def _apply_filter_and_sort(self):
        """Re-render completo: se llama al cargar el pool, al cambiar sort, o al hacer refresh."""
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
        if sort_idx == 1:
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

    def _apply_filter_only(self):
        """Filtrado rápido: solo show/hide de filas existentes, sin recrear widgets."""
        query = self._search.get_text().lower().strip()

        if query:
            matching_ids = {
                m["mod_id"] for m in self._pool
                if query in m["name"].lower()
                or query in (m.get("summary") or "").lower()
                or query in m["author"].lower()
            }
        else:
            matching_ids = set(self._mod_rows.keys())

        any_visible = False
        for mid, row in self._mod_rows.items():
            visible = mid in matching_ids
            row.set_visible(visible)
            if visible:
                any_visible = True

        self._visible_mods = [m for m in self._pool if m["mod_id"] in matching_ids]

        if not any_visible and query:
            self._stack.set_visible_child_name("empty")
        else:
            self._stack.set_visible_child_name("list")

        self._update_group_label()

    def _render_mods(self, mods: list[dict]):
        """Re-render completo: destruye filas existentes y crea las nuevas en orden."""
        for row in self._mod_rows.values():
            self._mods_group.remove(row)
        self._mod_rows.clear()

        for mod in mods:
            row = NexusModRow(mod, self._on_install, self._on_open_mod)
            self._mods_group.append(row)
            self._mod_rows[mod["mod_id"]] = row

        self._update_group_label()

    def _update_group_label(self):
        total = len(self._pool)
        shown = len(self._visible_mods) if self._search.get_text().strip() else total
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
        def _fetch(mod):
            url = mod.get("picture_url", "")
            if not url:
                return
            data = nexus_api.download_thumbnail(url)
            if data:
                mid = mod["mod_id"]
                row = self._mod_rows.get(mid)
                if row:
                    row._thumb_loaded = True
                    GLib.idle_add(row.set_thumbnail_bytes, data)

        for mod in mods:
            threading.Thread(target=_fetch, args=(mod,), daemon=True).start()

    # ── Events ───────────────────────────────────────────────────────────────

    def _on_search_changed(self, entry):
        if not self._pool:
            return
        if self._search_timer_id is not None:
            GLib.source_remove(self._search_timer_id)
            self._search_timer_id = None
        self._search_timer_id = GLib.timeout_add(250, self._do_filter)

    def _do_filter(self):
        self._search_timer_id = None
        self._apply_filter_only()
        return False

    def _on_sort_changed(self, dropdown, _param):
        if self._pool:
            self._apply_filter_and_sort()

    def _on_refresh(self, *_):
        if self._search_timer_id is not None:
            GLib.source_remove(self._search_timer_id)
            self._search_timer_id = None
        nexus_api._cache.clear()
        self._search.set_text("")
        self._pool = []
        self._pool_ids = set()
        self._loading_more = False
        self._more_spinner.stop()
        self._more_spinner_box.set_visible(False)
        self._end_label.set_visible(False)
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
