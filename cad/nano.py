#!/usr/bin/env python3
"""
shopkeeper NANO — two motorised drawers, as small as an SG90 allows.

92 x 74 x 66 mm. Two drawers SIDE BY SIDE so one mechanism deck serves both;
stacking them would have doubled the height, because a vertical SG90 costs
26 mm of dead space under every deck.

    top          0.91" OLED + 2 LEDs on the top face, and the OMMI FORGE mark
                 debossed into it, filled by the printed logo inlay
    drawers      2 x (39.8 x 59 x 18), riding on the deck, each pushed by a
                 rack whose drive fin hangs through the deck into the bay
    deck         2.5 thick at z=39.5, slotted for both drive fins
    mech bay     everything under the deck: 2 x SG90 (shaft up, each sitting
                 on a 4.6 mm printed shim) + 2 pinions + 2 racks + the
                 ESP32-S3 on its breadboard, behind the servos

Full mechanical travel is 31.42 mm - pi x the 10.0 mm pitch radius, which is
exactly one half turn of the m1.25 x 16T pinion. The firmware deliberately
commands less than all of it (650..2350 us = 1700 us = 153 deg = 26.7 mm),
holding 4.7 mm of the stroke back so the servo never drives onto its own end
stop; the geometry below is still cut for the full 31.42.

Geometry is verified by boolean interference sweep across the full stroke,
not by dimension arithmetic — that is what caught every bug in the bigger
versions.
"""
import os, math, glob, sys
import numpy as np
import trimesh
from trimesh.creation import box, cylinder, extrude_polygon
from shapely.geometry import Polygon
from shapely.ops import unary_union
from mf3 import write_3mf, write_3mf_plates, verify
from shapely.affinity import scale as _sc, translate as _tr
from logo import trace as _logo_trace

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "nano")
os.makedirs(OUT, exist_ok=True)

P = dict(
    # 58, not 55: the first cut at 55 was greedy. The breadboard stack is
    # 28.4 tall so the deck cannot come below 29.5, and the drawer + anti-tip
    # rib need their headroom back. Still 8 mm shorter than the 66 it was.
    cw=92.0, cd=74.0, ch=58.0, wall=2.0, floor_t=1.4,
    deck_z=29.5, deck_t=2.5,
    # ONE-PIECE DRAWER. The teeth are cut into the underside of the drawer's
    # own floor - there is no separate rack and no blade hanging below. The
    # floor thickens 1.8 -> 4.0 so 2.56 mm of tooth still leaves a solid bin
    # bottom, and the 13 mm the blade used to hang below the floor comes out
    # of the case: 66 -> 55 tall. This is why the change is worth a reprint.
    dr_h=20.0, dr_wall=1.8, dr_floor=4.0, dr_front=3.0,
    side_clear=1.2, mid_gap=6.0,
    # Taken off the drawer's outside, all round, AFTER the bay is set. The bay
    # stays where it is; only the drawer gets smaller. 0.60 mm a side arrives
    # as 0.50 once both surfaces have grown, which measured "perfect" in the
    # hand and perfect is exactly wrong for something that has to slide.
    dr_shrink=0.50,
    # 16T again - but LYING DOWN. With the teeth in the drawer's floor the
    # pinion rolls beneath the drawer with its axis horizontal, and its radius
    # must span from below the deck up to the floor: that stack forces
    # R_p ~ 10 whatever module is chosen. The 10T experiment was about a
    # vertical gear's footprint on the deck; a lying gear shows only a
    # 7.5 x 19 slot, so the size objection disappears with the orientation.
    # Travel returns to 26.7 mm commanded.
    module=1.25, teeth=16, press=math.radians(14.5),
    # STUB teeth: addendum 0.8m instead of 1.0m. A full-depth involute at m1.25
    # comes to a 0.45 mm tip - under one extrusion width, so the machine rounds
    # it off and the contact it was supposed to make never happens. 0.8m puts
    # the tip at 0.75 mm and still leaves a contact ratio of 1.8.
    add_f=0.8, ded_f=1.25,
    gear_t=6.0, backlash=0.50,
    fin_t=3.0, fin_h=11.2,
    # SG90, measured from the body base upward. sg_base lifts it off the case
    # floor so the horn lands where the rack's teeth are; sg_ear is where the
    # mounting flange sits; sg_horn is the face the horn screws to.
    sg_l=22.8, sg_w=12.2, sg_h=22.7, sg_tab=32.2, sg_spline=4.8,
    # sg_horn follows from the measured spline: body top (22.7) + 4.0 of
    # spline = 26.7 above the body base. It was 26.5, taken off a datasheet.
    sg_base=6.0, sg_ear=15.9, sg_horn=26.7,
    # The output spline itself: 20 teeth, ~4.8 mm across, ~3.8 mm of it proud
    # of the body top. hub="spline" bores the pinion straight onto it and drops
    # the horn entirely; hub="horn" keeps the old keyed arm slot.
    # 5.0 measured on the actual servo, not the 4.8 nominal I had assumed.
    # A 4.65 bore against a 5.0 spline is 0.35 undersize - that does not press
    # on, it splits the boss.
    sg_spl_d=5.0, sg_spl_h=4.0,
    # MEASURED, not derived. Three test pinions were printed at modelled bores
    # of 5.15 / 5.25 / 5.35 and pressed onto the real spline; 5.15 is the one
    # that grips. So the bore is modelled 0.15 OVER the spline, not under it -
    # the hole loses about 0.30 mm in the print, and sizing it 0.15 under (the
    # textbook press allowance) produced a part that would not go on at all.
    # This is printer-specific. Re-run nano/plates/plate_0_bore_test.3mf on a
    # different machine before trusting it.
    spl_press=0.15,
    hub="spline",
    # THE OUTPUT SHAFT IS NOT IN THE MIDDLE OF THE BODY. It sits ~5.9 mm from
    # one end, which is plain to see on the part and was modelled nowhere: the
    # pocket was centred on the pinion axis, so the servo either would not go
    # in at all (863 mm3 of interference) or, if it did, would put its shaft
    # 5.5 mm off the axis - a centre-distance error half as big as the pitch
    # radius. The gear could never have meshed.
    sg_shaft=5.9,
    # The servo can rock +/-0.35 in its pocket, and that play points straight
    # along the centre-distance axis. Measured (cad/meshsim.py): at -0.35 plus
    # normal print growth the running gap is 0.013 mm, and at -0.45 it jams.
    # The curve is one-sided - too close seizes, too far only adds backlash -
    # so the centre distance is biased OUT by half the pocket play. Worst case
    # is then 9.80 mm, which still runs at +0.10 growth. Free insurance: a rack
    # and an involute pinion stay conjugate at any centre distance.
    cd_bias=0.15,
    clear=0.35, gap=1.5,
    # 59, not 55. The drawer used to stop 4 mm inside the case, which on a
    # sales piece reads as a part that does not fit, and put the moulded finger
    # pull out of reach - so there was no manual override if a servo died. The
    # extra 4 mm is all on the FRONT: the rear face lands at y=59 either way,
    # so the case bay is untouched and case_lower/case_upper do not change.
    dr_d=59.0,
    # Fraction of full travel the firmware actually commands (650..2350 us of
    # 500..2500). The bin is sized to THIS, not to the mechanism's maximum,
    # because a bin deeper than the drawer's reach strands tools inside the
    # case where no hand can get to them.
    cmd_frac=153.0/180.0,
    esp_h=27.0,              # ESP32-S3 on its breadboard, pins connected
    pull="cut",              # "cut" = scalloped finger pull, "knob" = press-fit knob
)
M, N   = P["module"], P["teeth"]
R_P    = M*N/2                                  # 10.0
ADD, DED = P["add_f"]*M, P["ded_f"]*M           # 1.0, 1.5625
R_TIP, R_ROOT = R_P+ADD, R_P-DED                # 11.0, 8.4375
R_BASE = R_P*math.cos(P["press"])               # 9.6815
PITCH  = math.pi*M
TRAVEL = math.pi*R_P                            # 31.42
TOOTH_H  = ADD + DED                            # 2.5625
FIN_SPAN = P["fin_t"] + TOOTH_H
# servo-driven heights, all referenced to the case floor
SG_BASE = P["sg_base"]                          # servo body bottom
SG_HORN = SG_BASE + P["sg_horn"]                # horn face = pinion underside

