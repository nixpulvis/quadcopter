# quadctl

One file, `config/quad.yaml`, describes the quad and the radio. `quadctl` pushes
it to the FC (ArduPilot, over USB serial) and the Pocket (EdgeTX, over USB
storage), and checks that both sides agree. ELRS module settings are applied on
the radio by a small Lua boot script. Firmware is flashed only when a chip
differs from `config/firmware.lock`.

## Install (macOS)

```sh
brew install dfu-util            # only needed for DFU flashing
pipx install ./tools/quadctl     # or: uv tool install ./tools/quadctl
```

## Use

Plug in the FC, and plug in the Pocket and pick **USB Storage** on it.

| Command | What it does |
|---|---|
| `quadctl check` | Validate `quad.yaml` and run every rule offline |
| `quadctl pull` | Back up both devices into `backups/<time>/` |
| `quadctl plan` | Show what `apply` would change, plus firmware status |
| `quadctl apply` | Back up, write the FC and read it back, then write the Pocket |
| `quadctl verify` | Read both devices and run the rules on what they actually hold |
| `quadctl flash [--check] [--defaults]` | Flash only what differs from `firmware.lock` |
| `quadctl lock` | Download each firmware URL and fill in its sha256 |
| `quadctl restore backups/<time>` | Put a backup back |

`--only fc` or `--only radio` limits any command to one device. Without it,
`apply` needs both, so the two sides can't drift apart by accident.

### One-time radio setup

Add the boot script on the radio once: **Model > Special Functions > ON > Lua
Script > qelrs**. `verify` warns until it's there. The **Quad ELRS** Tools page
shows what the script did with each setting; ENTER drops hand-made overrides so
`quad.yaml` wins again (`apply --reset-elrs` does the same from the Mac).

## Switch layout

- **SA** (CH5): arm.
- **SB** (CH6): Loiter / AltHold / Stabilize.
- **SD**: Fly / Acro, mixed onto CH6.
- **SC**: Fly / RTL / Land, mixed onto CH6, and beats SD.

In Fly the switch below decides; any other position REPLACEs the channel with
a fixed value. EdgeTX runs the lines in order and the last active REPLACE wins,
so the priority is fixed (SC > SD > SB) no matter which switch moved last, and
ArduPilot only ever sees one mode channel.

Each output sits mid-slot: SB 1167/1295/1423 us (slots 1-3), Acro 1556 (4), RTL
1684 (5), Land 2012 (6), at least 63 us from any band edge. That uses all six
`FLTMODE` slots, so another mode switch (say SE as Brake) would go on its own
aux channel. `checks.py` evaluates the real mix lines for all 18 combinations
against the FC's `FLTMODE` slots. CH6 needs ELRS Switch Mode **Wide**; Hybrid
would quantize it.

## What goes where

- **FC params** (`compile.py`): channel map, arm switch, mode channel and every
  `FLTMODE` slot, RX port and the `RC_OPTIONS` bits quadctl owns, battery and
  failsafes, fence. Everything else (calibration, PIDs) is never touched.
- **Pocket model** (`radio.py`): every mix line on the channels quadctl owns
  (CH5 arm, CH6 mode), replaced in the model's YAML; other channels and the rest
  of the file stay byte-identical. Scripts from
  `radio/SCRIPTS/` and `SCRIPTS/QUAD/elrs.cfg` are copied to the card.
- **ELRS module** (`radio/SCRIPTS/QUAD/elrs.lua`): reads `elrs.cfg` at power-up and,
  with no receiver linked, writes what changed. A setting changed by hand on the
  radio is reported as an override and left alone.

### Sharing CRSF with the telemetry screen

The telemetry screen (`SCRIPTS/TELEMETRY/quad.lua`) decodes ArduPilot's CRSF
passthrough frames from the same `crossfireTelemetryPop()` queue the boot script
uses, so a frame either script pops is gone for the other. They take turns:

- The boot script only pushes or pops while no receiver is linked
  (`getRSSI() == 0`). With a link up it pauses and leaves the queue alone; any
  pending ELRS change waits until the quad is off again.
- Once it's in sync it goes idle and never pops again until the next power-up.

So power the radio first and the quad second: the check finishes in a second or
two before the link comes up, and the telemetry screen then has the queue to itself.
`quad.yaml` already sets the passthrough bit (`telemetry.passthrough`) and
`Telem Ratio 1:4`.

## Firmware

`flash --check` reports each chip as `ok`, `FLASH REQUIRED` (the running
firmware differs from the lock: `apply` stops, `verify` fails) or `defaults
stale` (only the FC's embedded defaults are behind `quad.yaml`: a note, the
params are still applied normally). Plain `flash` does only required flashes;
`--defaults` also refreshes stale defaults.

- **FC**: the locked `.apj` with quadctl's params embedded as defaults, uploaded
  by ArduPilot's own `uploader.py` (no BOOT button). After a param reset or with a
  fresh SD card the FC comes up on this config.
- **EdgeTX**: `dfu-util` with the Pocket plugged in while switched off. quadctl
  refuses unless exactly one STM32 DFU device is present and it has the F4 flash
  layout, so it can't flash the FC by mistake.
- **ELRS** (TX module and RP1): reported, and flashed as a pair with ExpressLRS
  Configurator for now; `flash` prints the steps.

## Security rules enforced

- No `RCx_OPTION` may be 11 (Fence), and `FENCE_*` must match `quad.yaml`.
- The RX port stays RCIN (not MAVLink) and ELRS `Link Mode` must be `Normal`.

## Not verified on hardware yet

Tested here against a simulated FC (MAVLink over UDP), a simulated ELRS module
(CRSF parameter frames) and a hand-written EdgeTX model file. Still assumed, to be
confirmed with `quadctl pull` on the real devices:

- EdgeTX YAML names: `mixData`/`destCh`/`srcRaw`, stick sources `Ail/Ele/Thr/Rud`,
  `moduleData.0.type: TYPE_CROSSFIRE`, `customFn` `PLAY_SCRIPT`, `semver` in `radio.yml`.
- The Pocket's switch names (`SA`-`SD` in `quad.yaml`) and EdgeTX's
  switch-position names in mix lines (`SC1` = middle, `SC2` = down, `SD1` = down), plus `MAX` and `REPLACE`.
- ELRS option text (`Dyn`, `100`) and the version bytes in the device-info frame.
- That function scripts can use `crossfireTelemetryPush/Pop` and share the
  `quadElrs` global with the Tools page.
- MAVLink FTP writing `/APM/quadctl.json` on this board, and `uploader.py` on macOS.
- The Pocket's MCU (STM32F4) for the DFU check, and the EdgeTX `.bin` start address.

## Tests

```sh
cd tools/quadctl
pip install -e '.[test]'
pytest
```
