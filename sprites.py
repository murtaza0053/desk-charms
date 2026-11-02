"""Sprites for Desk Charms.

Real photos (assets/, see CREDITS.txt) for the chilli, lemon, coal, bell and nazar; the wind
chime and the glass beads are drawn here with cairo. Sizes are in the app's model units.
"""
import math
import os
import random

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
DRAW_RES = 8  # pixels per model unit for the parts drawn in code

LEMON_WIDTH = 72
LEMON_RX, LEMON_RY = 34, 25   # clickable area around the lemon centre
COAL_WIDTH = 18
CHILLI_LENGTHS = (80, 72, 86)  # three sizes so the chillies don't all look identical
CHILLI_PIERCE = 0.45           # how far along the chilli the string goes through


def shadow_of(surface, blur=6):
    """A soft black silhouette, stored small so painting it scaled up blurs it."""
    margin = blur * 3
    w = (surface.get_width() + 2 * margin) // blur + 1
    h = (surface.get_height() + 2 * margin) // blur + 1
    small = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(small)
    cr.scale(1 / blur, 1 / blur)
    cr.set_source_rgba(0, 0, 0, 1)
    cr.mask_surface(surface, margin, margin)
    return small, margin, blur


class Sprite:
    def __init__(self, surface, ax, ay, res):
        """ax, ay: anchor in model units; res: surface pixels per model unit."""
        self.original, self.original_res = surface, res
        self.surface, self.res = surface, res
        self.ax, self.ay = ax, ay
        self.shadow, self.margin, self.blur = shadow_of(surface)

    def prepare(self, scale):
        """Downscale once to on-screen size so each frame only rotates, never shrinks."""
        src = self.original
        w = max(1, round(src.get_width() * scale / self.original_res))
        h = max(1, round(src.get_height() * scale / self.original_res))
        small = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(small)
        cr.scale(w / src.get_width(), h / src.get_height())
        cr.set_source_surface(src, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_BEST)
        cr.paint()
        self.surface, self.res = small, scale

    def paint(self, cr, flip=1, alpha=1.0):
        cr.save()
        cr.scale(flip / self.res, 1 / self.res)
        cr.set_source_surface(self.surface, -self.ax * self.res, -self.ay * self.res)
        cr.get_source().set_filter(cairo.FILTER_BILINEAR)
        cr.paint_with_alpha(alpha)
        cr.restore()

    def paint_shadow(self, cr, flip=1, alpha=0.3):
        res = self.original_res
        cr.save()
        cr.scale(flip / res, 1 / res)
        cr.translate(-self.ax * res - self.margin, -self.ay * res - self.margin)
        cr.scale(self.blur, self.blur)
        cr.set_source_surface(self.shadow, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_BILINEAR)
        cr.paint_with_alpha(alpha)
        cr.restore()


def recoloured(sprite, colour, amount=1.0, mirror=False, lighting=0.35, sphere=False, alpha=1.0):
    """A copy of a sprite's shape, tinted towards `colour` (amount 1 = solid colour).

    Used for the edge slices and backs of 3D charms. `lighting` adds a left-lit gradient,
    `sphere` a round shading for figures, `mirror` flips it (the back of a flat charm).
    """
    src = sprite.original
    w, h = src.get_width(), src.get_height()
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(out)
    cr.save()
    if mirror:
        cr.translate(w, 0)
        cr.scale(-1, 1)
    cr.set_source_surface(src, 0, 0)
    cr.paint_with_alpha(alpha)
    cr.restore()
    cr.set_operator(cairo.OPERATOR_ATOP)  # only touch pixels the shape already covers
    cr.set_source_rgba(*colour, amount)
    cr.paint()
    if sphere:
        shade = cairo.RadialGradient(w * 0.35, h * 0.3, min(w, h) * 0.05, w * 0.5, h * 0.5, max(w, h) * 0.62)
        shade.add_color_stop_rgba(0, 1, 1, 1, 0.35)
        shade.add_color_stop_rgba(0.55, 1, 1, 1, 0)
        shade.add_color_stop_rgba(1, 0, 0, 0, 0.45)
        cr.set_source(shade)
        cr.paint()
    if lighting:
        light = cairo.LinearGradient(0, 0, w, h * 0.3)
        light.add_color_stop_rgba(0, 1, 1, 1, lighting * 0.6)
        light.add_color_stop_rgba(0.5, 0, 0, 0, 0)
        light.add_color_stop_rgba(1, 0, 0, 0, lighting)
        cr.set_source(light)
        cr.paint()
    ax = (w / sprite.original_res - sprite.ax) if mirror else sprite.ax
    return Sprite(out, ax, sprite.ay, sprite.original_res)


