# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright 2021 Aleksey Shaferov (ls0h)

# This file is part of bubblejail.
# bubblejail is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# bubblejail is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with bubblejail.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

from functools import lru_cache
from typing import Optional, Union, Type, List, Dict, Sequence, Tuple

from abc import abstractmethod

from bubblejail.bubblejail_utils import BubblejailSettings
from bubblejail.bubblejail_directories import BubblejailDirectories
from bubblejail.bubblejail_instance import BubblejailInstance
from bubblejail.exceptions import BubblejailInstanceNotFoundError
from bubblejail.services import BubblejailService, ServiceOption, OptionBool, OptionStr, OptionSpaceSeparatedStr, \
    OptionStrList, CommonSettings

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gio

GLADE_UI_DIR = f'{BubblejailSettings.SHARE_PATH_STR}/bubblejail/gtk/'


@lru_cache
def list_installed_apps() -> Sequence[Gio.DesktopAppInfo]:
    return Gio.app_info_get_all()


def get_icon_name_by_app_id(app_id: str) -> Optional[str]:
    # TODO: Move it to a separate module?
    if not app_id.endswith('.desktop'):
        app_id = f'{app_id}.desktop'
    for app in list_installed_apps():
        if app.get_id() == app_id:
            icon: Gio.ThemedIcon = app.get_icon()
            if icon_names := icon.get_names():
                icon_names: Sequence[str]
                return icon_names[0]
    return None


class GladeBuilder:
    _glade_file: str
    _glade_root_id: str
    _glade_root_widget: Gtk.Widget
    _prefix = "_gui_"

    def __init__(self):
        super().__init__()
        builder = Gtk.Builder()
        builder.add_objects_from_file(self._glade_file, (self._glade_root_id,))
        classes: List[Type] = [self.__class__]
        classes.extend(self.__class__.__bases__)
        annotations: Dict[str, Type] = {}
        for cls in classes:
            if hasattr(cls, '__annotations__'):
                annotations.update(cls.__annotations__)
        for annotation in annotations:
            if annotation.startswith(self._prefix):
                setattr(self, annotation, builder.get_object(annotation[len(self._prefix):]))
        self._glade_root_widget = builder.get_object(self._glade_root_id)
        builder.connect_signals(self)


class GladeWidget(GladeBuilder, Gtk.Bin):
    def __init__(self):
        super().__init__()
        self.add(self._glade_root_widget)


class MainWindowInterface:
    _gui_left_button_group: Gtk.Container
    _gui_right_button_group: Gtk.Container

    def __init__(self):
        super().__init__()

    def get_left_buttons(self) -> Optional[Gtk.Container]:
        return self._gui_left_button_group

    def get_right_buttons(self) -> Optional[Gtk.Container]:
        return self._gui_right_button_group

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


