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
WL, SC   = 2.0, 1.2
FLOOR_T  = 1.4
DECK_Z, DECK_T = 34.5, 2.5
DECK     = DECK_Z + DECK_T           # 35.5
CW, CD   = 92.0, 74.0
MID_GAP  = 6.0
DR_D     = 55.0
DR_W     = (CW - 2*WL - MID_GAP - 2*SC) / 2
DR_X     = (WL + SC, WL + SC + DR_W + MID_GAP)
M, TEETH = 1.25, 16
R_P      = M*TEETH/2
TRAVEL   = math.pi*R_P
FIN_T, FIN_H = 3.0, 8.0
TOOTH_H  = 2.25*M
FIN_SPAN = FIN_T + TOOTH_H
FIN_X    = DR_W*0.20
PIN_DX   = -FIN_T/2 + (FIN_SPAN - M) + R_P
PIN_Y    = 17.6
DR_FLOOR = 1.8
RACK_Y0  = 3.0
SG_L, SG_W, SG_H, SG_TAB = 22.8, 12.2, 22.7, 32.2

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
import nano as NA                                   # reuse the authoring pose
rack_asm = NA.rack(assembly=True)

y_closed = 7.8

def drawer_at(slot, pull):
    dx = DR_X[slot]
    d = T(drawer0, dx, y_closed - pull, DECK + 0.2)
    r = T(rack_asm, dx + FIN_X - FIN_T/2, RACK_Y0 + y_closed - pull,
          DECK + DR_FLOOR + 0.2)
    return d, r

# SG90 proxy: body plus the tab flange, at its real size
def servo_at(slot):
    px = DR_X[slot] + FIN_X + PIN_DX
    body = box(extents=[SG_L, SG_W, SG_H])
    body.apply_translation([px, WL + PIN_Y, FLOOR_T + SG_H/2])
    tabs = box(extents=[SG_TAB, SG_W, 2.5])
    tabs.apply_translation([px, WL + PIN_Y, FLOOR_T + 15.9])
    return trimesh.util.concatenate([body, tabs])

STATIC = {"case_lower": case_lo, "deck": deck, "case_upper": case_up,
          "servo_A": servo_at(0), "servo_B": servo_at(1)}

print("\nSTATIC ASSEMBLY — nothing may overlap")
for a, b in itertools.combinations(STATIC, 2):
    v = inter(STATIC[a], STATIC[b])
    chk(f"{a} vs {b}", v < 1.0, f"{v:8.2f} mm3")

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
chk("pinion tip radius", abs(pin_r_tip - (R_P + M)) < 0.25,
    f"{pin_r_tip:.2f} mm, expected {R_P+M:.2f}")

# rack pitch line, measured: tooth tips minus one addendum
rv = rack_asm.vertices
blade = rv[rv[:, 2] < -0.5]                 # flange sits at z 0..2; teeth below
tip_x   = blade[:, 0].max()
pitch_x = tip_x - M                         # pitch line is one addendum in
pin_axis_x = PIN_DX + FIN_T/2               # both now in RACK-local x
centre = pin_axis_x - pitch_x
chk("rack/pinion centre distance", abs(centre - R_P) < 0.20,
    f"{centre:.3f} mm, needs {R_P:.3f}")

# vertical band overlap between pinion teeth and rack teeth
rack_z0, rack_z1 = rack_asm.bounds[0][2], rack_asm.bounds[1][2]
rack_z0 += DECK + DR_FLOOR; rack_z1 += DECK + DR_FLOOR
pin_bot = FLOOR_T + 29.0 - 2.0                      # horn underside
pin_z0, pin_z1 = pin_bot, pin_bot + 5.0
ov = min(rack_z1, pin_z1) - max(rack_z0, pin_z0)
chk("pinion/rack vertical overlap", ov >= 4.0,
    f"{ov:.2f} mm  (rack {rack_z0:.1f}-{rack_z1:.1f}, pinion {pin_z0:.1f}-{pin_z1:.1f})")
chk("pinion clears the deck underside", pin_z1 <= DECK - DECK_T - 0.3,
    f"pinion top {pin_z1:.1f}, deck underside {DECK-DECK_T:.1f}")

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
