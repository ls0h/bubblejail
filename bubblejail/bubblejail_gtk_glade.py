from typing import List, Type, Dict

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


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
