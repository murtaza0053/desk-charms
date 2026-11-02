"""The charms that can hang from the thread (KINDS at the bottom lists them all).

Every y below is the distance along the thread from the pivot when it hangs still. The
"handle" is the point the physics moves and the mouse grabs; the rest is drawn relative to it.
"""
import math
import random
from collections import namedtuple

from gi.repository import GLib

import sprites

Piece = namedtuple("Piece", "sprite x y x_scale tilt depth alpha shadow", defaults=(1.0, True))
Line = namedtuple("Line", "x0 y0 x1 y1 depth")  # thin fishing line between parts


def turned(heading, twist, minimum=0.1):
    """Horizontal scale of a flat thing facing `heading` once the thread has turned by `twist`."""
    across = math.cos(heading + twist)
    return math.copysign(max(abs(across), minimum), across)


class Kind:
    key = label = ""
    thread_end = handle_y = 0.0
    top = 0.0         # highest point of the object
    bottom = 0.0      # how far the object reaches below the handle
    hit = (30, 30)    # clickable half-width and half-height around the handle
    reach = 100       # furthest any part gets from the handle (for repainting)

    def __init__(self):
        self.sprites = None
        self.scale = None

    def ready(self, scale):
        if self.sprites is None:
            self.sprites = self.load()
        if self.scale != scale:
            for sprite in self.sprites:
                sprite.prepare(scale)
            self.scale = scale

    def load(self):
        raise NotImplementedError

    def layout(self, twist, state):
        """(pieces, lines) for the current twist of the thread. `state` is this dangle's own
        dict, for kinds that animate (see tick)."""
        raise NotImplementedError

    def tick(self, state, dt, dragging):
        """Advance any animation of the object itself (the nazar's blinking)."""

    def release(self, play, strength):
        """Let go after a pull; strength 0..1."""
        play("twang", 0.25 + 0.75 * strength)

    def knock(self, play, strength):
        """The swing reached an end while moving hard; strength > 1 is above the normal swing."""

    def ambient(self, play):
        """The normal swing reached an end (only when gentle sounds are on)."""


class NimbuMirchi(Kind):
    key, label = "nimbu", "Nimbu-mirchi"
    STRING_TOP = 62
    CHILLI_GAP = 9
    # which way each chilli points around the string, seen from above (golden-angle spread, nudged)
    HEADINGS = [i * 2.4 + d for i, d in enumerate((0.2, -0.3, 0.1, 0.35, -0.15, 0.25, -0.2))]
    LEMON_Y = STRING_TOP + (len(HEADINGS) - 1) * CHILLI_GAP + 30
    COAL_Y = LEMON_Y + sprites.LEMON_RY + 9
    thread_end = COAL_Y
    handle_y = LEMON_Y
    top = STRING_TOP - 6
    bottom = COAL_Y - LEMON_Y + 12
    hit = (sprites.LEMON_RX + 4, sprites.LEMON_RY + 4)
    reach = 115

    def load(self):
        self.chillies = sprites.chillies()
        self.lemon = sprites.photo("lemon.png", sprites.LEMON_WIDTH)
        self.coal = sprites.photo("coal.png", sprites.COAL_WIDTH)
        return [*self.chillies, self.lemon, self.coal]

    def layout(self, twist, state):
        pieces = []
        for i, heading in enumerate(self.HEADINGS):
            across = math.cos(heading + twist)
            pieces.append(Piece(self.chillies[i % len(self.chillies)], 0, self.STRING_TOP + i * self.CHILLI_GAP,
                                turned(heading, twist, 0.12), 0.14 * across,  # tips droop the way they point
                                math.sin(heading + twist)))
        pieces.append(Piece(self.lemon, 0, self.LEMON_Y, 0.8 + 0.2 * abs(math.cos(twist + 0.6)), 0, 0.5))
        pieces.append(Piece(self.coal, 0, self.COAL_Y, 0.85 + 0.15 * abs(math.cos(1.3 * twist)), 0, 0.5))
        return pieces, []

    def release(self, play, strength):
        play("release", 0.25 + 0.75 * strength)


