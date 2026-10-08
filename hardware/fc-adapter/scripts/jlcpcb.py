#!/usr/bin/env python3.12
"""Write JLCPCB assembly files: fab/jlcpcb-bom.csv and fab/jlcpcb-cpl.csv.

Only parts with a JLCPCB field (set from ASSEMBLY in generate.py) are listed.
Everything else (wire pads, headers, pad rows) is soldered by hand.

    python3 scripts/jlcpcb.py

JLCPCB's placement preview sometimes shows a part rotated (their library and
KiCad's disagree on a footprint's zero angle). Check each part in the preview
and fix the rotation there before paying.
"""
import csv
import os

import pcbnew

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(PROJ, "fc-adapter.kicad_pcb")
FAB = os.path.join(PROJ, "fab")


def main():
    want = {"fit"}
    board = pcbnew.LoadBoard(PCB)
    edge = board.GetBoardEdgesBoundingBox()
    x0, y1 = edge.GetLeft(), edge.GetBottom()   # JLCPCB: origin bottom-left, Y up
    groups, rows = {}, []
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        if not fp.HasProperty("JLCPCB") or fp.GetProperty("JLCPCB") not in want:
            continue
        ref = fp.GetReference()
        key = (fp.GetProperty("MPN"), fp.GetFPID().GetLibItemName().wx_str(), fp.GetProperty("LCSC"))
        groups.setdefault(key, []).append(ref)
        pos = fp.GetPosition()
        rows.append([ref, "%.3fmm" % pcbnew.ToMM(pos.x - x0), "%.3fmm" % pcbnew.ToMM(y1 - pos.y),
                     "Bottom" if fp.IsFlipped() else "Top", "%g" % (fp.GetOrientationDegrees() % 360)])
    os.makedirs(FAB, exist_ok=True)
    with open(os.path.join(FAB, "jlcpcb-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (mpn, fpname, lcsc), refs in groups.items():
            w.writerow([mpn, ",".join(refs), fpname, lcsc])
    with open(os.path.join(FAB, "jlcpcb-cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writerows(rows)
    print("JLCPCB parts:", ", ".join(r[0] for r in rows))


if __name__ == "__main__":
    main()
