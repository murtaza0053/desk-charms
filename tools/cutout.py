#!/usr/bin/env python3
"""Cut a charm out of a photo with a plain background, for use as a Desk Charms asset.

    python3 tools/cutout.py photo.jpg assets/mycharm.png --mode light
    python3 tools/cutout.py photo.jpg out.png --mode dark --crop 100,0,900,1000

Modes (what counts as part of the object; everything else that touches the photo's border is
background):
  light  plain white/grey backdrop: pixels more colourful than --sat, darker than --dark, or
         brighter than --bright (to keep white parts on a grey backdrop)
  dark   dark backdrop: pixels brighter than --bright
  red    red cloth backdrop: anything that is not strongly red

Holes inside the object (highlights, white eyes) are kept, only the largest piece is kept, and
the edge is softened. Look at the result on a grey background before adding it to the app.
Needs Pillow (sudo apt install python3-pil).
"""
import argparse
from collections import deque

from PIL import Image, ImageFilter


def is_object(rgb, args):
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    sat, val = ((mx - mn) / mx if mx else 0), mx / 255
    if args.mode == "light":
        return sat > args.sat or val < args.dark or val > args.bright
    if args.mode == "dark":
        return val > args.bright
    return not (r > 90 and r - max(g, b) > args.red * 255)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photo")
    parser.add_argument("output")
    parser.add_argument("--mode", choices=("light", "dark", "red"), default="light")
    parser.add_argument("--sat", type=float, default=0.25, help="light: colourfulness that counts as object")
    parser.add_argument("--dark", type=float, default=0.3, help="light: darkness that counts as object")
    parser.add_argument("--bright", type=float, default=2.0,
                        help="light: brightness that counts as object (default off); dark: required brightness")
    parser.add_argument("--red", type=float, default=0.18, help="red: how red the backdrop is")
    parser.add_argument("--crop", help="x0,y0,x1,y1 in photo pixels")
    parser.add_argument("--max-size", type=int, default=900, help="work at most this many pixels across")
    args = parser.parse_args()
    if args.mode == "dark" and args.bright > 1:
        args.bright = 0.42

    img = Image.open(args.photo).convert("RGB")
    if args.crop:
        img = img.crop(tuple(int(v) for v in args.crop.split(",")))
    img.thumbnail((args.max_size, args.max_size), Image.LANCZOS)
    w, h = img.size
    px = img.load()
    obj = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            obj[y * w + x] = is_object(px[x, y], args)

    # background: everything not-object that is connected to the border
    bg = bytearray(w * h)
    queue = deque()
    for x in range(w):
        queue.extend(((x, 0), (x, h - 1)))
    for y in range(h):
        queue.extend(((0, y), (w - 1, y)))
    queue = deque(p for p in queue if not obj[p[1] * w + p[0]])
    for x, y in queue:
        bg[y * w + x] = 1
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny * w + nx] and not obj[ny * w + nx]:
                bg[ny * w + nx] = 1
                queue.append((nx, ny))

    # keep the largest remaining piece (drops specks, rulers, watermarks)
    seen = bytearray(w * h)
    best = []
    for sy in range(h):
        for sx in range(w):
            if bg[sy * w + sx] or seen[sy * w + sx]:
                continue
            piece, queue = [], deque([(sx, sy)])
            seen[sy * w + sx] = 1
            while queue:
                x, y = queue.popleft()
                piece.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    j = ny * w + nx
                    if 0 <= nx < w and 0 <= ny < h and not bg[j] and not seen[j]:
                        seen[j] = 1
                        queue.append((nx, ny))
            if len(piece) > len(best):
                best = piece

    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for x, y in best:
        mp[x, y] = 255
    # pull the edge in a touch to drop the backdrop's fringe, then soften it
    mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    out = img.convert("RGBA")
    out.putalpha(mask)
    out = out.crop(mask.getbbox())
    out.thumbnail((480, 480), Image.LANCZOS)
    out.save(args.output)
    print(f"saved {args.output} {out.size[0]}x{out.size[1]}")


if __name__ == "__main__":
    main()