class WindChime(Kind):
    key, label = "chime", "Wind chime"
    DISC_Y = 66
    TUBE_TOP = 80
    TUBES = (64, 57, 50, 44, 38)
    RING = 15          # radius of the circle the tubes hang on
    STRIKER_Y = 108
    SAIL_Y = 150
    thread_end = 62
    handle_y = 112
    top = 56
    bottom = 58
    hit = (26, 50)
    reach = 100

    def load(self):
        self.disc = sprites.wood_disc(22, 5, seed=1)
        self.tubes = [sprites.metal_tube(length, 2.3, seed=i) for i, length in enumerate(self.TUBES)]
        self.striker = sprites.wood_disc(8, 3, seed=2)
        self.sail = sprites.wood_sail(22, 34, seed=3)
        return [self.disc, *self.tubes, self.striker, self.sail]

    def layout(self, twist, state):
        pieces = [Piece(self.disc, 0, self.DISC_Y, 1, 0, 0),
                  Piece(self.striker, 0, self.STRIKER_Y, 1, 0, 0),
                  Piece(self.sail, 0, self.SAIL_Y, turned(0.4, twist), 0, 0)]
        lines = [Line(0, self.DISC_Y + 3, 0, self.SAIL_Y - 15, 0)]
        for i, tube in enumerate(self.tubes):
            angle = i * 2 * math.pi / len(self.tubes) + twist
            x, depth = self.RING * math.sin(angle), math.cos(angle)
            pieces.append(Piece(tube, x, self.TUBE_TOP, 1, 0, depth))
            lines.append(Line(x, self.DISC_Y + 3, x, self.TUBE_TOP + 2.2, depth))
        return pieces, lines

    def _notes(self, play, count, volume):
        for k in range(count):
            note = f"chime{random.randrange(5)}"
            vol = volume * random.uniform(0.6, 1.0)
            if k == 0:
                play(note, vol)
            else:
                GLib.timeout_add(int(k * random.uniform(90, 160)), lambda n=note, v=vol: play(n, v) and False)

    def release(self, play, strength):
        super().release(play, strength * 0.6)
        self._notes(play, 2 + int(strength * 3), 0.3 + 0.6 * strength)

    def knock(self, play, strength):
        self._notes(play, 1 + int(min(strength, 6) / 3), min(1.0, 0.15 + 0.1 * strength))

    def ambient(self, play):
        if random.random() < 0.4:
            self._notes(play, 1, 0.12)


class Bell(Kind):
    key, label = "bell", "Bell"
    WIDTH = 64
    thread_end = 63
    handle_y = 97      # thread_end + half the photo's height at this width
    top = 60
    bottom = 37
    hit = (34, 36)
    reach = 70

    def load(self):
        self.bell = sprites.photo("bell.png", self.WIDTH)
        return [self.bell]

    def layout(self, twist, state):
        return [Piece(self.bell, 0, self.handle_y, 0.97 + 0.03 * math.cos(twist * 3), 0, 0.5)], []

    def release(self, play, strength):
        super().release(play, strength * 0.5)
        play("bell", 0.3 + 0.7 * strength)

    def knock(self, play, strength):
        play("bell", min(1.0, 0.15 + 0.12 * strength))

    def ambient(self, play):
        if random.random() < 0.25:
            play("bell", 0.08)


