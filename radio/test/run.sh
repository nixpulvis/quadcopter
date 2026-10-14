#!/bin/sh
# Run quad.lua through every sim scenario and render PNG previews.
# Usage: radio/test/run.sh [OUTDIR]   (needs lua5.2 or lua, and python3 + Pillow)
set -e
here=$(cd "$(dirname "$0")" && pwd)
out=${1:-$here/out}
mkdir -p "$out"
lua=$(command -v lua5.2 || command -v lua)
"$lua" "$here/sim.lua" "$here/../SCRIPTS/TELEMETRY/quad.lua" "$out"
for log in "$out"/*.log; do
  python3 "$here/render.py" "$log" "${log%.log}.png" 3
done
python3 "$here/render.py" --sheet "$out/sheet.png" \
  "$out/disarmed-level.png" "$out/armed-bank-right.png" \
  "$out/armed-dive-left.png" "$out/low-battery.png" \
  "$out/inverted.png" "$out/no-telemetry.png"
python3 "$here/render.py" --sheet "$out/sheet-passthrough.png" \
  "$out/pt-prearm.png" "$out/pt-flying.png" \
  "$out/pt-batt-failsafe.png" "$out/pt-ekf.png" \
  "$out/pt-fence-terrain.png" "$out/pt-page2.png"
echo "previews in $out"
