"""quad.yaml -> desired state for each target. Pure: no I/O."""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

from .config import AUX_OPTIONS, COPTER_MODES, FENCE_TYPES, TUNE_PARAMS, QuadConfig

# ArduPilot RCx_OPTION values (RC_Channel.cpp, Copter-4.7.2).
RC_OPTION_ARMDISARM = 153
RC_OPTION_LAND = 18
RC_OPTION_RTL = 4
RC_OPTION_ACRO = 52
RC_OPTION_FENCE = 11
RC_OPTION_TUNING = 219
RC_OPTION_TUNING2 = 220

# Params the FC tuning menu may set in RAM (checked by rule_tuning, not as drift).
TUNE_MENU_PARAMS = ("TUNE", "TUNE_MIN", "TUNE_MAX")
TUNE_SCRIPT = "quadtune.lua"
TUNE_MARKER = "local TARGETS = {} -- quadctl:targets"

# RC_OPTIONS bits (RC_Channels_VarInfo.h, Copter-4.7.2).
RC_OPT_CRSF_PASSTHROUGH = 1 << 8
RC_OPT_LQ_AS_RSSI = 1 << 11
RC_OPT_ELRS_420K = 1 << 13
RC_OPTIONS_STOCK = 32  # stock default; used only when the FC's value is unknown

SERIAL_PROTOCOL_RCIN = 23
SERIAL_PROTOCOL_MAVLINK = (1, 2)

# FLTMODE_CH PWM bands (ArduCopter/Parameters.cpp): slot n is used when
# pwm <= upper[n-1]; slot 6 is everything above 1749.
FLTMODE_UPPER = [1230, 1360, 1490, 1620, 1749]

STICKS = {"A": "roll", "E": "pitch", "T": "throttle", "R": "yaw"}

FS_THR = {"rtl": 1, "land": 3}
BATT_FS = {"rtl": 2, "land": 1}
FENCE_ACTION = {"report": 0, "rtl": 1, "land": 2, "smartrtl": 3, "brake": 4}  # 3 = SmartRTL or RTL or Land


def pct_to_pwm(pct: float) -> int:
    """EdgeTX channel percent -> pulse width as ArduPilot sees it over CRSF.

    -100% .. +100% maps to 988 .. 2012 us (ELRS / CRSF scaling).
    """
    return round(1500 + pct * 5.12)


def fltmode_slot(pwm: int) -> int:
    for i, upper in enumerate(FLTMODE_UPPER):
        if pwm <= upper:
            return i + 1
    return 6


def band_margin(pwm: int, slot_modes: dict[int, int] | None = None) -> int:
    """Distance in us from pwm to the nearest FLTMODE band edge that changes mode.

    Edges between two slots holding the same mode don't count, which is why
    compile_config() fills every slot: the centre position (1500 us) sits
    only 10 us above the 1490 edge, but slots 3 and 4 hold the same mode.
    """
    edges = [
        e for i, e in enumerate(FLTMODE_UPPER, start=1)
        if slot_modes is None or slot_modes.get(i) != slot_modes.get(i + 1)
    ]
    return min((abs(pwm - e) for e in edges), default=10_000)


SWITCH_RAW = {2: [-100, 100], 3: [-100, 0, 100]}

# Channel percent that lands in the middle of each FLTMODE slot.
SLOT_PCT = [-65, -40, -15, 11, 36, 100]


@dataclass
class Mix:
    channel: int               # 1-based
    source: str                # EdgeTX source: switch name (SA), MAX, I0...
    weight: float = 100
    offset: float = 0
    swtch: str | None = None   # line only active in this switch position, e.g. SC1
    mltpx: str = "ADD"         # ADD or REPLACE

    def key(self):
        return (self.source, float(self.weight), float(self.offset), self.swtch, self.mltpx)


def parse_position(swtch: str) -> tuple[str, int] | None:
    m = re.fullmatch(r"(S[A-Z])(\d)", swtch or "")
    return (m.group(1), int(m.group(2))) if m else None


def channel_pct(lines: list[Mix], positions: dict[str, tuple[int, int]]) -> float:
    """Evaluate an EdgeTX mixer channel. positions: switch -> (position, count)."""
    acc = 0.0
    for m in lines:
        if m.swtch:
            want = parse_position(m.swtch)
            if want is None or positions.get(want[0], (0, 0))[0] != want[1]:
                continue
        if m.source == "MAX":
            src = 100.0
        elif m.source in positions:
            pos, count = positions[m.source]
            src = SWITCH_RAW[count][pos]
        else:
            src = 0.0
        value = src * m.weight / 100 + m.offset
        acc = value if m.mltpx == "REPLACE" else acc + value
    return max(-100.0, min(100.0, acc))


