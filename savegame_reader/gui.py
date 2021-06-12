import json
import os
import urwid

from .enums import FieldType


class SavegameBrowser:
    palette = [
        ("body", "light gray", "black"),
        ("focus", "light gray", "dark blue", "standout"),
        ("head", "yellow", "black", "standout"),
        ("foot", "light gray", "black"),
        ("key", "light cyan", "black", "underline"),
        ("title", "white", "black", "bold"),
        ("flag", "dark gray", "light gray"),
        ("error", "dark red", "light gray"),
        ("disabled", "dark red", "black"),
    ]

    footer_text = [
        ("title", "Savegame Browser"),
        "    ",
        ("key", "UP"),
        ",",
        ("key", "DOWN"),
        ",",
        ("key", "PAGE UP"),
        ",",
        ("key", "PAGE DOWN"),
        "  ",
        ("key", "SPACE"),
        "  ",
        ("key", "+"),
        ",",
        ("key", "-"),
        "  ",
        ("key", "LEFT"),
        "  ",
        ("key", "HOME"),
        "  ",
        ("key", "END"),
        "  ",
        ("key", "Q"),
    ]

    def ChunkFocus(self):
        self.indexes.clear()

        if self.chunks.focus is None:
            return

        chunk = self.chunks[self.chunks.focus].original_widget.label

        if self._savegame.items[chunk]:
            for key in self._savegame.items[chunk].keys():
                button = urwid.Button(str(key))
                self.indexes.append(urwid.AttrMap(button, None, focus_map="reversed"))

    def add_table(self, tables, fields, table_key="root", prefix=""):
        table = tables[table_key]

        for key, value in fields.items():
            field = [field for field in table if field[2] == key][0]
            header = f"{field[0].name}"

            if field[0] == FieldType.STRUCT:
                svalue = value
                value = f"(length: {len(svalue)})"
            else:
                value = json.dumps(value)

            key_field = urwid.AttrMap(urwid.Text(f"{prefix}{key}"), None, focus_map="reversed")
            value_field = urwid.Text(value)
            type_field = urwid.Text(header)

            self.fields.append(
                urwid.Columns(
                    [(50, key_field), value_field, (10, type_field)],
                    dividechars=2,
                )
            )

            if field[0] == FieldType.STRUCT:
                for i, item in enumerate(svalue):
                    self.add_table(tables, item, field[2], f"{prefix}{field[2]}[{i}].")

    def IndexFocus(self):
        self.fields.clear()

        if self.indexes.focus is None:
            return

        chunk = self.chunks[self.chunks.focus].original_widget.label
        index = self.indexes[self.indexes.focus].original_widget.label

        tables = self._savegame.tables[chunk]
        fields = self._savegame.items[chunk][index]

        self.add_table(tables, fields)

    def __init__(self, savegame):
        self._savegame = savegame

        self.chunks = urwid.SimpleFocusListWalker([])
        self.indexes = urwid.SimpleFocusListWalker([])
        self.fields = urwid.SimpleFocusListWalker([])

        for key, table in self._savegame.tables.items():
            if "unsupported" in table:
                continue

            button = urwid.Button(key)
            self.chunks.append(urwid.AttrMap(button, None, focus_map="reversed"))

        for key, table in self._savegame.tables.items():
            if "unsupported" not in table:
                continue

            button = urwid.Button(key)
            self.chunks.append(urwid.AttrMap(button, "disabled", focus_map="reversed"))
        self.ChunkFocus()
        self.IndexFocus()

        urwid.connect_signal(self.chunks, "modified", self.ChunkFocus)
        urwid.connect_signal(self.indexes, "modified", self.IndexFocus)

        self.body = urwid.Columns(
            [(20, urwid.ListBox(self.chunks)), (10, urwid.ListBox(self.indexes)), urwid.ListBox(self.fields)],
            dividechars=2,
        )

        self.header = urwid.Text(f"Savegame: {os.path.basename(savegame.filename)}")
        self.footer = urwid.AttrWrap(urwid.Text(self.footer_text), "foot")
        self.view = urwid.Frame(
            urwid.AttrWrap(self.body, "body"), header=urwid.AttrWrap(self.header, "head"), footer=self.footer
        )

    def run(self):
        """Run the program."""

        self.loop = urwid.MainLoop(self.view, self.palette, unhandled_input=self.unhandled_input)
        self.loop.run()

    def unhandled_input(self, k):
        if k in ("q", "Q"):
            raise urwid.ExitMainLoop()
