#!/usr/bin/env python3
"""Desk Charms: a lucky charm (nimbu-mirchi, nazar, daruma, ...) hanging from the top of the screen.

The thread is elastic: drag the object down or sideways and let go to watch it bounce.
Left-click it to give it a push; right-click it for Settings and Quit.
Everything else on the window is click-through.

Settings live in ~/.config/desk-charms/settings.json. Command-line options override them
for this run: desk_charms.py [--object KEY] [--monitor N] [--size S] [--swing DEG] [--mute]
[x-position ...]
`desk_charms.py --settings` opens the settings window of the running copy (or starts one).
"""
import argparse
import math
import os
import random
import signal
import threading

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

import objects  # noqa: E402
import settings  # noqa: E402
import sounds  # noqa: E402

TWIST_STIFFNESS = 0.6  # torsion of the thread: a slow ~8s turn back and forth
TWIST_DAMPING = 0.08
TWIST_AMPLITUDE = 1.0  # radians either way it keeps turning by itself
TWIST_PUMP = 0.15
SHADOW = (4.0, 6.0)    # where the soft shadow falls on the screen, down and to the right
GRAVITY = 800.0        # px/s^2; with the string length this gives a ~2.6s swing
STIFFNESS = 160.0      # elastic string spring constant (per unit mass)
DAMPING = 0.5
MAX_FLING = 2500.0
PUMP = 150.0           # strongest sideways nudge used to hold the automatic swing
SUBSTEPS = 4
FPS = 60
PIDFILE = os.path.expanduser("~/.cache/desk-charms/running.pid")
SPACING = 0.12        # gap between several dangles, as a fraction of the screen width
LOOK_RANGE = 250       # px: the nazar's eye looks fully towards a pointer this far away
REBUILD_DELAY = 250    # ms to wait for a slider to settle before rebuilding the windows


def draw_thread(cr, x0, y0, x1, y1, width, shadow=False):
    """Cotton thread: a light core, darker edges and a twist pattern."""
    cr.save()
    cr.move_to(x0, y0)
    cr.line_to(x1, y1)
    if shadow:
        cr.set_source_rgba(0, 0, 0, 0.16)
        cr.set_line_width(width * 1.8)
        cr.stroke()
    else:
        cr.set_source_rgb(0.52, 0.47, 0.40)
        cr.set_line_width(width * 1.5)
        cr.stroke_preserve()
        cr.set_source_rgb(0.95, 0.92, 0.85)
        cr.set_line_width(width)
        cr.stroke_preserve()
        cr.set_source_rgba(0.60, 0.55, 0.46, 0.9)
        cr.set_line_width(width * 0.9)
        cr.set_dash([width * 0.7, width * 1.6])
        cr.stroke()
    cr.restore()


def draw_line(cr, line, offset, shadow=False):
    """Clear fishing line between the parts of a wind chime."""
    cr.move_to(line.x0, line.y0 + offset)
    cr.line_to(line.x1, line.y1 + offset)
    cr.set_source_rgba(0, 0, 0, 0.12) if shadow else cr.set_source_rgba(0.88, 0.88, 0.9, 0.85)
    cr.set_line_width(0.45)
    cr.stroke()


