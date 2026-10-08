#!/usr/bin/env python3.12
"""Generate the rev A schematic and board for the FC adapter / power board.

This writes fc-adapter.kicad_sch and fc-adapter.kicad_pcb from the parts and
placement tables below. It is meant to bootstrap the board; once the board is being
edited by hand in KiCad, edit the KiCad files directly instead of re-running
this (it overwrites both files).

    python3 scripts/generate.py            # schematic + placed board + zones
    python3 scripts/route.py               # only if signal nets are added that build_board doesn't route

Coordinates are millimetres relative to the board centre. +Y points to the
REAR of the aircraft (KiCad's Y axis points down the page), so the front edge
is at the top of the board drawing.
"""
import math
import os
import uuid

import pcbnew
from kiutils.items.common import Effects, Font, Position, Property, PageSettings, TitleBlock
from kiutils.items.schitems import (LocalLabel, NoConnect, SchematicSymbol, SymbolInstance,
                                    HierarchicalSheetInstance, Text)
from kiutils.schematic import Schematic
from kiutils.symbol import SymbolLib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
NAME = "fc-adapter"
SCH_PATH = os.path.join(PROJ, NAME + ".kicad_sch")
PCB_PATH = os.path.join(PROJ, NAME + ".kicad_pcb")
SYSLIB = "/usr/share/kicad"

# ---------------------------------------------------------------------------
# Mechanical parameters
# ---------------------------------------------------------------------------
# Frame standoff pattern, centre to centre (measured by the user 2026-10-08).
FRAME_X = 44.0          # side to side
FRAME_Y = 44.0          # front to back
FRAME_HOLE = 3.2        # M3 clearance
BOARD_W = 94.0
BOARD_H = 94.0
CORNER_R = 4.0
FC_PITCH = 30.5         # Lumenier LUX F765 NDAA mounting pattern (M3)
FC_SIZE = 38.0          # LUX F765 board outline
FC_ZONE = 54.0          # keep-low square under the FC
ORIGIN = (150.0, 100.0)  # where board centre lands on the KiCad page

# ---------------------------------------------------------------------------
# Parts. pins maps pin number -> net name (None = no connect).
# pos/rot are board placement (mm, deg). sch is the schematic position.
# ---------------------------------------------------------------------------
GEN = "Connector_Generic"
PARTS = []


def part(ref, lib, sym, value, fp, pins, pos, rot=0, sch=None, label=None, dnp=False):
    PARTS.append(dict(ref=ref, lib=lib, sym=sym, value=value, fp=fp, pins=pins,
                      pos=pos, rot=rot, sch=sch, label=label, dnp=dnp))


# Battery input. The battery plugs into a Holybro PM02 power module (current
# and voltage sense for the FC) and the PM02's output plugs into J1, which
# feeds the ESC bus directly.
part("J1", GEN, "Conn_01x02", "XT60 male (from PM02)",
     "Connector_AMASS:AMASS_XT60PW-M_1x02_P7.20mm_Horizontal",
     {"1": "GND_ESC", "2": "VBAT_ESC"}, (3.6, 29.5), 180, sch=(40.64, 50.8))

# Battery lead up to the FC's VBAT pads (the LUX regulates its own 5V).
part("P1", "fc-adapter", "WirePad", "FC VBAT+", "fc-adapter:WirePad_14AWG",
     {"1": "VBAT_ESC"}, (-12.0, 31.0), sch=(76.2, 45.72))
part("P2", "fc-adapter", "WirePad", "FC VBAT-", "fc-adapter:WirePad_14AWG",
     {"1": "GND_ESC"}, (12.0, 31.0), sch=(76.2, 55.88))

part("C1", "Device", "C_Polarized", "1000uF 35V",
     "Capacitor_THT:CP_Radial_D12.5mm_P5.00mm",
     {"1": "VBAT_ESC", "2": "GND_ESC"}, (37.5, 2.5), 90, sch=(76.2, 101.6))
part("C2", "Device", "C_Polarized", "1000uF 35V",
     "Capacitor_THT:CP_Radial_D12.5mm_P5.00mm",
     {"1": "VBAT_ESC", "2": "GND_ESC"}, (-37.5, 2.5), 90, sch=(99.06, 101.6))

