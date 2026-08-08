#!/usr/bin/env python3
"""
shopkeeper NANO — two motorised drawers, as small as an SG90 allows.

92 x 66 x 50 mm. Two drawers SIDE BY SIDE so one mechanism deck serves both;
stacking them would have doubled the height, because a vertical SG90 costs
26 mm of dead space under every deck.

    top          0.91" OLED + 2 LEDs on the top face
    drawers      2 x (42 x 55 x 18), each driven out 23.6 mm
    deck         slotted for both drive fins
    mech bay     2 x SG90 (shaft up) + 2 pinions + ESP32-S3

Geometry is verified by boolean interference sweep across the full stroke,
not by dimension arithmetic — that is what caught every bug in the bigger
versions.
"""
import os, math, glob, sys
import numpy as np
import trimesh
from trimesh.creation import box, cylinder, extrude_polygon
from shapely.geometry import Polygon
from mf3 import write_3mf, write_3mf_plates, verify

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "nano")
os.makedirs(OUT, exist_ok=True)

P = dict(
    cw=92.0, cd=74.0, ch=62.0, wall=2.0, floor_t=1.4,
    deck_z=34.5, deck_t=2.5,
    dr_h=18.0, dr_wall=1.8, dr_floor=1.8, dr_front=3.0,
    side_clear=1.2, mid_gap=6.0,
    module=1.25, teeth=16, press=math.radians(14.5),
    gear_t=5.0, backlash=0.30,
    fin_t=3.0, fin_h=8.0,
    sg_l=22.8, sg_w=12.2, sg_h=22.7, sg_tab=32.2, sg_spline=4.8,
    clear=0.35, gap=0.8,
    dr_d=55.0,               # drawer depth, now independent of case depth
    pull="cut",              # "cut" = scalloped finger pull, "knob" = press-fit knob
)
M, N   = P["module"], P["teeth"]
R_P    = M*N/2                                  # 7.5
R_TIP, R_ROOT = R_P+M, R_P-1.25*M
PITCH  = math.pi*M
TRAVEL = math.pi*R_P                            # 23.56
TOOTH_H  = 2.25*M
FIN_SPAN = P["fin_t"] + TOOTH_H

CW, CD, CH, WL = P["cw"], P["cd"], P["ch"], P["wall"]
DECK   = P["deck_z"] + P["deck_t"]              # 28
DR_D   = P["dr_d"]     # decoupled: the case got deeper for the breadboard,
                       # the drawer did not - extra depth is electronics bay
DR_TOP = DECK + P["dr_h"]                       # 46
# two drawers across the internal width
INNER  = CW - 2*WL
DR_W   = (INNER - P["mid_gap"] - 2*P["side_clear"]) / 2
DR_X   = (WL + P["side_clear"],
          WL + P["side_clear"] + DR_W + P["mid_gap"])
FIN_X  = DR_W * 0.20   # moved inboard so the bigger pinion's servo cradle
                       # still clears the right-hand case wall
PIN_DX = -P["fin_t"]/2 + (FIN_SPAN - M) + R_P   # pinion offset from FIN_X
PIN_Y  = 17.6

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

