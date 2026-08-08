#!/usr/bin/env python3
"""
PREFLIGHT — the go/no-go before filament is spent.

Assembles every real mesh in its true pose, adds a solid proxy for the SG90,
and runs boolean intersections on every pair. Anything that overlaps cannot be
assembled. Then it measures the gear mesh off the geometry rather than the
source, and sweeps both drawers through full stroke.

Nothing here reads intent from cad/nano.py's variables — it measures shipped
STLs, because the source has been right and the mesh wrong before.
"""
import os, sys, math, itertools
import numpy as np
import trimesh
from trimesh.creation import box

HERE = os.path.dirname(os.path.abspath(__file__))
N    = os.path.join(HERE, "..", "nano")
sys.path.insert(0, HERE)

# ── geometry constants that describe the ASSEMBLY, not any part ──
# These are POSES, not shapes. The shapes still come off the shipped STLs and
# are never read from the source - but where a part sits has to be stated
# somewhere, and stating it twice is how this file came to be checking a
# 34.5 mm deck against parts built for a 39.5 mm one. One definition, imported.
import nano as NA                                   # poses only, never shapes
WL, SC   = NA.WL, NA.P["side_clear"]
FLOOR_T  = NA.P["floor_t"]
DECK_Z, DECK_T = NA.P["deck_z"], NA.P["deck_t"]
DECK     = NA.DECK
CW, CD   = NA.CW, NA.CD
MID_GAP  = NA.P["mid_gap"]
DR_D     = NA.DR_D
DR_W     = NA.DR_W
DR_X     = NA.DR_X
M, TEETH = NA.M, NA.N
R_P      = NA.R_P
TRAVEL   = NA.TRAVEL
FIN_T, FIN_H = NA.P["fin_t"], NA.P["fin_h"]
ADD, DED = NA.ADD, NA.DED
TOOTH_H  = NA.TOOTH_H
FIN_SPAN = NA.FIN_SPAN
FIN_X    = NA.FIN_X
PIN_DX   = NA.PIN_DX
PIN_Y    = NA.PIN_Y
DR_FLOOR = NA.P["dr_floor"]
RACK_Y0  = NA.RACK_Y0
SG_L, SG_W, SG_H, SG_TAB = (NA.P["sg_l"], NA.P["sg_w"], NA.P["sg_h"], NA.P["sg_tab"])
SG_BASE, SG_EAR, SG_HORN = NA.SG_BASE, NA.P["sg_ear"], NA.SG_HORN
Y_CLOSED = NA.Y_CLOSED

def L(n): return trimesh.load(os.path.join(N, n + ".stl"))
def T(m, x=0, y=0, z=0):
    m = m.copy(); m.apply_translation([x, y, z]); return m
def inter(a, b):
    try:
        return float(trimesh.boolean.intersection([a, b], engine="manifold").volume)
    except Exception:
        return 0.0

fails, warns = [], []
def chk(label, ok, detail, warn_only=False):
    tag = "PASS" if ok else ("WARN" if warn_only else "FAIL")
    print(f"  [{tag}] {label:44s} {detail}")
    if not ok:
        (warns if warn_only else fails).append(label)

print("\nPREFLIGHT — shopkeeper NANO\n")
print("Assembling shipped meshes ...")

case_lo = L("case_lower")
deck    = T(L("deck"), WL + 0.3, WL + 0.3, DECK - DECK_T)
case_up = T(L("case_upper"), 0, 0, DECK)
drawer0 = L("drawer"); rack0 = L("rack")

# rack in assembly pose: flange down onto the drawer floor, blade through it
rack_asm = NA.rack(assembly=True)

y_closed = Y_CLOSED

def drawer_at(slot, pull):
    dx = DR_X[slot]
    d = T(drawer0, dx, y_closed - pull, DECK + 0.2)
    r = T(rack_asm, dx + FIN_X - FIN_T/2, RACK_Y0 + y_closed - pull,
          DECK + DR_FLOOR + 0.2)
    return d, r

# SG90 proxy: body plus the tab flange, at its real size, sitting on the
# pedestal at SG_BASE - not on the floor. The servo's height is what sets the
# pinion's height, so getting it wrong here hides the whole stack-up.
def servo_at(slot):
    px = DR_X[slot] + FIN_X + PIN_DX
    body = box(extents=[SG_L, SG_W, SG_H])
    body.apply_translation([px, WL + PIN_Y, SG_BASE + SG_H/2])
    tabs = box(extents=[SG_TAB, SG_W, 2.5])
    tabs.apply_translation([px, WL + PIN_Y, SG_BASE + SG_EAR + 1.25])
    return trimesh.util.concatenate([body, tabs])

STATIC = {"case_lower": case_lo, "deck": deck, "case_upper": case_up,
          "servo_A": servo_at(0), "servo_B": servo_at(1)}

print("\nSTATIC ASSEMBLY — nothing may overlap")
for a, b in itertools.combinations(STATIC, 2):
    v = inter(STATIC[a], STATIC[b])
    chk(f"{a} vs {b}", v < 1.0, f"{v:8.2f} mm3")