class InstanceListWindow(MainWindowInterface, GladeWidget):
    _glade_file = f'{GLADE_UI_DIR}instance_list_ui.glade'
    _glade_root_id = 'instance_list_window'

    _gui_delete_instance_button: Gtk.Button
    _gui_add_instance_button: Gtk.Button
    _gui_edit_instance_button: Gtk.Button
    _gui_instance_list: Gtk.ListBox
    _gui_instance_info_label: Gtk.Label
    _gui_instance_info_icon: Gtk.Image
    _gui_instance_info_group: Gtk.Box

    def __init__(self, app: BubblejailConfigApp):
        super().__init__()
        self._app = app
        self._fill_list()
        # FIXME: Implement action for Delete button
        self._gui_delete_instance_button.get_parent().remove(self._gui_delete_instance_button)

    def select_instance(self, selection: Optional[str] = None):
        if selection is None:
            self.change_state_to_no_selection()
        else:
            # TODO: Find a better way to select list item by text
            for item in self._gui_instance_list.get_children():
                item: InstanceListItem
                if item.instance_name == selection:
                    self._gui_instance_list.select_row(item)
                    break
            self.change_state_to_user_selected()

    def _fill_list(self) -> None:
        names = sorted([instance_path.name for instance_path in BubblejailDirectories.iter_instances_path()])
        for name in names:
            self._gui_instance_list.add(InstanceListItem(name))

    def change_state_to_no_selection(self) -> None:
        # TODO: Unselect any selected row
        self._gui_instance_list.unselect_all()
        self._gui_delete_instance_button.set_sensitive(False)
        self._gui_edit_instance_button.set_sensitive(False)
        self._gui_instance_info_group.hide()

    def change_state_to_user_selected(self) -> None:
        self._gui_delete_instance_button.set_sensitive(True)
        self._gui_edit_instance_button.set_sensitive(True)
        self._gui_instance_info_group.show()
        self._fill_instance_info()

    def _fill_instance_info(self):
        row: InstanceListItem = self._gui_instance_list.get_selected_row()
        text = ''
        bubblejail_instance = BubblejailDirectories.instance_get(row.instance_name)
        instance_config = bubblejail_instance._read_config()
        service_names: List[str] = []
        for service in instance_config.iter_services():
            if service.pretty_name != 'Default settings':
                service_names.append(service.pretty_name)
            if isinstance(service, CommonSettings):
                service: CommonSettings
                executable = service.executable_name.get_gui_value().replace('\t', '\n')
                text += f'\n<b>Command line:</b> {executable}\n'
        if len(service_names) > 0:
            text += '\n<b>Enabled services:</b>\n' + ', '.join(service_names) + '\n'
        else:
            text += '\n<b>Enabled services:</b> None\n'
        self._gui_instance_info_label.set_label(text)
        icon_name: Optional[str] = None
        if desktop_entry_name := bubblejail_instance.metadata_desktop_entry_name:
            icon_name = get_icon_name_by_app_id(desktop_entry_name)
        if icon_name:
            self._gui_instance_info_icon.show()
            self._gui_instance_info_icon.set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        else:
            self._gui_instance_info_icon.hide()

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
        self._app.switch_to_new()

    def on_edit_instance_button_clicked(self, button: Gtk.Button) -> None:
        self._switch_app_to_edit_mode()

    def _switch_app_to_edit_mode(self) -> None:
        if selected_row := self._gui_instance_list.get_selected_row():
            selected_row: InstanceListItem
            self._app.switch_to_edit(selected_row.instance_name)


class OptionWidgetBase:
    def __init__(self, option: ServiceOption):
        super().__init__()
        self._option = option

    @abstractmethod
    def save(self) -> None: ...

    @abstractmethod
    def get_sizegroup_subwidget(self) -> Optional[Gtk.Widget]: ...


class BoolOptionWidget(OptionWidgetBase, GladeWidget):
    _glade_file = f'{GLADE_UI_DIR}instance_edit_ui.glade'
    _glade_root_id = 'bool_option_widget'

    _gui_bool_option_label: Gtk.Label
    _gui_bool_option_switch: Gtk.Switch

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gui_bool_option_label.set_text(self._option.pretty_name)
        self._gui_bool_option_label.set_tooltip_text(self._option.description)
        self._gui_bool_option_switch.set_active(bool(self._option.get_value()))
        self._gui_bool_option_switch.set_tooltip_text(self._option.description)

    def save(self) -> None:
        self._option.set_value(self._gui_bool_option_switch.get_active())

    def get_sizegroup_subwidget(self) -> Optional[Gtk.Widget]:
        return self._gui_bool_option_label


class StringOptionWidget(OptionWidgetBase, GladeWidget):
    _glade_file = f'{GLADE_UI_DIR}instance_edit_ui.glade'
    _glade_root_id = 'string_option_widget'

    _gui_string_option_label: Gtk.Label
    _gui_string_option_entry: Gtk.Entry

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gui_string_option_label.set_text(self._option.pretty_name)
        self._gui_string_option_label.set_tooltip_text(self._option.description)
        data = self._option.get_value()
        if isinstance(data, List):
            data = '\t'.join(data)
        self._gui_string_option_entry.set_text(data)
        self._gui_string_option_entry.set_tooltip_text(self._option.description)

    def save(self) -> None:
        self._option.set_value(self._gui_string_option_entry.get_text())

    def get_sizegroup_subwidget(self) -> Optional[Gtk.Widget]:
        return self._gui_string_option_label


class StrListItemWidget(GladeWidget):
    _glade_file = f'{GLADE_UI_DIR}instance_edit_ui.glade'
    _glade_root_id = 'strlist_item_widget'

    _gui_strlist_item_entry: Gtk.Entry

    def __init__(self, strlist_widget: StrListOptionWidget, string: str):
        super().__init__()
        self._strlist_widget = strlist_widget
        self._gui_strlist_item_entry.set_text(string)

    def get_text(self) -> str:
        return self._gui_strlist_item_entry.get_text()

    def on_strlist_item_del_button_clicked(self, button: Gtk.Button):
        self._strlist_widget.remove_item(self)