# ESC power pads. ArduPilot Quad X: M1 front-right, M2 rear-left,
# M3 front-left, M4 rear-right.
ESC_PADS = {1: (36.0, -1), 2: (-36.0, 1), 3: (-36.0, -1), 4: (36.0, 1)}  # x, front(-1)/rear(+1)
n = 7
for m in (1, 2, 3, 4):
    x, side = ESC_PADS[m]
    part("P%d" % n, "fc-adapter", "WirePad", "M%d ESC+" % m, "fc-adapter:WirePad_14AWG",
         {"1": "VBAT_ESC"}, (x, 24.0 * side), sch=(132.08, 76.2 + (m - 1) * 15.24))
    part("P%d" % (n + 1), "fc-adapter", "WirePad", "M%d ESC-" % m, "fc-adapter:WirePad_14AWG",
         {"1": "GND_ESC"}, (x, 17.0 * side), sch=(132.08, 81.28 + (m - 1) * 15.24))
    n += 2

# ESC signal header: four servo plugs side by side. The middle row (the ESC's
# BEC +5V) is left unconnected so the plugs fit as-is without back-feeding 5V.
# Like every front port, the device plugs in at the front edge and the FC
# link sits inside it, towards the FC. The header is turned 180 degrees so
# its S row faces the FC link (G row at the edge); columns are renumbered so
# S1 is still on the left.
ESC_SIG_X0 = -3.81    # x of the S1 column; centres the 4 columns on the board
ESC_SIG_Y0 = -39.42   # y of the S row (NC and G rows are in front of it)
FC_LINK_Y = -33.5     # FC pad rows of all the front ports
esc_pins = {}
for k in range(4):
    esc_pins.update({str(3 * k + 1): "S%d" % (4 - k), str(3 * k + 2): None, str(3 * k + 3): "GND"})
part("J2", GEN, "Conn_01x12", "ESC signal 3x4", "fc-adapter:ESC_Header_3x04_P2.54mm",
     esc_pins, (ESC_SIG_X0 + 7.62, ESC_SIG_Y0), 180, sch=(180.34, 50.8))

# Link to the FC: a short hand-made lead from here to the LUX's S1-S4 and G.
part("J3", GEN, "Conn_01x05", "FC link",
     "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
     {"1": "S1", "2": "S2", "3": "S3", "4": "S4", "5": "GND"},
     (ESC_SIG_X0, FC_LINK_Y), 90, sch=(180.34, 91.44),
     label=["S1", "S2", "S3", "S4", "G"])

# Plug-in ports. The LUX F765 only has solder pads, so each port gets a pad
# row for a short lead soldered once to the FC's matching pad group, and a
# JST-GH socket that the device plugs into. TX/RX are named from the FC side.
# The front ports share the ESC header's layout: socket at the front edge,
# FC pad row behind it at FC_LINK_Y.
GH = "Connector_JST:JST_GH_BM%02dB-GHS-TBT_1x%02d-1MP_P1.25mm_Vertical"
HDR = "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical"
SOCKET_Y = -43.2
PORTS = []


def port(name, sock_ref, row_ref, x, nets, labels, sch_y, socket_nets=None, socket_y=SOCKET_Y,
         row_y=FC_LINK_Y, row_x=None):
    """A JST-GH socket centred on x, with its FC pad row."""
    n = len(socket_nets or nets)
    sn = socket_nets or nets
    part(sock_ref, GEN, "Conn_01x%02d" % n, "%s GH-%d" % (name, n), GH % (n, n),
         {str(i + 1): net for i, net in enumerate(sn)}, (x, socket_y), 0,
         sch=(233.68, sch_y))
    m = len(nets)
    if row_x is None:
        row_x = x - 2.54 * (m - 1) / 2
    part(row_ref, GEN, "Conn_01x%02d" % m, "%s lead" % name, HDR % m,
         {str(i + 1): net for i, net in enumerate(nets)}, (row_x, row_y), 90,
         sch=(271.78, sch_y), label=labels)
    PORTS.append((name, sock_ref, row_ref))


# NewBeeDrone BeeID Pro M10 (GPS + compass + Remote ID). Its GH 6-pin order,
# per the RMRC listing, is TX RX GND 5V SCL SDA from the module's side, so
# pin 1 (module TX) is the FC's RX and pin 2 the FC's TX.
port("GPS+ID", "J5", "J6", -18.5, ["GPS_RX", "GPS_TX", "GND", "GPS_5V", "GPS_SCL", "GPS_SDA"],
     ["RX", "TX", "G", "5V", "SCL", "SDA"], 45.72)