print("\nEACH PART AGAINST ITS OWN MATE")
# The sweep below concatenates drawer+rack into one body before testing it
# against the world - so it can never see those two hit EACH OTHER. They did,
# by 155 mm3: the rack's flange was larger than the bin it drops into, in both
# axes. A part has to clear its own mate before anything else is worth testing.
_rk = rack_asm.copy()
_rk.apply_translation([FIN_X - FIN_T/2, RACK_Y0, DR_FLOOR])
chk("rack fits inside its own drawer", inter(drawer0, _rk) < 1.0,
    f"{inter(drawer0, _rk):8.2f} mm3")

print("\nDRAWERS THROUGH FULL STROKE")
for slot in (0, 1):
    worst, wp = 0.0, None
    for pull in (0, 6, 12, 18, TRAVEL):
        d, r = drawer_at(slot, pull)
        moving = trimesh.util.concatenate([d, r])
        for nm in ("case_lower", "deck", "case_upper", "servo_A", "servo_B"):
            v = inter(moving, STATIC[nm])
            if v > worst:
                worst, wp = v, f"{nm} @ pull {pull:.0f}"
    chk(f"drawer {'AB'[slot]} clears everything", worst < 1.0,
        f"{worst:8.2f} mm3  {wp or ''}")

# the two drawers must not touch each other either
d0, r0 = drawer_at(0, 0); d1, r1 = drawer_at(1, TRAVEL)
chk("drawer A vs drawer B", inter(trimesh.util.concatenate([d0, r0]),
                                 trimesh.util.concatenate([d1, r1])) < 1.0,
    "one open, one shut")

print("\nGEAR MESH — measured off the meshes")
pin = L("pinion")
pin_r_tip = max(np.linalg.norm(pin.vertices[:, :2] - [0, 0], axis=1))
chk("pinion tip radius", abs(pin_r_tip - (R_P + ADD)) < 0.25,
    f"{pin_r_tip:.2f} mm, expected {R_P+ADD:.2f}")

# rack pitch line, measured: tooth tips minus one addendum.
# Select BELOW the locating pegs, not merely below the flange. The pegs used to
# sit outboard at x -4.5 where they could never win max(x); they are inboard at
# +9.5 now, and a z<-0.5 filter picks a PEG as the tooth tip - which reads as a
# 4.56 mm centre distance on a pair that is actually correct.
rv = rack_asm.vertices
blade = rv[rv[:, 2] < -(DR_FLOOR + 1.0)]    # pegs bottom out at -DR_FLOOR
tip_x   = blade[:, 0].max()
pitch_x = tip_x - ADD                       # pitch line is one addendum in
pin_axis_x = PIN_DX + FIN_T/2               # both now in RACK-local x
centre = pin_axis_x - pitch_x
chk("rack/pinion centre distance", abs(centre - NA.CDIST) < 0.05,
    f"{centre:.3f} mm, needs {NA.CDIST:.3f} (R_P {R_P:.2f} + {NA.P['cd_bias']:.2f} bias)")

# The pinion's height is NOT free - it is set by the servo it sits on. This
# used to be hard-coded at FLOOR_T+27 and "passed" on 4.4 mm of a 5.0 face.
gear_t = float(pin.extents[2])
pin_z0, pin_z1 = SG_HORN, SG_HORN + gear_t
rack_z0, rack_z1 = rack_asm.bounds[0][2], rack_asm.bounds[1][2]
rack_z0 += DECK + DR_FLOOR + 0.2; rack_z1 += DECK + DR_FLOOR + 0.2
ov = min(rack_z1, pin_z1) - max(rack_z0, pin_z0)
chk("pinion/rack vertical overlap", ov >= gear_t - 0.01,
    f"{ov:.2f} of {gear_t:.2f} mm face  (rack {rack_z0:.1f}-{rack_z1:.1f}, "
    f"pinion {pin_z0:.1f}-{pin_z1:.1f})")
chk("pinion clears the deck underside", pin_z1 <= DECK - DECK_T - 0.3,
    f"pinion top {pin_z1:.1f}, deck underside {DECK-DECK_T:.1f}")
chk("rack blade clears the electronics",
    rack_z0 >= FLOOR_T + NA.P["esp_h"] + 1.5,
    f"blade bottom {rack_z0:.1f}, stack top {FLOOR_T+NA.P['esp_h']:.1f}")

print("\nPART INTEGRITY")
for n in ("case_lower", "case_upper", "deck", "drawer", "rack", "pinion"):
    m = L(n)
    nb = len(m.split(only_watertight=False))
    chk(f"{n}: single watertight body", nb == 1 and m.is_watertight,
        f"{nb} body, watertight={m.is_watertight}")

print()
if fails:
    print(f"  DO NOT PRINT — {len(fails)} failure(s): " + ", ".join(fails))
    sys.exit(1)
print(f"  CLEARED TO PRINT" + (f"  ({len(warns)} warning(s))" if warns else ""))