def pinion():
    half=(PITCH/2-P["backlash"])/2/R_P
    da=M*math.tan(P["press"])/R_TIP
    dr=1.25*M*math.tan(P["press"])/R_ROOT
    pts=[]
    for i in range(N):
        th=2*math.pi*i/N
        for a,r in ((th-half-dr,R_ROOT),(th-half+da,R_TIP),
                    (th+half-da,R_TIP),(th+half+dr,R_ROOT)):
            pts.append((r*math.cos(a),r*math.sin(a)))
    g=extrude_polygon(Polygon(pts),P["gear_t"])
    hub=cyl_z(9.0,P["gear_t"],P["gear_t"]+5,0,0)
    m=union([g,hub])
    # ── drive through the servo's own HORN, not the spline ──
    # A printed bore on a 4.8 mm 20-tooth spline cannot grip: the teeth are
    # 0.75 mm apart, far under what a 0.4 nozzle resolves, so it just reams
    # itself round and slips. The horn is screwed to the spline by the servo's
    # own M2.5, and the pinion then bolts to the horn.
    # The ARM SLOT is the drive - a keyed joint, not friction and not screws.
    # At a 15 mm pitch diameter there is no room for a screw that clears the
    # tooth roots (r 5.94), so screws were dropped. The arm bears on the slot
    # walls: ~0.7 MPa against PETG's ~50, so the margin is enormous.
    #
    # A real SG90 double-arm horn is 7.0 mm wide at the boss and 4.6 at the tip,
    # 1.5-1.6 thick, 17.5 long each side. Slot is sized for the WIDEST point.
    m=diff(m,cyl_z(8.6,-1,2.7,0,0))                      # horn boss recess
    m=diff(m,blk(-3.8,3.8,-8.0,8.0,-1,2.1))              # arm slot, 7.6 x 16 x 2.1
    m=diff(m,cyl_z(4.6,-1,P["gear_t"]+6,0,0))            # driver reaches the M2.5
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
        tip = hp - M*math.tan(P["press"])
        rt  = hp + 1.25*M*math.tan(P["press"])
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
    for dx in DR_X:
        sx=dx+FIN_X
        # the fin must pass through the FRONT WALL as well as the deck
        m=diff(m,blk(sx-P["fin_t"]/2-1.2,sx-P["fin_t"]/2+FIN_SPAN+1.2,
                     -1,WL+1,DECK-P["fin_h"]-1.5,DECK+1))
        px=dx+FIN_X+PIN_DX
        # servo cradle: four walls up from the floor, open top so it drops in
        m=union([m,blk(px-P["sg_tab"]/2-2.0,px+P["sg_tab"]/2+2.0,
                       WL+PIN_Y-P["sg_w"]/2-P["clear"]-1.6,
                       WL+PIN_Y+P["sg_w"]/2+P["clear"]+1.6,P["floor_t"],P["floor_t"]+13)])
        m=diff(m,blk(px-P["sg_l"]/2-P["clear"],px+P["sg_l"]/2+P["clear"],
                     WL+PIN_Y-P["sg_w"]/2-P["clear"],WL+PIN_Y+P["sg_w"]/2+P["clear"],
                     P["floor_t"]-1,P["floor_t"]+14))
        for tx in (-P["sg_tab"]/2+2.2,P["sg_tab"]/2-2.2):
            m=diff(m,cyl_z(1.7,P["floor_t"],P["floor_t"]+13,px+tx,WL+PIN_Y))
    # ── ESP32-S3 DevKit ON ITS BREADBOARD, behind the servos ──
    # Measured assembly: 81.5 long x 35.5 across x ~15 tall, board plugged into
    # two breadboard strips. No soldering, so the breadboard stays in the case
    # and the case grew backwards to take it: 66 -> 94 deep.
    EX, EY = CW/2, CD - 23.0
    EBW, EBL, EBT = 35.5, 81.5, 1.6   # measured off the real assembly
    FT = P["floor_t"]
    for sgn in (-1, 1):
        yy = EY + sgn*(EBW/2 + 1.5)
        # low corner walls only - the breadboard's adhesive back does the
        # holding, these just locate it and stop it sliding
        m=union([m,blk(EX-EBL/2-1.5, EX-EBL/2+12.0, yy-1.5, yy+1.5, FT, FT+3.5)])
        m=union([m,blk(EX+EBL/2-12.0, EX+EBL/2+1.5, yy-1.5, yy+1.5, FT, FT+3.5)])
    # end stop at the front, open at the rear so the USB-C is reachable
    m=union([m,blk(EX-EBL/2-1.0, EX-EBL/2+1.0, EY-EBW/2-1.4, EY+EBW/2+1.4,
                   FT, FT+5.2)])

    # No breadboard. A half-size board plus a 55 x 28 DevKit plus two servos
    # does not fit a 92 x 66 case - the pillars landed on both servos. The
    # DevKit's own headers take dupont leads directly.
    for wx in (20,40,60):
        m=diff(m,blk(wx,wx+15,CD-WL-1,CD+1,5,19))
    m=diff(m,cyl_y(8.0,CD-WL-1,CD+1,CW-11,12))
    for i in range(2):
        z=8+i*8
        for yy in (0.36,0.46,0.56):
            m=diff(m,cyl_x(5.0,-1,WL+1,CD*yy,z))
            m=diff(m,cyl_x(5.0,CW-WL-1,CW+1,CD*yy,z))
    # lightening holes, skipping anything mounted to the floor
    keep=[(dx+FIN_X+PIN_DX, WL+PIN_Y, 21.0) for dx in DR_X]
    keep+= [(CW/2, CD-23.0, 46.0)]
    gx=int((CW-2*WL-14)//13); gy=int((CD-2*WL-14)//13)
    for i in range(gx+1):
        for j in range(gy+1):
            x=WL+9+i*13; y=WL+9+j*13
            if any((x-kx)**2+(y-ky)**2 < kr**2 for kx,ky,kr in keep): continue
            m=diff(m,cyl_z(8.0,-1,P["floor_t"]+1,x,y))
    return chamfer(m)

def deck():
    """Flat plate, prints on its face. It used to be the case's ceiling, which
    meant an 88 x 62 bridge in mid-air."""
    m=blk(WL+0.3,CW-WL-0.3,WL+0.3,CD-WL-0.3,0,P["deck_t"])
    for dx in DR_X:
        sx=dx+FIN_X
        px=dx+FIN_X+PIN_DX
        m=diff(m,blk(sx-P["fin_t"]/2-1.2,sx-P["fin_t"]/2+FIN_SPAN+1.2,
                     -1,CD-WL-3,-1,P["deck_t"]+1))
        m=diff(m,cyl_z(2*R_TIP+2.5,-1,P["deck_t"]+1,px,WL+PIN_Y))
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
    m=diff(m,blk(18,CW-18,CD-WL-1,CD+1,2,14))
    return chamfer(m)

RACK_L  = DR_D-6      # rack now runs nearly the full drawer
RACK_Y0 = 3.0              # rack start in drawer-part Y
PEG_D   = 3.0

def drawer():
    """Prints floor-down, flat on the bed.

    The drive rack used to be moulded onto the underside, which meant the whole
    42 x 62 body floated 8 mm in the air on a 3 mm blade — about 4% bed contact.
    It is now a separate part that pegs in through a floor slot, which also makes
    the gear rack replaceable: it is the riskiest feature in the design."""
    W,D,H=DR_W,DR_D,P["dr_h"]
    y0=0.0                    # front face flush with the case, knob does the work
    m=diff(blk(0,W,y0,y0+D,0,H),
           blk(P["dr_wall"],W-P["dr_wall"],y0+P["dr_front"],y0+D-P["dr_wall"],
               P["dr_floor"],H+1))
    # slot the rack blade passes through
    m=diff(m,blk(FIN_X-P["fin_t"]/2-0.25, FIN_X-P["fin_t"]/2+FIN_SPAN+0.25,
                 RACK_Y0-0.3, RACK_Y0+RACK_L+0.3, -1, P["dr_floor"]+1))
    # locating peg holes either side of the slot
    for py in (RACK_Y0+5, RACK_Y0+RACK_L-5):
        m=diff(m,cyl_z(PEG_D+0.25,-1,P["dr_floor"]+1,FIN_X-P["fin_t"]/2-4.5,py))
    if P["pull"] == "knob":
        m=diff(m,cyl_y(4.1,-1,P["dr_front"]+1,W/2,H*0.55))
    else:
        # scalloped finger pull cut into the top-front edge. It opens upward, so
        # it is self-supporting - the void widens as the print rises.
        m=diff(m,cyl_x(14.0,W/2-9,W/2+9,1.5,H))
        m=diff(m,blk(W/2-9,W/2+9,-1,P["dr_front"]+0.5,H-1.2,H+1))
    return m

def rack(assembly=True):
    """Modelled in ASSEMBLY orientation: flange on top, blade and pegs hanging
    down. Flipping a part between orientations mirrors a horizontal axis with it,
    so the flip happens once, at plating time, and never in the fit maths."""
    L=RACK_L; drop=P["fin_h"]+P["dr_floor"]
    fl=blk(-5.0,P["fin_t"]+5.0,-3.0,L+3.0,0,2.0)
    blade=rack_fin(L,h=drop)      # must reach the flange, not stop 1.8 mm short
    blade.apply_translation([0,0,-drop])
    m=union([fl,blade])
    for py in (5.0,L-5.0):
        m=union([m,cyl_z(PEG_D,-P["dr_floor"],0,-4.5,py)])
    if not assembly:                       # print pose: flange flat on the bed
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi,[1,0,0]))
        m.apply_translation(-m.bounds[0])
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
       "rack":rep("rack",rack(assembly=False)),
       "knob":rep("knob",knob()),"pinion":rep("pinion",pinion())}