CW, CD, CH, WL = P["cw"], P["cd"], P["ch"], P["wall"]
DECK   = P["deck_z"] + P["deck_t"]              # 28
DR_D   = P["dr_d"]     # decoupled: the case got deeper for the breadboard,
                       # the drawer did not - extra depth is electronics bay
DR_TOP = DECK + P["dr_h"]                       # 46
DR_UND  = DECK + 0.2                            # drawer underside
PITCH_Z = DR_UND + ADD                          # rack pitch line, in Z now
AXIS_Z  = PITCH_Z - R_P                         # lying pinion axis height
# two drawers across the internal width
INNER  = CW - 2*WL
DR_W   = (INNER - P["mid_gap"] - 2*P["side_clear"]) / 2
DR_X   = (WL + P["side_clear"],
          WL + P["side_clear"] + DR_W + P["mid_gap"])
FIN_X  = DR_W * 0.20   # moved inboard so the bigger pinion's servo cradle
                       # still clears the right-hand case wall
# Pinion axis, measured from the rack's PITCH LINE - which sits one dedendum
# out from the blade face, not at the tooth tip. Getting this wrong by one
# addendum is the classic way to build a gear pair that binds.
# NOT "CD" - that name is already the case depth, and shadowing it built the
# whole case 10.15 mm deep instead of 74.
CDIST  = R_P + P["cd_bias"]                     # design centre distance
PIN_DX = P["fin_t"]/2 + DED + CDIST             # pinion offset from FIN_X
# 12.3, not 17.6. The lying servo bodies run 22.8 mm REARWARD from the axis,
# and at 17.6 they (and their pedestals) ploughed into the breadboard's front
# rail - the 3-body split in case_lower was the boolean engine choking on
# exactly that overlap. 12.3 parks the rear mounting ear 0.3 clear of the
# board face while the contact point stays well inside the tooth window.
PIN_Y  = 12.3          # pinion axis Y - must stay inside the tooth window
# ── LYING DRIVE: all Z references for the flat pinion ──
# teeth open downward out of the drawer floor; tips at the drawer underside,
# pitch line one addendum up inside
PITCH_Z = None          # set after DECK exists, below
# Which way each servo's body points from its own shaft. Slot 1 MUST run -x:
# pointing +x puts its mounting ear 1.77 mm through the right-hand wall.
SG_DIR = (+1, +1)
def sg_body_cx(slot, px):
    """Centre of the servo BODY, given the pinion axis. The ears are centred on
    the body, not on the shaft, so every mount feature hangs off this."""
    return px + SG_DIR[slot]*(P["sg_l"]/2 - P["sg_shaft"])
# ── alignment pins: ONE definition, used by all three parts ──
# case_lower grows them, deck is drilled for them, case_upper is socketed for
# them. Three parts reading one list is the only way they stay in agreement.
PIN_D, PIN_HOLE, PIN_SOCK = 2.5, 3.0, 3.1
PIN_POS = ((WL+4.5, CD-WL-4.5), (CW-WL-4.5, CD-WL-4.5), (CW/2, WL+4.0))
PAD = ((WL, CD-WL, 1, -1), (CW-WL, CD-WL, -1, -1))   # two rear corners
PAD_MULL = (CW/2-3.0, CW/2+3.0, WL, WL+7.0)          # front mullion, on case_lower
PAD_MULL_U = (CW/2-2.4, CW/2+2.4, WL, WL+7.0)        # narrower: drawers pass either side

def T(m,x=0,y=0,z=0): m.apply_translation([x,y,z]); return m
def blk(x0,x1,y0,y1,z0,z1):
    x0,x1=sorted((x0,x1)); y0,y1=sorted((y0,y1)); z0,z1=sorted((z0,z1))
    assert x1>x0 and y1>y0 and z1>z0, f"degenerate {x0,x1,y0,y1,z0,z1}"
    return T(box(extents=[x1-x0,y1-y0,z1-z0]),(x0+x1)/2,(y0+y1)/2,(z0+z1)/2)
def cyl_z(d,z0,z1,x,y,s=48): return T(cylinder(radius=d/2,height=z1-z0,sections=s),x,y,(z0+z1)/2)
def cyl_x(d,x0,x1,y,z,s=40):
    c=cylinder(radius=d/2,height=x1-x0,sections=s)
    c.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,[0,1,0]))
    return T(c,(x0+x1)/2,y,z)
def cyl_y(d,y0,y1,x,z,s=40):
    c=cylinder(radius=d/2,height=y1-y0,sections=s)
    c.apply_transform(trimesh.transformations.rotation_matrix(-math.pi/2,[1,0,0]))
    return T(c,x,(y0+y1)/2,z)
def diff(a,b): return trimesh.boolean.difference([a,b],engine="manifold")
def union(p): return trimesh.boolean.union(p,engine="manifold")

def chamfer(m,c=2.5):
    s=c*math.sqrt(2); cuts=[]
    for (x,y) in ((0,0),(CW,0),(0,CD),(CW,CD)):
        b=box(extents=[s,s,300])
        b.apply_transform(trimesh.transformations.rotation_matrix(math.pi/4,[0,0,1]))
        cuts.append(T(b,x,y,0))
    return diff(m,union(cuts))

def _inv(a):
    """Involute function. The whole gear is three lines of maths hung off this."""
    return math.tan(a) - a

def tooth_half_angle(r):
    """Half the tooth's angular thickness at radius r, on the involute.

    Inside the base circle the involute does not exist, so the flank drops
    radially to the root - the standard printed-gear approximation, and at
    m1.25 the difference is well under one extrusion width."""
    r = max(r, R_BASE)
    a = math.acos(min(1.0, R_BASE/r))
    # thickness at the pitch circle, thinned by the backlash allowance
    th_p = (PITCH/2 - P["backlash"]) / 2 / R_P
    return th_p + _inv(P["press"]) - _inv(a)

def pinion():
    """A DISC now, not a tower. The pinion lies on its side in the assembly -
    axis horizontal - rolling beneath the drawer whose floor carries the
    teeth. In its own frame it is modelled flat: involute profile extruded
    gear_t, spline bore straight through, M2.5 counterbored from the far
    face. It prints lying flat with full bed contact and no supports.

    The spline bore is THROUGH because the servo enters from one side and the
    screw from the other. Bore diameter is the measured 5.0 plus the measured
    +0.15 press allowance - see the bore-test plate."""
    STEPS = 16
    pts = []
    for i in range(N):
        th = 2*math.pi*i/N
        rs = [R_ROOT] + [R_BASE + (R_TIP-R_BASE)*k/(STEPS-1) for k in range(STEPS)]
        for r in rs:
            a = th - tooth_half_angle(r)
            pts.append((r*math.cos(a), r*math.sin(a)))
        for r in reversed(rs):
            a = th + tooth_half_angle(r)
            pts.append((r*math.cos(a), r*math.sin(a)))
    m = extrude_polygon(Polygon(pts), P["gear_t"])
    # spline enters this face 4.0 deep at the measured press diameter
    m = diff(m, cyl_z(P["sg_spl_d"] + P["spl_press"], -0.1, P["sg_spl_h"] + 0.2, 0, 0))
    # M2.5 clearance the rest of the way, head recessed into the far face
    m = diff(m, cyl_z(2.8, -0.1, P["gear_t"] + 0.1, 0, 0))
    m = diff(m, cyl_z(5.2, P["gear_t"] - 1.8, P["gear_t"] + 0.1, 0, 0))
    return m

def rack_fin(length,h=None):
    h=P["fin_h"] if h is None else h
    t=P["fin_t"]
    base=blk(0,t,0,length,0,h); tt=[]
    for i in range(int(length/PITCH)):
        yc=(i+0.5)*PITCH
        # half-thickness is defined at the PITCH LINE, which sits one addendum
        # below the tip - not at the tip itself
        hp  = (PITCH/2-P["backlash"])/2
        tip = hp - ADD*math.tan(P["press"])
        rt  = hp + DED*math.tan(P["press"])
        tt.append(extrude_polygon(Polygon(
            [(t,yc-rt),(t+TOOTH_H,yc-tip),(t+TOOTH_H,yc+tip),(t,yc+rt)]),h))
    return union([base]+tt)

