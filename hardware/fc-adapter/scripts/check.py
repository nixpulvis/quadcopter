#!/usr/bin/env python3.12
"""Fill zones, run DRC and check the board's nets against the schematic netlist.

KiCad 7's kicad-cli has no ERC/DRC commands, so DRC runs through pcbnew and
the schematic check compares every pin's net in the exported netlist with the
matching pad on the board. Results go to docs/drc.rpt and docs/netlist-check.txt.
"""
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import pcbnew

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCH = os.path.join(PROJ, "fc-adapter.kicad_sch")
PCB = os.path.join(PROJ, "fc-adapter.kicad_pcb")
DOCS = os.path.join(PROJ, "docs")


def main():
    board = pcbnew.LoadBoard(PCB)
    # generate.py leaves the pours unfilled; fill them so DRC and the
    # exports see the real copper.
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    drc = os.path.join(DOCS, "drc.rpt")
    if not pcbnew.WriteDRCReport(board, drc, pcbnew.EDA_UNITS_MILLIMETRES, True):
        sys.exit("DRC failed to run")
    report = open(drc).read()
    # Strip the absolute path and timestamp so the committed report only
    # changes when the results do.
    report = "\n".join(l for l in report.splitlines() if not l.startswith("** Created on"))
    report = report.replace(PCB, "fc-adapter.kicad_pcb")
    open(drc, "w").write(report + "\n")

    with tempfile.TemporaryDirectory() as tmp:
        xml = os.path.join(tmp, "net.xml")
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
                        "-o", xml, SCH], check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(xml).getroot()
    sch = {}
    for net in root.find("nets"):
        name = net.get("name").lstrip("/")
        for node in net.findall("node"):
            if not name.startswith("unconnected-"):
                sch[(node.get("ref"), node.get("pin"))] = name
    pcb = {}
    refs_pcb = set()
    for fp in board.GetFootprints():
        refs_pcb.add(fp.GetReference())
        for pad in fp.Pads():
            if pad.GetNetname():
                pcb[(fp.GetReference(), pad.GetNumber())] = pad.GetNetname()
    refs_sch = {c.get("ref") for c in root.find("components")}
    bad = sorted(k for k in set(sch) | set(pcb) if sch.get(k) != pcb.get(k))
    lines = ["Schematic vs board net check",
             "schematic pins with nets: %d, board pads with nets: %d" % (len(sch), len(pcb)),
             "parts only in schematic: %s" % (sorted(refs_sch - refs_pcb) or "none"),
             "parts only on board: %s" % (sorted(refs_pcb - refs_sch) or "none"),
             "pin/net mismatches: %d" % len(bad)]
    lines += ["  %s pin %s: schematic %s, board %s" % (k[0], k[1], sch.get(k), pcb.get(k)) for k in bad]
    out = "\n".join(lines) + "\n"
    open(os.path.join(DOCS, "netlist-check.txt"), "w").write(out)
    print(report)
    print(out)


if __name__ == "__main__":
    main()
