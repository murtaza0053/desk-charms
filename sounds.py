"""Sound effects for Desk Charms, synthesised once into WAV files and played with paplay.

creak    - rubbery squeak while the thread is being stretched
release  - elastic twang plus the chillies rustling when the nimbu-mirchi is let go
twang    - the elastic twang on its own, for the other objects
chime0-4 - aluminium chime tubes, a pentatonic set
bell     - a small brass bell
clink    - glass beads knocking together
thud     - a hollow wooden / papier-mache knock (daruma, drishti mask)
clank    - forged iron or heavy metal (horseshoe, hamsa)
"""
import math
import os
import random
import shutil
import struct
import subprocess
import wave

RATE = 44100
CACHE = os.path.expanduser("~/.cache/desk-charms/sounds-v2")
PLAYER = shutil.which("paplay")
CHIME_NOTES = (1046.5, 1174.7, 1318.5, 1568.0, 1760.0)  # C6 D6 E6 G6 A6


def _write(path, samples):
    peak = max(1e-9, max(abs(s) for s in samples))
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(b"".join(struct.pack("<h", int(s / peak * 0.9 * 32767)) for s in samples))
    os.replace(tmp, path)  # so a half-written file is never played


def _creak():
    """Stick-slip squeak: a rising rubbery tone chopped into tiny grains."""
    rng = random.Random(1)
    out, phase = [], 0.0
    n = int(RATE * 0.16)
    for i in range(n):
        t = i / RATE
        freq = 280 + 260 * (t / 0.16)
        phase += 2 * math.pi * freq / RATE
        tone = math.sin(phase) + 0.5 * math.sin(2 * phase) + 0.25 * math.sin(3 * phase)
        grain = 0.5 + 0.5 * math.sin(2 * math.pi * 38 * t) ** 8  # the stick-slip judder
        env = min(1.0, t / 0.01) * (1 - t / 0.16) ** 1.5
        out.append((tone * grain + 0.15 * rng.uniform(-1, 1)) * env)
    return out


def _release(rustle=True):
    """A twanging elastic snap back, then (for the nimbu-mirchi) the chillies rattling."""
    rng = random.Random(2)
    out, phase = [], 0.0
    n = int(RATE * (0.9 if rustle else 0.6))
    noise_lp = 0.0
    for i in range(n):
        t = i / RATE
        # twang: pitch falls as the thread slackens, with a wobble from the bounce
        freq = 95 + 130 * math.exp(-t * 9) + 6 * math.sin(2 * math.pi * 11 * t)
        phase += 2 * math.pi * freq / RATE
        twang = (math.sin(phase) + 0.35 * math.sin(2 * phase)) * math.exp(-t * 5.5) * min(1.0, t / 0.004)
        snap = rng.uniform(-1, 1) * math.exp(-t * 90)
        sample = twang * 0.8 + snap * 0.6
        if rustle:  # noise in little bursts as the chillies knock together
            noise_lp += 0.35 * (rng.uniform(-1, 1) - noise_lp)
            bursts = max(0.0, math.sin(2 * math.pi * 17 * t + 3 * math.sin(2 * math.pi * 3 * t))) ** 3
            sample += (rng.uniform(-1, 1) - noise_lp) * bursts * math.exp(-t * 4) * 0.5
        out.append(sample)
    return out


def _ring(partials, seconds, strike=0.0, seed=3):
    """Sum of decaying sine partials: (frequency, amplitude, decay per second)."""
    rng = random.Random(seed)
    steps = [2 * math.pi * f / RATE for f, _a, _d in partials]
    out = []
    for i in range(int(RATE * seconds)):
        t = i / RATE
        s = 0.0
        for (f, a, d), w in zip(partials, steps):
            s += a * math.exp(-d * t) * math.sin(w * i)
        attack = min(1.0, t / 0.002)
        out.append(s * attack + strike * rng.uniform(-1, 1) * math.exp(-t * 400))
    return out


def _chime(f):
    # free-free bar overtones are inharmonic: 1, 2.76, 5.40, 8.93
    return _ring([(f, 1.0, 1.1), (f * 2.756, 0.45, 2.2), (f * 5.404, 0.22, 4.0),
                  (f * 8.933, 0.1, 6.0), (f * 1.003, 0.4, 1.0)], 3.0, strike=0.15)


def _bell():
    f = 640.0  # small brass bell: hum, prime, tierce, quint, nominal and up, with a slight beat
    return _ring([(f * 0.5, 0.3, 0.7), (f, 1.0, 1.0), (f + 1.6, 0.6, 1.0), (f * 1.19, 0.55, 1.5),
                  (f * 1.5, 0.35, 1.7), (f * 2.0, 0.5, 2.0), (f * 2.51, 0.25, 2.6),
                  (f * 2.66, 0.2, 2.8), (f * 3.01, 0.15, 3.4)], 2.8, strike=0.25)


def _clink():
    first = _ring([(2730, 1.0, 22), (4120, 0.6, 30), (5890, 0.4, 38), (7420, 0.25, 45)], 0.45, 0.3, 5)
    second = _ring([(3110, 0.7, 26), (4630, 0.45, 34), (6610, 0.3, 42)], 0.38, 0.3, 6)
    delay = int(RATE * 0.075)
    out = first + [0.0] * delay
    for i, s in enumerate(second):
        out[delay + i] += 0.55 * s
    return out


def _thud():
    return _ring([(185, 1.0, 16), (410, 0.5, 24), (760, 0.3, 34), (1180, 0.15, 45)], 0.4, strike=0.5, seed=7)


def _clank():
    return _ring([(520, 1.0, 5.5), (523, 0.4, 5.5), (1373, 0.6, 8), (2412, 0.45, 11), (3620, 0.3, 14)],
                 1.3, strike=0.45, seed=8)


SOUNDS = {
    "thud": _thud,
    "clank": _clank,
    "creak": _creak,
    "release": _release,
    "twang": lambda: _release(rustle=False),
    "bell": _bell,
    "clink": _clink,
    **{f"chime{i}": (lambda f=f: _chime(f)) for i, f in enumerate(CHIME_NOTES)},
}


def _path(name):
    return os.path.join(CACHE, name + ".wav")


def prepare():
    """Synthesise any missing sound files (a few seconds the first time)."""
    os.makedirs(CACHE, exist_ok=True)
    for name, make in SOUNDS.items():
        if not os.path.exists(_path(name)):
            _write(_path(name), make())


def play(name, volume=1.0):
    """Fire and forget; volume 0..1. Does nothing if there is no player or the file isn't ready."""
    path = _path(name)
    if not PLAYER or volume <= 0.005 or not os.path.exists(path):
        return
    subprocess.Popen([PLAYER, "--volume", str(int(65536 * min(1.0, volume))), path],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
