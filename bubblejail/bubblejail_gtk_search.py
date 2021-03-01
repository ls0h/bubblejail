from typing import Callable

import gi

from bubblejail.bubblejail_utils import BubblejailSettings

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from bubblejail.bubblejail_gtk_glade import GladeBuilder, GladeWidget


GLADE_UI_DIR = f'{BubblejailSettings.SHARE_PATH_STR}/bubblejail/gtk/'


class SearchBar(GladeWidget):
    _glade_file = f'{GLADE_UI_DIR}common.glade'
    _glade_root_id = 'search_revealer'

    _gui_search_revealer: Gtk.Revealer
    _gui_search_entry: Gtk.SearchEntry

    def __init__(self, toggle_button: Gtk.ToggleButton, search_cb: Callable[[str], None]):
        super().__init__()
        self._toggle_button = toggle_button
        self._search_cb = search_cb
        toggle_button.connect("toggled", self.on_button_toggled)

    def on_button_toggled(self, button: Gtk.ToggleButton):
        active = button.get_active()
        self._gui_search_revealer.set_reveal_child(active)
        if active:
            self._gui_search_entry.grab_focus()
        else:
            self._search_cb('')

    def on_search_entry_search_changed(self, entry: Gtk.SearchEntry):
        self._search_cb(entry.get_text().lower())

    def on_search_entry_stop_search(self, entry: Gtk.SearchEntry):
        entry.set_text('')
        self._toggle_button.set_active(False)
        self._search_cb('')