def prism_y(pts_xz,y0,y1):
    """Extrude a profile given as (x,z) points along the Y axis."""
    m=extrude_polygon(Polygon(pts_xz),y1-y0)
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,[1,0,0]))
    m.apply_translation([0,y1,0]); return m

def prism_x(pts_yz,x0,x1):
    m=extrude_polygon(Polygon(pts_yz),x1-x0)
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,[1,0,0]))
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,[0,0,1]))
    m.apply_translation([x0,0,0]); return m   # x0: the prism grows +X from here

LEDGE=1.5

def case_lower():
    """Mech bay, OPEN TOP. Prints floor-down with no ceiling anywhere.

    Floor is thinner than the walls and perforated: it carries nothing but the
    servo cradles and the ESP32 posts, and every gram there is print time."""
    H=DECK; FT=P["floor_t"]
    m=diff(blk(0,CW,0,CD,0,H), blk(WL,CW-WL,WL,CD-WL,FT,H+1))
    # Deck ledge as a 45 deg gusset rather than a square shelf: a flat shelf
    # underside is unsupported, a 45 deg one prints itself. Seat stays at
    # H-deck_t. No front rail - it sat in the path of both drive fins.
    zt=H-P["deck_t"]
    m=union([m,prism_y([(WL,zt),(WL+LEDGE,zt),(WL,zt-LEDGE)],WL,CD-WL)])
    m=union([m,prism_y([(CW-WL,zt),(CW-WL-LEDGE,zt),(CW-WL,zt-LEDGE)],WL,CD-WL)])
    m=union([m,prism_x([(CD-WL,zt),(CD-WL-LEDGE,zt),(CD-WL,zt-LEDGE)],
                       WL,CW-WL)])
    for _slot, dx in enumerate(DR_X):
        sx=dx+FIN_X
        # (no front-wall slot any more: nothing hangs below the drawer)
        # ── LYING SERVO. Shaft horizontal along X, pinion a disc on its
        # end, rolling beneath the drawer. The body rests on its 12.2 side:
        # axis at AXIS_Z, so the bed the body lies on is 6.1 lower. SG_DIR
        # mirrors slot 1 so both pinions sit inboard of their servos.
        px = dx + FIN_X + P["fin_t"]/2 + 1.0     # pinion disc centre, X
        sgn = SG_DIR[_slot]
        body_x0 = px + sgn*(P["gear_t"]/2 + 1.6)             # spline-side face
        body_x1 = body_x0 + sgn*P["sg_h"]                    # far face
        bx0, bx1 = min(body_x0, body_x1), max(body_x0, body_x1)
        bed_z = AXIS_Z - P["sg_w"]/2                          # body underside
        # pedestal the body lies on, walls up its long sides
        m=union([m, blk(bx0-1.6, bx1+1.6, WL+PIN_Y-5.9-1.6,
                        WL+PIN_Y+P["sg_l"]-5.9+1.6, P["floor_t"], bed_z)])
        m=diff(m, blk(bx0-0.35, bx1+0.35, WL+PIN_Y-5.9-0.35,
                      WL+PIN_Y+P["sg_l"]-5.9+0.35, bed_z, DECK+1))
        # walls flanking the body, stopping under the deck ledge
        for wy0, wy1 in ((WL+PIN_Y-5.9-1.6, WL+PIN_Y-5.9-0.35),
                         (WL+PIN_Y+P["sg_l"]-5.9+0.35, WL+PIN_Y+P["sg_l"]-5.9+1.6)):
            m=union([m, blk(bx0-1.6, bx1+1.6, wy0, wy1, P["floor_t"],
                            min(AXIS_Z+P["sg_w"]/2, DECK-P["deck_t"]-0.4))])
    # ── ESP32-S3 DevKit ON ITS BREADBOARD, behind the servos ──
    # Measured assembly: 81.5 long x 35.5 across x ~15 tall, board plugged into
    # two breadboard strips. No soldering, so the breadboard stays in the case
    # and the case grew backwards to take it: 66 -> 94 deep.
    EX, EY = CW/2, CD - 20.05     # board shifted rearward, clear of the servos
    EBW, EBL, EBT = 35.5, 81.5, 1.6   # measured off the real assembly
    EBX = 2.0                          # slack each end so it drops in, not wedges
    FT = P["floor_t"]
    for sgn in (-1, 1):
        yy = EY + sgn*(EBW/2 + 1.5)
        # The breadboard interlocks like every other one: MALE dovetails down
        # one long side, FEMALE sockets down the other. So the two walls are
        # NOT the same part - one gets pegs, the other gets clearance.
        #   +Y wall  ->  pegs, they enter the FEMALE sockets
        #   -Y wall  ->  notches, they receive the MALE dovetails
        # Insert with the female side facing the rear wall.
        # The rear rail's outer face landed 0.25 mm shy of the rear wall - a
        # slot no nozzle can enter, so the slicer either welds it shut or
        # leaves a void. Run it INTO the wall instead.
        ry1 = (CD-WL) if sgn > 0 else (yy+1.5)
        m=union([m,blk(EX-EBL/2-EBX-1.5, EX+EBL/2+EBX+1.5, yy-1.5, ry1, FT, FT+6.5)])
        for sx0 in (13.5, 67.5):
            px_ = EX - EBL/2 + sx0
            if sgn > 0:
                # started 1.0 mm above the floor, so its underside printed on
                # nothing. It reaches the floor now.
                m=union([m,blk(px_-1.4, px_+1.4, yy-1.5, yy-3.0, FT, FT+4.6)])
            else:
                m=diff(m,blk(px_-2.0, px_+2.0, yy-1.6, yy+1.6,
                             FT+0.6, FT+5.4))
    # end stop at the front, open at the rear so the USB-C is reachable
    # End stop sits OUTSIDE the board envelope. It was at EX-EBL/2 from when the
    # board was 63 long; at 81.5 that put a 1.5mm rib inside the bay.
    m=union([m,blk(EX-EBL/2-EBX-1.6, EX-EBL/2-EBX, EY-EBW/2-1.4, EY+EBW/2+1.4,
                   FT, FT+5.2)])

    # This comment used to say "No breadboard" and describe a 92 x 66 case.
    # Both were superseded: the case is 92 x 74 x 66 and the breadboard is
    # modelled thirty lines above. Rear vents. The
    # DevKit's own headers take dupont leads directly.
    for wx in (20,40,60):
        m=diff(m,blk(wx,wx+15,CD-WL-1,CD+1,5,19))
    # ── USB-C x2 (native + UART) on the RIGHT-HAND wall ──
    # They sit on one END of the DevKit, and that end faces a SIDE wall, not
    # the rear. Orient the board with its USB end to the right.
    # Ports measured at 15 mm above the assembly base, which sits on the 1.4 mm
    # floor -> centreline z = 16.4. Window centred on that with 5 mm each way.
    m=diff(m,blk(CW-WL-1, CW+1, EY-13.0, EY+13.0, 11.4, 21.4))
    m=diff(m,cyl_y(8.0,CD-WL-1,CD+1,CW-11,12))
    # Vertical louvres, not scattered holes. Reads as a designed grille, and
    # vertical walls print themselves - only the 2.6 mm tops bridge.
    for k in range(5):
        yy = CD*0.30 + k*5.2
        for x0,x1 in ((-1, WL+1), (CW-WL-1, CW+1)):
            m=diff(m, blk(x0, x1, yy, yy+2.6, 7.0, 21.0))
    # lightening holes, skipping anything mounted to the floor
    keep=[(sg_body_cx(_s, dx+FIN_X+PIN_DX), WL+PIN_Y, 21.0)
          for _s, dx in enumerate(DR_X)]
    keep+= [(CW/2, CD-23.0, 46.0)]
    # Hex honeycomb on an offset grid. Same weight saved, but it reads as
    # engineered rather than as holes punched to save plastic.
    PX, PY = 11.5, 10.0
    gx=int((CW-2*WL-12)//PX); gy=int((CD-2*WL-12)//PY)
    for j in range(gy+1):
        for i in range(gx+1):
            x = WL+8 + i*PX + (PX/2 if j % 2 else 0)
            y = WL+8 + j*PY
            if x > CW-WL-6 or y > CD-WL-6: continue
            if any((x-kx)**2+(y-ky)**2 < kr**2 for kx,ky,kr in keep): continue
            m=diff(m, cyl_z(9.2, -1, P["floor_t"]+1, x, y, s=6))
    # ── alignment pins, on solid shoulders ──
    # Mid-wall pins stood in 2 mm of wall and would snap off. Corners are the
    # right idea, but the two FRONT corners sit inside the drawers' travel -
    # a pad there is struck at 8 mm of pull. So: both REAR corners, where two
    # walls meet, plus the front MULLION, which is 6 mm of solid material
    # between the two drawer mouths. Three well-spread points beat four with
    # one in the way.
    # Pads stop at the DECK UNDERSIDE, not at the deck's top face. They used to
    # fill the deck's own thickness, which forced three notches into the deck -
    # and one of those notches is what cut it down to a 0.60 mm neck. Now the
    # pins simply pass through the deck, which locates it as a bonus.
    zt = H - P["deck_t"]
    pb = H - 5.0                                  # pad underside
    for (cx, cy, sx, sy) in PAD:
        m=union([m, blk(cx, cx+7.0*sx, cy, cy+7.0*sy, pb, zt)])
        # 45 deg gusset off the rear wall. Without it the pad is a flat 7x7
        # shelf hanging in mid-air 37 mm up - 140 mm2 of the part's entire
        # unsupported area is these three pads.
        m=union([m, prism_x([(cy, pb-7.0), (cy+7.0*sy, pb), (cy, pb)],
                            min(cx, cx+7.0*sx), max(cx, cx+7.0*sx))])
    m=union([m, blk(*PAD_MULL, pb, zt)])
    m=union([m, prism_x([(WL, pb-7.0), (WL+7.0, pb), (WL, pb)],
                        PAD_MULL[0], PAD_MULL[1])])
    for (hx, hy) in PIN_POS:
        # Ø2.5, not Ø3.0. A 3.0 pin in a 3.35 socket is 0.36 diametral, which
        # after PLA's usual hole shrink and peg growth lands in INTERFERENCE -
        # and a 3 mm printed pin forced into interference snaps.
        m=union([m, cyl_z(PIN_D, zt, H+4.0, hx, hy)])
    return chamfer(m)

def deck():
    """Flat plate, prints on its face. It used to be the case's ceiling, which
    meant an 88 x 62 bridge in mid-air."""
    m=blk(WL+0.3,CW-WL-0.3,WL+0.3,CD-WL-0.3,0,P["deck_t"])
    for dx in DR_X:
        # The lying pinion pokes up through the deck: a disc gear_t thick in X
        # crossing the deck band. Chord at the deck top is what sizes the slot.
        px = dx + FIN_X + P["fin_t"]/2 + 1.0
        half = math.sqrt(max(1.0, R_TIP**2 - (DECK - AXIS_Z)**2)) + 1.5
        m=diff(m, blk(px - P["gear_t"]/2 - 0.75, px + P["gear_t"]/2 + 0.75,
                      WL + PIN_Y - half, WL + PIN_Y + half, -1, P["deck_t"]+1))
    # Pin CLEARANCE HOLES, not corner notches. The notches were what created the
    # neck, and they left the deck loose - it just rested on two 1.2 mm ledges
    # with nothing holding it down. Now the same three pins that register the
    # case halves pass through the deck and locate it too.
    for (hx, hy) in PIN_POS:
        m=diff(m, cyl_z(PIN_HOLE, -1, P["deck_t"]+1, hx, hy))
    m.apply_translation([-(WL+0.3),-(WL+0.3),0])
    return m

def case_upper():
    """Drawer bay + top face. Printed UPSIDE DOWN: the top face lands on the
    bed, the walls rise, and the drawer mouths open out of the top."""
    H=CH-DECK
    m=diff(blk(0,CW,0,CD,0,H), blk(WL,CW-WL,WL,CD-WL,-1,H-WL))
    mouth_top=DR_TOP+P["gap"]-DECK
    for dx in DR_X:
        x0,x1=dx-P["side_clear"]*0.5,dx+DR_W+P["side_clear"]*0.5
        m=diff(m,blk(x0,x1,-1,WL+1,-1,mouth_top))
        # 45 deg relief above the mouth so the flipped print self-supports
        # blk() already places the box; build it centred on the origin or the
        # T() below shifts it a second time and it lands on the mullion
        w=blk(-(x1-x0)/2,(x1-x0)/2,-1.4,1.4,-1.4,1.4)
        w.apply_transform(trimesh.transformations.rotation_matrix(
            math.radians(45),[1,0,0]))
        m=diff(m,T(w,(x0+x1)/2,WL/2,mouth_top))
    m=diff(m,blk(CW/2-13,CW/2+13,CD*0.62-5,CD*0.62+5,H-WL-1,H+1))
    for ddx in (-26,26): m=diff(m,cyl_z(5.0,H-WL-1,H+1,CW/2+ddx,CD*0.62))
    for ddx in (-16,16):
        m=union([m,blk(CW/2+ddx-2,CW/2+ddx+2,CD*0.62-3,CD*0.62+3,H-5,H-WL)])
    # Rear vent as FOUR windows. As one 56 mm opening its roof was a single
    # 56 x 2 mm bridge at print height 23 of 25 - half of this part's entire
    # unsupported area in one span. Four 11 mm windows bridge themselves.
    for k in range(4):
        vx = 18 + k*15.0
        m=diff(m,blk(vx,vx+11.0,CD-WL-1,CD+1,2,14))
    # matching shoulders and sockets
    # Gussets slope the OTHER WAY here. This part prints top-face-down, so its
    # local +z is downward on the bed: what supports a pad is material at
    # HIGHER local z, not lower. Copying case_lower's gusset would have hung it
    # in the air and doubled the problem.
    for (cx, cy, sx, sy) in PAD:
        m=union([m, blk(cx, cx+7.0*sx, cy, cy+7.0*sy, 0, 5.0)])
        m=union([m, prism_x([(cy, 12.0), (cy+7.0*sy, 5.0), (cy, 5.0)],
                            min(cx, cx+7.0*sx), max(cx, cx+7.0*sx))])
    # The mullion pad was CW/2 +/- 3.0 = x 43..49, and the drawers run to 43.00
    # and from 49.00 - zero clearance over their bottom 5 mm, so it pinched
    # them. Narrowed to +/- 2.4, which still carries the socket.
    m=union([m, blk(*PAD_MULL_U, 0, 5.0)])
    m=union([m, prism_x([(WL, 12.0), (WL+7.0, 5.0), (WL, 5.0)],
                        PAD_MULL_U[0], PAD_MULL_U[1])])
    for (hx, hy) in PIN_POS:
        m=diff(m, cyl_z(PIN_SOCK, -1, 4.6, hx, hy))

    # ── OMMI FORGE mark, debossed into the top face ──
    # case_upper prints top-face-down, so the mark's edges form against the
    # bed - the crispest surface the machine makes. No second colour: it is
    # white PLA, same as the case. White-on-white reads as shadow, so it is
    # cut 1.1 deep rather than 0.7 - deep enough to catch light. The top
    # plate is 2.0, so 0.9 of material remains under it.
    g = _logo_trace()[0]
    LH = 11.0                                   # mark height on the part
    g = _sc(g, LH/0.772, LH/0.772, origin=(0, 0))
    g = _tr(g, CW/2, 9.0)                       # front border, ahead of the keypad
    # the mark is 7 disjoint shapes and extrude_polygon takes ONE polygon
    cut = []
    for poly in (list(g.geoms) if hasattr(g, "geoms") else [g]):
        e = extrude_polygon(poly, 2.2)   # must break the top surface
        e.apply_translation([0, 0, H - 1.4])
        cut.append(e)
    # 0.4 relief across the whole mark at the pocket floor: the inlay's shapes
    # are tied together by a web down there, hidden once it is seated
    b = g.bounds
    cut.append(blk(b[0]-0.4, b[2]+0.4, b[1]-0.4, b[3]+0.4, H-1.4, H-1.0))
    m = diff(m, union(cut))
    return chamfer(m)

# 2.0, not 3.0. At 3.0 the rib left 0.80 mm to the bay ceiling, which is
# 0.70 as printed - close enough that a hair of warp drags the rib along the
# roof for the entire stroke. 2.0 leaves 1.80 and still holds droop under a
# millimetre, because droop scales with the GAP and the gap is still small.
ANTITIP = 2.5         # rear wall stands this proud, to catch the bay ceiling.
                      # 1.3 to the ceiling - deliberately looser than the 0.6
                      # that bound the last print. The drawer cannot actually
                      # droop that far anyway: with the teeth in its floor the
                      # drawer RESTS ON THE PINION at the contact point, a
                      # mid-span support the old hanging blade never had. The
                      # rib is the backstop, not the bearing.
POST_DX, POST_W = (-16.0, 16.0), 2.0   # OLED posts hanging from the bay ceiling

def post_bands():
    """Local-x bands on a drawer that the OLED posts hang into.

    The posts drop to 3 mm above the drawer, so an anti-tip rib has to step
    around them. Derived from the SAME constant case_upper builds them from -
    hardcoding the gaps is how two parts drift apart. Both drawers use one
    part, so the bands from BOTH bays are merged."""
    out = []
    for dx in DR_X:
        for ddx in POST_DX:
            x0 = CW/2 + ddx - POST_W - dx - 0.8
            x1 = CW/2 + ddx + POST_W - dx + 0.8
            if x1 > 0 and x0 < DR_W:
                out.append((max(0.0, x0), min(DR_W, x1)))
    return sorted(out)

def rib_segments():
    """The complement of post_bands() across the drawer's width."""
    segs, x = [], 0.0
    for b0, b1 in post_bands():
        if b0 - x > 2.0:
            segs.append((x, b0))
        x = max(x, b1)
    if DR_W - x > 2.0:
        segs.append((x, DR_W))
    return segs
RACK_L  = DR_D-6      # rack now runs nearly the full drawer
RACK_Y0 = 3.0              # rack start in drawer-part Y
PEG_D   = 3.0
# ── the rack lives INSIDE the drawer bin, so it must fit inside it ──
# The flange used to run -5.0 .. +8.0 in x and -3.0 .. L+3.0 in y, which is
# larger than the bin it drops into in BOTH axes: it ploughed through the front
# wall, the rear wall and 0.34 mm into the left side wall. The pegs sat at
# x -4.5, which put a 3.25 hole 1.96 mm from the drawer's outer face and left
# 0.33 mm of a 1.8 mm wall - less than one extrusion, so the slicer simply
# deleted it and opened the side of the drawer.
# Everything now grows INBOARD, away from the walls.
RK_X0, RK_X1 = -4.0, 12.5   # flange, rack-local x
PEG_X = 9.5                 # pegs, rack-local x - clear of the blade and the wall

# Where the bin has to stop. The drawer clears the case by exactly the
# commanded stroke; anything behind that line is inside the case even when the
# drawer is fully out, so it is solid material rather than a place to lose a
# tool.
BIN_BACK = TRAVEL * P["cmd_frac"]

def drawer():
    """Prints floor-down, flat on the bed.

    The drive rack used to be moulded onto the underside, which meant the whole
    42 x 62 body floated 8 mm in the air on a 3 mm blade — about 4% bed contact.
    It is now a separate part that pegs in through a floor slot, which also makes
    the gear rack replaceable: it is the riskiest feature in the design."""
    W,D,H=DR_W-2*P["dr_shrink"],DR_D,P["dr_h"]
    y0=0.0                    # front face flush with the case, knob does the work
    # bin stops at the reach line, not at the back of the drawer
    bin_back = min(y0+D-P["dr_wall"], y0+BIN_BACK)
    m=diff(blk(0,W,y0,y0+D,0,H),
           blk(P["dr_wall"],W-P["dr_wall"],y0+P["dr_front"],bin_back,
               P["dr_floor"],H+1))
    # (the separate rack, its floor slot, its pegs and its flange channel are
    # gone - the teeth live in the floor itself, cut below)
    # Hollow the rear, OPEN AT THE TOP. Left solid the drawer went 12.3 -> 33.5 g;
    # enclosed, its ceiling was a 36 x 28 mm bridge in mid-air - 963 mm2, 41% of
    # the footprint. Open-topped it costs nothing to print and nothing can fall
    # in anyway: the rear is inside the case whenever the drawer is out, and
    # under the bay roof when it is shut. The divider at bin_back is what stops
    # a tool sliding back out of reach.
    m=diff(m, blk(P["dr_wall"], W-P["dr_wall"],
                  bin_back + P["dr_wall"], y0+D-P["dr_wall"],
                  P["dr_floor"], H+1))
    # ── TEETH, cut up into the floor from below ──
    # The drawer IS the rack now. Tooth spaces are cut as prisms rising
    # TOOTH_H into the 4.0 floor, leaving 1.44 mm of solid bin bottom above
    # them. Printed floor-down the teeth are 2.56 mm-deep slots in the bed
    # face: full bed contact, no overhang, and the crispest surfaces the
    # machine makes form the flanks.
    hp  = (PITCH/2-P["backlash"])/2
    tip = hp - ADD*math.tan(P["press"])
    rt  = hp + DED*math.tan(P["press"])
    x0t = FIN_X - P["fin_t"]/2            # teeth run in the old blade's lane
    x1t = x0t + P["fin_t"] + 2.0          # a little wider for pinion alignment
    # SPACES between teeth, cut upward from the underside: wide at z=0 where
    # the tooth tips are, narrowing to the root at z=TOOTH_H. prism_x takes
    # (y,z) points directly - the previous hand-rolled rotation put 1.56 mm
    # of each cut BELOW the part, which is how a drawer shipped with 1 mm
    # stubs and preflight counted only 56 underside vertices.
    for i in range(int(RACK_L/PITCH)+1):
        yc = RACK_Y0 + i*PITCH
        sp = prism_x([(yc-(PITCH/2-tip), -0.2), (yc-(PITCH/2-rt), TOOTH_H),
                      (yc+(PITCH/2-rt), TOOTH_H), (yc+(PITCH/2-tip), -0.2)],
                     x0t, x1t)
        m=diff(m, sp)
    if P["pull"] == "knob":
        m=diff(m,cyl_y(4.1,-1,P["dr_front"]+1,W/2,H*0.55))
    else:
        # scalloped finger pull cut into the top-front edge. It opens upward, so
        # it is self-supporting - the void widens as the print rises.
        m=diff(m,cyl_x(14.0,W/2-9,W/2+9,1.5,H))
        m=diff(m,blk(W/2-9,W/2+9,-1,P["dr_front"]+0.5,H-1.2,H+1))
    # ── ANTI-TIP, and it lives on the DRAWER, not the case ──
    # An extended drawer has nothing holding it down: the rack is free to pitch
    # in the deck slot, so the drawer can rotate nose-down until its rear
    # corner finds the bay ceiling 3.8 mm above. That was a 5.1 mm nose droop -
    # enough to walk a tooth out of mesh.
    # The fix wants to be a rib on the bay wall, but the case is already on the
    # printer. Standing the REAR wall 3 mm proud does the same job from the
    # other side, against the ceiling that is already there: the rear corner
    # now has 0.8 mm to rise instead of 3.8. It stays clear of the mouth
    # because it is at the rear and the mouth is 24 mm ahead of it at full
    # travel, and the drawers are placed on the deck before the lid goes on,
    # so nothing has to pass through the mouth to assemble.
    # clamp the rib to the SHRUNK width - it is built from DR_W, and left
    # unclamped it holds the drawer at full size and undoes dr_shrink entirely
    for rx0, rx1 in rib_segments():
        rx0, rx1 = min(rx0, W), min(rx1, W)
        if rx1 - rx0 < 2.0:
            continue
        m=union([m,blk(rx0,rx1,y0+D-P["dr_wall"],y0+D,H,H+ANTITIP)])
    return m

def rack(assembly=True):
    """Modelled in ASSEMBLY orientation: flange on top, blade and pegs hanging
    down. Flipping a part between orientations mirrors a horizontal axis with it,
    so the flip happens once, at plating time, and never in the fit maths."""
    L=RACK_L; drop=P["fin_h"]+P["dr_floor"]
    fl=blk(RK_X0,RK_X1,0.3,L-0.3,0,2.0)
    blade=rack_fin(L,h=drop)      # must reach the flange, not stop 1.8 mm short
    blade.apply_translation([0,0,-drop])
    m=union([fl,blade])
    for py in (5.0,L-5.0):
        m=union([m,cyl_z(PEG_D,-P["dr_floor"],0,PEG_X,py)])
    if not assembly:                       # print pose: flange flat on the bed
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi,[1,0,0]))
        m.apply_translation(-m.bounds[0])
    return m