class Sheen:
    """A soft band of reflected light clipped to a sprite's shape; `pos` slides it across."""

    def __init__(self, shape, pos, strength):
        self.shape, self.pos, self.strength = shape, pos, strength

    def paint(self, cr, flip=1, alpha=1.0):
        s = self.shape
        cr.save()
        cr.scale(flip / s.res, 1 / s.res)
        w, h = s.surface.get_width(), s.surface.get_height()
        x0, y0 = -s.ax * s.res, -s.ay * s.res
        centre = x0 + w * self.pos
        band = cairo.LinearGradient(centre - w * 0.35, y0, centre + w * 0.35, y0 + h * 0.25)
        band.add_color_stop_rgba(0, 1, 1, 1, 0)
        band.add_color_stop_rgba(0.5, 1, 1, 1, self.strength * alpha)
        band.add_color_stop_rgba(1, 1, 1, 1, 0)
        cr.set_source(band)
        cr.mask_surface(s.surface, x0, y0)
        cr.restore()

    def paint_shadow(self, *_args, **_kw):
        pass


# --- photos -----------------------------------------------------------------------------------

def _load(name):
    return cairo.ImageSurface.create_from_png(os.path.join(ASSETS, name))


def photo(name, width, anchor=(0.5, 0.5)):
    """A photo `width` model units wide, anchored at a fraction of its size."""
    surface = _load(name)
    res = surface.get_width() / width
    return Sprite(surface, anchor[0] * surface.get_width() / res,
                  anchor[1] * surface.get_height() / res, res)


def _column_centre(surface, x):
    """Middle of the opaque pixels in one column, i.e. the chilli's centre line there."""
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()
    ys = [y for y in range(surface.get_height()) if data[y * stride + x * 4 + 3] > 128]
    return (ys[0] + ys[-1]) / 2 if ys else surface.get_height() / 2


def emoji(text, width):
    """A colour emoji from the system emoji font, `width` model units wide, anchored at its centre."""
    def layout_on(cr):
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription("Noto Color Emoji 109"))
        layout.set_text(text, -1)
        return layout

    ink, _logical = layout_on(cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))).get_pixel_extents()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, ink.width), max(1, ink.height))
    cr = cairo.Context(surface)
    cr.move_to(-ink.x, -ink.y)
    PangoCairo.show_layout(cr, layout_on(cr))
    res = surface.get_width() / width
    return Sprite(surface, width / 2, surface.get_height() / res / 2, res)


def chillies():
    chilli = _load("chilli.png")
    cw = chilli.get_width()
    cy = _column_centre(chilli, int(cw * CHILLI_PIERCE))
    return [Sprite(chilli, CHILLI_PIERCE * length, cy * length / cw, cw / length)
            for length in CHILLI_LENGTHS]


# --- drawn in code ----------------------------------------------------------------------------