@dataclass
class Desired:
    fc_params: dict[str, float] = field(default_factory=dict)
    # bitmask params where quadctl owns only some bits: name -> (mask, bits)
    fc_bits: dict[str, tuple[int, int]] = field(default_factory=dict)
    radio_mixes: list[Mix] = field(default_factory=list)
    # every (switch positions, expected flight mode) the mode channel must produce
    mode_outputs: list[tuple[dict[str, tuple[int, int]], str]] = field(default_factory=list)
    radio_model: str = ""
    # transmitter tuning targets the FC menu may pick: {name, tune, min, max, param}
    tune_targets: list[dict] = field(default_factory=list)
    elrs: dict[str, str] = field(default_factory=dict)

    def owned_params(self) -> set[str]:
        return set(self.fc_params) | set(self.fc_bits)

    def resolve_params(self, current: dict[str, float] | None = None) -> dict[str, float]:
        """Full desired values, with owned bits merged into current values."""
        out = dict(self.fc_params)
        for name, (mask, bits) in self.fc_bits.items():
            base = int((current or {}).get(name, RC_OPTIONS_STOCK if name == "RC_OPTIONS" else 0))
            out[name] = float((base & ~mask) | bits)
        return out


def compile_config(cfg: QuadConfig) -> Desired:
    d = Desired(radio_model=cfg["model"]["name"], elrs=cfg.elrs)
    p = d.fc_params

    # Sticks.
    for i, letter in enumerate(cfg["model"]["channel_order"], start=1):
        p[f"RCMAP_{STICKS[letter].upper()}"] = i

    # Switches.
    sw = cfg.switches
    arm, mode = sw["arm"], sw["mode"]
    p[f"RC{arm.channel}_OPTION"] = RC_OPTION_ARMDISARM
    p[f"RC{mode.channel}_OPTION"] = 0
    p["FLTMODE_CH"] = mode.channel
    d.radio_mixes.append(Mix(arm.channel, arm.switch))
    d.radio_mixes.extend(mode_mixes(mode, cfg.overrides))
    d.mode_outputs = mode_outputs(mode, cfg.overrides)
    lines = [m for m in d.radio_mixes if m.channel == mode.channel]
    pwms = [(pct_to_pwm(channel_pct(lines, pos)), name) for pos, name in d.mode_outputs]
    for a in cfg.aux:
        # Momentary/2-position switch, optionally forced low while another
        # switch position is active (e.g. no Brake while in Acro).
        p[f"RC{a['channel']}_OPTION"] = AUX_OPTIONS[a["option"]]
        d.radio_mixes.append(Mix(a["channel"], a["switch"]))
        if a.get("disabled_by"):
            d.radio_mixes.append(Mix(a["channel"], "MAX", -100, 0, a["disabled_by"], "REPLACE"))
    tun = cfg.tuning
    if tun:
        # S1 dial straight onto its channel; the FC applies it to TUNE's target.
        # TUNE starts Off (and MIN = MAX turns the dial off too); the FC menu
        # script picks a target in RAM only.
        k = tun["knob"]
        p[f"RC{k['channel']}_OPTION"] = RC_OPTION_TUNING
        d.radio_mixes.append(Mix(k["channel"], k["source"]))
        p.update({"TUNE": 0, "TUNE_MIN": 0, "TUNE_MAX": 0, "TUNE2": 0, "SCR_ENABLE": 1})
        d.tune_targets = [
            {"name": t["name"], "tune": int(t["tune"]), "min": float(t["min"]), "max": float(t["max"]),
             "param": TUNE_PARAMS[t["tune"]]}
            for t in tun["targets"]
        ]
    centers = [1165, 1295, 1425, 1555, 1685, 1875]
    for slot in range(1, 7):
        # Every slot gets the mode of the nearest output, so a slightly-off
        # PWM still lands on an intended mode; unused slots never hold a
        # mode nobody asked for.
        _, name = min(pwms, key=lambda x: abs(x[0] - centers[slot - 1]))
        p[f"FLTMODE{slot}"] = COPTER_MODES[name]

    # Receiver.
    rx = cfg["rx"]
    p[f"SERIAL{rx['serial']}_PROTOCOL"] = SERIAL_PROTOCOL_RCIN
    mask = RC_OPT_ELRS_420K | RC_OPT_LQ_AS_RSSI | RC_OPT_CRSF_PASSTHROUGH
    bits = 0
    if rx.get("baud_420k"):
        bits |= RC_OPT_ELRS_420K
    if rx.get("lq_as_rssi"):
        bits |= RC_OPT_LQ_AS_RSSI
        p["RSSI_TYPE"] = 3
    if (cfg.raw.get("telemetry") or {}).get("passthrough"):
        bits |= RC_OPT_CRSF_PASSTHROUGH
    d.fc_bits["RC_OPTIONS"] = (mask, bits)

    # Battery (PM02 V3: analog current on the Current pad; voltage from VBAT).
    b = cfg["battery"]
    p["BATT_MONITOR"] = 4
    p["BATT_VOLT_PIN"] = 12
    p["BATT_CURR_PIN"] = 13
    if b.get("amp_per_volt") is not None:
        p["BATT_AMP_PERVLT"] = float(b["amp_per_volt"])
    p["BATT_CAPACITY"] = b["capacity_mah"]
    p["BATT_LOW_VOLT"] = round(b["cells"] * b["low_volt_per_cell"], 2)
    p["BATT_CRT_VOLT"] = round(b["cells"] * b["critical_volt_per_cell"], 2)
    p["MOT_BAT_CURR_MAX"] = b["current_max_a"]

    fs = cfg["failsafe"]
    p["FS_THR_ENABLE"] = FS_THR[fs["rc"]]
    p["BATT_FS_LOW_ACT"] = BATT_FS[fs["battery_low"]]
    p["BATT_FS_CRT_ACT"] = BATT_FS[fs["battery_critical"]]

    f = cfg["fence"]
    p["FENCE_ENABLE"] = 1 if f["enable"] else 0
    p["FENCE_TYPE"] = sum(FENCE_TYPES[t] for t in f["type"])
    p["FENCE_ALT_MAX"] = f["alt_max_m"]
    p["FENCE_RADIUS"] = f["radius_m"]
    p["FENCE_ACTION"] = FENCE_ACTION[f["action"]]
    avoid = f.get("avoid")
    if avoid:
        # Push back from the fence before it's hit (position modes only).
        d.fc_bits["AVOID_ENABLE"] = (1, 1)  # bit 0: UseFence
        p["AVOID_MARGIN"] = avoid["margin_m"]
        p["AVOID_BACKUP_SPD"] = avoid["backup_speed_ms"]

    d.fc_params = {k: float(v) for k, v in p.items()}
    return d