# ELRS receiver (RP1): 5V TX RX GND.
port("RX", "J7", "J8", 18.5, ["RX_5V", "RX_TX", "RX_RX", "GND"], ["5V", "TX", "RX", "G"], 81.28)
# Holybro PM02 V3 sense cable (VCC VCC CUR VOLT GND GND). Its 5V (pins 1-2)
# stays unconnected: the LUX has its own BEC. Its GND is battery negative,
# the ESC bus GND, so only CUR and VOLT need a lead to the FC (whose ground
# already meets the ESC bus through the FC VBAT- lead).
PM_POS = (24.0, 39.5)
port("PM02", "J9", "J10", PM_POS[0], ["PM_CUR", "PM_VOLT"], ["CUR", "VOLT"], 111.76,
     socket_nets=[None, None, "PM_CUR", "PM_VOLT", "GND_ESC", "GND_ESC"],
     socket_y=PM_POS[1], row_y=45.3, row_x=20.5)

# Mechanical: frame holes, FC standoff holes, zip-tie slots.
hx, hy = FRAME_X / 2, FRAME_Y / 2
for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
    part("H%d" % (i + 1), "Mechanical", "MountingHole", "Frame M3",
         "MountingHole:MountingHole_3.2mm_M3", {}, (sx * hx, sy * hy),
         sch=(40.64 + 12.7 * i, 160.02))
f = FC_PITCH / 2
for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
    part("H%d" % (i + 5), "Mechanical", "MountingHole", "FC M3",
         "MountingHole:MountingHole_3.2mm_M3", {}, (sx * f, sy * f),
         sch=(91.44 + 12.7 * i, 160.02))
k = 1
for m in (1, 2, 3, 4):
    x, side = ESC_PADS[m]
    sx = 1 if x > 0 else -1
    for y in (13.0, 28.0):
        part("ZT%d" % k, "Mechanical", "MountingHole", "Zip-tie slot",
             "fc-adapter:ZipTieSlot_1.6x4.0mm", {}, (sx * 42.5, y * side),
             sch=(147.32 + 12.7 * ((k - 1) % 8), 160.02))
        k += 1

# Parts JLCPCB supplies and fits (PCBA). Each gets MPN/LCSC fields in the
# schematic and on the board, and scripts/jlcpcb.py turns them into JLCPCB's
# BOM and placement files. LCSC numbers are left blank where unconfirmed:
# JLCPCB's order page matches those by MPN and lets you pick.
ASSEMBLY = {
    "J1": ("Amass XT60PW-M", "", "fit"),
    "C1": ("1000uF 35V low-ESR electrolytic, 12.5mm radial, 5mm pitch", "", "fit"),
    "C2": ("1000uF 35V low-ESR electrolytic, 12.5mm radial, 5mm pitch", "", "fit"),
    "J5": ("JST BM06B-GHS-TBT", "", "fit"),
    "J7": ("JST BM04B-GHS-TBT", "", "fit"),
    "J9": ("JST BM06B-GHS-TBT", "", "fit"),
}

# Reference text placement overrides: (dx, dy, angle), angles add to the footprint rotation.
REF_POS = {}

POWER_NETS = ["VBAT_ESC", "GND_ESC"]
SUPPLY_NETS = ["GND", "GPS_5V", "RX_5V"]

# ---------------------------------------------------------------------------
# Schematic
# ---------------------------------------------------------------------------
_libs = {}


def lib_symbol(lib, name):
    path = (os.path.join(PROJ, "lib", "fc-adapter.kicad_sym") if lib == "fc-adapter"
            else os.path.join(SYSLIB, "symbols", lib + ".kicad_sym"))
    if path not in _libs:
        _libs[path] = SymbolLib.from_file(path)
    for s in _libs[path].symbols:
        if s.entryName == name:
            return s
    raise KeyError(lib + ":" + name)


def uid():
    return str(uuid.uuid4())


def font(size=1.27, hide=False, justify=None):
    e = Effects(font=Font(height=size, width=size), hide=hide)
    if justify:
        e.justify.horizontally = justify
    return e


