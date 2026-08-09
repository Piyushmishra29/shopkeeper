"""
The top-face display: an animated attract loop, 128 x 64, one colour.

Read at arm's length, across a table, by someone who has not been told what to
look at. That rules out most of what looks good on a desk.

  - One thing is big. A glyph is 8 px per scale step, so scale 3 fits five
    characters across and scale 4 fits four. That is the whole typographic
    budget; everything else is subordinate to whatever gets the big line.
  - Inverted bars, not outlines. A filled block with knocked-out text is the
    highest-contrast mark a mono panel can make.
  - Animation earns its place. The gear screen turns a real 10-tooth pinion
    against a real rack at the real ratio - one rack pitch per gear tooth -
    because the pitch of the whole project is that this mechanism works. Drawer
    glyphs slide by measured position. Nothing else moves.

NOTHING WRITES OUTSIDE THE PANEL. Every string goes through _fit(), which
truncates to the pixels actually left at that x and scale. The first version
did the arithmetic by eye and put three strings over the edge - "TOOL ACCESS
CONTROL" is 19 characters, which is 152 px on a 128 px panel, and the bay
caption started at x=90 and ran to 146. Truncating at the draw call means a
long string can look clipped, but it can never silently vanish off the side.

MicroPython: no f-strings with =, no dict unpacking, no str.ljust.
"""
import math
import time

W, H = 128, 64
RAIL_H = 11


# ── text that cannot leave the panel ──────────────────────────────────────

def _fit(s, x=0, scale=1):
    room = (W - x) // (8 * scale)
    return s[:room] if room > 0 else ""


def txt(d, s, x, y, c=1):
    d.text(_fit(s, x), x, y, c)


