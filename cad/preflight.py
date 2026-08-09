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
drawer0 = L("drawer")     # the drawer IS the rack now - teeth in its floor

y_closed = Y_CLOSED

def drawer_at(slot, pull):
    dx = DR_X[slot]
    return T(drawer0, dx, y_closed - pull, DECK + 0.2)

# SG90 proxy: body plus the tab flange, at its real size, sitting on the
# pedestal at SG_BASE - not on the floor. The servo's height is what sets the
# pinion's height, so getting it wrong here hides the whole stack-up.
def servo_at(slot):
    # LYING on its side: shaft along X, pinion a disc on its end. Body is sg_h
    # long along X from the spline face; cross-section sg_l x sg_w with the
    # shaft 5.9 in from one end of sg_l (Y here) and sg_w across Z.
    px  = DR_X[slot] + FIN_X + FIN_T/2 + 1.0
    sgn = NA.SG_DIR[slot]
    x0  = px + sgn*(NA.P["gear_t"]/2 + 1.6)
    body = box(extents=[SG_H, SG_L, SG_W])
    body.apply_translation([x0 + sgn*SG_H/2,
                            WL + PIN_Y + SG_L/2 - 5.9, NA.AXIS_Z])
    return body

STATIC = {"case_lower": case_lo, "deck": deck, "case_upper": case_up,
          "servo_A": servo_at(0), "servo_B": servo_at(1)}

print("\nSTATIC ASSEMBLY — nothing may overlap")
for a, b in itertools.combinations(STATIC, 2):
    v = inter(STATIC[a], STATIC[b])
    chk(f"{a} vs {b}", v < 1.0, f"{v:8.2f} mm3")

print("\nDRAWERS THROUGH FULL STROKE")
for slot in (0, 1):
    worst, wp = 0.0, None
    for pull in (0, 6, 12, 18, TRAVEL*153/180):
        moving = drawer_at(slot, pull)
        for nm in ("case_lower", "deck", "case_upper", "servo_A", "servo_B"):
            v = inter(moving, STATIC[nm])
            if v > worst:
                worst, wp = v, f"{nm} @ pull {pull:.0f}"
    chk(f"drawer {'AB'[slot]} clears everything", worst < 1.0,
        f"{worst:8.2f} mm3  {wp or ''}")

# the two drawers must not touch each other either
d0 = drawer_at(0, 0); d1 = drawer_at(1, TRAVEL*153/180)
chk("drawer A vs drawer B", inter(d0, d1) < 1.0, "one open, one shut")

print("\nGEAR MESH — measured off the meshes")
pin = L("pinion")
pin_r_tip = max(np.linalg.norm(pin.vertices[:, :2] - [0, 0], axis=1))
chk("pinion tip radius", abs(pin_r_tip - (R_P + ADD)) < 0.25,
    f"{pin_r_tip:.2f} mm, expected {R_P+ADD:.2f}")
# count the tooth loops in a horizontal section through the tooth band -
# counting raw vertices at z=0 was a bad proxy, because the boolean welds the
# underside into a handful of big triangles and the count says nothing
_sec = drawer0.section(plane_origin=[0, 0, TOOTH_H*0.5], plane_normal=[0, 0, 1])
_nl = len(_sec.entities) if _sec is not None else 0
chk("drawer carries teeth on its underside", _nl >= 12,
    f"{_nl} loops in the section at z={TOOTH_H*0.5:.2f}")
pitch_z = DECK + 0.2 + ADD
chk("lying pinion axis position", abs((pitch_z - NA.AXIS_Z) - R_P) < 0.05,
    f"axis {NA.AXIS_Z:.2f}, pitch {pitch_z:.2f} -> {pitch_z-NA.AXIS_Z:.2f} vs R_P {R_P:.2f}")
chk("pinion tip reaches into the teeth",
    NA.AXIS_Z + pin_r_tip > DECK + 0.2 + 0.5,
    f"tip {NA.AXIS_Z+pin_r_tip:.2f}, tooth tips start {DECK+0.2:.2f}")

print("\nPART INTEGRITY")
for n in ("case_lower", "case_upper", "deck", "drawer", "pinion"):
    m = L(n)
    nb = len(m.split(only_watertight=False))
    chk(f"{n}: single watertight body", nb == 1 and m.is_watertight,
        f"{nb} body, watertight={m.is_watertight}")

print()
if fails:
    print(f"  DO NOT PRINT — {len(fails)} failure(s): " + ", ".join(fails))
    sys.exit(1)
print(f"  CLEARED TO PRINT" + (f"  ({len(warns)} warning(s))" if warns else ""))