def logo_inlay():
    """The mark in WHITE, pressed into the black case's recess.

    1.2 tall in a 1.0 recess, so it stands 0.2 proud - embossed, in a second
    colour, with no filament change and no purge tower. Outline shrunk 0.15
    per side so it drops in rather than needing force."""
    g = _logo_trace()[0]
    LH = 11.0
    g = _sc(g, LH/0.772, LH/0.772, origin=(0, 0))
    b = g.bounds
    # hidden web ties the seven shapes into one handleable piece
    parts = [blk(b[0]-0.25, b[2]+0.25, b[1]-0.25, b[3]+0.25, 0, 0.4)]
    for poly in (list(g.geoms) if hasattr(g, "geoms") else [g]):
        sh = poly.buffer(-0.15)
        if sh.is_empty:
            continue
        for q in (list(sh.geoms) if hasattr(sh, "geoms") else [sh]):
            e = extrude_polygon(q, 1.2)
            e.apply_translation([0, 0, 0.4])
            parts.append(e)
    m = union(parts)
    m.apply_translation(-m.bounds[0])
    return m

def servo_shim():
    """Sets the servo's height, and therefore the pinion's.

    This is the only part in the design whose thickness comes from a number
    nobody has measured on the actual hardware. Making it a separate 2 g part
    means that number can be wrong without costing a 95 g case: measure your
    SG90 from the base of its body to the flat face the horn screws onto, and
    if it is not sg_horn, change sg_base by the difference and reprint THIS.

    Two are needed. Drops into the servo well; the servo body sits on it."""
    t = SG_BASE - P["floor_t"]
    # -0.6 diametral, not -0.3. At -0.3 the shim prints ~0.05/side over and the
    # well ~0.05/side under, so it arrives at +0.05 per side and has to be
    # forced - and a shim you have to force is a shim you cannot swap, which is
    # the entire reason it is a separate part.
    w, d = P["sg_l"]+2*P["clear"]-0.6, P["sg_w"]+2*P["clear"]-0.6
    m = blk(0, w, 0, d, 0, t)
    # finger holes, so a shim that has to come back out can be pushed out
    for fx in (5.0, w-5.0):
        m = diff(m, cyl_z(3.0, -1, t+1, fx, d/2))
    return m

