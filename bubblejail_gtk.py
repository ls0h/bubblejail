from __future__ import annotations

from sys import path
from typing import Generator, Optional, Union

from bubblejail.bubblejail_directories import BubblejailDirectories
from bubblejail.services import BubblejailService

path.append('/usr/local/lib/x86_64-linux-gnu/bubblejail/python_packages')
from abc import ABC, abstractmethod
from enum import IntEnum, auto
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

GLADE_UI_FILE = './data/gtk/ui.glade'


class GtkGladeUI:
    _glade_ui_file: str
    _glade_ui_root: str
    _prefix = "_gui_"

    def __init__(self):
        super().__init__()
        builder = Gtk.Builder()
        builder.add_objects_from_file(self._glade_ui_file, (self._glade_ui_root,))
        for annotation in self.__class__.__annotations__.keys():
            if annotation.startswith(self._prefix):
                setattr(self, annotation, builder.get_object(annotation[len(self._prefix):]))
        builder.connect_signals(self)


class MainWindowInterface:
    def __init__(self):
        super().__init__()

    @abstractmethod
    def get_left_buttons(self) -> Optional[Gtk.Container]: ...

    @abstractmethod
    def get_right_buttons(self) -> Optional[Gtk.Container]: ...

    @abstractmethod
    def get_subtitle(self) -> str: ...


class InstanceListItem(Gtk.ListBoxRow):
    def __init__(self, instance_name: str):
        super().__init__()
        self.instance_name = instance_name
        label = Gtk.Label('  ' + instance_name)
        # TODO: Gtk.Misc.set_alignment is deprecated
        label.set_alignment(0, 0)
        self.add(label)


class InstanceListWindow(MainWindowInterface, GtkGladeUI, Gtk.Bin):
    _glade_ui_file = GLADE_UI_FILE
    _glade_ui_root = 'instance_list_window'

    _gui_delete_instance_button: Gtk.Button
    _gui_add_instance_button: Gtk.Button
    _gui_edit_instance_button: Gtk.Button
    _gui_instance_list: Gtk.ListBox

    _gui_il_left_button_group: Gtk.HBox
    _gui_il_right_button_group: Gtk.HBox
    _gui_instance_list_window: Gtk.VBox

    def __init__(self, app: BubblejailConfigApp):
        super().__init__()
        self._app = app
        self.add(self._gui_instance_list_window)
        self.fill_list()
        self.change_state_to_no_selection()

    def get_left_buttons(self) -> Optional[Gtk.Container]:
        return self._gui_il_left_button_group

    def get_right_buttons(self) -> Optional[Gtk.Container]:
        return self._gui_il_right_button_group

    def fill_list(self) -> None:
        for instance_path in BubblejailDirectories.iter_instances_path():
            self._gui_instance_list.add(InstanceListItem(instance_path.name))

    def change_state_to_no_selection(self) -> None:
        # TODO: Unselect any selected row
        self._gui_instance_list.unselect_all()
        self._gui_delete_instance_button.set_sensitive(False)
        self._gui_edit_instance_button.set_sensitive(False)

    def change_state_to_user_selected(self) -> None:
        self._gui_delete_instance_button.set_sensitive(True)
        self._gui_edit_instance_button.set_sensitive(True)

    def get_subtitle(self) -> str:
        return 'Existing instances'

    def on_instance_list_row_activated(self, *args):
        self._switch_app_to_edit_mode()

    def on_instance_list_row_selected(self, list_box: Gtk.ListBox, instance_list_item: Optional[InstanceListItem]) -> None:
        if instance_list_item:
            self.change_state_to_user_selected()
        else:
            self.change_state_to_no_selection()

    def on_delete_instance_button_clicked(self, button: Gtk.Button) -> None:
        print(button)

    def on_add_instance_button_clicked(self, button: Gtk.Button) -> None:
        print(button)

    def on_edit_instance_button_clicked(self, button: Gtk.Button) -> None:
        self._switch_app_to_edit_mode()

    def _switch_app_to_edit_mode(self) -> None:
        if selected_row := self._gui_instance_list.get_selected_row():
            selected_row: InstanceListItem
            self._app.switch_to_edit(selected_row.instance_name)