class Dangle(Gtk.Window):
    def __init__(self, app, kind, x_frac, monitor, scale):
        super().__init__(title="Desk Charms")
        self.app = app
        self.kind = kind
        self.scale = scale
        self.natural = kind.handle_y - GRAVITY / STIFFNESS  # so the handle rests exactly at handle_y
        self.creak_at = 0.0   # stretch at which the last creak played
        self.creak_time = 0
        self.last_knock = 0
        self.menu = None
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)
        self.stick()
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        display = Gdk.Display.get_default()
        mon = display.get_monitor(monitor) if monitor is not None and monitor < display.get_n_monitors() else None
        geo = (mon or display.get_primary_monitor() or display.get_monitor(0)).get_geometry()
        # the window covers the whole monitor so the object can be pulled anywhere on it;
        # it stays transparent and click-through apart from the object itself
        self.set_default_size(geo.width, geo.height)
        self.move(geo.x, geo.y)
        self.origin = (geo.x, geo.y)
        self.w, self.h = geo.width / scale, geo.height / scale
        self.pivot_x = self.w * x_frac
        self.dirty = None

        # handle position relative to the pivot, and its velocity
        h = kind.handle_y
        self.x = random.uniform(-0.3, 0.3) * h
        self.y = math.sqrt(h ** 2 - self.x ** 2)
        self.vx = self.vy = 0.0
        self.twist = random.uniform(-1, 1)
        self.twist_v = 0.0
        self.kind_state = {}  # the object's own animation (nazar blinking)
        self.last = GLib.get_monotonic_time()

        self.dragging = False
        self.moved = False
        self.grab = (0.0, 0.0)
        self.press = (0.0, 0.0)
        self.last_motion = 0

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_press)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("button-release-event", self.on_release)
        self.connect("realize", lambda _w: self.set_hand("grab"))
        self.timers =[GLib.timeout_add(1000 // FPS, self.tick), GLib.timeout_add(2500, self.breeze)]
        self.connect("destroy", lambda _w: [GLib.source_remove(t) for t in self.timers])

    def set_hand(self, name):
        """Open hand over the object ("grab"), closed hand while dragging ("grabbing")."""
        display = self.get_display()
        fallback = {"grab": "openhand", "grabbing": "closedhand"}[name]
        cursor = Gdk.Cursor.new_from_name(display, name) or Gdk.Cursor.new_from_name(display, fallback)
        if self.get_window():
            self.get_window().set_cursor(cursor)

    def play(self, name, volume):
        s = self.app.settings
        if s["sound"]:
            sounds.play(name, volume * s["volume"])

    def swing_energy(self, degrees=None):
        """Energy of a swing that reaches `degrees` either side (the setting by default)."""
        degrees = self.app.settings["swing"] if degrees is None else degrees
        return GRAVITY * self.kind.handle_y * (1 - math.cos(math.radians(degrees)))

    def energy(self):
        return 0.5 * (self.vx ** 2 + self.vy ** 2) + GRAVITY * (self.kind.handle_y - self.y)

    def handle_centre(self):
        return self.pivot_x + self.x, self.y

    def update_input_shape(self):
        # only the object catches clicks; the rest of the window passes them through
        x, y = self.handle_centre()
        rx, ry = self.kind.hit
        s = self.scale
        rect = cairo.RectangleInt(int((x - rx) * s), int((y - ry) * s), int(2 * rx * s), int(2 * ry * s))
        self.input_shape_combine_region(cairo.Region(rect))

    def keep_in_window(self):
        kind = self.kind
        min_x, max_x = 40 - self.pivot_x, self.w - 40 - self.pivot_x
        min_y, max_y = kind.handle_y - kind.top + 6, self.h - kind.bottom - 16
        if not min_x <= self.x <= max_x:
            self.x = min(max(self.x, min_x), max_x)
            self.vx *= -0.3
        if not min_y <= self.y <= max_y:
            self.y = min(max(self.y, min_y), max_y)
            self.vy *= -0.3

    def step(self, h, target):
        r = math.hypot(self.x, self.y)
        ax, ay = 0.0, GRAVITY
        if target > 0:
            # nudge along the swing when it is too small, brake when it is too big
            deficit = max(-1.0, min(1.0, (target - self.energy()) / target))
            direction = math.copysign(1.0, self.vx) if abs(self.vx) > 1 else 1.0
            ax += PUMP * deficit * direction
        if r > self.natural:  # an elastic string only pulls, it never pushes
            pull = STIFFNESS * (r - self.natural) / r
            ax -= pull * self.x
            ay -= pull * self.y
        self.vx += (ax - DAMPING * self.vx) * h
        self.vy += (ay - DAMPING * self.vy) * h
        self.x += self.vx * h
        self.y += self.vy * h

    def step_twist(self, dt):
        """The thread twisting and untwisting, kept going at about TWIST_AMPLITUDE."""
        energy = 0.5 * self.twist_v ** 2 + 0.5 * TWIST_STIFFNESS * self.twist ** 2
        amplitude = getattr(self.kind, "twist_amplitude", TWIST_AMPLITUDE)
        target = 0.5 * TWIST_STIFFNESS * amplitude ** 2
        deficit = max(-1.0, min(1.0, (target - energy) / target))
        direction = math.copysign(1.0, self.twist_v) if abs(self.twist_v) > 0.01 else 1.0
        accel = (-TWIST_STIFFNESS * self.twist - TWIST_DAMPING * self.twist_v
                 + TWIST_PUMP * deficit * direction)
        self.twist_v += accel * dt
        self.twist += self.twist_v * dt

    def swing_end_sounds(self, old_vx):
        """When the swing turns round: knock hard after a pull, or softly if gentle sounds are on."""
        if self.dragging or old_vx == 0 or (old_vx > 0) == (self.vx > 0):
            return
        now = GLib.get_monotonic_time()
        if now - self.last_knock < 250_000:
            return
        self.last_knock = now
        strength = self.energy() / self.swing_energy(20)
        if strength > 2.0:
            self.kind.knock(self.play, strength)
        elif self.app.settings["ambient"]:
            self.kind.ambient(self.play)

    def tick(self):
        now = GLib.get_monotonic_time()
        dt = min((now - self.last) / 1e6, 0.05)
        self.last = now
        if not self.dragging:
            old_vx = self.vx
            target = self.swing_energy()
            for _ in range(SUBSTEPS):
                self.step(dt / SUBSTEPS, target)
            self.keep_in_window()
            self.swing_end_sounds(old_vx)
        self.step_twist(dt)
        if getattr(self.kind, "follows_pointer", False):
            self.kind_state["look_target"] = self.look_target()
        self.kind.tick(self.kind_state, dt, self.dragging)
        if self.get_realized():
            self.update_input_shape()
        self.queue_redraw()
        return True

    def look_target(self):
        """Direction from the object to the mouse pointer, in the dangle's own (swung) frame,
        as a vector up to length 1 (full length from LOOK_RANGE pixels away)."""
        _screen, px, py = self.get_display().get_default_seat().get_pointer().get_position()
        dx = px - (self.origin[0] + (self.pivot_x + self.x) * self.scale)
        dy = py - (self.origin[1] + self.y * self.scale)
        dist = math.hypot(dx, dy)
        if dist < 1:
            return 0.0, 0.0
        angle = math.atan2(-self.x, self.y)  # the drawing is rotated by the swing, so undo it
        lx = dx * math.cos(angle) + dy * math.sin(angle)
        ly = -dx * math.sin(angle) + dy * math.cos(angle)
        reach = min(1.0, dist / LOOK_RANGE) / dist
        return lx * reach, ly * reach

    def queue_redraw(self):
        # repaint only around the thread and object (old and new spot), not the whole monitor
        x, y = self.handle_centre()
        s, reach = self.scale, self.kind.reach
        box = cairo.RectangleInt(int((min(self.pivot_x, x) - reach) * s), 0,
                                 int((abs(x - self.pivot_x) + 2 * reach) * s), int((y + reach) * s))
        region = cairo.Region(box)
        if self.dirty:
            region.union(self.dirty)
        self.dirty = box
        self.queue_draw_region(region)

    def breeze(self):
        if not self.dragging and random.random() < 0.6:
            self.vx += random.uniform(-35, 35)
        return True

    def show_menu(self, event):
        self.menu = Gtk.Menu()
        for label, action in (("Settings…", self.app.open_settings), ("Quit Desk Charms", self.app.quit)):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _i, a=action: a())
            self.menu.append(item)
        self.menu.show_all()
        self.menu.attach_to_widget(self)
        self.menu.popup_at_pointer(event)

    def on_press(self, _widget, event):
        if event.button == 3:
            self.show_menu(event)
        elif event.button == 1:
            x, y = self.handle_centre()
            ex, ey = event.x / self.scale, event.y / self.scale
            self.dragging = True
            self.moved = False
            self.grab = (ex - x, ey - y)
            self.press = (ex, ey)
            self.last_motion = event.time
            self.vx = self.vy = 0.0
            self.creak_at = self.stretch()
            self.set_hand("grabbing")
        return True

    def stretch(self):
        return math.hypot(self.x, self.y) - self.kind.handle_y

    def creak_while_pulling(self, time):
        """A rubbery creak each time the thread is pulled another notch longer."""
        stretch = self.stretch()
        self.creak_at = min(self.creak_at, stretch)  # easing off lets the next pull creak again
        if stretch > self.creak_at + 35 and time - self.creak_time > 90:
            self.play("creak", 0.3 + 0.5 * min(1.0, stretch / 400))
            self.creak_at = stretch
            self.creak_time = time

    def on_motion(self, _widget, event):
        if not self.dragging:
            return False
        old_x, old_y = self.x, self.y
        ex, ey = event.x / self.scale, event.y / self.scale
        self.x = ex - self.grab[0] - self.pivot_x
        self.y = ey - self.grab[1]
        self.keep_in_window()
        if math.hypot(ex - self.press[0], ey - self.press[1]) > 4:
            self.moved = True
        self.creak_while_pulling(event.time)
        # remember how fast the hand was moving so letting go can fling it
        elapsed = max(event.time - self.last_motion, 1) / 1000
        self.last_motion = event.time
        self.vx = 0.5 * self.vx + 0.5 * (self.x - old_x) / elapsed
        self.vy = 0.5 * self.vy + 0.5 * (self.y - old_y) / elapsed
        return True

    def on_release(self, _widget, event):
        if event.button != 1 or not self.dragging:
            return False
        self.dragging = False
        self.set_hand("grab")
        if self.moved and self.stretch() > 15:
            self.kind.release(self.play, min(1.0, self.stretch() / 350))
        if not self.moved:  # a plain click is a push away from the click
            x, _ = self.handle_centre()
            self.vx += 250 if event.x / self.scale < x else -250
        elif event.time - self.last_motion > 80:  # held still before letting go
            self.vx = self.vy = 0.0
        speed = math.hypot(self.vx, self.vy)
        if speed > MAX_FLING:
            self.vx *= MAX_FLING / speed
            self.vy *= MAX_FLING / speed
        self.twist_v += self.vx * 0.0015  # a sideways fling sets it spinning too
        self.last_knock = 0
        return True

    def on_draw(self, _widget, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.scale(self.scale, self.scale)

        kind = self.kind
        r = max(math.hypot(self.x, self.y), 1.0)
        angle = math.atan2(-self.x, self.y)
        cr.translate(self.pivot_x, 0)
        cr.rotate(angle)
        # undo the swing rotation so the shadow always falls the same way on the screen
        sx, sy = SHADOW
        shadow = (sx * math.cos(angle) + sy * math.sin(angle),
                  -sx * math.sin(angle) + sy * math.cos(angle))

        offset = r - kind.handle_y  # the object rides on the stretched part of the thread
        thread_end = kind.thread_end + offset
        width = max(0.6, 1.3 * min(1.0, kind.handle_y / r))  # the thread thins as it stretches
        pieces, lines = kind.layout(self.twist, self.kind_state)

        cr.save()
        cr.translate(*shadow)
        draw_thread(cr, 0, 0, 0, thread_end, width, shadow=True)
        for line in lines:
            draw_line(cr, line, offset, shadow=True)
        cr.restore()
        for piece in pieces:
            if not piece.shadow:
                continue
            cr.save()
            cr.translate(shadow[0] + piece.x, shadow[1] + offset + piece.y)
            cr.rotate(piece.tilt)
            piece.sprite.paint_shadow(cr, piece.x_scale)
            cr.restore()

        # back to front; the main thread sits at depth 0
        items = [(p.depth, 1, p) for p in pieces] + [(l.depth, 0, l) for l in lines]
        items.sort(key=lambda item: (item[0], item[1]))
        thread_drawn = False
        for depth, _order, item in items:
            if depth >= 0 and not thread_drawn:
                draw_thread(cr, 0, 0, 0, thread_end, width)
                thread_drawn = True
            if isinstance(item, objects.Line):
                draw_line(cr, item, offset)
                continue
            cr.save()
            cr.translate(item.x, offset + item.y)
            cr.rotate(item.tilt)
            item.sprite.paint(cr, item.x_scale, item.alpha)
            cr.restore()
        if not thread_drawn:
            draw_thread(cr, 0, 0, 0, thread_end, width)
        return False


class App:
    def __init__(self, prefs, positions=None):
        self.settings = prefs
        self.fixed_positions = positions  # from the command line, if given
        self.dangles = []
        self.settings_window = None
        self.rebuild_timer = None

    def positions(self):
        if self.fixed_positions:
            return self.fixed_positions
        n, start = self.settings["count"], self.settings["position"]
        start = min(start, max(0.02, 0.98 - (n - 1) * SPACING))  # keep them all on the screen
        return [start + i * SPACING for i in range(n)]

    def build(self):
        s = self.settings
        kind = objects.BY_KEY[s["object"]]
        if isinstance(kind, objects.EmojiCharm):
            kind.set_text(s["emoji"])
        kind.ready(s["size"])
        old, self.dangles = self.dangles, []
        for x_frac in self.positions():
            dangle = Dangle(self, kind, x_frac, s["monitor"], s["size"])
            dangle.show_all()
            self.dangles.append(dangle)
        for dangle in old:
            dangle.destroy()

    def change(self, key, value):
        self.settings[key] = value
        if key == "position":
            self.fixed_positions = None
        settings.save(self.settings)
        if key in ("object", "size", "monitor", "position", "count") or (
                key == "emoji" and self.settings["object"] == "emoji"):
            if self.rebuild_timer:
                GLib.source_remove(self.rebuild_timer)
            self.rebuild_timer = GLib.timeout_add(REBUILD_DELAY, self.rebuild_now)

    def rebuild_now(self):
        self.rebuild_timer = None
        self.build()
        return False

    def open_settings(self):
        if self.settings_window is None:
            self.settings_window = settings.SettingsWindow(self)
            self.settings_window.connect("destroy", lambda _w: setattr(self, "settings_window", None))
            self.settings_window.show_all()
        self.settings_window.present()

    def quit(self):
        Gtk.main_quit()


def running_pid():
    """PID of a Desk Charms that is already running, or None."""
    try:
        with open(PIDFILE) as f:
            pid = int(f.read().strip())
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            if b"desk_charms" in f.read():
                return pid
    except (OSError, ValueError):
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description="Lucky charm that hangs from the top of the screen.")
    parser.add_argument("positions", nargs="*", type=float)
    parser.add_argument("--object", choices=list(objects.BY_KEY))
    parser.add_argument("--monitor", type=int)
    parser.add_argument("--size", type=float)
    parser.add_argument("--swing", type=float)
    parser.add_argument("--mute", action="store_true")
    parser.add_argument("--settings", action="store_true", help="open the settings window")
    args = parser.parse_args()

    pid = running_pid()
    overrides = args.positions or any(getattr(args, k) is not None for k in ("object", "monitor", "size", "swing"))
    if pid and (args.settings or not overrides):
        # already running (e.g. started at login): show its settings instead of a second copy
        os.kill(pid, signal.SIGUSR1)
        return

    prefs = settings.load()
    for key in ("object", "monitor", "size", "swing"):
        if getattr(args, key) is not None:
            prefs[key] = getattr(args, key)
    if args.mute:
        prefs["sound"] = False
    threading.Thread(target=sounds.prepare, daemon=True).start()  # first run: a few seconds

    app = App(prefs, args.positions or None)
    app.build()
    if args.settings:
        app.open_settings()
    os.makedirs(os.path.dirname(PIDFILE), exist_ok=True)
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, lambda: app.open_settings() or True)
    try:
        Gtk.main()
    finally:
        if running_pid() == os.getpid():
            os.remove(PIDFILE)


if __name__ == "__main__":
    main()
