# shopkeeper

A tool crib that knows who took what.

Type a PIN, and the one bin you're cleared for slides open by itself. Take what you need, close it,
and the pick is logged against your name. Try a bin you're not cleared for and nothing moves.

Built as a working demonstrator to pitch against ZOLLER's »toolOrganizer« — a smart cutting-tool
cabinet that lands in India around **₹20 lakh**. Same job, built from a spool of PETG and about
₹2,000 of parts.

<!-- ![shopkeeper](docs/img/hero.jpg) -->

## Status

| | |
|---|---|
| Design | approved, parts generated, **nothing printed yet** |
| Spec | [`docs/superpowers/specs/2026-08-08-toolcell-design.md`](docs/superpowers/specs/2026-08-08-toolcell-design.md) |
| Next | print `case_mid` + `drawer` + lids, verify the rack meshes |

## What it is

A purpose-built three-module cabinet, 216 × 136 × 169 mm, printable on a 256 mm bed.

```
   control head    42 mm   4×4 keypad on top, 0.91" OLED in front, tablet cradle
   drawer bay      60 mm   the live drawer — two bins, two servos
   electronics bay 55 mm   ESP32-S3, 5 V supply, terminal blocks
   feet            12 mm
```

Each bin is **99 × 75 × 32 mm** and closed by a lid that **slides** on a rack driven by an SG90
through a printed 24-tooth pinion. 180° of servo gives 56.5 mm of travel, opening 57% of the bin.

An ESP32-S3 runs its own WiFi access point and serves the operator kiosk to any phone or tablet —
no router, no internet, no laptop.

## Why sliding lids, not hinged flaps

The first design used a hinged flap driven straight off the servo. It worked on paper and was
wrong in practice: a flap that opens 66° rises **76 mm above the drawer**, so the drawer had to be
pulled its full 105 mm out every single time. Anything less and the servo drives the flap into the
underside of the bay above and strips its nylon gears.

Sliding needs **zero vertical clearance**. Drawer position stops mattering, the servo can never
stall against an obstruction, and the interlock switch and limit stop both disappear from the BOM.

It also gives something for free: the two lids ride at different heights and slide over one
another, so **only one bin can be open at a time** — which is exactly what ZOLLER's cabinets
enforce.

The cost is that a lid opens about half its bin rather than swinging fully clear.

## Build it

```bash
python3 -m venv .venv
.venv/bin/pip install numpy trimesh manifold3d networkx shapely mapbox_earcut
.venv/bin/python cad/cabinet.py     # → out/*.stl
```

Every dimension lives in the `P` dict at the top of `cad/cabinet.py`. Change a number, re-run.
The script asserts its own geometry before exporting — bed fit, watertightness, gear travel, lid
clearance, servo envelope — because on this project the silent failures were the expensive ones.

| Script | Does |
|---|---|
| `cad/cabinet.py` | the whole cabinet, drawer, lids and gears |
| `cad/toolcell.py` | earlier hinged-flap mechanism, kept for reference |
| `cad/plates.py` | shelf-packs parts onto 256 mm plates, one 3MF each |
| `cad/mf3.py` | 3MF writer — trimesh 5.0 emits an empty `<build>` section |
| `tools/measure_stl.py` | bounding boxes and ray-cast internal cavities of any STL |

## Bill of materials

| | Qty | ₹ |
|---|---|---|
| ESP32-S3 dev board | 1 | on hand |
| SG90 servo (MG90S for a pilot) | 2 | on hand |
| 4×4 matrix keypad | 1 | on hand |
| 0.91″ SSD1306 OLED, I²C | 1 | ~150 |
| IR obstacle board | 2 | on hand |
| 5 V 3 A supply, DC jack, switch | 1 | on hand |
| M2 / M3 fasteners, 1/16″ steel pin | — | ~150 |
| PETG | ~1 kg | ~1,300 |

Runs off a USB power bank through a USB-A → 5.5×2.1 barrel lead, so it sets up on a meeting table
with no socket.

## What it deliberately isn't

**It does not count anything.** Stock decrements because the software said you'd take two. Worth
knowing: ZOLLER works the same way — their inventory is trust-based, with no sensors anywhere in
the product. The moat is access control and the database, not sensing.

## Licence

MIT for the code and models. ZOLLER, Ryobi and DeWALT are trademarks of their respective owners
and this project is not affiliated with any of them.