def drawn(w, h, ax, ay, draw):
    """Render `draw(cr)` (model units, origin at the anchor) into a sprite w x h units big."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w * DRAW_RES), int(h * DRAW_RES))
    cr = cairo.Context(surface)
    cr.scale(DRAW_RES, DRAW_RES)
    cr.translate(ax, ay)
    draw(cr)
    return Sprite(surface, ax, ay, DRAW_RES)


WOOD_LIGHT, WOOD, WOOD_DARK = (0.74, 0.55, 0.35), (0.58, 0.40, 0.23), (0.36, 0.23, 0.12)


def _grain(cr, rng, x0, x1, y0, y1, count, vertical=False):
    """Fine wavy wood grain lines inside the current clip."""
    for _ in range(count):
        c = rng.uniform(y0, y1) if not vertical else rng.uniform(x0, x1)
        amp, freq, phase = rng.uniform(0.1, 0.5), rng.uniform(0.15, 0.5), rng.uniform(0, 6)
        steps = 40
        for i in range(steps + 1):
            t = (x0 + (x1 - x0) * i / steps) if not vertical else (y0 + (y1 - y0) * i / steps)
            off = c + amp * math.sin(t * freq + phase)
            px, py = (t, off) if not vertical else (off, t)
            cr.line_to(px, py) if i else cr.move_to(px, py)
        cr.set_source_rgba(0.22, 0.12, 0.05, rng.uniform(0.06, 0.2))
        cr.set_line_width(rng.uniform(0.1, 0.3))
        cr.stroke()


def wood_disc(rx, thick, seed):
    """A wooden disc seen from slightly below: the rim band and the curve of its underside."""
    ry = rx * 0.18

    def shape(cr):
        cr.new_path()
        cr.save()
        cr.translate(0, -thick / 2)
        cr.scale(rx, ry)
        cr.arc(0, 0, 1, math.pi, 2 * math.pi)
        cr.restore()
        cr.save()
        cr.translate(0, thick / 2)
        cr.scale(rx, ry)
        cr.arc(0, 0, 1, 0, math.pi)
        cr.restore()
        cr.close_path()

    def draw(cr):
        rng = random.Random(seed)
        cr.save()
        shape(cr)
        cr.clip()
        grad = cairo.LinearGradient(-rx, 0, rx, 0)  # round rim: lit from the left
        grad.add_color_stop_rgb(0, *WOOD_DARK)
        grad.add_color_stop_rgb(0.25, *WOOD_LIGHT)
        grad.add_color_stop_rgb(0.6, *WOOD)
        grad.add_color_stop_rgb(1, *WOOD_DARK)
        cr.set_source(grad)
        cr.paint()
        _grain(cr, rng, -rx, rx, -thick / 2 - ry, thick / 2 + ry, int(thick * 4))
        under = cairo.LinearGradient(0, thick / 2 - ry, 0, thick / 2 + ry)
        under.add_color_stop_rgba(0, 0, 0, 0, 0)
        under.add_color_stop_rgba(1, 0, 0, 0, 0.35)
        cr.set_source(under)
        cr.paint()
        cr.restore()
        shape(cr)
        cr.set_source_rgba(0.18, 0.1, 0.04, 0.6)
        cr.set_line_width(0.2)
        cr.stroke()

    return drawn(2 * rx + 2, thick + 2 * ry + 2, rx + 1, thick / 2 + ry + 1, draw)


def metal_tube(length, r, seed):
    """An aluminium chime tube, anchored at the middle of its top end."""
    ry = r * 0.32

    def draw(cr):
        rng = random.Random(seed)
        cr.new_path()
        cr.move_to(-r, 0)
        cr.line_to(-r, length)
        cr.save()
        cr.translate(0, length)
        cr.scale(r, ry)
        cr.arc_negative(0, 0, 1, math.pi, 0)
        cr.restore()
        cr.line_to(r, 0)
        cr.save()
        cr.scale(r, ry)
        cr.arc_negative(0, 0, 1, 0, -math.pi)
        cr.restore()
        cr.close_path()
        cr.save()
        cr.clip_preserve()
        # environment reflection across the round tube: dark edges, bright streaks
        grad = cairo.LinearGradient(-r, 0, r, 0)
        for stop, v in ((0, 0.28), (0.08, 0.5), (0.2, 0.93), (0.3, 0.78), (0.48, 0.52),
                        (0.66, 0.6), (0.8, 0.86), (0.9, 0.97), (1, 0.32)):
            grad.add_color_stop_rgb(stop, v * 0.97, v * 0.98, v * 1.03)
        cr.set_source(grad)
        cr.fill()
        for _ in range(int(r * 18)):  # brushed finish
            x = rng.uniform(-r, r)
            cr.move_to(x, 0)
            cr.line_to(x, length)
            cr.set_source_rgba(1, 1, 1, rng.uniform(0.0, 0.06)) if rng.random() < 0.5 else \
                cr.set_source_rgba(0, 0, 0, rng.uniform(0.0, 0.06))
            cr.set_line_width(rng.uniform(0.03, 0.1))
            cr.stroke()
        cr.restore()
        # the open bottom end
        cr.save()
        cr.translate(0, length)
        cr.scale(r, ry)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgb(0.42, 0.43, 0.45)
        cr.fill()
        cr.save()
        cr.translate(0, length)
        cr.scale(r * 0.72, ry * 0.72)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgb(0.08, 0.08, 0.09)
        cr.fill()
        # hanging hole near the top
        cr.arc(0, 2.2, 0.45, 0, 2 * math.pi)
        cr.set_source_rgba(0.05, 0.05, 0.05, 0.8)
        cr.fill()

    return drawn(2 * r + 2, length + 2 * ry + 2, r + 1, ry + 1, draw)


def wood_sail(w, h, seed):
    """The flat wooden leaf that catches the wind, anchored at its centre."""
    def shape(cr):
        cr.new_path()
        cr.move_to(0, -h / 2)
        cr.curve_to(w * 0.46, -h * 0.34, w * 0.5, h * 0.18, 0, h / 2)
        cr.curve_to(-w * 0.5, h * 0.18, -w * 0.46, -h * 0.34, 0, -h / 2)
        cr.close_path()

    def draw(cr):
        rng = random.Random(seed)
        cr.save()
        shape(cr)
        cr.clip()
        grad = cairo.RadialGradient(-w * 0.15, -h * 0.15, 1, 0, 0, h * 0.6)
        grad.add_color_stop_rgb(0, *WOOD_LIGHT)
        grad.add_color_stop_rgb(0.7, *WOOD)
        grad.add_color_stop_rgb(1, *WOOD_DARK)
        cr.set_source(grad)
        cr.paint()
        _grain(cr, rng, -w / 2, w / 2, -h / 2, h / 2, int(w * 1.5), vertical=True)
        cr.restore()
        shape(cr)
        cr.set_source_rgba(0.2, 0.11, 0.04, 0.7)
        cr.set_line_width(0.35)
        cr.stroke()
        cr.arc(0, -h / 2 + 2.6, 0.8, 0, 2 * math.pi)
        cr.set_source_rgb(0.12, 0.07, 0.03)
        cr.fill()

    return drawn(w + 2, h + 2, w / 2 + 1, h / 2 + 1, draw)


# --- 3D glass nazar: drawn as layers that the app stacks in depth -------------------------------

COBALT = (0.05, 0.17, 0.70)
COBALT_DEEP = (0.01, 0.05, 0.36)
NAZAR_EYE_Y = 0.08  # eye centre below the disc centre, as a fraction of the radius


def _disc_path(cr, r):
    cr.new_path()
    cr.arc(0, 0, r, 0, 2 * math.pi)


def nazar_face(r, hole_y, seed, back=False):
    """One flat face of the glass disc: cobalt glass with bubbles, swirls and the hanging hole."""
    def draw(cr):
        rng = random.Random(seed)
        _disc_path(cr, r)
        grad = cairo.RadialGradient(-r * 0.25, -r * 0.3, r * 0.05, 0, 0, r)
        grad.add_color_stop_rgb(0, *(c * (0.8 if back else 1.15) for c in COBALT))
        grad.add_color_stop_rgb(0.75, *(c * (0.75 if back else 1.0) for c in COBALT))
        grad.add_color_stop_rgb(1, *COBALT_DEEP)
        cr.set_source(grad)
        cr.fill()
        cr.save()
        _disc_path(cr, r)
        cr.clip()
        # light passing through the glass pools on the far side
        caustic = cairo.RadialGradient(r * 0.35, r * 0.45, 0, r * 0.35, r * 0.45, r * 0.75)
        caustic.add_color_stop_rgba(0, 0.45, 0.70, 1.0, 0.35)
        caustic.add_color_stop_rgba(1, 0.45, 0.70, 1.0, 0)
        cr.set_source(caustic)
        cr.paint()
        for _ in range(7):  # faint swirls from the molten glass
            a0 = rng.uniform(0, 2 * math.pi)
            cr.arc(rng.uniform(-r * 0.3, r * 0.3), rng.uniform(-r * 0.3, r * 0.3), rng.uniform(r * 0.3, r * 0.9),
                   a0, a0 + rng.uniform(0.6, 1.8))
            cr.set_source_rgba(0.6, 0.8, 1.0, rng.uniform(0.04, 0.1))
            cr.set_line_width(rng.uniform(0.2, 0.6))
            cr.stroke()
        for _ in range(45):  # trapped air bubbles
            bx, by = rng.uniform(-r, r), rng.uniform(-r, r)
            if bx * bx + by * by > (r * 0.92) ** 2:
                continue
            br = rng.uniform(0.12, 0.55)
            cr.arc(bx, by, br, 0, 2 * math.pi)
            cr.set_source_rgba(0.75, 0.88, 1.0, 0.28)
            cr.set_line_width(0.1)
            cr.stroke()
            cr.arc(bx - br * 0.3, by - br * 0.3, br * 0.3, 0, 2 * math.pi)
            cr.set_source_rgba(1, 1, 1, 0.35)
            cr.fill()
        # glass gets darker towards the rim (seen through more of it)
        rim = cairo.RadialGradient(0, 0, r * 0.7, 0, 0, r)
        rim.add_color_stop_rgba(0, 0, 0, 0.1, 0)
        rim.add_color_stop_rgba(1, 0, 0, 0.1, 0.45)
        cr.set_source(rim)
        cr.paint()
        cr.restore()
        # the hanging hole, punched right through
        hr = r * 0.075
        cr.arc(0, hole_y, hr, 0, 2 * math.pi)
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.fill()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.arc(0, hole_y, hr, 0, 2 * math.pi)
        cr.set_source_rgba(0.55, 0.75, 1.0, 0.8)
        cr.set_line_width(0.5)
        cr.stroke()

    return drawn(2 * r + 2, 2 * r + 2, r + 1, r + 1, draw)


def nazar_rim_slice(r, width):
    """A thin ring of the disc's edge; stacked at different depths they make its thickness."""
    def draw(cr):
        cr.new_path()
        cr.arc(0, 0, r, 0, 2 * math.pi)
        cr.arc_negative(0, 0, r - width, 2 * math.pi, 0)
        grad = cairo.LinearGradient(-r, -r, r, r)  # lit from the top left
        grad.add_color_stop_rgb(0, 0.20, 0.40, 0.92)
        grad.add_color_stop_rgb(0.45, 0.05, 0.18, 0.70)
        grad.add_color_stop_rgb(1, 0.01, 0.04, 0.28)
        cr.set_source(grad)
        cr.fill()

    return drawn(2 * r + 2, 2 * r + 2, r + 1, r + 1, draw)