class StrListOptionWidget(OptionWidgetBase, GladeWidget):
    _glade_file = f'{GLADE_UI_DIR}instance_edit_ui.glade'
    _glade_root_id = 'strlist_option_widget'

    _gui_strlist_option_label: Gtk.Label
    _gui_strlist_option_strings: Gtk.VBox
    _gui_strlist_option_add_button: Gtk.Button

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gui_strlist_option_label.set_text(self._option.pretty_name)
        self._gui_strlist_option_label.set_tooltip_text(self._option.description)
        self._gui_strlist_option_add_button.set_tooltip_text(self._option.description)
        for string in self._option.get_value():
            self._gui_strlist_option_strings.add(StrListItemWidget(self, string))

    def _remove_empty_items(self):
        for item in self._gui_strlist_option_strings.get_children():
            item: StrListItemWidget
            if item.get_text() == '':
                self._gui_strlist_option_strings.remove(item)

    def save(self) -> None:
        self._remove_empty_items()
        strings: List[str] = []
        for item in self._gui_strlist_option_strings.get_children():
            item: StrListItemWidget
            strings.append(item.get_text())
        self._option.set_value(strings)

    def get_sizegroup_subwidget(self) -> Optional[Gtk.Widget]:
        return None

    def remove_item(self, item: StrListItemWidget):
        self._remove_empty_items()
        if item in self._gui_strlist_option_strings.get_children():
            self._gui_strlist_option_strings.remove(item)

    def on_strlist_option_add_button_clicked(self, button: Gtk.Button):
        self._remove_empty_items()
        self._gui_strlist_option_strings.add(StrListItemWidget(strlist_widget=self, string=''))
        self._gui_strlist_option_strings.show_all()


class ServiceWidget(GladeWidget):
    _glade_file = f'{GLADE_UI_DIR}instance_edit_ui.glade'
    _glade_root_id = 'service_widget'

    _gui_service_title: Gtk.Label
    _gui_rollup_button_image: Gtk.Image
    _gui_add_del_button_image: Gtk.Image
    _gui_service_description: Gtk.Label
    _gui_service_content: Gtk.VBox
    _gui_service_params_list: Gtk.VBox

    def __init__(self, edit_window: InstanceEditWindow, service: BubblejailService):
        super().__init__()
        self._option_widgets: List[OptionWidgetBase] = []
        self._size_group = Gtk.SizeGroup()
        self._size_group.set_mode(Gtk.SizeGroupMode.HORIZONTAL)
        self._rolled_up = False
        self._edit_window = edit_window
        self.service = service
        self._gui_service_title.set_text(service.pretty_name)
        self._gui_service_description.set_text(service.description)
        self._set_enabled_or_available_state()
        for option in service.iter_options():
            option_widget_class: Type[Union[OptionWidgetBase, Gtk.Container]]
            if isinstance(option, OptionBool):
                option_widget_class = BoolOptionWidget
            elif isinstance(option, (OptionStr, OptionSpaceSeparatedStr)):
                option_widget_class = StringOptionWidget
            elif isinstance(option, OptionStrList):
                option_widget_class = StrListOptionWidget
            else:
                raise NotImplementedError
            option_widget = option_widget_class(option=option)
            self._option_widgets.append(option_widget)
            self._gui_service_params_list.add(option_widget)
            if subwidget := option_widget.get_sizegroup_subwidget():
                self._size_group.add_widget(subwidget)

    def _set_enabled_or_available_state(self):
        # TODO: Find icons like stock gtk-delete, gtk-add
        #  DeprecationWarning: Gtk.Image.set_from_stock is deprecated
        icons = {True: 'gtk-delete', False: 'gtk-add'}
        self._gui_add_del_button_image.set_from_stock(icons[self.service.enabled], Gtk.IconSize.BUTTON)
        self._gui_service_params_list.set_sensitive(self.service.enabled)

    def save(self):
        for option_widget in self._option_widgets:
            option_widget.save()

    def on_add_del_button_clicked(self, button: Gtk.Button) -> None:
        self.service.enabled = not self.service.enabled
        self._edit_window.reparent_service_widget(self)
        self._set_enabled_or_available_state()

    def on_rollup_button_clicked(self, button: Gtk.Button) -> None:
        # TODO: Find icons like stock gtk-go-down, 'gtk-go-up
        #  DeprecationWarning: Gtk.Image.set_from_stock is deprecated
        self._rolled_up = not self._rolled_up
        icons = {True: 'gtk-go-down', False: 'gtk-go-up'}
        self._gui_service_content.set_visible(not self._rolled_up)
        self._gui_rollup_button_image.set_from_stock(icons[self._rolled_up], Gtk.IconSize.BUTTON)