def spline_gauge():
    """Five test bores, so the press fit is MEASURED instead of assumed.

    A generic SG90's output spline is nominally 4.8 mm but clones run 4.6-4.9
    and some have 21 teeth rather than 20. The pinion presses onto that spline
    with no second chance - too tight splits the boss, too loose slips under
    load. One gram of PLA settles it: press each bore onto the real servo,
    find the one that needs firm thumb pressure and then holds, and that
    number goes into sg_spl_d.

    Bores are 4.60 to 5.10 in 0.10 steps, marked with 1..6 notches so they can
    be told apart by feel as well as by eye. The range brackets the 5.0 mm
    measured on the real servo: the fit that works is usually 0.10-0.20 under
    the spline, so expect 4.80 or 4.90."""
    n, pitch, t = 6, 11.0, P["sg_spl_h"] + 1.6
    W = n*pitch + 5.0
    m = blk(0, W, 0, 13.0, 0, t)
    for i in range(n):
        cx = 5.0 + i*pitch - 2.5 + pitch/2
        d = 4.60 + i*0.10
        m = diff(m, cyl_z(d, -1, t+1, cx, 6.5))
        # i+1 notches along the front edge: countable with a fingernail
        for k in range(i+1):
            nx = cx - (i*0.9) + k*1.8
            m = diff(m, blk(nx-0.45, nx+0.45, -0.1, 1.4, t-1.0, t+1))
    return m

