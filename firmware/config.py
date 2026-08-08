"""
shopkeeper NANO — configuration.

Everything a given unit needs to differ on lives here, so no other file has to
be edited per build. Calibration written from the web UI is persisted to
/data/cal.json and overrides the defaults below at boot.
"""

# ── network ────────────────────────────────────────────────────────────────
# AP is the default on purpose. A demonstrator has to work on a shop floor and
# in a meeting room with no guest wifi, so the cabinet brings its own network
# and the salesperson's phone joins it. Set JOIN to a (ssid, password) tuple to
# also try an existing network first.
AP_SSID     = "shopkeeper-NANO"
AP_PASSWORD = "forge2026"          # >= 8 chars or the ESP refuses to start the AP
# Joining the house network first means the cabinet is reachable from a laptop
# that is also on the internet. Falls back to its own AP if the join fails, so
# the meeting-room case still works.
#
# CREDENTIALS DO NOT LIVE IN THIS FILE. This is a public repository and a real
# SSID and password were committed here once already. secrets.py is gitignored;
# copy secrets_example.py to secrets.py and put them there.
try:
    from secrets import JOIN
except ImportError:
    JOIN = None                    # no secrets.py -> AP mode only, which is safe
JOIN_TIMEOUT_S = 12

# ── servos ─────────────────────────────────────────────────────────────────
# Pulse widths, microseconds. An SG90 nominally spans 500..2500 us for 180 deg,
# but clones reach 160-175 before they stall against their own end stop and
# start cooking, so the defaults deliberately ask for less than the mechanism
# can do.
#
#   span_us / 2000 * 180 = degrees,  degrees / 180 * 31.42 = mm of drawer
#   650..2350  ->  1700 us  ->  153 deg  ->  26.7 mm of the 31.4 available
#
# (An earlier comment here claimed 700..2300 was 160 deg. It is 144. The
# arithmetic is written out above so the next person can check it.)
#
# The web UI writes these live, so calibrate against the real drawer rather
# than trusting the numbers here.
SERVO_FREQ_HZ = 50
DRAWERS = [
    {"id": 0, "name": "Drawer A", "pin": 5,  "closed_us": 650, "open_us": 2350},
    {"id": 1, "name": "Drawer B", "pin": 6,  "closed_us": 650, "open_us": 2350},
]

# How long a full open or close takes. The mechanism does not need easing to
# survive - 17.6 N against a 0.06 N load - but a drawer that glides reads as a
# product and a drawer that snaps reads as a toy.
TRAVEL_MS = 1100

# An SG90 hunts audibly when it is holding position and gets warm doing it. The
# rack and pinion is not backdriveable enough to matter over a demo, so cut the
# signal once the move has settled.
DETACH_AFTER_MS = 450

# ── access ─────────────────────────────────────────────────────────────────
# This is the whole product thesis in four lines. ZOLLER's toolOrganizer does
# not weigh, photograph or RFID anything - inventory is trust-based, and what
# is actually sold is controlled access plus a record of who opened what. So
# that is what this implements.
# Set False to bypass the lock entirely while working on the bench. The access
# control IS the product - it is the whole argument against ZOLLER - so this is
# a development switch, not a feature. The terminal shows a loud BYPASSED chip
# whenever it is off, because demonstrating this cabinet with its lock disabled
# would undo the pitch in one sentence.
REQUIRE_PIN = False
PIN         = "2468"
PIN_TIMEOUT_S = 120        # re-lock after this long with no activity
LOG_MAX     = 60           # entries kept in RAM and mirrored to /data/log.json

# ── inventory ──────────────────────────────────────────────────────────────
# Slot list per drawer. Purely a register: nothing on this machine senses
# whether a tool is physically present, and the UI says so rather than
# implying a measurement it never takes.
TOOLS = {
    0: [
        {"slot": "A1", "tool": "END MILL 10mm 4FL",  "code": "EM-10-4F"},
        {"slot": "A2", "tool": "END MILL 6mm 3FL",   "code": "EM-06-3F"},
        {"slot": "A3", "tool": "DRILL HSS 8.5mm",    "code": "DR-085-H"},
        {"slot": "A4", "tool": "CHAMFER 90deg 12mm", "code": "CH-12-90"},
    ],
    1: [
        {"slot": "B1", "tool": "FACE MILL 40mm",     "code": "FM-40-5I"},
        {"slot": "B2", "tool": "BORING HEAD 20-50",  "code": "BH-2050"},
        {"slot": "B3", "tool": "TAP M8 x 1.25",      "code": "TP-M8-C"},
        {"slot": "B4", "tool": "REAMER 12H7",        "code": "RM-12H7"},
    ],
}

# ── identity ───────────────────────────────────────────────────────────────
# A cabinet on a shop floor has an asset tag, and the UI shows it. This is the
# difference between a demo and a machine somebody signs for.
UNIT     = "SK-N-0001"
FW       = "1.0.0"
SITE     = "OMMI FORGE / MALUR"

DATA_DIR = "/data"