class InstanceEditWindow(MainWindowInterface, GladeWidget):
    _glade_file = f'{GLADE_UI_DIR}instance_edit_ui.glade'
    _glade_root_id = 'instance_edit_window'

    _gui_enabled_services_vbox: Gtk.VBox
    _gui_enabled_services_stub: Gtk.Label
    _gui_available_services_vbox: Gtk.VBox

    def __init__(self, app: BubblejailConfigApp, instance_name: str):
        super().__init__()
        self._app = app
        self._need_save = False
        self._instance_name = instance_name
        self._service_widgets: List[ServiceWidget] = []
        self._bubblejail_instance = BubblejailDirectories.instance_get(instance_name)
        self._instance_config = self._bubblejail_instance._read_config()
        for service in self._instance_config.iter_services(iter_disabled=True, iter_default=False):
            service_widget = ServiceWidget(edit_window=self, service=service)
            self._service_widgets.append(service_widget)
            if service.enabled:
                self._gui_enabled_services_vbox.add(service_widget)
            else:
                self._gui_available_services_vbox.add(service_widget)
        self.on_enabled_services_vbox_add_remove()

    def get_subtitle(self) -> str:
        return self._instance_name

    def reparent_service_widget(self, service_widget: ServiceWidget):
        if service_widget in self._gui_enabled_services_vbox.get_children():
            self._gui_enabled_services_vbox.remove(service_widget)
        if service_widget in self._gui_available_services_vbox.get_children():
            self._gui_available_services_vbox.remove(service_widget)
        if service_widget.service.enabled:
            self._gui_enabled_services_vbox.add(service_widget)
        else:
            self._gui_available_services_vbox.add(service_widget)

    def on_back_to_list_button_clicked(self, button: Gtk.Button) -> None:
        if not self._need_save:
            self._app.switch_to_list()
        else:
            # FIXME: Add dialog box!
            print('Add dialog box!')

    def on_save_instance_button_clicked(self, button: Gtk.Button) -> None:
        for sw in self._service_widgets:
            sw.save()
        self._bubblejail_instance.save_config(self._instance_config)

    def on_enabled_services_vbox_add_remove(self, *args, **kwargs):
        if len(self._gui_enabled_services_vbox.get_children()) == 0:
            self._gui_enabled_services_stub.show()
        else:
            self._gui_enabled_services_stub.hide()