def build_schematic():
    sch = Schematic.create_new()
    sch.uuid = uid()
    sch.paper = PageSettings(paperSize="A4")
    sch.titleBlock = TitleBlock(title="Quadcopter FC adapter / power board", date="2026-10-08",
                                revision="A", company="nixpulvis/quadcopter")
    used = {}
    for p in PARTS:
        key = p["lib"] + ":" + p["sym"]
        if key not in used:
            s = lib_symbol(p["lib"], p["sym"])
            s.libraryNickname = p["lib"]
            used[key] = s
            sch.libSymbols.append(s)
    pwr = lib_symbol("power", "PWR_FLAG")
    pwr.libraryNickname = "power"
    sch.libSymbols.append(pwr)

    def add_symbol(lib, sym, ref, value, fp, x, y, in_bom=True, dnp=False):
        # Small symbols get their fields beside them so stacked pads stay readable.
        dy = 1.27 if sym == "WirePad" else 5.08
        s = SchematicSymbol(libraryNickname=lib, entryName=sym, position=Position(x, y, 0),
                            unit=1, inBom=in_bom, onBoard=True, uuid=uid())
        if dnp:
            s.dnp = True
        s.properties = [
            Property(key="Reference", value=ref, id=0, position=Position(x + 2.54, y - dy, 0),
                     effects=font(justify="left")),
            Property(key="Value", value=value, id=1, position=Position(x + 2.54, y + dy, 0),
                     effects=font(justify="left")),
            Property(key="Footprint", value=fp, id=2, position=Position(x, y, 0), effects=font(hide=True)),
            Property(key="Datasheet", value="~", id=3, position=Position(x, y, 0), effects=font(hide=True)),
        ]
        for i, (k, v) in enumerate(zip(("MPN", "LCSC", "JLCPCB"), ASSEMBLY.get(ref, ()))):
            s.properties.append(Property(key=k, value=v, id=4 + i, position=Position(x, y, 0),
                                         effects=font(hide=True)))
        libsym = lib_symbol(lib, sym)
        pins = [pin for u in libsym.units for pin in u.pins]
        s.pins = {pin.number: uid() for pin in pins}
        sch.schematicSymbols.append(s)
        sch.symbolInstances.append(SymbolInstance(path="/" + s.uuid, reference=ref, unit=1,
                                                  value=value, footprint=fp))
        return s, pins

    for p in PARTS:
        x, y = p["sch"]
        s, pins = add_symbol(p["lib"], p["sym"], p["ref"], p["value"], p["fp"], x, y,
                             in_bom=not p["ref"].startswith(("H", "ZT")), dnp=p["dnp"])
        p["uuid"] = s.uuid
        for pin in pins:
            px, py = x + pin.position.X, y - pin.position.Y
            net = p["pins"].get(pin.number)
            if net is None:
                sch.noConnects.append(NoConnect(position=Position(px, py), uuid=uid()))
                continue
            ang = (pin.position.angle + 180) % 360
            just = "right" if ang in (180, 270) else "left"  # KiCad's convention
            sch.labels.append(LocalLabel(text=net, position=Position(px, py, ang),
                                         effects=font(justify=just), uuid=uid()))

    # PWR_FLAGs: every power net is driven from off-board (battery, FC).
    for i, net in enumerate(POWER_NETS + ["GND"]):
        x, y = 40.64 + 22.86 * i, 139.7
        s, pins = add_symbol("power", "PWR_FLAG", "#FLG%02d" % (i + 1), "PWR_FLAG", "", x, y, in_bom=False)
        sch.labels.append(LocalLabel(text=net, position=Position(x, y, 270),
                                     effects=font(justify="right"), uuid=uid()))

    notes = [
        ((25.4, 25.4), "POWER PATH (rev A): battery -> Holybro PM02 (current sense) -> J1 XT60 -> ESC bus.\n"
                       "ESC bus -> M1..M4 ESC pads, P1/P2 (FC VBAT) -> FC VBAT pads.\n"
                       "C1, C2: low-ESR, one each side for balance. Signal GND only meets GND_ESC through the FC."),
        ((165.1, 25.4), "ESC signal headers: pin 2 (ESC BEC +5V) is left unconnected,\n"
                        "so the ESC plugs fit unmodified without back-feeding the FC's servo rail.\n"
                        "J3 is wired to the FC's S1-S4 and G pads.\n"
                        "J5-J10: GPS, RX and PM02 sockets, each with a pad row for a lead to the FC.\n"
                        "TX/RX are named from the FC side. PM02 VCC (J9 pins 1-2) is not connected."),
        ((25.4, 152.4), "Mechanical: H1-H4 frame standoffs 44mm M3, H5-H8 FC 30.5mm M3,\n"
                        "ZT1-ZT8 zip-tie slots for ESC lead strain relief."),
    ]
    for (x, y), t in notes:
        sch.texts.append(Text(text=t.replace("\n", "\\n"), position=Position(x, y, 0), effects=font(justify="left"),
                              uuid=uid()))
    sch.sheetInstances = [HierarchicalSheetInstance(instancePath="/", page="1")]
    sch.to_file(SCH_PATH)


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------
def mm(v):
    return pcbnew.FromMM(v)