def knob():
    """Turned profile, revolved. Prints face-down: the flat outer face is the
    whole bed contact, and every upward surface is under 50 deg."""
    prof=np.array([[0.0,0.0],[5.5,0.0],[5.5,4.0],[3.0,7.0],
                   [1.95,7.6],[1.95,13.0],[0.0,13.0]])
    return trimesh.creation.revolve(prof, sections=64)

def rep(n,m):
    e=m.extents
    print(f"  {n:9s} {e[0]:6.1f} x {e[1]:6.1f} x {e[2]:5.1f}   "
          f"{m.volume/1000*1.27:5.1f} g   wt={m.is_watertight}")
    m.export(os.path.join(OUT,n+".stl")); return m

print("shopkeeper NANO\n")
print(f"  case       {CW:.0f} x {CD:.0f} x {CH:.0f} mm")
print(f"  drawers    2 x ({DR_W:.1f} x {DR_D:.1f} x {P['dr_h']:.1f})")
print(f"  bin usable {DR_W-2*P['dr_wall']:.0f} x {DR_D-P['dr_wall']-P['dr_front']:.0f} x {P['dr_h']-P['dr_floor']:.0f}")
print(f"  pinion     m{M} x {N}T, pitch dia {2*R_P:.1f}")
print(f"  travel     {TRAVEL:.1f} mm\n")

CASE_ASM=None
parts={"case_lower":rep("case_lower",case_lower()),
       "deck":rep("deck",deck()),
       "case_upper":rep("case_upper",case_upper()),
       "drawer":rep("drawer",drawer()),
       "knob":rep("knob",knob()),
       "logo_inlay":rep("logo_inlay",logo_inlay()),"pinion":rep("pinion",pinion()),
       "servo_shim":rep("servo_shim",servo_shim()),
       "spline_gauge":rep("spline_gauge",spline_gauge())}

FLIP={"case_upper"}          # top face down: crispest surface the machine makes
                             # (pinion is a flat disc now; it prints as modelled)

def bed_ratio(m,name=""):
    if name in FLIP:
        m=m.copy()
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi,[1,0,0]))
        m.apply_translation(-m.bounds[0])
    """Bed-contact area as a fraction of the largest cross-section. A part that
    stands on a sliver of itself will topple or print in mid-air; the old drawer
    scored 4%."""
    zmin=m.bounds[0][2]
    n=m.face_normals[:,2]; zc=m.triangles_center[:,2]
    base=float(m.area_faces[(n<-0.9)&(zc<zmin+0.2)].sum())
    return base/(m.extents[0]*m.extents[1])

print("\n  PHYSICAL CHECKS")
fails=[]
def chk(l,c,d):
    print(f"    [{'PASS' if c else 'FAIL'}] {l:32s} {d}")
    if not c: fails.append(l)

d0=parts["drawer"]
Y_CLOSED=0.0           # FLUSH. The drawer front now lands level with the case
y_closed=Y_CLOSED      # face; the rack grew with the drawer to keep the mesh
# assembly pose: drawer floor on the deck, rack flipped blade-down through it
# the case is three parts now; assemble them for the interference sweep
_lo=parts["case_lower"].copy()
_dk=parts["deck"].copy();  _dk.apply_translation([WL+0.3,WL+0.3,DECK-P["deck_t"]])
_up=parts["case_upper"].copy(); _up.apply_translation([0,0,DECK])
CASE_ASM=trimesh.util.concatenate([_lo,_dk,_up])

# the drawer IS the rack now - the sweep below is drawer-only
worst,wy,wslot=0.0,None,None
for slot,dx in enumerate(DR_X):
    for pull in (0,8,16,TRAVEL):
        d=d0.copy(); d.apply_translation([dx, y_closed-pull, DECK+0.2])
        h=trimesh.boolean.intersection([d, CASE_ASM], engine="manifold")
        v=float(h.volume)
        if v>worst:
            worst,wy,wslot=v,pull,slot
            wb=h.bounds
_loc = ""
if worst >= 1.0:
    _loc = (f"  @ x {wb[0][0]:.1f}..{wb[1][0]:.1f}"
            f"  y {wb[0][1]:.1f}..{wb[1][1]:.1f}"
            f"  z {wb[0][2]:.1f}..{wb[1][2]:.1f}")
chk("neither drawer fouls the case",worst<1.0,
    f"worst {worst:.2f} mm3" + (f" (slot {wslot}, pull {wy:.1f}){_loc}" if wy is not None else " across both slots, full stroke"))

