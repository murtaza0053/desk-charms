"""Desk Charms settings: saved in ~/.config/desk-charms/settings.json, edited in a small window."""
import json
import os

from gi.repository import Gdk, Gtk

import objects

PATH = os.path.expanduser("~/.config/desk-charms/settings.json")
DEFAULTS = {
    "object": "nimbu",
    "size": 1.6,
    "swing": 20,        # degrees either way it keeps swinging on its own
    "sound": True,
    "volume": 0.8,
    "ambient": False,   # soft chime / bell / clink sounds during the normal swing
    "monitor": None,    # GDK monitor index; None = main screen
    "position": 0.5,    # fraction of the screen width
    "count": 1,
    "emoji": "🍀",      # what "Any emoji" hangs
}


def load():
    settings = dict(DEFAULTS)
    try:
        with open(PATH) as f:
            settings.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    if settings["object"] not in objects.BY_KEY:
        settings["object"] = DEFAULTS["object"]
    return settings


def save(settings):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp, PATH)


class SettingsWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(title="Desk Charms Settings")
        self.app = app
        s = app.settings
        self.set_keep_above(True)
        self.set_border_width(18)
        self.set_default_size(420, -1)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name("preferences-desktop")

        grid = Gtk.Grid(column_spacing=18, row_spacing=12)
        self.add(grid)
        self.row = 0

        kinds = Gtk.ComboBoxText()
        for kind in objects.KINDS:
            kinds.append(kind.key, kind.label)
        kinds.set_active_id(s["object"])
        kinds.connect("changed", lambda w: self.set("object", w.get_active_id()))
        self.add_row("Object", kinds)

        emoji = Gtk.Entry(text=s["emoji"], max_length=8, width_chars=6)
        emoji.set_tooltip_text("Used when the object is \"Any emoji\". Press Super+. to open the emoji picker.")
        emoji.connect("changed", lambda w: self.set("emoji", w.get_text()))
        self.add_row("Emoji", emoji)

        self.add_row("Size", self.slider(1.0, 3.0, 0.1, s["size"], 1, "size"))
        self.add_row("Swing", self.slider(0, 40, 1, s["swing"], 0, "swing", "°"))

        self.add_heading("Sound")
        self.add_row("Sound effects", self.switch("sound"))
        self.add_row("Volume", self.slider(0, 100, 5, s["volume"] * 100, 0, "volume", "%", factor=0.01))
        self.add_row("Gentle sounds while swinging", self.switch("ambient"))

        self.add_heading("Where")
        screens = Gtk.ComboBoxText()
        screens.append("main", "Main screen")
        display = Gdk.Display.get_default()
        for i in range(display.get_n_monitors()):
            mon = display.get_monitor(i)
            model = mon.get_model() or ""
            name = ("Laptop screen" if model.startswith(("eDP", "LVDS", "DSI")) else
                    f"{model.split('-')[0]} screen" if model else f"Screen {i + 1}")
            screens.append(str(i), f"{name}{' (main)' if mon.is_primary() else ''}")
        screens.set_active_id("main" if s["monitor"] is None else str(s["monitor"]))
        screens.connect("changed", lambda w: self.set(
            "monitor", None if w.get_active_id() == "main" else int(w.get_active_id())))
        self.add_row("Screen", screens)
        self.add_row("Position from left", self.slider(0, 100, 1, s["position"] * 100, 0, "position", "%",
                                                       factor=0.01))
        count = Gtk.SpinButton.new_with_range(1, 5, 1)
        count.set_value(s["count"])
        count.connect("value-changed", lambda w: self.set("count", int(w.get_value())))
        count.set_halign(Gtk.Align.START)
        self.add_row("How many", count)

        close = Gtk.Button(label="Close")
        close.connect("clicked", lambda _b: self.destroy())
        close.set_halign(Gtk.Align.END)
        grid.attach(close, 0, self.row, 2, 1)

    def add_row(self, label, widget):
        text = Gtk.Label(label=label, xalign=0)
        widget.set_hexpand(True)
        self.get_child().attach(text, 0, self.row, 1, 1)
        self.get_child().attach(widget, 1, self.row, 1, 1)
        self.row += 1

    def add_heading(self, label):
        heading = Gtk.Label(xalign=0)
        heading.set_markup(f"<b>{label}</b>")
        heading.set_margin_top(6)
        self.get_child().attach(heading, 0, self.row, 2, 1)
        self.row += 1

    def slider(self, low, high, step, value, digits, key, unit="", factor=1.0):
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, low, high, step)
        scale.set_value(value)
        scale.set_digits(digits)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        if unit:
            scale.connect("format-value", lambda _s, v: f"{v:.{digits}f}{unit}")
        scale.connect("value-changed", lambda w: self.set(key, round(w.get_value() * factor, 3)))
        return scale

    def switch(self, key):
        switch = Gtk.Switch(active=self.app.settings[key])
        switch.set_halign(Gtk.Align.START)
        switch.set_hexpand(False)
        switch.connect("notify::active", lambda w, _p: self.set(key, w.get_active()))
        return switch

    def set(self, key, value):
        self.app.change(key, value)