def P(x, y):
    return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = (os.path.join(PROJ, "lib", lib + ".pretty") if lib == "fc-adapter"
            else os.path.join(SYSLIB, "footprints", lib + ".pretty"))
    fp = pcbnew.FootprintLoad(path, name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def segment(board, a, b, layer, width=0.15):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    board.Add(s)


def rect(board, x0, y0, x1, y1, layer, width=0.15, filled=False):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_RECT)
    s.SetStart(P(x0, y0))
    s.SetEnd(P(x1, y1))
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    s.SetFilled(filled)
    board.Add(s)


def text(board, t, x, y, layer=pcbnew.F_SilkS, size=1.0, angle=0, bold=False, width=None):
    tx = pcbnew.PCB_TEXT(board)
    tx.SetText(t)
    tx.SetPosition(P(x, y))
    tx.SetLayer(layer)
    tx.SetTextSize(pcbnew.VECTOR2I(mm(width or size), mm(size)))
    # JLCPCB's minimum silkscreen line is 0.15 mm.
    tx.SetTextThickness(mm(max(0.15, size * (0.2 if bold else 0.15))))
    tx.SetTextAngleDegrees(angle)
    if layer in (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_Mask):
        tx.SetMirrored(True)
    board.Add(tx)
    return tx


def poly_rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def poly_circle(cx, cy, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def zone(board, net, layers, pts, priority=0, solid=True, name=None):
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetNet(board.FindNet(net))
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(P(x, y))
    z.SetAssignedPriority(priority)
    z.SetMinThickness(mm(0.5))   # drops thin slivers between pins and tracks
    z.SetLocalClearance(mm(0.5 if net in POWER_NETS else 0.3))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if solid else pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(0.4))
    z.SetThermalReliefSpokeWidth(mm(0.5))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    if name:
        z.SetZoneName(name)
    board.Add(z)
    return z


def keepout(board, pts, name, layers=(pcbnew.F_Cu, pcbnew.B_Cu)):
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetZoneName(name)
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(P(x, y))
    board.Add(z)


# Logic area: everything signal-level lives in the front strip.
LOGIC = (-31.5, -BOARD_H / 2, 31.5, -27.5)


def outline(board):
    w, h, r = BOARD_W / 2, BOARD_H / 2, CORNER_R
    L = pcbnew.Edge_Cuts
    segment(board, (-w + r, -h), (w - r, -h), L, 0.1)
    segment(board, (w, -h + r), (w, h - r), L, 0.1)
    segment(board, (w - r, h), (-w + r, h), L, 0.1)
    segment(board, (-w, h - r), (-w, -h + r), L, 0.1)
    for cx, cy, a0 in [(w - r, -h + r, -90), (w - r, h - r, 0), (-w + r, h - r, 90), (-w + r, -h + r, 180)]:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
               for a in (a0, a0 + 45, a0 + 90)]
        s.SetArcGeometry(P(*pts[0]), P(*pts[1]), P(*pts[2]))
        s.SetLayer(L)
        s.SetWidth(mm(0.1))
        board.Add(s)


STACKUP = """    (stackup
      (layer "F.SilkS" (type "Top Silk Screen"))
      (layer "F.Paste" (type "Top Solder Paste"))
      (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
      (layer "F.Cu" (type "copper") (thickness 0.07))
      (layer "dielectric 1" (type "core") (thickness 1.84) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
      (layer "B.Cu" (type "copper") (thickness 0.07))
      (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
      (layer "B.Paste" (type "Bottom Solder Paste"))
      (layer "B.SilkS" (type "Bottom Silk Screen"))
      (copper_finish "HAL lead-free")
      (dielectric_constraints no)
    )
"""


def set_stackup(path):
    """2 oz copper on a 2.0 mm board. The stackup isn't exposed to Python in
    KiCad 7, so patch it into the saved file."""
    s = open(path).read()
    s = s.replace("(setup\n", "(setup\n" + STACKUP, 1)
    s = s.replace("(thickness 1.6)", "(thickness 2)", 1)
    open(path, "w").write(s)