def nazar_eye_layer(r, colour, rim_colour, seed, wobble=0.0, dome=0.25):
    """One raised glass layer of the eye, domed with a soft highlight."""
    def draw(cr):
        rng = random.Random(seed)
        cr.new_path()
        steps = 48
        for i in range(steps + 1):  # a slightly hand-made, uneven outline
            a = 2 * math.pi * i / steps
            k = 1 + wobble * math.sin(3 * a + seed) + wobble * 0.5 * math.sin(5 * a + 1.7 * seed)
            x, y = r * k * math.cos(a), r * k * 1.04 * math.sin(a)
            cr.line_to(x, y) if i else cr.move_to(x, y)
        cr.close_path()
        grad = cairo.RadialGradient(-r * 0.35, -r * 0.4, r * 0.05, 0, 0, r * 1.05)
        grad.add_color_stop_rgb(0, *(min(1.0, c + dome) for c in colour))
        grad.add_color_stop_rgb(0.7, *colour)
        grad.add_color_stop_rgb(1, *rim_colour)
        cr.set_source(grad)
        cr.fill_preserve()
        cr.set_source_rgba(0, 0, 0.1, 0.25)
        cr.set_line_width(0.25)
        cr.stroke()
        for _ in range(int(r)):  # tiny bubbles in this layer too
            bx, by = rng.uniform(-r * 0.7, r * 0.7), rng.uniform(-r * 0.7, r * 0.7)
            cr.arc(bx, by, rng.uniform(0.08, 0.25), 0, 2 * math.pi)
            cr.set_source_rgba(1, 1, 1, 0.25)
            cr.fill()

    return drawn(2.4 * r + 2, 2.4 * r + 2, 1.2 * r + 1, 1.2 * r + 1, draw)