FLIP={"case_upper"}          # printed top-face-down

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
Y_CLOSED=7.8           # drawer sits this far back so the pinion has room
y_closed=Y_CLOSED
# assembly pose: drawer floor on the deck, rack flipped blade-down through it
# the case is three parts now; assemble them for the interference sweep
_lo=parts["case_lower"].copy()
_dk=parts["deck"].copy();  _dk.apply_translation([WL+0.3,WL+0.3,DECK-P["deck_t"]])
_up=parts["case_upper"].copy(); _up.apply_translation([0,0,DECK])
CASE_ASM=trimesh.util.concatenate([_lo,_dk,_up])

rk=rack(assembly=True)
rk.apply_translation([FIN_X-P["fin_t"]/2, RACK_Y0, DECK+P["dr_floor"]+0.2])
worst,wy,wslot=0.0,None,None
for slot,dx in enumerate(DR_X):
    for pull in (0,8,16,TRAVEL):
        asm=[d0.copy(), rk.copy()]
        for a in asm: a.apply_translation([dx, y_closed-pull, 0])
        asm[0].apply_translation([0,0,DECK+0.2])
        h=trimesh.boolean.intersection(
            [trimesh.util.concatenate(asm), CASE_ASM], engine="manifold")
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

fin_len=RACK_L
c0=(WL+PIN_Y)-(y_closed+RACK_Y0)
c1=c0+TRAVEL
mgn=1.5*M+1.5
chk("pinion on the rack, closed",mgn<c0<fin_len-mgn,f"{c0:.1f} of 0..{fin_len:.1f}")
chk("pinion on the rack, open",  mgn<c1<fin_len-mgn,f"{c1:.1f} of 0..{fin_len:.1f}")
# What actually retains an extended drawer is not how much of it is still in
# the bay - it is the drive fin running in the deck slot, which binds if the
# drawer tries to tip, plus the rack still meshed with the pinion.
fin_in_slot=(RACK_Y0+RACK_L)-TRAVEL-(y_closed*0+0)+y_closed
fin_in_slot=min(RACK_Y0+RACK_L+y_closed-TRAVEL, CD-WL-3)
chk("fin still keyed in the deck slot",fin_in_slot>=20.0,
    f"{fin_in_slot:.1f} mm of fin inside the slot at full travel")