def build_board():
    board = pcbnew.NewBoard(PCB_PATH)
    board.SetCopperLayerCount(2)
    tb = board.GetTitleBlock()
    tb.SetTitle("Quadcopter FC adapter / power board")
    tb.SetRevision("A")
    tb.SetDate("2026-10-08")
    tb.SetCompany("nixpulvis/quadcopter")

    nets = sorted({n for p in PARTS for n in p["pins"].values() if n})
    for n in nets:
        board.Add(pcbnew.NETINFO_ITEM(board, n))

    for p in PARTS:
        fp = load_fp(p["fp"])
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        fp.SetPosition(P(*p["pos"]))
        fp.SetOrientationDegrees(p["rot"])
        fp.SetPath(pcbnew.KIID_PATH("/" + p["uuid"]))
        fp.SetProperty("Sheetname", "")
        fp.SetProperty("Sheetfile", NAME + ".kicad_sch")
        if p["ref"] in ASSEMBLY:
            mpn, lcsc, fit = ASSEMBLY[p["ref"]]
            fp.SetProperty("MPN", mpn)
            fp.SetProperty("LCSC", lcsc)
            fp.SetProperty("JLCPCB", fit)
        if p["dnp"]:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        if p["ref"].startswith(("H", "ZT", "P", "J", "C1", "C2", "F")):
            fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        # The XT60's own +/- marks are unreadable at this size; the board
        # has its own.
        drop = {"J1": ("+", "-")}.get(p["ref"], ())
        for item in [g for g in fp.GraphicalItems()
                     if isinstance(g, pcbnew.FP_TEXT) and g.GetText() in drop]:
            fp.Remove(item)
        if p["ref"] in REF_POS:
            dx, dy, ang = REF_POS[p["ref"]]
            fp.Reference().SetPosition(P(p["pos"][0] + dx, p["pos"][1] + dy))
            fp.Reference().SetTextAngleDegrees(ang)
        for pad in fp.Pads():
            net = p["pins"].get(pad.GetNumber())
            if net:
                pad.SetNet(board.FindNet(net))
        board.Add(fp)
        p["fpobj"] = fp

    outline(board)
    board.GetDesignSettings().SetBoardThickness(mm(2.0))

    w, h = BOARD_W / 2, BOARD_H / 2
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    # Power pours. The ESC bus is VBAT_ESC on top and GND_ESC on the bottom,
    # both nearly full-board; the front strip is a logic GND area.
    whole = poly_rect(-w, -h, w, h)
    zone(board, "VBAT_ESC", [F], whole, 0, name="ESC bus +")
    zone(board, "GND_ESC", [B], whole, 0, name="ESC bus -")
    for L in (F, B):
        zone(board, "GND", [L], poly_rect(*LOGIC), 3, name="Logic GND")

    for i in range(4):
        keepout(board, poly_circle(*PARTS_BY_REF["H%d" % (i + 1)]["pos"], 4.5), "Frame standoff")
        keepout(board, poly_circle(*PARTS_BY_REF["H%d" % (i + 5)]["pos"], 3.6), "FC standoff")

    # Exposed copper strips along the ESC bus, to thicken with solder if needed.
    for sx in (-1, 1):
        rect(board, sx * 28.0, -24.0, sx * 29.8, 26.0, pcbnew.F_Mask, 0, True)
        rect(board, sx * 28.0, -24.0, sx * 29.8, 26.0, pcbnew.B_Mask, 0, True)

    signal_tracks(board)
    silk(board)
    pcbnew.SaveBoard(PCB_PATH, board)
    set_stackup(PCB_PATH)
    write_project_rules()
    return board


def signal_tracks(board):
    """S1-S4 run straight from the FC link down to the ESC header's S row.
    G needs no track: both headers sit in the logic GND pour."""
    j3 = pads_by_number("J3")
    for i in range(4):
        hx, hy = xy(j3[str(i + 1)])
        ex = ESC_SIG_X0 + 2.54 * i   # J3 sits under the S columns, so these are straight
        track(board, [(hx, hy), (ex, ESC_SIG_Y0)], "S%d" % (i + 1), 0.5)
    for name, sock, row in PORTS:
        port_tracks(board, sock, row)


def pads_by_number(ref):
    fp = PARTS_BY_REF[ref]["fpobj"]
    return {pd.GetNumber(): pd for pd in fp.Pads() if pd.GetNetname()}


def track(board, pts, net, width, layer=pcbnew.F_Cu):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(mm(width))
        t.SetLayer(layer)
        t.SetNet(board.FindNet(net))
        board.Add(t)


def xy(pad):
    v = pad.GetPosition()
    return pcbnew.ToMM(v.x) - ORIGIN[0], pcbnew.ToMM(v.y) - ORIGIN[1]