# the teeth live in the drawer floor from RACK_Y0 to RACK_Y0+RACK_L; the
# pinion's contact point is fixed at PIN_Y and the teeth slide over it
c0=(WL+PIN_Y)-(y_closed+RACK_Y0)
c1=c0+TRAVEL*153/180
mgn=1.5*M+1.5
chk("pinion under the teeth, closed",mgn<c0<RACK_L-mgn,f"{c0:.1f} of 0..{RACK_L:.1f}")
chk("pinion under the teeth, open",  mgn<c1<RACK_L-mgn,f"{c1:.1f} of 0..{RACK_L:.1f}")
chk("pinion reaches the tooth zone", abs((AXIS_Z+R_TIP)-(DR_UND+TOOTH_H-0.56)) < 1.0,
    f"tip {AXIS_Z+R_TIP:.2f} into teeth {DR_UND:.2f}..{DR_UND+TOOTH_H:.2f}")
chk("lying servo clears the deck", AXIS_Z+P["sg_w"]/2 <= DECK-P["deck_t"]-0.199,
    f"body top {AXIS_Z+P['sg_w']/2:.2f}, deck underside {DECK-P['deck_t']:.2f}")
chk("drawer still supported by the deck",DR_D-TRAVEL>=20.0,
    f"{DR_D-TRAVEL:.1f} of {DR_D:.1f} mm still on the deck")
_reach = BIN_BACK - P["dr_front"]
_binlen = BIN_BACK - P["dr_front"]
chk("every part of the bin clears the case", _reach >= _binlen - 0.01,
    f"{_reach:.1f} mm reachable of {_binlen:.1f} mm bin (100%)")
chk("servo shim sets the servo height",
    abs((parts["servo_shim"].extents[2] + P["floor_t"]) - SG_BASE) < 1e-6,
    f"shim {parts['servo_shim'].extents[2]:.2f} + floor {P['floor_t']:.2f} = {SG_BASE:.2f}")
chk("cradle walls never touch the ears first",
    (SG_BASE + P["sg_ear"] - 1.9) < SG_BASE + P["sg_ear"] - 1.0,
    f"wall top {SG_BASE+P['sg_ear']-1.9:.2f}, lowest plausible ear {SG_BASE+P['sg_ear']-1.0:.2f}")
chk("servo fits under the deck",P["sg_h"]+SG_BASE<=P["deck_z"],f"{P['sg_h']+SG_BASE:.1f} of {P['deck_z']:.1f}")
chk("ESP+breadboard clears the deck",
    P["floor_t"]+P["esp_h"] <= P["deck_z"]-1.0,
    f"stack top {P['floor_t']+P['esp_h']:.1f}, deck underside {P['deck_z']:.1f}")
# ── the Z stack-up that nothing used to check ──
# The pinion's height is set by the servo, the rack's by the drawer, and the
# two have to overlap over the gear's full face. Neither was ever computed:
# preflight hard-coded the pinion height and "passed" on 4.4 mm of a 5.0 face.
chk("servo body clears the electronics",
    AXIS_Z - P["sg_w"]/2 >= P["floor_t"] + 8.0,
    f"body bottom {AXIS_Z-P['sg_w']/2:.1f} - breadboard must sit clear or aside")
# involute sanity: a tip thinner than one extrusion is a tip the machine rounds
_tip = 2*tooth_half_angle(R_TIP)*R_TIP
chk("pinion tooth tip is printable", _tip >= 0.60, f"{_tip:.3f} mm at the tip")
# lying servos: bodies run along X from each pinion, ears along Y
_ear_y0 = WL + PIN_Y - 5.9 - (P["sg_tab"]-P["sg_l"])/2
_ear_y1 = WL + PIN_Y + P["sg_l"] - 5.9 + (P["sg_tab"]-P["sg_l"])/2
_bod = []
for _s, _dx in enumerate(DR_X):
    _px = _dx + FIN_X + P["fin_t"]/2 + 1.0
    _x0 = _px + SG_DIR[_s]*(P["gear_t"]/2 + 1.6)
    _x1 = _x0 + SG_DIR[_s]*P["sg_h"]
    _bod.append((min(_x0,_x1), max(_x0,_x1)))
chk("the two servos do not clash", _bod[1][0] >= _bod[0][1] or _bod[0][0] >= _bod[1][1],
    f"A {_bod[0][0]:.1f}..{_bod[0][1]:.1f}  B {_bod[1][0]:.1f}..{_bod[1][1]:.1f}")
chk("servo bodies stay inside the case",
    all(b0 >= WL and b1 <= CW-WL for b0,b1 in _bod),
    f"A {_bod[0][0]:.1f}..{_bod[0][1]:.1f}  B {_bod[1][0]:.1f}..{_bod[1][1]:.1f} in {WL:.0f}..{CW-WL:.0f}")
chk("servo ears stay inside the case",
    _ear_y0 >= WL - 0.01 and _ear_y1 <= CD - WL,
    f"ears y {_ear_y0:.1f}..{_ear_y1:.1f} in {WL:.0f}..{CD-WL:.0f}")
chk("shaft offset is modelled, not assumed centred", P["sg_shaft"] != P["sg_l"]/2,
    f"shaft {P['sg_shaft']:.1f} from the near end of a {P['sg_l']:.1f} body")
chk("drawer clears the case top",DR_TOP+P["gap"]<=CH-WL-2,f"{DR_TOP:.1f} of {CH-WL-2:.1f}")
# ── how far can an extended drawer droop? ──
_ceil   = CH - WL                      # bay ceiling, assembly Z
_ribtop = DECK + 0.2 + P["dr_h"] + ANTITIP
_rise   = _ceil - _ribtop              # how far the rear corner can lift
_ondeck = DR_D - TRAVEL                # still supported at full travel
_droop  = TRAVEL * _rise/_ondeck
chk("anti-tip rib steps around the OLED posts",
    all(not (a0 < b1 and b0 < a1) for a0,a1 in rib_segments() for b0,b1 in post_bands()),
    f"{len(rib_segments())} segments: " +
    ", ".join(f"{a:.1f}-{b:.1f}" for a,b in rib_segments()))
chk("anti-tip rib clears the bay ceiling", _rise >= 0.4,
    f"{_rise:.2f} mm (rib top {_ribtop:.1f}, ceiling {_ceil:.1f})")
chk("extended drawer cannot droop out of mesh", _droop <= 2.0,
    f"{_droop:.2f} mm nose drop at full travel, was 5.14 without the rib")
chk("all watertight",all(m.is_watertight for m in parts.values()),"")
for n,m in parts.items():
    nb=len(m.split(only_watertight=False))
    chk(f"{n} is one solid piece",nb==1,
        f"{nb} bodies" + ("" if nb==1 else "  <-- something is detached"))
def neck(m, name="", lo=0.15, hi=2.0, step=0.05):
    """Narrowest neck in the FIRST LAYERS, measured by erosion.

    Watertight and single-body both PASS on a part hanging together by 0.6 mm -
    that is exactly how the deck shipped with its whole left bearing finger on
    a 0.60 mm thread. Erode the first-layer footprint until it falls apart;
    twice that erosion is the neck.

    This is deliberately a BED test, not a whole-part test. What it is looking
    for is the part that breaks when you lever it off the plate, and it has to
    be measured in the print pose - so parts printed upside down get flipped
    first, or the test reads a face that never touches the bed."""
    if name in FLIP:
        m = m.copy()
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi,[1,0,0]))
    sec = m.section(plane_origin=[0,0,m.bounds[0][2]+0.25], plane_normal=[0,0,1])
    if sec is None:
        return hi, None
    try:
        g = unary_union(list(sec.to_planar()[0].polygons_full))
    except Exception:
        return hi, None
    e = lo
    while e <= hi:
        b = g.buffer(-e)
        # Fragments under 2 mm2 are shapely noise, not geometry - eroding the
        # 1011-vertex logo outline throws off 0.001 mm2 specks that appear at
        # 0.10, vanish at 0.30 and come back at 0.65. A real neck, once parted,
        # stays parted. Only count pieces big enough to be a piece.
        qs = [q for q in (list(b.geoms) if hasattr(b, "geoms") else
                          ([] if b.is_empty else [b])) if q.area >= 2.0]
        if len(qs) != 1:
            sm = min(qs, key=lambda q: q.area) if qs else None
            return 2*e, (tuple(round(v,1) for v in sm.bounds) if sm is not None else None)
        e += step
    return hi, None

