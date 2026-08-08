#!/usr/bin/env python3
"""
Tolerance audit for shopkeeper NANO.

Every fit in the design, checked against practical FDM values for a 0.4 mm
nozzle in PETG. Dimension checks confirm parts do not collide; this confirms
they collide *by the right amount* — a joint can pass every interference test
and still rattle, seize, or slip.

Reference bands used (per side unless stated):
  press / interference   -0.10 .. +0.05   glue-free, needs force
  location (slip + glue)  0.08 .. 0.20
  running / sliding       0.30 .. 0.60
  free clearance          0.60 +
  M2 self-tap pilot       dia 1.60 .. 1.75
  gear backlash           0.10 .. 0.20 x module
"""
import math, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# mirror cad/nano.py — kept explicit so this file is readable on its own
P = dict(cw=92.0, cd=66.0, ch=53.0, wall=2.0, deck_z=25.5, deck_t=2.5,
         dr_h=18.0, dr_wall=1.8, dr_floor=1.8, dr_front=3.0,
         side_clear=1.2, mid_gap=2.0, module=1.25, teeth=12,
         gear_t=5.0, backlash=0.30, fin_t=3.0, fin_h=8.0,
         sg_l=22.8, sg_w=12.2, sg_h=22.7, sg_spline=4.8, clear=0.35,
         gap=0.8, peg=3.0)
M = P["module"]
TOOTH_H  = 2.25*M
FIN_SPAN = P["fin_t"] + TOOTH_H
PITCH    = math.pi*M
NOZZLE   = 0.4

rows, bad, warn = [], 0, 0

def fit(name, nominal, actual, lo, hi, kind, note=""):
    """lo/hi are the acceptable per-side clearance band."""
    global bad, warn
    cl = (actual - nominal) / 2.0
    if cl < lo - 1e-9:
        v, sev = "TIGHT", 2
    elif cl > hi + 1e-9:
        v, sev = "LOOSE", 1
    else:
        v, sev = "ok", 0
    bad += (sev == 2); warn += (sev == 1)
    rows.append((name, f"{nominal:.2f}", f"{actual:.2f}", f"{cl:+.3f}",
                 f"{lo:.2f}..{hi:.2f}", kind, v, note))

def val(name, actual, lo, hi, kind, note=""):
    global bad, warn
    if actual < lo - 1e-9:   v, sev = "UNDER", 2
    elif actual > hi + 1e-9: v, sev = "OVER", 1
    else:                    v, sev = "ok", 0
    bad += (sev == 2); warn += (sev == 1)
    rows.append((name, "-", f"{actual:.2f}", "-", f"{lo:.2f}..{hi:.2f}",
                 kind, v, note))

# ── sliding joints ────────────────────────────────────────────────────
fit("drawer in case, width", 2*41.8 + P["mid_gap"],
    P["cw"] - 2*P["wall"], 0.30, 0.60, "running",
    "both drawers across the internal width")
fit("rack blade in deck slot", FIN_SPAN, FIN_SPAN + 2.4, 0.30, 0.60,
    "running", "must also absorb drawer side-play")
fit("rack blade in floor slot", FIN_SPAN, FIN_SPAN + 0.5, 0.08, 0.20,
    "location", "rack is glued/pegged, not sliding")

# ── press and location fits ───────────────────────────────────────────
# spline is abandoned: 20 teeth on a 4.8 dia = 0.75 mm pitch, far under what a
# 0.4 nozzle resolves. Drive is through the servo horn, bolted.
fit("pinion recess on horn boss", 7.0, 8.4, 0.30, 0.90, "clearance",
    "horn is bolted, not pressed")
fit("pinion screw hole for M2", 2.0, 1.9, -0.10, 0.05, "thread",
    "M2 cuts its own thread in PETG")
fit("rack peg in drawer floor", P["peg"], P["peg"] + 0.25, 0.08, 0.20,
    "location", "pegged then glued")

# ── servo pocket ──────────────────────────────────────────────────────
fit("servo pocket, length", P["sg_l"], P["sg_l"] + 2*P["clear"],
    0.25, 0.45, "location", "SG90 body")
fit("servo pocket, width", P["sg_w"], P["sg_w"] + 2*P["clear"],
    0.25, 0.45, "location", "SG90 body")

# ── vertical stack ────────────────────────────────────────────────────
fit("drawer under case top", P["dr_h"], P["dr_h"] + P["gap"],
    0.30, 0.80, "running", "vertical rattle vs binding")

# ── gears ─────────────────────────────────────────────────────────────
val("gear backlash", P["backlash"], 0.10*M, 0.20*M, "gear",
    f"module {M}")
PRESS=math.radians(14.5)
_hp=(PITCH/2-P["backlash"])/2
val("tooth thickness at pitch line", 2*_hp, 3*NOZZLE, 99.0,
    "printability", "needs >= 3 extrusion widths")
val("tooth thickness at tip", 2*(_hp-M*math.tan(PRESS)), 2*NOZZLE, 99.0,
    "printability", "thin tips shear off")
val("trough width at root", PITCH-2*(_hp+1.25*M*math.tan(PRESS)),
    2*NOZZLE, 99.0, "printability", "nozzle must fit between teeth")
val("tooth height", TOOTH_H, 4*0.2, 99.0, "printability",
    "layers at 0.2 mm")
val("rack blade thickness", P["fin_t"], 2.5*NOZZLE, 99.0, "printability",
    "carries the full drive load")

# ── fasteners and walls ───────────────────────────────────────────────
val("M2 self-tap pilot", 1.70, 1.60, 1.75, "thread", "servo tabs")
val("case wall", P["wall"], 3*NOZZLE, 99.0, "printability", "")
val("drawer wall", P["dr_wall"], 3*NOZZLE, 99.0, "printability", "")
val("deck thickness", P["deck_t"], 2.0, 99.0, "structure",
    "spans the full internal width, loaded")

W = [30, 8, 8, 8, 12, 13, 6]
hdr = ("fit", "nominal", "actual", "per side", "target", "kind", "verdict")
print("\nTOLERANCE AUDIT — shopkeeper NANO\n")
print("  " + "".join(h.ljust(w) for h, w in zip(hdr, W)))
print("  " + "-" * (sum(W) + 2))
for r in rows:
    line = "".join(str(c).ljust(w) for c, w in zip(r[:7], W))
    print(f"  {line}  {r[7]}")
print(f"\n  {bad} tight/under (will not work), {warn} loose/over (will work but sloppy)")
sys.exit(1 if bad else 0)