def port_tracks(board, sock, row):
    """Fan each socket pin out to the pad of the same net in the FC pad row:
    straight out of the socket pad, a diagonal, then straight into the pad."""
    rows = {pd.GetNetname(): pd for pd in pads_by_number(row).values()}
    for pd in pads_by_number(sock).values():
        net = pd.GetNetname()
        (sx, sy), width = xy(pd), (0.5 if net in SUPPLY_NETS else 0.3)
        if net in rows:
            hx, hy = xy(rows[net])
            d = 1 if hy > sy else -1
            ya = sy + d * 1.35
            yb = hy - d * 1.4 if d * (hy - d * 1.4 - ya) > 0 else ya
            track(board, [(sx, sy), (sx, ya), (hx, yb), (hx, hy)], net, width)
    # PM02 GND pins drop through a via to the ESC bus GND pour underneath.
    if sock == "J9":
        g = sorted(xy(pd) for pd in pads_by_number(sock).values() if pd.GetNetname() == "GND_ESC")
        y = g[0][1] + 1.6
        vx = g[-1][0] + 1.6
        for x, sy in g:
            track(board, [(x, sy), (x, y)], "GND_ESC", 0.5)
        track(board, [(g[0][0], y), (vx, y)], "GND_ESC", 0.5)
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(P(vx, y))
        v.SetWidth(mm(0.8))
        v.SetDrill(mm(0.4))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(board.FindNet("GND_ESC"))
        board.Add(v)


def write_project_rules():
    """Design rules and net classes live in the .kicad_pro in KiCad 7+."""
    import json
    pro = os.path.join(PROJ, NAME + ".kicad_pro")
    d = json.load(open(pro)) if os.path.exists(pro) else {}
    rules = d.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
    rules.update({
        # JLCPCB 2-layer, 2 oz copper limits, with margin.
        "min_clearance": 0.2, "min_track_width": 0.2, "min_via_diameter": 0.6,
        "min_via_annular_width": 0.15, "min_through_hole_diameter": 0.3,
        "min_hole_clearance": 0.25, "min_hole_to_hole": 0.3,
        "min_copper_edge_clearance": 0.5, "min_silk_clearance": 0.0,
        "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1,
    })
    def nc(name, clearance, track, via=0.8, drill=0.4):
        return {"name": name, "clearance": clearance, "track_width": track,
                "via_diameter": via, "via_drill": drill,
                "microvia_diameter": 0.3, "microvia_drill": 0.1,
                "diff_pair_width": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                "wire_width": 6, "bus_width": 12, "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
                "schematic_color": "rgba(0, 0, 0, 0.000)"}
    ns = d.setdefault("net_settings", {})
    # 0.3mm clearance keeps tracks from squeezing between 2.54mm header pins.
    ns["classes"] = [nc("Default", 0.3, 0.3), nc("Supply", 0.3, 0.5),
                     nc("Power", 0.5, 2.0, 1.2, 0.6)]
    ns["netclass_patterns"] = [{"netclass": "Power", "pattern": n} for n in POWER_NETS] + \
                              [{"netclass": "Supply", "pattern": n} for n in SUPPLY_NETS]
    ns.setdefault("meta", {"version": 3})
    d.setdefault("meta", {"filename": NAME + ".kicad_pro", "version": 1})
    json.dump(d, open(pro, "w"), indent=2)


