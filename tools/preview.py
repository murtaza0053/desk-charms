#!/usr/bin/env python3
"""Render charms to a PNG without starting the app, to check how they look.

    python3 tools/preview.py                   every charm -> docs/charms.png (the README picture)
    python3 tools/preview.py nazar -o out.png  one charm, turning through several angles
"""
import argparse
import os
import sys

import cairo

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import desk_charms as app  # noqa: E402
import objects  # noqa: E402


def render(cr, kind, angle, state=None):
    """Draw one charm hanging still, the same way the app's on_draw does."""
    pieces, lines = kind.layout(angle - 0.3, state or {})
    for line in lines:
        app.draw_line(cr, line, 0, shadow=True)
    for p in pieces:
        if p.shadow:
            cr.save()
            cr.translate(app.SHADOW[0] + p.x, app.SHADOW[1] + p.y)
            cr.rotate(p.tilt)
            p.sprite.paint_shadow(cr, p.x_scale)
            cr.restore()
    items = sorted([(p.depth, 1, p) for p in pieces] + [(l.depth, 0, l) for l in lines],
                   key=lambda item: (item[0], item[1]))
    thread_drawn = False
    for depth, _order, item in items:
        if depth >= 0 and not thread_drawn:
            app.draw_thread(cr, 0, 0, 0, kind.thread_end, 1.3)
            thread_drawn = True
        if isinstance(item, objects.Line):
            app.draw_line(cr, item, 0)
            continue
        cr.save()
        cr.translate(item.x, item.y)
        cr.rotate(item.tilt)
        item.sprite.paint(cr, item.x_scale, item.alpha)
        cr.restore()
    if not thread_drawn:
        app.draw_thread(cr, 0, 0, 0, kind.thread_end, 1.3)


def sheet(cells, cols, cw, ch, scale, path):
    """cells: list of (kind, angle, label)."""
    rows = (len(cells) + cols - 1) // cols
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, cols * cw, rows * ch)
    cr = cairo.Context(surface)
    bg = cairo.LinearGradient(0, 0, 0, rows * ch)
    bg.add_color_stop_rgb(0, 0.93, 0.91, 0.87)
    bg.add_color_stop_rgb(1, 0.82, 0.80, 0.76)
    cr.set_source(bg)
    cr.paint()
    for i, (kind, angle, label) in enumerate(cells):
        kind.ready(scale)
        x0, y0 = (i % cols) * cw, (i // cols) * ch
        cr.save()
        cr.rectangle(x0, y0, cw, ch - 26)
        cr.clip()
        cr.translate(x0 + cw / 2, y0 - 62)
        cr.scale(scale, scale)
        render(cr, kind, angle)
        cr.restore()
        cr.set_source_rgb(0.2, 0.2, 0.2)
        cr.select_font_face("Sans")
        cr.set_font_size(13)
        ext = cr.text_extents(label)
        cr.move_to(x0 + (cw - ext.width) / 2, y0 + ch - 9)
        cr.show_text(label)
    surface.write_to_png(path)
    print("saved", path)


def main():
    keys = [kind.key for kind in objects.KINDS]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("charm", nargs="?", choices=keys, help="show one charm turning")
    parser.add_argument("-o", "--output", help="PNG to write")
    args = parser.parse_args()
    if args.charm:
        kind = objects.BY_KEY[args.charm]
        cells = [(kind, a, f"{a:.1f} rad") for a in (0.0, 0.6, 1.2, 1.6, 2.2, 3.0)]
        sheet(cells, 6, 150, 280, 1.6, args.output or f"{args.charm}-preview.png")
    else:
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        cells = [(kind, 0.35, kind.label) for kind in objects.KINDS]
        sheet(cells, 7, 140, 250, 1.25, args.output or os.path.join(root, "docs", "charms.png"))


if __name__ == "__main__":
    main()
