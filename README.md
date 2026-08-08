# ToolCell

A controlled-access tool drawer. Type a PIN, the drawer tells you which bin holds the tool you're
allowed to draw, that bin's flap opens itself, and every pick is logged against your name.

Built as a sales demonstrator to pitch against ZOLLER's »toolOrganizer« — a smart cutting-tool
cabinet that lands in India around **₹20 lakh**.

## Where it stands

| | |
|---|---|
| Status | design approved, not yet built |
| Spec | [`docs/superpowers/specs/2026-08-08-toolcell-design.md`](docs/superpowers/specs/2026-08-08-toolcell-design.md) |
| Next | phase 1 — bench rig, verify 3.3 V PWM drives an SG90 |

## What it is, physically

Two live compartments in one drawer of a printed multi-drawer chest. Each live compartment has a
hinged flap driven directly by an SG90 servo. Two more drawers are dummies, for grid context.

An ESP32-S3 runs its own WiFi access point and serves the operator kiosk to any phone or tablet — no
router, no internet, no laptop. A 4×4 keypad takes the PIN, a 16×2 LCD confirms the operator, IR
boards detect flap closure, and transactions append to flash.

**Everything electronic is already on the bench.** Out-of-pocket cost is about ₹1,700, mostly spare
servos and filament.

## What it deliberately is not

**It is not a lock.** The servo sits on the hinge, so the gearbox is the only thing resisting a pull.
It *guides* access rather than enforcing it. That was a deliberate trade to keep the build to one
moving part per cell. The sliding-bolt design that makes it a real lock is documented in §9 of the
spec.

**It does not count anything.** Stock decrements because the software said you'd take two. Worth
knowing: ZOLLER works exactly the same way — their inventory is trust-based too, with no sensors
anywhere in the product.

## Host body

Built into MakerWorld model 1105895, *Ryobi Mini Desktop Toolbox*. Geometry was measured directly
from the STLs rather than taken from the listing:

- Assembly 200 × 208 × 110 mm, four drawers in stackable bays
- Large drawer cavity **172.6 × 91 × 52 mm** — the measurement everything else depends on
- Small drawer cavity 172.6 × 91 × 27 mm

`tools/measure_stl.py` reproduces those numbers. It bounding-boxes every STL and ray-casts through
the drawers to find internal cavity dimensions and wall thicknesses.

**Do not print `obj_1_Ryobi badge.stl`.** Shipping a demonstrator carrying another manufacturer's
marks is a taste problem in front of a buyer and a trademark problem if this is ever sold.

## Why this is worth building

ZOLLER's cabinet is the cheap half of their product — the money is in TMS, their tool-management
software. But they're priced for German tier-1 automotive, and most Indian job shops will never buy
at ₹20 lakh.

The same hardware, built here, costs roughly **₹1.4 lakh** for a full 10-drawer cabinet. At a ₹4–5
lakh sale price that's a 4–5× undercut with healthy margin. Those figures are estimates and need a
real fabricator quote before they go in front of anyone.

The drawer gets you in the room. The software is the actual business.