class ServiceWidget(GtkGladeUI, Gtk.Bin):
    _glade_ui_file = GLADE_UI_FILE
    _glade_ui_root = 'service_widget'

    _gui_service_widget: Gtk.VBox
    _gui_service_title: Gtk.Label
    _gui_service_description: Gtk.Label

    def __init__(self, service: BubblejailService):
        super().__init__()
        self._service = service
        self._gui_service_title.set_text(service.pretty_name)
        self._gui_service_description.set_text(service.description)
        self.add(self._gui_service_widget)


class InstanceEditWindow(MainWindowInterface, GtkGladeUI, Gtk.Bin):
    _glade_ui_file = GLADE_UI_FILE
    _glade_ui_root = 'instance_edit_window'

    _gui_ie_left_button_group: Gtk.Hbox
    _gui_ie_right_button_group: Gtk.Hbox
    _gui_instance_edit_window: Gtk.VBox

    _gui_enabled_services_vbox: Gtk.VBox
    _gui_available_services_vbox: Gtk.VBox

    def __init__(self, app: BubblejailConfigApp, instance_name: str):
        super().__init__()
        self._app = app
        self._need_save = False
        self._instance_name = instance_name
        self.add(self._gui_instance_edit_window)

        instance_config = BubblejailDirectories.instance_get(instance_name)._read_config()
        for service in instance_config.iter_services(iter_disabled=True, iter_default=False):
            if service.enabled:
                self._gui_enabled_services_vbox.add(ServiceWidget(service))
            else:
                self._gui_available_services_vbox.add(ServiceWidget(service))

    def get_left_buttons(self) -> Optional[Gtk.Container]:
        return self._gui_ie_left_button_group

    def get_right_buttons(self) -> Optional[Gtk.Container]:
        return self._gui_ie_right_button_group

    def get_subtitle(self) -> str:
        return self._instance_name

    def on_back_to_list_button_clicked(self, button: Gtk.Button) -> None:
        if not self._need_save:
            self._app.switch_to_list()
        else:
            # FIXME: Add dialog box!
            print('Add dialog box!')


class BubblejailConfigApp(GtkGladeUI):
    _glade_ui_file = GLADE_UI_FILE
    _glade_ui_root = 'main_window'

    _gui_main_window: Gtk.Window
    _gui_main_window_headerbar: Gtk.HeaderBar
    _gui_main_window_container: Gtk.Box

    def __init__(self):
        super().__init__()
        self.switch_to_list()
        self._gui_main_window.show_all()
        Gtk.main()

    def _clear_window(self) -> None:
        self._gui_main_window_container.foreach(self._gui_main_window_container.remove)
        self._gui_main_window_headerbar.foreach(self._gui_main_window_headerbar.remove)
        self._gui_main_window_headerbar.set_subtitle('')

    def _attach_window_interface(self, window_interface: Union[MainWindowInterface, Gtk.Widget]) -> None:
        self._clear_window()
        for buttons, pack in ((window_interface.get_left_buttons(), self._gui_main_window_headerbar.pack_start),
                         (window_interface.get_right_buttons(), self._gui_main_window_headerbar.pack_end)):
            if buttons:
                bg_parent: Gtk.Container = buttons.get_parent()
                bg_parent.remove(buttons)
                pack(buttons)
        self._gui_main_window_headerbar.set_subtitle(window_interface.get_subtitle())
        self._gui_main_window_headerbar.show_all()
        self._gui_main_window_container.add(window_interface)
        self._gui_main_window_container.show_all()

    def switch_to_list(self) -> None:
        self._attach_window_interface(InstanceListWindow(app=self))

    def switch_to_edit(self, instance_name: str) -> None:
        self._attach_window_interface(InstanceEditWindow(app=self, instance_name=instance_name))

    def on_main_window_destroy(self, *args) -> None:
        Gtk.main_quit()


if __name__ == '__main__':
    app = BubblejailConfigApp()