class EvilEye(Kind):
    """A 3D glass nazar: a thick cobalt disc with a raised eye, turning on the thread.

    The disc is built from layers placed in depth: back face, a stack of thin rim slices that
    give it a rounded edge, the front face, the raised eye layers and the reflection. Turning by
    angle a, a layer at depth z moves sideways by z*sin(a) and squashes by cos(a), so the eye
    layers shift against the glass (parallax) and the edge shows as the disc turns side-on.
    """
    key, label = "nazar", "Evil eye (nazar)"
    R = 33.0              # outer radius of the disc
    FACE = 0.93           # the flat faces are a little smaller than the rounded rim
    THICK = 0.17 * R
    SLICES = 11
    TOP_EDGE = 72
    HOLE = -0.72 * R      # hanging hole, above the centre
    BEADS = (54, 60.5, 67)
    twist_amplitude = 1.6  # turns far enough to show the edge and some of the back
    follows_pointer = True  # the app passes the mouse direction in state["look_target"]
    handle_y = TOP_EDGE + R
    thread_end = handle_y + HOLE
    top = 50
    bottom = R + 6
    hit = (R + 2, R + 2)
    reach = 80

    def load(self):
        R, face_r = self.R, self.R * self.FACE
        self.front = sprites.nazar_face(face_r, self.HOLE, seed=11)
        self.back = sprites.nazar_face(face_r, self.HOLE, seed=12, back=True)
        self.shade = sprites.flat_disc(face_r)
        self.slices = []
        for i in range(self.SLICES):
            z = -self.THICK / 2 + self.THICK * i / (self.SLICES - 1)
            r = R * math.sqrt(1 - (1 - self.FACE ** 2) * (2 * z / self.THICK) ** 2)
            self.slices.append((z, sprites.nazar_rim_slice(r, R * 0.12)))
        e = sprites.NAZAR_EYE_Y * R
        top = self.THICK / 2
        self.eye = [  # (sprite, height above the glass)
            (sprites.nazar_eye_layer(0.40 * R, (0.96, 0.95, 0.90), (0.76, 0.79, 0.86), seed=1, wobble=0.035), top + 0.012 * R, e),
            (sprites.nazar_eye_layer(0.27 * R, (0.42, 0.74, 0.96), (0.18, 0.48, 0.84), seed=2, wobble=0.02), top + 0.024 * R, e),
            (sprites.nazar_eye_layer(0.13 * R, (0.05, 0.06, 0.16), (0.0, 0.0, 0.05), seed=3, dome=0.18), top + 0.034 * R, e),
        ]
        self.highlight = sprites.nazar_highlight(0.34 * R)
        self.bead = sprites.glass_bead(2.8)
        return [self.front, self.back, self.shade, self.highlight, self.bead,
                *(s for _z, s in self.slices), *(s for s, _h, _y in self.eye)]

    BLINK_CLOSE, BLINK_HOLD, BLINK_OPEN = 0.07, 0.05, 0.11

    def tick(self, state, dt, dragging):
        """Blink every few seconds (sometimes twice), squint while held, blink after letting go."""
        now = state.get("time", 0.0) + dt
        state["time"] = now
        # the eye eases towards the mouse rather than jumping
        tx, ty = state.get("look_target", (0.0, 0.0))
        lx, ly = state.get("look", (0.0, 0.0))
        k = min(1.0, dt * 8)
        state["look"] = (lx + (tx - lx) * k, ly + (ty - ly) * k)
        if dragging:
            state["lids"] = min(0.8, state.get("lids", 0.0) + dt * 6)  # screw the eye up
            state["held"] = True
            return
        if state.pop("held", False):
            state["blinks"] = [now + 0.15, now + 0.45]  # surprised double blink on release
        blinks = state.setdefault("blinks", [now + random.uniform(1.5, 4)])
        if not blinks:
            nxt = now + random.uniform(2.5, 6.5)
            blinks.append(nxt)
            if random.random() < 0.25:
                blinks.append(nxt + 0.32)
        amount = 0.0
        start = blinks[0]
        t = now - start
        total = self.BLINK_CLOSE + self.BLINK_HOLD + self.BLINK_OPEN
        if t >= total:
            blinks.pop(0)
        elif t >= 0:
            if t < self.BLINK_CLOSE:
                amount = t / self.BLINK_CLOSE
            elif t < self.BLINK_CLOSE + self.BLINK_HOLD:
                amount = 1.0
            else:
                amount = 1 - (t - self.BLINK_CLOSE - self.BLINK_HOLD) / self.BLINK_OPEN
        # ease out of a squint rather than snapping open
        state["lids"] = max(amount, state.get("lids", 0.0) - dt * 5)

    def layout(self, twist, state):
        a = twist + 0.3
        cos_a, sin_a = math.cos(a), math.sin(a)
        squash = math.copysign(max(abs(cos_a), 0.02), cos_a)
        cy = self.handle_y

        def at(x0, y, z, sprite, **kw):
            return Piece(sprite, x0 * cos_a + z * sin_a, y, squash, 0, -x0 * sin_a + z * cos_a, **kw)

        half = self.THICK / 2
        pieces = [Piece(self.bead, 0, y, 1, 0, 50, shadow=True) for y in self.BEADS]
        pieces.append(at(0, cy, -half, self.back, alpha=0.82, shadow=False))  # see-through glass
        pieces += [at(0, cy, z, s, shadow=(i == self.SLICES // 2)) for i, (z, s) in enumerate(self.slices)]
        # seen from behind, the eye shows through the glass
        pieces.append(at(0, cy, half, self.front, alpha=1.0 if cos_a >= 0 else 0.5, shadow=False))
        # the iris and pupil turn towards the mouse; the pupil travels a little further
        lx, ly = (state or {}).get("look", (0.0, 0.0))
        for (s, h, dy), travel in zip(self.eye, (0.0, 0.11 * self.R, 0.15 * self.R)):
            pieces.append(at(lx * travel, cy + dy + ly * travel, h, s, shadow=False))
        lids = (state or {}).get("lids", 0.0)
        if lids > 0.01:
            e = sprites.NAZAR_EYE_Y * self.R
            pieces.append(at(0, cy + e, half + 0.038 * self.R,
                             sprites.Eyelids(0.42 * self.R, 0.45 * self.R, lids), shadow=False))
        # light from the front left: each face darkens as it turns away from it
        lx, lz = -0.5, 0.87
        front_lit = max(0.0, lx * sin_a + lz * cos_a)
        back_lit = max(0.0, -lx * sin_a - lz * cos_a)
        pieces.append(at(0, cy, half + 0.04 * self.R, self.shade, alpha=0.5 * (1 - front_lit), shadow=False))
        pieces.append(at(0, cy, -half - 0.001, self.shade, alpha=0.5 * (1 - back_lit), shadow=False))
        # the reflection slides across the glass as it turns
        glint = max(0.0, cos_a) ** 2
        if glint > 0.02:
            pieces.append(Piece(self.highlight, -0.3 * self.R * cos_a + 0.5 * self.R * sin_a, cy - 0.38 * self.R,
                                squash, 0, 100, alpha=0.9 * glint, shadow=False))
        pieces.sort(key=lambda p: p.depth)
        return pieces, []

    def release(self, play, strength):
        super().release(play, strength * 0.6)
        play("clink", 0.3 + 0.6 * strength)

    def knock(self, play, strength):
        play("clink", min(1.0, 0.12 + 0.1 * strength))

    def ambient(self, play):
        if random.random() < 0.15:
            play("clink", 0.08)


class PhotoCharm(Kind):
    """A photographed charm made into a 3D object.

    Flat charms get thickness from a stack of slices of their own outline in the edge
    `material`, a back face (the photo mirrored and tinted, as a real back looks), shading as
    each face turns from the light, and a sheen that slides across. Round figures (daruma,
    maneki-neko, cornicello) turn like solids: the front fades into a shaded back.
    """
    TOP = 62
    BEAD_GAP = 6.5
    LIGHT = (-0.5, 0.87)  # light from the front left (x, z)

    def __init__(self, key, label, file, width, attach=0.03, flat=True, beads=0, sound=None,
                 thick=3.0, material=(0.4, 0.4, 0.4), back_tint=0.45, gloss=0.35):
        super().__init__()
        self.key, self.label = key, label
        self.file, self.width, self.attach = file, width, attach
        self.flat, self.beads, self.sound = flat, beads, sound
        self.thick, self.material, self.back_tint, self.gloss = thick, material, back_tint, gloss
        self.twist_amplitude = 1.6 if flat else 1.9  # turn far enough to show the back now and then

    def photo(self):
        return sprites.photo(self.file, self.width)

    def load(self):
        self.charm = self.photo()
        if self.flat:
            self.edge = sprites.recoloured(self.charm, self.material, 0.85)
            self.back = sprites.recoloured(self.charm, self.material, self.back_tint, mirror=True)
        else:
            self.edge = None
            self.back = sprites.recoloured(self.charm, self.material, self.back_tint, mirror=True,
                                           lighting=0, sphere=True)
        self.shade = sprites.recoloured(self.charm, (0, 0, 0), 1.0, lighting=0)
        self.bead = sprites.glass_bead(2.6) if self.beads else None
        height = self.charm.original.get_height() / self.charm.original_res
        top_edge = self.TOP + self.BEAD_GAP * self.beads
        self.bead_ys = [top_edge - 4 - self.BEAD_GAP * i for i in range(self.beads)]
        self.thread_end = top_edge + self.attach * height
        self.handle_y = top_edge + height / 2
        self.top = min([top_edge, *self.bead_ys]) - 4
        self.bottom = height / 2 + 4
        self.hit = (self.width / 2 + 4, height / 2 + 4)
        self.reach = max(self.width, height) + 20
        return [s for s in (self.charm, self.edge, self.back, self.shade, self.bead) if s]

    def layout(self, twist, state):
        a = twist + 0.3
        cos_a, sin_a = math.cos(a), math.sin(a)
        cy = self.handle_y
        pieces = [Piece(self.bead, 0, y, 1, 0, 50) for y in self.bead_ys]
        lx, lz = self.LIGHT
        front_lit = max(0.0, lx * sin_a + lz * cos_a)
        back_lit = max(0.0, -lx * sin_a - lz * cos_a)
        if self.flat:
            squash = math.copysign(max(abs(cos_a), 0.02), cos_a)
            half = self.thick / 2

            def at(z, sprite, **kw):
                return Piece(sprite, z * sin_a, cy, squash, 0, z * cos_a, **kw)

            slices = max(4, int(self.thick * 1.6))
            for i in range(slices):
                z = -half + self.thick * i / (slices - 1)
                pieces.append(at(z, self.edge, shadow=(i == slices // 2)))
            pieces.append(at(-half - 0.01, self.back, shadow=False))
            pieces.append(at(-half - 0.02, self.shade, alpha=0.55 * (1 - back_lit), shadow=False))
            pieces.append(at(half + 0.01, self.charm, shadow=False))
            pieces.append(at(half + 0.02, self.shade, alpha=0.55 * (1 - front_lit), shadow=False))
            if cos_a > 0.05:
                sheen = sprites.Sheen(self.charm, 0.25 + 0.55 * (sin_a + 1) / 2, self.gloss)
                pieces.append(at(half + 0.03, sheen, alpha=cos_a, shadow=False))
        else:
            # a solid figure: squashes only a little, front and back cross-fade near side-on
            squash = 0.84 + 0.16 * abs(cos_a)
            front = max(0.0, min(1.0, 0.5 + cos_a * 2.5))
            # each side is fully solid until halfway through the turn, so neither looks see-through,
            # and the back stays hidden while the front faces us (it can peek out on curved shapes)
            if front < 1:
                pieces.append(Piece(self.back, 0, cy, squash, 0, 0.1, alpha=min(1.0, 2 * (1 - front)), shadow=True))
            if front > 0:
                pieces.append(Piece(self.charm, 0, cy, squash, 0, 0.2, alpha=min(1.0, 2 * front),
                                    shadow=front >= 1))
            lit = front * front_lit + (1 - front) * back_lit
            pieces.append(Piece(self.shade, 0, cy, squash, 0, 0.3, alpha=0.45 * (1 - lit), shadow=False))
            sheen = sprites.Sheen(self.charm, 0.3 + 0.4 * (sin_a + 1) / 2, self.gloss)
            pieces.append(Piece(sheen, 0, cy, squash, 0, 0.4, alpha=0.5, shadow=False))
        pieces.sort(key=lambda p: p.depth)
        return pieces, []

    def release(self, play, strength):
        super().release(play, strength * (0.6 if self.sound else 1.0))
        if self.sound:
            play(self.sound, 0.3 + 0.6 * strength)

    def knock(self, play, strength):
        if self.sound:
            play(self.sound, min(1.0, 0.12 + 0.1 * strength))

    def ambient(self, play):
        if self.sound and random.random() < 0.2:
            play(self.sound, 0.08)


class EmojiCharm(PhotoCharm):
    """Any emoji, hanging with a small copy of itself as a bead on the thread."""

    def __init__(self):
        super().__init__("emoji", "Any emoji", None, 60, attach=0.0, beads=1,
                         thick=3.0, material=(0.86, 0.9, 0.95), back_tint=0.15, gloss=0.5)
        self.text = "🍀"

    def set_text(self, text):
        text = text.strip() or "🍀"
        if text != self.text:
            self.text = text
            self.sprites, self.scale = None, None  # draw it again next time it is needed

    def photo(self):
        return sprites.emoji(self.text, self.width)

    def load(self):
        loaded = super().load()
        self.bead = sprites.emoji(self.text, 9)
        return [*loaded, self.bead]


KINDS = [
    NimbuMirchi(),
    PhotoCharm("drishti", "Drishti bommai", "drishti.png", 66, attach=0.08, sound="thud",
               thick=6, material=(0.45, 0.10, 0.06), back_tint=0.75, gloss=0.25),
    EvilEye(),
    PhotoCharm("hamsa", "Hamsa", "hamsa.png", 42, beads=3, sound="clank",
               thick=2.5, material=(0.62, 0.46, 0.16), back_tint=0.5, gloss=0.6),
    PhotoCharm("daruma", "Daruma", "daruma.png", 58, flat=False, sound="thud",
               material=(0.80, 0.07, 0.05), back_tint=0.92, gloss=0.45),
    PhotoCharm("maneki", "Maneki-neko", "maneki.png", 50, flat=False, sound="clink",
               material=(0.94, 0.93, 0.89), back_tint=0.9, gloss=0.55),
    PhotoCharm("scarab", "Scarab", "scarab.png", 44, attach=0.05, beads=1, sound="thud",
               thick=8, material=(0.36, 0.34, 0.22), back_tint=0.55, gloss=0.3),
    PhotoCharm("horseshoe", "Horseshoe", "horseshoe.png", 60, attach=0.0, sound="clank",
               thick=3.5, material=(0.33, 0.27, 0.20), back_tint=0.4, gloss=0.25),
    PhotoCharm("cornicello", "Cornicello", "cornicello.png", 20, attach=0.01, flat=False, sound="clink",
               material=(0.80, 0.78, 0.72), back_tint=0.2, gloss=0.6),
    PhotoCharm("knot", "Chinese knot", "knot.png", 52, attach=0.01,
               thick=2, material=(0.60, 0.07, 0.04), back_tint=0.3, gloss=0.2),
    PhotoCharm("omamori", "Omamori", "omamori.png", 40, attach=0.02,
               thick=5, material=(0.08, 0.12, 0.26), back_tint=0.35, gloss=0.2),
    WindChime(),
    Bell(),
    EmojiCharm(),
]
BY_KEY = {kind.key: kind for kind in KINDS}