def nazar_highlight(r):
    """The window-like reflection on the glass; the app slides it across as the disc turns."""
    def draw(cr):
        soft = cairo.RadialGradient(0, 0, 0, 0, 0, r)
        soft.add_color_stop_rgba(0, 1, 1, 1, 0.55)
        soft.add_color_stop_rgba(1, 1, 1, 1, 0)
        cr.save()
        cr.scale(1, 0.55)
        cr.arc(0, 0, r, 0, 2 * math.pi)
        cr.restore()
        cr.set_source(soft)
        cr.fill()
        cr.save()
        cr.translate(-r * 0.2, -r * 0.08)
        cr.rotate(-0.4)
        cr.scale(r * 0.32, r * 0.1)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.fill()

    return drawn(2 * r + 2, 2 * r + 2, r + 1, r + 1, draw)


class Eyelids:
    """Cobalt glass eyelids over the nazar's eye; amount 0 = open, 1 = shut."""
    LOWER = 0.38  # the lower lid does this share of the closing

    def __init__(self, rx, ry, amount):
        self.rx, self.ry, self.amount = rx, ry, amount

    def _lid(self, cr, edge, upper):
        rx, ry = self.rx * 1.3, self.ry * 1.3
        far = -ry if upper else ry
        sag = self.ry * 0.28 * (1 if upper else -1)  # lids curve with the eyeball
        cr.new_path()
        cr.move_to(-rx, far)
        cr.line_to(rx, far)
        cr.line_to(rx, edge - sag)
        cr.curve_to(rx * 0.45, edge + sag * 0.6, -rx * 0.45, edge + sag * 0.6, -rx, edge - sag)
        cr.close_path()
        grad = cairo.LinearGradient(0, far, 0, edge)
        grad.add_color_stop_rgb(0, *(c * (1.25 if upper else 0.8) for c in COBALT))
        grad.add_color_stop_rgb(1, *COBALT)
        cr.set_source(grad)
        cr.fill()
        # the lid's rim and a few lashes on the upper one
        cr.move_to(-rx, edge - sag)
        cr.curve_to(rx * -0.45, edge + sag * 0.6, rx * 0.45, edge + sag * 0.6, rx, edge - sag)
        cr.set_source_rgb(0.02, 0.04, 0.2)
        cr.set_line_width(0.7)
        cr.stroke()
        if upper and self.amount > 0.25:
            for i in range(-3, 4):
                x = i * self.rx * 0.22
                y = edge + sag * 0.6 * (1 - (x / rx) ** 2)
                cr.move_to(x, y)
                cr.line_to(x * 1.12, y + self.ry * 0.16 * self.amount)
            cr.set_line_width(0.45)
            cr.stroke()

    def paint(self, cr, flip=1, alpha=1.0):
        if self.amount <= 0.01:
            return
        cr.save()
        cr.scale(flip, 1)
        cr.push_group()
        cr.save()
        cr.scale(self.rx, self.ry)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.clip()
        span = 2 * self.ry * self.amount
        self._lid(cr, -self.ry + span * (1 - self.LOWER), upper=True)
        self._lid(cr, self.ry - span * self.LOWER, upper=False)
        cr.pop_group_to_source()
        cr.paint_with_alpha(alpha)
        cr.restore()

    def paint_shadow(self, *_args, **_kw):
        pass