def mode_slots(mode, overrides) -> tuple[list[int], list[list[int]]]:
    """FLTMODE slots for the mode switch positions, and for each override's
    non-Fly positions (packed at the top, in order)."""
    base = [1, 2, 3] if mode.positions == 3 else [1, 3]
    k = sum(len(o.modes) - 1 for o in overrides)
    slot = 7 - k
    over = []
    for o in overrides:
        over.append(list(range(slot, slot + len(o.modes) - 1)))
        slot += len(o.modes) - 1
    return base, over


def mode_mixes(mode, overrides) -> list[Mix]:
    """Mode switch on the mode channel, with override switches REPLACEing it.

    The mode switch line puts each position in the middle of its slot (one
    linear line: weight 25, offset -40 gives -65/-40/-15 %). Each override
    position past the first (Fly) replaces the channel with a fixed value.
    EdgeTX runs the lines in order and the last active REPLACE wins, so a
    later override beats an earlier one, whatever order they were flipped in.
    """
    base, over = mode_slots(mode, overrides)
    lo, hi = SLOT_PCT[base[0] - 1], SLOT_PCT[base[-1] - 1]
    weight, offset = (hi - lo) / 2, (hi + lo) / 2
    out = [Mix(mode.channel, mode.switch, weight, offset)]
    for o, slots in zip(overrides, over):
        for j, slot in enumerate(slots, start=1):
            out.append(Mix(mode.channel, "MAX", SLOT_PCT[slot - 1], 0, f"{o.switch}{j}", "REPLACE"))
    return out


def mode_outputs(mode, overrides) -> list[tuple[dict[str, tuple[int, int]], str]]:
    """Every combination of switch positions and the mode it must select."""
    out = []
    ranges = [range(mode.positions)] + [range(o.positions) for o in overrides]
    for combo in itertools.product(*ranges):
        pos = {mode.switch: (combo[0], mode.positions)}
        name = mode.modes[combo[0]]
        for o, p in zip(overrides, combo[1:]):
            pos[o.switch] = (p, o.positions)
            if p:
                name = o.modes[p]
        out.append((pos, name))
    return out


def tune_script(template: str, targets: list[dict]) -> str:
    """The FC menu script with quad.yaml's targets filled in."""
    if TUNE_MARKER not in template:
        raise ValueError(f"{TUNE_SCRIPT}: marker line missing")
    rows = ",\n".join(
        f'  {{ name = "{t["name"]}", tune = {t["tune"]}, min = {t["min"]!r}, max = {t["max"]!r}, param = "{t["param"]}" }}'
        for t in targets)
    return template.replace(TUNE_MARKER, "local TARGETS = { -- written by quadctl from quad.yaml\n" + rows + "\n}", 1)


def defaults_file(d: Desired, current: dict[str, float] | None = None) -> str:
    """Text for ArduPilot's embedded defaults (same format as a .parm file)."""
    params = d.resolve_params(current)
    lines = [f"{k} {_fmt(v)}" for k, v in sorted(params.items())]
    return "\n".join(lines) + "\n"


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else repr(float(v))