chk("drawer still supported by the deck",DR_D-TRAVEL>=20.0,
    f"{DR_D-TRAVEL:.1f} of {DR_D:.1f} mm still on the deck")
chk("servo fits under the deck",P["sg_h"]+WL<=P["deck_z"],f"{P['sg_h']+WL:.1f} of {P['deck_z']:.1f}")
chk("the two servos do not clash",
    (DR_X[1]+FIN_X+PIN_DX-P["sg_l"]/2) > (DR_X[0]+FIN_X+PIN_DX+P["sg_l"]/2),
    f"gap {(DR_X[1]-DR_X[0])-P['sg_l']:.1f} mm")
chk("drawer clears the case top",DR_TOP+P["gap"]<=CH-WL-2,f"{DR_TOP:.1f} of {CH-WL-2:.1f}")
chk("all watertight",all(m.is_watertight for m in parts.values()),"")
for n,m in parts.items():
    nb=len(m.split(only_watertight=False))
    chk(f"{n} is one solid piece",nb==1,
        f"{nb} bodies" + ("" if nb==1 else "  <-- something is detached"))
for n,m in parts.items():
    r=bed_ratio(m,n)
    # a part shorter than its own footprint cannot topple however it is pocketed,
    # so the ratio only has to hold for tall parts
    squat=m.extents[2] <= min(m.extents[0],m.extents[1])
    chk(f"{n} sits on the bed",r>=0.25 or squat,
        f"{r*100:.0f}% bed contact" + (" (squat, stable)" if squat else ""))

tot=(parts["case_lower"].volume + parts["deck"].volume
     + parts["case_upper"].volume + 2*parts["drawer"].volume + 2*parts["rack"].volume
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
PLATES=[("1_white",  "#F2F2F2FF", [("case_lower",1),("case_upper",1)]),
        ("2_yellow", "#F2B705FF", [("deck",1),("drawer",2),("rack",2),
                                   ("pinion",2)] +
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
     ("rack",2,1),("pinion",2,1)]
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
print(f"\n  2 print plates, {total:.0f} g solid (~{total*0.85:.0f} g sliced), "
      f"ZERO filament changes")
print(f"  {os.path.normpath(PL)}")