def txt_c(d, s, y, c=1):
    s = _fit(s)
    d.text(s, (W - len(s) * 8) // 2, y, c)


def big_c(d, s, y, scale):
    s = _fit(s, 0, scale)
    d.big(s, (W - len(s) * 8 * scale) // 2, y, scale)


def txt_r(d, s, y, pad=3, c=1):
    s = _fit(s)
    d.text(s, W - len(s) * 8 - pad, y, c)


def rail(d, left, right=""):
    d.fill_rect(0, 0, W, RAIL_H, 1)
    r = _fit(right, 0)
    lmax = (W - len(r) * 8 - 10) // 8
    d.text(left[:max(lmax, 0)], 3, 2, 0)
    if r:
        d.text(r, W - len(r) * 8 - 3, 2, 0)


def drawer_glyph(d, x, y, pos, w=42, h=11):
    """Case outline with the drawer sliding out. pos 0..1, real position."""
    w = min(w, W - x - 1)
    d.rect(x, y, w, h, 1)
    slide = int((w // 3) * max(0.0, min(1.0, pos)))
    d.fill_rect(x + 2 + slide, y + 2, max(w - 10, 2), h - 4, 1)


def bar(d, x, y, w, h, frac):
    w = min(w, W - x - 1)
    d.rect(x, y, w, h, 1)
    fill = int((w - 4) * max(0.0, min(1.0, frac)))
    if fill > 0:
        d.fill_rect(x + 2, y + 2, fill, h - 4, 1)


# ── screens. each takes (d, ph, ctx); ph runs 0..1 across the dwell ───────

def _ease(t):
    return t*t*(3-2*t)


def _stagger(ph, i, n, lead=0.55):
    """Phase for row i of n, so rows arrive one after another."""
    a = i * (1.0 - lead) / max(n - 1, 1)
    return max(0.0, min(1.0, (ph - a) / lead))


def s_nameplate(d, ph, ctx):
    d.fill(0)
    rail(d, "SHOPKEEPER", ctx.get("link", ""))
    # wordmark drops in, then a highlight sweeps down it
    e = _ease(min(ph * 2.2, 1.0))
    big_c(d, "NANO", int(2 + 16 * e), 3)
    if ph > 0.45:
        y = RAIL_H + 4 + int((ph - 0.45) / 0.55 * (H - RAIL_H - 8))
        d.fill_rect(0, y, W, 2, 0)
        d.hline(0, y + 2, W, 1)
    if ph > 0.3:
        txt_c(d, "TOOL ACCESS", 52)


def s_mechanism(d, ph, ctx):
    """10-tooth pinion driving the rack, at the true ratio."""
    d.fill(0)
    rail(d, "RACK+PINION", "m1.25")
    N, R, rr = 10, 15, 9
    cxp, cyp = 34, 40
    rot = ph * 2 * math.pi / N * 4
    for i in range(N):
        a = rot + i * 2 * math.pi / N
        ca, sa = math.cos(a), math.sin(a)
        d.fb.line(int(cxp + rr*ca), int(cyp + rr*sa),
                  int(cxp + R*ca), int(cyp + R*sa), 1)
    d.fb.ellipse(cxp, cyp, rr, rr, 1)
    d.fb.ellipse(cxp, cyp, 3, 3, 1, True)
    pitch = 2 * math.pi * R / N
    off = (rot * R) % pitch
    y = cyp + R + 2
    d.hline(54, y + 6, 72, 1)
    x = 54 - off
    while x < W - 3:
        if x >= 54:
            d.fb.line(int(x), y + 6, int(x + 2), y, 1)
            d.fb.line(int(x + 2), y, int(x + 4), y + 6, 1)
        x += pitch
    txt(d, "19.6mm", 56, 18)
    txt(d, "TRAVEL", 56, 28)
    # a marker riding the rack, so the linear motion reads as motion
    d.fill_rect(54 + int((ph * 70) % 70), y - 5, 3, 3, 1)


def s_hours(d, ph, ctx):
    """How long it took. The only claim the panel makes."""
    d.fill(0)
    rail(d, "SHOPKEEPER")
    txt_c(d, "BUILT IN", 15)
    n = int(_ease(min(ph * 1.8, 1.0)) * 36)      # counts up to 36 and stops
    big_c(d, str(n), 25, 4)
    txt_c(d, "HOURS", 56)
    half = int(_ease(min(ph * 1.8, 1.0)) * 40)
    if half:
        d.hline(64 - half, 53, half * 2, 1)


def s_bays(d, ph, ctx):
    d.fill(0)
    rail(d, ctx.get("unit", "NANO"), ctx.get("link", ""))
    st = ctx.get("bays", [("BAY 1", 0.0, "SHUT"), ("BAY 2", 0.0, "SHUT")])
    for i, row in enumerate(st[:2]):
        label, pos, cap = row
        y = 16 + i * 24
        e = _stagger(ph, i, 2)
        if e <= 0:
            continue
        txt(d, label, 2, y + 2)
        drawer_glyph(d, 46, y, pos * _ease(e), w=40)
        if e > 0.5:
            txt(d, cap, 90, y + 12)
    d.hline(0, 39, W, 1)


def s_travel(d, ph, ctx):
    """Stroke, drawn as the drawer actually moves it. Out and back."""
    d.fill(0)
    rail(d, "STROKE", "153deg")
    mm = ctx.get("travel_mm", 16.7)
    pos = _ease(1.0 - abs(1.0 - 2.0 * ph))       # ping-pong
    drawer_glyph(d, 22, 16, pos, w=84, h=14)
    bar(d, 8, 36, 112, 9, pos)
    txt_c(d, "%.1f mm" % (mm * pos), 50)


def s_register(d, ph, ctx):
    n = ctx.get("tools", 8)
    d.fill(0)
    rail(d, ctx.get("unit", "NANO"), "REGISTER")
    shown = int(_ease(min(ph * 1.8, 1.0)) * n)
    big_c(d, str(shown), 14, 4)
    # one tick per tool, arriving with the count
    for i in range(n):
        x = 6 + i * ((W - 12) // max(n, 1))
        if i < shown:
            d.fill_rect(x, 48, 6, 4, 1)
        else:
            d.rect(x, 48, 6, 4, 1)
    txt_c(d, "TOOLS LOGGED", 56)


def s_stats(d, ph, ctx):
    d.fill(0)
    rail(d, ctx.get("unit", "NANO"), "STATUS")
    rows = (("CYCLES", str(ctx.get("cycles", 0))),
            ("UPTIME", ctx.get("uptime", "-")),
            ("HEAP", ctx.get("heap", "-")))
    for i, kv in enumerate(rows):
        e = _stagger(ph, i, 3)
        if e <= 0:
            continue
        y = 16 + i * 13
        txt(d, kv[0], 3, y)
        v = kv[1]
        txt_r(d, v[:max(1, int(len(v) * _ease(e)))], y)
        if i < 2:
            d.hline(3, y + 9, int((W - 6) * _ease(e)), 1)


def s_ledger(d, ph, ctx):
    """The record. This is the product, so it gets a screen of its own."""
    d.fill(0)
    rail(d, "LEDGER", str(ctx.get("events", 0)))
    log = ctx.get("log", [("1s", "UNLOCKED"), ("2m", "OPENED"), ("3m", "CLOSED")])
    for i, row in enumerate(log[:3]):
        e = _stagger(ph, i, 3)
        if e <= 0:
            continue
        y = 16 + i * 15
        slide = int((1.0 - _ease(e)) * 40)       # rows fly in from the right
        d.fill_rect(2 + slide, y, 3, 9, 1)
        txt(d, row[0], 8 + slide, y + 1)
        txt(d, row[1], 44 + slide, y + 1)


def s_spec(d, ph, ctx):
    d.fill(0)
    rail(d, "SPEC")
    rows = ("GEAR  m1.25x10T", "DRIVE SG90 x2", "PRINT 140g PLA", "CASE  92x74x66")
    for i, r in enumerate(rows):
        e = _stagger(ph, i, 4)
        if e <= 0:
            continue
        txt(d, r[:max(1, int(len(r) * _ease(e)))], 3, 15 + i * 12)


def s_net(d, ph, ctx):
    d.fill(0)
    rail(d, ctx.get("unit", "NANO"), "LINK")
    ssid = ctx.get("ssid", "shopkeeper-NANO")
    txt_c(d, ssid, 18)
    ip = _fit(ctx.get("ip", "192.168.4.1"))
    shown = ip[:max(1, int(len(ip) * _ease(min(ph * 2.0, 1.0))))]   # types out
    x = (W - len(ip) * 8) // 2
    d.text(shown, x, 32, 1)
    cx = x + len(shown) * 8
    if int(ph * 6) % 2 == 0 and cx + 6 < W:
        d.fill_rect(cx + 1, 32, 5, 8, 1)
    # signal bars climbing in the corner
    for i in range(4):
        if ph * 4 > i:
            d.fill_rect(W - 22 + i * 5, 46 - i * 2 - 2, 3, 4 + i * 2, 1)
    if ph > 0.5:
        txt(d, "OPEN IN", 3, 50)


def s_lock(d, ph, ctx):
    d.fill(0)
    rail(d, ctx.get("unit", "NANO"), "LOCKED")
    bx, by = W // 2 - 9, 24
    d.rect(bx + 4, by - 8, 10, 10, 1)
    d.fill_rect(bx + 6, by - 6, 6, 8, 0)
    d.fill_rect(bx, by, 18, 14, 1)
    d.fill_rect(bx + 8, by + 5, 2, 5, 0)
    for k in (0, 1):
        r = 12 + int(((ph + k * 0.5) % 1.0) * 16)
        d.fb.ellipse(W // 2, by + 7, r, min(r - 4, 22), 1)
    txt_c(d, "AUTHORISE", 52)


def s_moving(d, ph, ctx):
    """While a drawer actually travels. pos is measured, not animated - this is
    the one screen that must not lie about where the drawer is."""
    d.fill(0)
    label = ctx.get("moving_label", "BAY 1")
    pos = ctx.get("moving_pos", 0.0)
    mm = ctx.get("travel_mm", 16.7)
    rail(d, label, "MOVING")
    drawer_glyph(d, 22, 16, pos, w=84, h=14)
    bar(d, 8, 36, 112, 9, pos)
    txt_c(d, "%.1f mm" % (mm * pos), 50)


SCREENS = (s_nameplate, s_mechanism, s_hours, s_bays, s_travel,
           s_register, s_stats, s_ledger, s_spec, s_net)


# ── the loop ──────────────────────────────────────────────────────────────

def wipe_in(d, render, ctx, steps=4):
    render(d, 0.0, ctx)
    snap = bytes(d.buf)
    for k in range(steps):
        d.buf[:] = snap
        cut = H - int(H * (k + 1) / steps)
        if cut:
            d.fill_rect(0, H - cut, W, cut, 0)
        d.show()


def carousel(d, ctx, dwell=2.0, fps=18, screens=None, rounds=1, locked=False):
    seq = screens if screens is not None else ((s_lock,) if locked else SCREENS)
    n = 0
    while rounds == 0 or n < rounds:
        for render in seq:
            wipe_in(d, render, ctx)
            t0 = time.ticks_ms()
            while True:
                el = time.ticks_diff(time.ticks_ms(), t0) / 1000.0
                if el >= dwell:
                    break
                render(d, el / dwell, ctx)
                d.show()
        n += 1


class Loop:
    """Frame-at-a-time carousel, so it can live inside the asyncio loop next to
    the HTTP server instead of blocking it. carousel() above is the blocking
    version and is only for the bench."""

    def __init__(self, d, screens=None, dwell=2.0):
        self.d = d
        self.screens = screens if screens is not None else SCREENS
        self.dwell = dwell
        self.i = 0
        self.t0 = time.ticks_ms()
        self._was_override = False

    def tick(self, ctx, override=None):
        d = self.d
        if override is not None:
            # a live state beats the attract loop; run it on its own slow phase
            ph = (time.ticks_ms() % 2000) / 2000.0
            override(d, ph, ctx)
            d.show()
            self._was_override = True
            self.t0 = time.ticks_ms()
            return
        if self._was_override:
            self._was_override = False
            self.t0 = time.ticks_ms()
        el = time.ticks_diff(time.ticks_ms(), self.t0) / 1000.0
        if el >= self.dwell:
            self.i = (self.i + 1) % len(self.screens)
            self.t0 = time.ticks_ms()
            el = 0.0
        self.screens[self.i](d, el / self.dwell, ctx)
        d.show()