class NewInstanceWindow(MainWindowInterface, GladeWidget):
    _glade_file = f'{GLADE_UI_DIR}new_instance_ui.glade'
    _glade_root_id = 'new_instance_window'

    _gui_name_entry: Gtk.Entry
    _gui_profile_combo: Gtk.ComboBoxText
    _gui_desktop_switch: Gtk.Switch
    _gui_warning_label: Gtk.Label
    _gui_status_label: Gtk.Label
    _gui_save_instance_button: Gtk.Button

    def __init__(self, app: BubblejailConfigApp):
        super().__init__()
        self._app = app
        self._generate_profiles_list()
        self._validate_data()

    def get_subtitle(self) -> str:
        return 'Create new instance'

    def _generate_profiles_list(self):
        profiles_names = set()
        for profiles_directory in BubblejailDirectories.iter_profile_directories():
            for profile_file in profiles_directory.iterdir():
                profiles_names.add(profile_file.stem)
        for profile_name in sorted(profiles_names):
            self._gui_profile_combo.append_text(profile_name)


    def _validate_data(self):
        ok = False
        text = ''
        new_instance_name = self._gui_name_entry.get_text()
        profile_name = self._gui_profile_combo.get_active_text()
        existing_instance: Optional[BubblejailInstance] = None
        try:
            existing_instance = BubblejailDirectories.instance_get(new_instance_name)
        except BubblejailInstanceNotFoundError:
            ...
        if new_instance_name == '':
            text = 'Please enter a name for the instance'
        elif existing_instance is not None:
            text = f"Name '{new_instance_name}' is already used!"
        elif profile_name != 'None':
            profile = BubblejailDirectories.profile_get(profile_name)
            if profile.dot_desktop_path is not None and not profile.dot_desktop_path.is_file():
                text = f"Desktop entry for '{profile_name}' profile does not exist\n" \
                       f"Maybe you don't have application installed?"
            else:
                ok = True
                text = f"{profile.description}\n" \
                       f"Import tips:  {profile.import_tips}"
        else:
            ok = True
            text = 'Click Save to create new instance with empty profile'
        self._gui_status_label.set_text(text)
        if ok:
            self._gui_warning_label.hide()
            self._gui_save_instance_button.set_sensitive(True)
        else:
            self._gui_warning_label.show()
            self._gui_save_instance_button.set_sensitive(False)

    def on_back_to_list_button_clicked(self, button: Gtk.Button) -> None:
        self._app.switch_to_list()

    def on_save_instance_button_clicked(self, button: Gtk.Button) -> None:
        new_instance_name = self._gui_name_entry.get_text()
        create_dot_desktop = self._gui_desktop_switch.get_active()
        profile_name = self._gui_profile_combo.get_active_text()
        if profile_name == 'None':
            profile_name = None
        BubblejailDirectories.create_new_instance(
            new_name=new_instance_name,
            profile_name=profile_name,
            create_dot_desktop=create_dot_desktop,
        )
        self._app.switch_to_list(selection=new_instance_name)

    def on_name_entry_changed(self, entry: Gtk.Entry):
        self._validate_data()

    def on_profile_combo_changed(self, combo: Gtk.ComboBoxText):
        if profile_name := combo.get_active_text():
            profile = BubblejailDirectories.profile_get(profile_name)
            if profile.dot_desktop_path is not None:
                self._gui_name_entry.set_text(profile.dot_desktop_path.stem)
        self._validate_data()


class BubblejailConfigApp(GladeBuilder):
    _glade_file = f'{GLADE_UI_DIR}main_window.glade'
    _glade_root_id = 'main_window'

    _gui_main_window: Gtk.Window
    _gui_main_window_headerbar: Gtk.HeaderBar
    _gui_main_window_container: Gtk.Box

    _main_window_sizes: Dict[str, Tuple[int, int]] = {}

    def __init__(self):
        super().__init__()
        self.switch_to_list()
        self._gui_main_window.show_all()
        Gtk.main()

    def _clear_window(self) -> None:
        if len(self._gui_main_window_container.get_children()) > 0:
            # TODO: Multiple widgets?
            current_window_interface: Gtk.Widget = self._gui_main_window_container.get_children()[0]
            w, h = self._gui_main_window.get_size()
            self._main_window_sizes[current_window_interface.__class__.__name__] = (w, h)
        self._gui_main_window_container.foreach(self._gui_main_window_container.remove)
        self._gui_main_window_headerbar.foreach(self._gui_main_window_headerbar.remove)
        self._gui_main_window_headerbar.set_subtitle('')

    def _attach_window_interface(self, window_interface: Union[MainWindowInterface, Gtk.Widget]) -> None:
        self._clear_window()
        interface_name = window_interface.__class__.__name__
        if interface_name in self._main_window_sizes:
            # Restore previous size for that interface state
            w, h = self._main_window_sizes[interface_name]
            self._gui_main_window.resize(w, h)
        else:
            # Resize to minimal size
            w,h = self._gui_main_window.get_size()
            self._gui_main_window.resize(w, 100)
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

    def switch_to_list(self, selection: Optional[str] = None) -> None:
        window_interface = InstanceListWindow(app=self)
        self._attach_window_interface(window_interface)
        window_interface.select_instance(selection)

    def switch_to_edit(self, instance_name: str) -> None:
        self._attach_window_interface(InstanceEditWindow(app=self, instance_name=instance_name))

    def switch_to_new(self) -> None:
        self._attach_window_interface(NewInstanceWindow(app=self))

    def on_main_window_destroy(self, *args) -> None:
        Gtk.main_quit()
