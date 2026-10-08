# Rev A fab files (archived)

The board as ordered from OSH Park on 2026-10-08, built from commit 4dd9a79.

- `fc-adapter-gerbers.zip`: Gerbers, drill files and job file. OSH Park standard
  2-layer service: 1.6 mm FR4, 1 oz copper, ENIG.
- `jlcpcb-bom.csv`, `jlcpcb-cpl.csv`: the JLCPCB assembly BOM and placement
  files for the same revision (C1, C2, J1, J5, J7, J9). Not used for the OSH
  Park order, where the parts are hand-soldered.

These are frozen copies. `scripts/export.sh` rebuilds `fab/` from the current
design, which may have moved past rev A.