def silk(board):
    S = pcbnew.F_SilkS
    z = FC_ZONE / 2
    # FC keep-low area and forward arrow.
    # (bottom edge is broken where the XT60's body crosses it)
    for a, b in [((-z, -z), (z, -z)), ((z, -z), (z, z)), ((z, z), (9, z)), ((-9, z), (-z, z)),
                 ((-z, z), (-z, -z))]:
        segment(board, a, b, S, 0.12)
    text(board, "FC  30.5 mm M3", 0, 21.0, size=1.0)
    text(board, "FRAME  %g mm M3" % FRAME_X, 0, z - 2.0, size=1.0)  # mirrors the FC label
    # The LUX F765 itself (38 x 38 mm).
    rect(board, -FC_SIZE / 2, -FC_SIZE / 2, FC_SIZE / 2, FC_SIZE / 2, S, 0.12)
    segment(board, (0, 8), (0, -12), S, 0.6)
    segment(board, (0, -12), (-4, -7), S, 0.6)
    segment(board, (0, -12), (4, -7), S, 0.6)
    text(board, "FRONT", 0, -14.5, size=2.0, bold=True)

    # Power pads.
    # The FC's battery lead, named after the FC pads it goes to.
    text(board, "FC VBAT+", -13.2, 35.0, size=1.0)
    text(board, "FC VBAT-", 13.2, 35.0, size=1.0)
    # One polarity mark per side of the XT60 (its footprint's own marks are removed).
    text(board, "+", -3.6, 41.0, size=2.5, bold=True)
    text(board, "-", 3.6, 41.0, size=2.5, bold=True)
    for m in (1, 2, 3, 4):
        x, side = ESC_PADS[m]
        tx = x - 4.4 if x > 0 else x + 4.4
        text(board, "M%d" % m, tx, 20.5 * side, size=1.5, bold=True)
        text(board, "+", tx, 24.0 * side, size=1.5, bold=True)
        text(board, "-", tx, 17.0 * side, size=1.5, bold=True)
        # Same marks on the back, for wires soldered from underneath.
        bx = x - 4.4 if x > 0 else x + 4.4
        text(board, "M%d" % m, bx, 20.5 * side, pcbnew.B_SilkS, size=1.5, bold=True)
        text(board, "+", bx, 24.0 * side, pcbnew.B_SilkS, size=1.5, bold=True)
        text(board, "-", bx, 17.0 * side, pcbnew.B_SilkS, size=1.5, bold=True)
    for x, lab in ((-13.2, "FC VBAT+"), (13.2, "FC VBAT-")):
        text(board, lab, x, 35.0, pcbnew.B_SilkS, size=1.0)

    # Signal headers. Every front port reads the same way, front to back:
    # device connector, FC pad row, its pin names, then the port's name.
    # The ESC header also names its rows on the left.
    PIN = 1.0
    PIN_W = 0.75     # condensed, so SCL and SDA fit side by side at 2.54 mm
    NAME_Y = FC_LINK_Y + 4.6

    def just(t, side):
        # Mirrored (bottom) text flips its justification, so ask for the
        # opposite side there to keep the text on the same side of the anchor.
        right = (side == "right") != (t.GetLayer() == pcbnew.B_SilkS)
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT if right else pcbnew.GR_TEXT_H_ALIGN_LEFT)

    # Pin and port names go on both sides: the FC leads are soldered from
    # underneath.
    for L in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        for ref in ["J3"] + [row for _, _, row in PORTS if PARTS_BY_REF[row]["pos"][1] < 0]:
            pads = pads_by_number(ref)
            for i, lab in enumerate(PARTS_BY_REF[ref]["label"]):
                px, py = xy(pads[str(i + 1)])
                text(board, lab, px, py + 2.3, L, size=PIN, width=PIN_W)
        text(board, "ESC", 0, NAME_Y, L, size=1.2, bold=True)
        for name, sock, row in PORTS:
            sx, sy = PARTS_BY_REF[sock]["pos"]
            x0, y0 = PARTS_BY_REF[row]["pos"]
            if y0 < 0:
                text(board, name, sx, NAME_Y, L, size=1.2, bold=True)
                continue
            # PM02, at the rear edge: no room below, so the pin names go
            # either side of the pad row.
            a, b = PARTS_BY_REF[row]["label"]
            just(text(board, a, x0 - 1.4, y0, L, size=PIN, width=PIN_W), "right")
            just(text(board, b, x0 + 2.54 + 1.4, y0, L, size=PIN, width=PIN_W), "left")
            if L == pcbnew.F_SilkS:
                half = 1.25 * (len(PARTS_BY_REF[sock]["pins"]) + 1) / 2 + 1.35
                just(text(board, name, sx - half - 0.6, sy - 1.4, L, size=1.2, bold=True), "right")
            else:
                # The socket is on top only; name the pad row instead.
                text(board, name, x0 + 1.27, y0 - 2.8, L, size=1.2, bold=True)
        for r, lab in enumerate(("S", "NC", "G")):
            just(text(board, lab, ESC_SIG_X0 - 1.6, ESC_SIG_Y0 - 2.54 * r, L, size=PIN, width=PIN_W),
                 "right")

    # Board name in the empty rear-left corner, opposite the PM02 port.
    text(board, "QUAD PDB", -24.0, 40.5, size=1.6, bold=True)
    text(board, "rev A", -24.0, 43.2, size=1.0)

    B = pcbnew.B_SilkS
    # Title block, evenly spaced lines under a bold name.
    text(board, "QUADCOPTER POWER BOARD", 0, -6.0, B, 1.8, bold=True)
    for i, line in enumerate(("rev A  2026-10",
                              "FC: Lumenier LUX F765 (30.5 mm M3)",
                              "Battery -> PM02 -> XT60",
                              "2 oz Cu, 2.0 mm FR4",
                              "github.com/nixpulvis/quadcopter")):
        text(board, line, 0, -2.5 + 2.2 * i, B, 1.0)


PARTS_BY_REF = {p["ref"]: p for p in PARTS}

if __name__ == "__main__":
    build_schematic()
    build_board()
    print("wrote", SCH_PATH)
    print("wrote", PCB_PATH)