for n,m in parts.items():
    w,where=neck(m,n)
    # 3 perimeters at 0.42 is 1.26; anything under that is a snap waiting to
    # happen, and it snaps on bed removal rather than in service
    chk(f"{n} has no thin neck", w >= 1.3,
        f"narrowest {w:.2f} mm" + ("" if w >= 1.3 else f"  <-- parts at {where}"))
for n,m in parts.items():
    r=bed_ratio(m,n)
    # a part shorter than its own footprint cannot topple however it is pocketed,
    # so the ratio only has to hold for tall parts
    squat=m.extents[2] <= min(m.extents[0],m.extents[1])
    chk(f"{n} sits on the bed",r>=0.25 or squat,
        f"{r*100:.0f}% bed contact" + (" (squat, stable)" if squat else ""))

tot=(parts["case_lower"].volume + parts["deck"].volume
     + parts["case_upper"].volume + 2*parts["drawer"].volume
     + 2*parts["pinion"].volume
     + (2*parts["knob"].volume if P["pull"]=="knob" else 0))/1000*1.27
print(f"\n  {tot:.0f} g solid  (~{tot*0.85:.0f} g sliced)   vs MINI 187 g, cabinet 1365 g")
if fails:
    print("  *** "+", ".join(fails)); sys.exit(1)
print("  ALL CHECKS PASSED")

PL=os.path.join(OUT,"plates"); os.makedirs(PL,exist_ok=True)
for f in glob.glob(os.path.join(PL,"*.3mf")): os.remove(f)

def land(m):
    m=m.copy(); m.apply_translation(-m.bounds[0])
    if m.extents[1]>m.extents[0]:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[0,0,1]))
        m.apply_translation(-m.bounds[0])
    return m

def print_pose(nm):
    mm=parts[nm].copy()
    if nm in FLIP:
        mm.apply_transform(trimesh.transformations.rotation_matrix(math.pi,[1,0,0]))
    return land(mm)

BED=256.0
# ONE COLOUR PER PLATE. A single-nozzle machine changing colour mid-plate
# purges a tower for every swap; splitting the plates costs nothing and wastes
# nothing. Swap the spool between the two prints.
# A test plate before the real one. Three questions it answers that no script
# in this repo can: does the spline bore actually grip, do the printed teeth
# actually drive, and does the machine hold the tooth profile at this size.
# 16 g and twenty minutes against a 66 g plate.
PLATES=[        ("1_case",  "#F2F2F2FF", [("case_lower",1),("case_upper",1)]),
        ("2_mechanism", "#F2B705FF", [("deck",1),("drawer",2),
                                   ("pinion",2),("servo_shim",2),
                                   ("spline_gauge",1),("logo_inlay",1)] +
                                  ([("knob",2)] if P["pull"]=="knob" else []))]

def pack(items):
    placed,x,y,row=[],6.0,6.0,0.0
    for nm,q in items:
        mm=print_pose(nm)
        for k in range(q):
            if x+mm.extents[0]>BED-6: x=6.0; y+=row+6.0; row=0.0
            placed.append((nm if q==1 else f"{nm}_{chr(65+k)}",mm,x,y))
            x+=mm.extents[0]+5; row=max(row,mm.extents[1])
    return placed,max(px+m.extents[0] for _,m,px,_ in placed),y+row+6

total=0.0
for lab,col,items in PLATES:
    placed,w,h=pack(items)
    assert w<=BED and h<=BED, f"plate {lab} is {w:.0f}x{h:.0f}, bed is {BED:.0f}"
    g=sum(m.volume/1000*1.27 for _,m,_,_ in placed); total+=g
    path=os.path.join(PL,f"plate_{lab}.3mf")
    # NO basematerials group. Declaring one makes Bambu treat the file as
    # multi-material and refuse to slice until filaments are mapped - and on a
    # single-nozzle machine there is nothing to map. The colour comes from
    # whichever spool is loaded, not from the file.
    write_3mf(path,[(n,m,px,py) for n,m,px,py in placed])
    o,b=verify(path)
    # Also emit a plain STL per plate. An STL carries no filament, extruder or
    # material data of any kind, so Bambu cannot ask for a mapping - it just
    # slices with whatever filament the profile already has loaded.
    merged=trimesh.util.concatenate(
        [T(m.copy(),px,py,0) for _,m,px,py in placed])
    merged.export(os.path.join(PL,f"plate_{lab}.stl"))
    print(f"\n  plate_{lab:9s} {w:5.0f} x {h:3.0f} mm   {g:5.1f} g   "
          f"{len(placed)} objects  ok={o==b}")
    for n,m,_,_ in placed: print(f"      {n}")
# combined view: everything on one plate, colour-coded, for looking at the
# whole product in one file. Print from the two single-colour plates above -
# this one would cost a filament change.
ALL=[("case_lower",1,0),("case_upper",1,0),("deck",1,1),("drawer",2,1),
     ("pinion",2,1)]
placed,x,y,row=[],6.0,6.0,0.0
for nm,q,ci in ALL:
    mm=print_pose(nm)
    for k in range(q):
        if x+mm.extents[0]>BED-6: x=6.0; y+=row+6.0; row=0.0
        placed.append((nm if q==1 else f"{nm}_{chr(65+k)}",mm,x,y,ci))
        x+=mm.extents[0]+5; row=max(row,mm.extents[1])
aw=max(px+m.extents[0] for _,m,px,_,_ in placed)
ah=max(py+m.extents[1] for _,m,_,py,_ in placed)
assert aw<=BED and ah<=BED, f"combined plate {aw:.0f}x{ah:.0f} exceeds bed"
# Two separate single-colour files. A multi-plate 3MF was tried and Bambu did
# not bin the objects into separate plates - they all landed in one scene and
# overlapped. Open one file, slice, swap the spool, open the other.
# ── ONE PLATE, everything on it ──
# Case parts on the left, the yellow interiors on the right, the white logo
# inlay tucked in beside them. Three colours means two swaps if you print it
# as one job - or hide what you are not running and do it in passes.
ALL = [("case_lower",1), ("case_upper",1), ("logo_inlay",1),
       ("deck",1), ("drawer",2), ("pinion",2), ("servo_shim",2)]
placed, x, y, row = [], 6.0, 6.0, 0.0
for nm, q in ALL:
    mm = print_pose(nm)
    for k in range(q):
        if x + mm.extents[0] > BED - 6:
            x = 6.0; y += row + 6.0; row = 0.0
        placed.append((nm if q == 1 else f"{nm}_{chr(65+k)}", mm, x, y))
        x += mm.extents[0] + 5; row = max(row, mm.extents[1])
aw = max(px + m.extents[0] for _, m, px, _ in placed)
ah = max(py + m.extents[1] for _, m, _, py in placed)
assert aw <= BED and ah <= BED, f"one-plate layout {aw:.0f}x{ah:.0f} exceeds the bed"
pall = os.path.join(PL, "plate_ALL.3mf")
# Colour the viewing copy: both case halves WHITE, everything else yellow.
# This DOES make Bambu ask for a filament mapping - it is a viewing file, and
# the two single-colour plates stay clean for actually printing.
WHITE_PARTS = {"case_lower", "case_upper"}
write_3mf(pall,
          [(n, m, px, py, 0 if n in WHITE_PARTS else 1) for n, m, px, py in placed],
          materials=[("white", "#F4F4F4FF"), ("yellow", "#F2B705FF")])
merged = trimesh.util.concatenate([T(m.copy(), px, py, 0) for _, m, px, py in placed])
merged.export(os.path.join(PL, "plate_ALL.stl"))
gall = sum(m.volume/1000*1.24 for _, m, _, _ in placed)
print(f"\n  plate_ALL          {aw:5.0f} x {ah:3.0f} mm   {gall:5.1f} g   "
      f"{len(placed)} objects  (everything, one plate)")
for nm, m, px, py in placed:
    print(f"      {nm:14s} at ({px:5.1f},{py:5.1f})")

print(f"\n  2 print plates, {total:.0f} g solid (~{total*0.85:.0f} g sliced), "
      f"ZERO filament changes")
print(f"  {os.path.normpath(PL)}")
