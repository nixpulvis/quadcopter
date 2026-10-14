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
- **SC**: Fly / RTL / Land, mixed onto CH6.
- **SD**: Fly / Acro, mixed onto CH6. A strict override: the only way out of Acro is SD.
- **SE** (CH7, `RC7_OPTION` 33): hold to Brake. Forced off while SD is in Acro.
- **S1** dial (CH8, `RC8_OPTION` 219): transmitter tuning, see below.

In Fly the switch below decides; any other position REPLACEs the channel with
a fixed value. EdgeTX runs the lines in order and the last active REPLACE wins,
so the priority is fixed (SD > SC > SB) no matter which switch moved last, and
ArduPilot only ever sees one mode channel. (The FC can still change mode by
itself, for example a failsafe RTL.)

Each output sits mid-slot: SB 1167/1295/1423 us (slots 1-3), RTL 1556 (4), Land
1684 (5), Acro 2012 (6), at least 63 us from any band edge. That uses all six
`FLTMODE` slots, so any further switch goes on its own aux channel like SE.
`checks.py` evaluates the real mix lines for every switch combination against
the FC's `FLTMODE` slots and aux options. CH6 needs ELRS Switch Mode **Wide**;
Hybrid would quantize it.

## Tuning dial (S1)

ArduPilot moves one gain live with the dial: `TUNE` picks which one, and the dial
sweeps it from `TUNE_MIN` to `TUNE_MAX`. The tuned value is in RAM only, so it's
gone after a reboot unless you note it and save it (QGC).

You pick the target over the air in the FC's **Quad Tune** menu: ELRS Lua >
Other Devices > the flight controller > Quad Tune. `fc/scripts/quadtune.lua`
(installed by `apply` as `APM/scripts/quadtune.lua`, with `SCR_ENABLE 1`) builds
that menu from `tuning.targets` in `quad.yaml`:

- **Target**: Off or one of the listed targets. It also sets that target's
  `TUNE_MIN`/`MAX` from the list, so a range can never be paired with the wrong
  gain. The radio only sends a row number.
- A new target is accepted only while disarmed; Off works any time.
- Everything is RAM only (never saved), so every boot starts Off. `apply` also
  writes `TUNE 0` and `TUNE_MIN = TUNE_MAX = 0` (a dial that does nothing).
- **Value** shows the live value of the gain being tuned.

The default ranges are centred on ArduCopter's defaults, so the dial's middle is
stock: Rate P 0.07-0.20 (0.135), Rate D 0.0016-0.0056 (0.0036), Acro rate
180-540 deg/s (360). Centre the dial before picking a target, because the gain
jumps to the dial's position the moment one is set.

## What goes where

- **FC params** (`compile.py`): channel map, arm switch, mode channel and every
  `FLTMODE` slot, RX port and the `RC_OPTIONS` bits quadctl owns, battery and
  failsafes, fence, tuning knob (plus the menu script on the FC's SD card). Everything else (calibration, PIDs) is never touched.
- **Pocket model** (`radio.py`): every mix line on the channels quadctl owns
  (CH5 arm, CH6 mode, CH7 brake, CH8 tuning dial), replaced in the model's YAML; other channels and the rest
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

- No `RCx_OPTION` may be 11 (Fence), and `FENCE_*` / `AVOID_*` must match `quad.yaml`
  (fence breach = SmartRTL, which retraces the path back inside, falling back to RTL
  then Land; avoidance backs the quad away from the fence in Loiter/AltHold).
- The RX port stays RCIN (not MAVLink) and ELRS `Link Mode` must be `Normal`.
- The one over-the-air setting is the tuning target, and only as a row of
  `quad.yaml`'s list: `verify` fails on a `TUNE` outside the list, a range that
  doesn't match its row, a second knob (`RCx_OPTION` 220 or `TUNE2`), a tuning
  knob on another channel, or a menu script that differs from what quadctl wrote.

## Not verified on hardware yet

Tested here against a simulated FC (MAVLink over UDP), a simulated ELRS module
(CRSF parameter frames) and a hand-written EdgeTX model file. Still assumed, to be
confirmed with `quadctl pull` on the real devices:

- EdgeTX YAML names: `mixData`/`destCh`/`srcRaw`, stick sources `Ail/Ele/Thr/Rud`,
  `moduleData.0.type: TYPE_CROSSFIRE`, `customFn` `PLAY_SCRIPT`, `semver` in `radio.yml`.
- The Pocket's switch names (`SA`-`SE` in `quad.yaml`; SE taken as a 2-position momentary) and EdgeTX's
  switch-position names in mix lines (`SC1` = middle, `SC2` = down, `SD1` = down), plus `MAX` and `REPLACE`.
- ELRS option text (`Dyn`, `100`) and the version bytes in the device-info frame.
- That function scripts can use `crossfireTelemetryPush/Pop` and share the
  `quadElrs` global with the Tools page.
- MAVLink FTP writing `/APM/quadctl.json` and `/APM/scripts/quadtune.lua` on this board, and `uploader.py` on macOS.
- The Pocket's dial as mix source `S1`, and the ELRS Lua listing the FC's CRSF
  menu under Other Devices. The menu API itself was checked against the
  Copter-4.7.2 source (`AP_CRSF_SCRIPTING_ENABLED` holds for this board), not run.
- The Pocket's MCU (STM32F4) for the DFU check, and the EdgeTX `.bin` start address.

## Tests

```sh
cd tools/quadctl
pip install -e '.[test]'
pytest
```
