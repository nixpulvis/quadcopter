#!/usr/bin/env python3.12
"""Autoroute the signal nets with Freerouting, then fill zones and run DRC.

Power nets are carried by the copper pours from generate.py, so only the
logic nets in the front strip are routed. Freerouting works on a scratch copy
of the board that has the power parts removed and everything outside the
front strip marked as keepout; its tracks are then copied onto the real board.

    FREEROUTING_JAR=/path/to/freerouting-2.1.0.jar python3 scripts/route.py
"""
import math
import os
import re
import subprocess
import sys
import tempfile

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import (BOARD_H, BOARD_W, LOGIC, ORIGIN, PCB_PATH, POWER_NETS, PROJ,  # noqa: E402
                      keepout, poly_rect)

JAR = os.environ.get("FREEROUTING_JAR", "freerouting.jar")


def sexp(text):
    """Tiny s-expression reader for the Specctra session file."""
    tokens = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t.strip('"'))
    return stack[0][0]


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def parse_ses(text):
    """Return (tracks, vias) from a Freerouting .ses file, in KiCad nm.

    ExportSpecctraDSN writes (resolution um 10) and a Y axis pointing up, and
    pcbnew.ImportSpecctraSES only works inside the editor, so read it here."""
    root = sexp(text)
    routes = find(root, "routes")[0]
    res = find(routes, "resolution")[0]
    scale = {"um": 1000, "mm": 1000000, "mil": 25400}[res[1]] / float(res[2])
    tracks, vias = [], []
    for net in find(find(routes, "network_out")[0], "net"):
        name = net[1]
        for wire in find(net, "wire"):
            path = find(wire, "path")[0]
            layer, width = path[1], float(path[2]) * scale
            pts = [(float(path[i]) * scale, -float(path[i + 1]) * scale)
                   for i in range(3, len(path) - 1, 2)]
            for a, b in zip(pts, pts[1:]):
                tracks.append((name, layer, width, a, b))
        for via in find(net, "via"):
            m = re.search(r"_(\d+):(\d+)_um", via[1])
            vias.append((name, (float(via[2]) * scale, -float(via[3]) * scale),
                         int(m.group(1)) * 1000, int(m.group(2)) * 1000))
    return tracks, vias


def prune_stubs(board, tracks, vias):
    """Drop dead-end segments Freerouting sometimes leaves behind."""
    pads = [(p.GetNetname(), p) for p in board.GetPads()]

    def key(pt):
        return (round(pt[0] / 1000), round(pt[1] / 1000))   # 1 um grid

    while True:
        ends = {}
        for t in tracks:
            for pt in (t[3], t[4]):
                ends.setdefault((t[0], t[1], key(pt)), 0)
                ends[(t[0], t[1], key(pt))] += 1
        via_pts = {(v[0], key(v[1])) for v in vias}

        def on_other(t, pt):
            # Freerouting also ends wires part way along another wire (a T).
            for o in tracks:
                if o is t or o[0] != t[0] or o[1] != t[1]:
                    continue
                (ax, ay), (bx, by) = o[3], o[4]
                dx, dy = bx - ax, by - ay
                l2 = dx * dx + dy * dy
                u = 0 if l2 == 0 else max(0, min(1, ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / l2))
                if math.hypot(ax + u * dx - pt[0], ay + u * dy - pt[1]) <= o[2] / 2:
                    return True
            return False

        def connected(t, pt):
            if ends[(t[0], t[1], key(pt))] > 1 or (t[0], key(pt)) in via_pts or on_other(t, pt):
                return True
            v = pcbnew.VECTOR2I(int(pt[0]), int(pt[1]))
            return any(n == t[0] and p.HitTest(v) for n, p in pads)

        keep = [t for t in tracks if connected(t, t[3]) and connected(t, t[4])]
        if len(keep) == len(tracks):
            return keep
        tracks = keep


def export_dsn(dsn):
    """Stage 1, run in its own process: KiCad 7's SWIG wrappers misbehave once
    a board has been modified or a second board loaded in the same process."""
    b = pcbnew.LoadBoard(PCB_PATH)
    zones = [z for z in b.Zones() if not z.GetIsRuleArea()]
    power = [fp for fp in b.Footprints()
             if any(p.GetNetname() in POWER_NETS for p in fp.Pads())]
    for item in zones + power:
        b.Remove(item)
    # Keep top-side tracks out from under silkscreen labels so they stay legible.
    texts = [d for d in b.GetDrawings()
             if d.GetLayer() == pcbnew.F_SilkS and isinstance(d, pcbnew.PCB_TEXT)]
    texts += [fp.Reference() for fp in b.Footprints() if fp.Reference().IsVisible()]
    for t in texts:
        bb = t.GetBoundingBox()
        bb.Inflate(pcbnew.FromMM(0.2))
        pts = [(pcbnew.ToMM(x) - ORIGIN[0], pcbnew.ToMM(y) - ORIGIN[1]) for x, y in
               ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()),
                (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom()))]
        keepout(b, pts, "route: under label", (pcbnew.F_Cu,))
    w, h = BOARD_W / 2, BOARD_H / 2
    x0, y0, x1, y1 = LOGIC
    keepout(b, poly_rect(-w - 1, y1, w + 1, h + 1), "route: not logic")
    keepout(b, poly_rect(-w - 1, -h - 1, x0, y1), "route: not logic")
    keepout(b, poly_rect(x1, -h - 1, w + 1, y1), "route: not logic")
    if not pcbnew.ExportSpecctraDSN(b, dsn):
        sys.exit("DSN export failed")


def main():
    tmp = tempfile.mkdtemp()
    dsn = os.path.join(tmp, "scratch.dsn")
    ses = os.path.join(tmp, "scratch.ses")
    subprocess.run([sys.executable, __file__, "--export-dsn", dsn], check=True)
    subprocess.run(["java", "-jar", JAR, "--gui.enabled=false",
                    "-de", dsn, "-do", ses, "-mp", "50"], check=True, stdout=subprocess.DEVNULL)
    tracks, vias = parse_ses(open(ses).read())

    board = pcbnew.LoadBoard(PCB_PATH)
    if len(board.GetTracks()):
        sys.exit("board already has tracks; run generate.py first")
    tracks = prune_stubs(board, tracks, vias)
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    for name, layer, width, a, b in tracks:
        s = pcbnew.PCB_TRACK(board)
        s.SetStart(pcbnew.VECTOR2I(int(a[0]), int(a[1])))
        s.SetEnd(pcbnew.VECTOR2I(int(b[0]), int(b[1])))
        s.SetWidth(int(width))
        s.SetLayer(layers[layer])
        s.SetNet(board.FindNet(name))
        board.Add(s)
    for name, pos, dia, drill in vias:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(int(pos[0]), int(pos[1])))
        v.SetWidth(dia)
        v.SetDrill(drill)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(board.FindNet(name))
        board.Add(v)
    print("added %d track segments, %d vias" % (len(tracks), len(vias)))

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB_PATH, board)
    print("saved", PCB_PATH, "- run scripts/check.py for DRC")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--export-dsn":
        export_dsn(sys.argv[2])
    else:
        main()