def flat_disc(r, colour=(0, 0, 0)):
    """A plain filled disc, used to darken the face as it turns away from the light."""
    def draw(cr):
        cr.arc(0, 0, r, 0, 2 * math.pi)
        cr.set_source_rgb(*colour)
        cr.fill()

    return drawn(2 * r + 2, 2 * r + 2, r + 1, r + 1, draw)


def glass_bead(r):
    """A glossy blue glass bead."""
    def draw(cr):
        grad = cairo.RadialGradient(-r * 0.35, -r * 0.35, r * 0.05, 0, 0, r)
        grad.add_color_stop_rgb(0, 0.62, 0.78, 1.0)
        grad.add_color_stop_rgb(0.3, 0.16, 0.32, 0.92)
        grad.add_color_stop_rgb(0.85, 0.04, 0.10, 0.52)
        grad.add_color_stop_rgb(1, 0.02, 0.05, 0.30)
        cr.arc(0, 0, r, 0, 2 * math.pi)
        cr.set_source(grad)
        cr.fill()
        cr.save()
        cr.translate(-r * 0.32, -r * 0.38)
        cr.scale(r * 0.22, r * 0.15)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgba(1, 1, 1, 0.85)
        cr.fill()
        cr.arc(0, 0, r * 0.92, 0.2, 1.6)
        cr.set_source_rgba(0.6, 0.8, 1.0, 0.35)
        cr.set_line_width(r * 0.12)
        cr.stroke()

    return drawn(2 * r + 2, 2 * r + 2, r + 1, r + 1, draw)
