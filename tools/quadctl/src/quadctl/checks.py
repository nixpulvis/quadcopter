"""Cross-device compatibility rules.

The same rules run on the desired state (from quad.yaml alone) and on the
state read back from the devices, so a hand edit in QGC or on the radio is
caught. Anything a rule can't see (device not connected) is skipped, not
assumed fine: `verify` reports what it could not check.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field

from . import compile as c
from .compile import Desired, Mix
from .config import COPTER_MODES, QuadConfig

# ArduPilot aux switch thresholds (RC_Channel.h AUX_PWM_TRIGGER_HIGH/LOW).
AUX_HIGH = 1800
AUX_LOW = 1200
BAND_MARGIN_US = 30
PARAM_TOL = 1e-3


@dataclass
class Finding:
    level: str   # "error", "warn" or "info"
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():5} {self.rule}: {self.message}"


@dataclass
class State:
    """What is (or should be) on the devices. None = not known."""
    fc_params: dict[str, float] | None = None
    fc_version: str | None = None
    fc_board: str | None = None
    radio_mixes: dict[int, list[Mix]] | None = None
    radio_sticks: dict[int, str] | None = None   # channel -> roll/pitch/throttle/yaw
    radio_module_crsf: bool | None = None
    radio_boot_script: bool | None = None
    edgetx_version: str | None = None
    elrs_tx: dict[str, str] | None = None
    elrs_tx_version: str | None = None
    elrs_rx_version: str | None = None
    elrs_overrides: dict[str, tuple[str, str]] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)


def desired_state(cfg: QuadConfig, d: Desired) -> State:
    mixes: dict[int, list[Mix]] = {}
    for m in d.radio_mixes:
        mixes.setdefault(m.channel, []).append(m)
    sticks = {i: c.STICKS[l] for i, l in enumerate(cfg["model"]["channel_order"], 1)}
    return State(
        fc_params=d.resolve_params(),
        radio_mixes=mixes,
        radio_sticks=sticks,
        radio_module_crsf=True,
        radio_boot_script=True,
        elrs_tx=dict(d.elrs),
    )


def run(cfg: QuadConfig, d: Desired, s: State) -> list[Finding]:
    out: list[Finding] = []
    for rule in RULES:
        rule(cfg, d, s, out)
    return out


def _p(s: State, name: str) -> float | None:
    if s.fc_params is None:
        return None
    return s.fc_params.get(name)


def _channel(s: State, ch: int, out: list[Finding], rule: str) -> list[Mix] | None:
    if s.radio_mixes is None:
        return None
    lines = s.radio_mixes.get(ch, [])
    if not lines:
        out.append(Finding("error", rule, f"radio CH{ch} has no mixes"))
        return None
    return lines


def rule_channel_order(cfg, d, s, out):
    want = {i: c.STICKS[l] for i, l in enumerate(cfg["model"]["channel_order"], 1)}
    if s.radio_sticks is not None:
        for ch, axis in want.items():
            got = s.radio_sticks.get(ch)
            if got != axis:
                out.append(Finding("error", "channel-order", f"radio CH{ch} is {got or 'unknown'}, expected {axis}"))
    for ch, axis in want.items():
        v = _p(s, f"RCMAP_{axis.upper()}")
        if v is not None and int(v) != ch:
            out.append(Finding("error", "channel-order", f"RCMAP_{axis.upper()}={int(v)}, radio sends {axis} on CH{ch}"))


def rule_arm(cfg, d, s, out):
    a = cfg.switches["arm"]
    v = _p(s, f"RC{a.channel}_OPTION")
    if v is not None and int(v) != c.RC_OPTION_ARMDISARM:
        out.append(Finding("error", "arm", f"RC{a.channel}_OPTION={int(v)}, expected {c.RC_OPTION_ARMDISARM} (Arm/Disarm)"))
    lines = _channel(s, a.channel, out, "arm")
    if not lines:
        return
    pwms = [c.pct_to_pwm(c.channel_pct(lines, {a.switch: (pos, 2)})) for pos in range(2)]
    if not (pwms[0] < AUX_LOW and pwms[1] > AUX_HIGH):
        out.append(Finding("error", "arm", f"arm switch {a.switch} sends {pwms} us; ArduPilot needs <{AUX_LOW} disarmed and >{AUX_HIGH} armed"))


def rule_aux(cfg, d, s, out):
    from .config import AUX_OPTIONS
    for a in cfg.aux:
        ch, opt = a["channel"], AUX_OPTIONS[a["option"]]
        v = _p(s, f"RC{ch}_OPTION")
        if v is not None and int(v) != opt:
            out.append(Finding("error", "aux", f"RC{ch}_OPTION={int(v)}, expected {opt} ({a['option']})"))
        lines = _channel(s, ch, out, "aux")
        if not lines:
            continue
        gate = c.parse_position(a.get("disabled_by") or "")
        counts = {x.switch: x.positions for x in [*cfg.switches.values(), *cfg.overrides]}
        for on in (0, 1):
            for gated in ((0, 1) if gate else (0,)):
                pos = {a["switch"]: (on, 2)}
                if gate:
                    pos[gate[0]] = (gate[1] if gated else 0, counts.get(gate[0], 3))
                pwm = c.pct_to_pwm(c.channel_pct(lines, pos))
                want_high = on and not gated
                if want_high and pwm <= AUX_HIGH or not want_high and pwm >= AUX_LOW:
                    state = f"{a['switch']} {'down' if on else 'up'}" + (f", {a['disabled_by']} active" if gated else "")
                    out.append(Finding("error", "aux", f"CH{ch} sends {pwm} us with {state}; {a['option']} should be {'on' if want_high else 'off'}"))


def _describe(pos: dict[str, tuple[int, int]]) -> str:
    names = {2: ["up", "down"], 3: ["up", "mid", "down"]}
    return ", ".join(f"{sw} {names[n][p]}" for sw, (p, n) in pos.items())


def rule_mode(cfg, d, s, out):
    m = cfg.switches["mode"]
    v = _p(s, "FLTMODE_CH")
    if v is not None and int(v) != m.channel:
        out.append(Finding("error", "mode", f"FLTMODE_CH={int(v)}, mode switch is on CH{m.channel}"))
    lines = _channel(s, m.channel, out, "mode")
    if not lines:
        return
    slot_modes = {}
    for slot in range(1, 7):
        got = _p(s, f"FLTMODE{slot}")
        slot_modes[slot] = int(got if got is not None else d.fc_params[f"FLTMODE{slot}"])
    for pos, mode in d.mode_outputs:
        pwm = c.pct_to_pwm(c.channel_pct(lines, pos))
        slot = c.fltmode_slot(pwm)
        where = f"{_describe(pos)} sends {pwm} us"
        margin = c.band_margin(pwm, slot_modes)
        if margin < BAND_MARGIN_US:
            out.append(Finding("error", "mode", f"{where}, only {margin} us from a FLTMODE band edge that changes mode"))
        got = slot_modes[slot]
        if got != COPTER_MODES[mode]:
            name = next((k for k, x in COPTER_MODES.items() if x == got), str(got))
            out.append(Finding("error", "mode", f"{where} = FLTMODE{slot} {name}, expected {mode}"))


def rule_switch_resolution(cfg, d, s, out):
    """ELRS Hybrid sends CH6-CH11 as 6-position values, which can't carry the
    mode channel's mixed outputs; Wide keeps them at full enough resolution."""
    sm = (s.elrs_tx or {}).get("Switch Mode")
    if sm is None or sm == "Wide":
        return
    lines = d.radio_mixes
    outputs = {round(c.channel_pct([x for x in lines if x.channel == cfg.switches["mode"].channel], pos))
               for pos, _ in d.mode_outputs}
    if len(outputs) > 3:
        out.append(Finding("error", "mode", f"ELRS Switch Mode {sm} can't carry {len(outputs)} distinct mode-channel values; use Wide"))


def rule_duplicate_options(cfg, d, s, out):
    if s.fc_params is None:
        return
    arm = cfg.switches["arm"].channel
    aux = {a["channel"] for a in cfg.aux}
    for ch in range(1, 17):
        v = s.fc_params.get(f"RC{ch}_OPTION")
        if v is None or ch == arm or ch in aux:
            continue
        if int(v) == c.RC_OPTION_ARMDISARM:
            out.append(Finding("error", "switches", f"RC{ch}_OPTION={int(v)} arms from a second channel"))
        elif int(v) in (c.RC_OPTION_LAND, c.RC_OPTION_RTL, c.RC_OPTION_ACRO):
            out.append(Finding("warn", "switches", f"RC{ch}_OPTION={int(v)} changes flight mode outside the CH6 mode channel; quad.yaml doesn't use it"))


def rule_rx(cfg, d, s, out):
    ser = cfg["rx"]["serial"]
    if s.radio_module_crsf is False:
        out.append(Finding("error", "rx", "radio internal module isn't set to CRSF"))
    if s.fc_params is None:
        return
    v = s.fc_params.get(f"SERIAL{ser}_PROTOCOL")
    if v is not None and int(v) != c.SERIAL_PROTOCOL_RCIN:
        out.append(Finding("error", "rx", f"SERIAL{ser}_PROTOCOL={int(v)}, expected 23 (RCIN)"))
    for n in range(0, 9):
        if n == ser:
            continue
        v = s.fc_params.get(f"SERIAL{n}_PROTOCOL")
        if v is not None and int(v) == c.SERIAL_PROTOCOL_RCIN:
            out.append(Finding("warn", "rx", f"SERIAL{n}_PROTOCOL is also RCIN"))
    mask, bits = d.fc_bits["RC_OPTIONS"]
    v = s.fc_params.get("RC_OPTIONS")
    if v is not None and (int(v) & mask) != bits:
        out.append(Finding("error", "rx", f"RC_OPTIONS={int(v)}: owned bits are {int(v) & mask:#x}, expected {bits:#x}"))


def _ratio_den(text: str) -> int | None:
    m = re.fullmatch(r"\s*1:(\d+)\s*", text or "")
    return int(m.group(1)) if m else None


def rule_telemetry(cfg, d, s, out):
    if not (cfg.raw.get("telemetry") or {}).get("passthrough"):
        return
    ratio = (s.elrs_tx or {}).get("Telem Ratio")
    if ratio is None:
        return
    den = _ratio_den(ratio)
    if den is None:
        out.append(Finding("warn", "telemetry", f"ELRS Telem Ratio {ratio!r}: passthrough telemetry wants a fixed 1:N ratio, 1:8 or faster"))
    elif den > 8:
        out.append(Finding("warn", "telemetry", f"ELRS Telem Ratio {ratio} is thin for passthrough telemetry; use 1:8 or faster"))


def rule_battery(cfg, d, s, out):
    if cfg["battery"].get("amp_per_volt") is None:
        out.append(Finding("warn", "battery", "battery.amp_per_volt is unset: current and mAh readings use the board default scale (17), not the PM02 V3"))


def rule_fence_usb_only(cfg, d, s, out):
    """Security rule: the fence is set over USB only; no RC switch may touch it."""
    if s.fc_params is None:
        return
    if "AVOID_ENABLE" in d.fc_bits:
        v = s.fc_params.get("AVOID_ENABLE")
        if v is not None and not int(v) & 1:
            out.append(Finding("error", "security-fence", "AVOID_ENABLE has the fence bit off: the quad won't back away from the fence"))
    for ch in range(1, 17):
        v = s.fc_params.get(f"RC{ch}_OPTION")
        if v is not None and int(v) == c.RC_OPTION_FENCE:
            out.append(Finding("error", "security-fence", f"RC{ch}_OPTION=11 lets a switch change the fence"))
    for name in ("FENCE_ENABLE", "FENCE_TYPE", "FENCE_ALT_MAX", "FENCE_RADIUS", "FENCE_ACTION",
                 "AVOID_MARGIN", "AVOID_BACKUP_SPD"):
        if name not in d.fc_params:
            continue
        v = s.fc_params.get(name)
        want = d.fc_params[name]
        if v is not None and abs(v - want) > PARAM_TOL:
            out.append(Finding("error", "security-fence", f"{name}={_f(v)}, quad.yaml says {_f(want)}"))


def rule_plain_crsf(cfg, d, s, out):
    """Security rule: ELRS stays plain CRSF (no MAVLink over the RC link)."""
    ser = cfg["rx"]["serial"]
    v = _p(s, f"SERIAL{ser}_PROTOCOL")
    if v is not None and int(v) in c.SERIAL_PROTOCOL_MAVLINK:
        out.append(Finding("error", "security-crsf", f"SERIAL{ser} (the RX port) speaks MAVLink"))
    lm = (s.elrs_tx or {}).get("Link Mode")
    if lm is not None and lm != "Normal":
        out.append(Finding("error", "security-crsf", f"ELRS Link Mode is {lm}, must be Normal"))


def rule_fc_drift(cfg, d, s, out):
    if s.fc_params is None:
        return
    for name, want in d.fc_params.items():
        if name.startswith(("FENCE_", "AVOID_")):
            continue  # reported by rule_fence_usb_only
        got = s.fc_params.get(name)
        if got is None:
            out.append(Finding("warn", "fc-params", f"{name} missing on the FC (wrong firmware?)"))
        elif abs(got - want) > PARAM_TOL:
            out.append(Finding("error", "fc-params", f"{name}={_f(got)}, quad.yaml says {_f(want)}"))


def rule_radio_boot(cfg, d, s, out):
    if s.radio_boot_script is False:
        out.append(Finding("warn", "elrs-boot", "model has no special function running Lua script qelrs; ELRS settings won't be applied (see README)"))
    for label, (actual, wanted) in s.elrs_overrides.items():
        out.append(Finding("warn", "elrs-override", f"{label} is {actual} on the module (set by hand), quad.yaml says {wanted}"))


def _ver_ok(version: str | None, pattern: str) -> bool:
    return version is None or fnmatch.fnmatch(version, pattern)


def rule_versions(cfg, d, s, out):
    fw = cfg["firmware"]
    if not _ver_ok(s.fc_version, fw["ardupilot"]):
        out.append(Finding("error", "versions", f"FC runs ArduCopter {s.fc_version}, quad.yaml wants {fw['ardupilot']}"))
    if s.fc_board is not None and s.fc_board.replace("_", "-") != fw["board"].replace("_", "-"):
        out.append(Finding("error", "versions", f"FC board is {s.fc_board}, quad.yaml says {fw['board']}"))
    if not _ver_ok(s.edgetx_version, fw["edgetx"]):
        out.append(Finding("error", "versions", f"Pocket runs EdgeTX {s.edgetx_version}, quad.yaml wants {fw['edgetx']}"))
    for who, v in (("TX module", s.elrs_tx_version), ("RP1", s.elrs_rx_version)):
        if not _ver_ok(v, fw["elrs"]):
            out.append(Finding("error", "versions", f"ELRS {who} runs {v}, quad.yaml wants {fw['elrs']}"))
    if s.elrs_tx_version and s.elrs_rx_version:
        if s.elrs_tx_version.split(".")[0] != s.elrs_rx_version.split(".")[0]:
            out.append(Finding("error", "versions", f"ELRS TX {s.elrs_tx_version} and RX {s.elrs_rx_version} have different major versions and won't link"))
        elif s.elrs_tx_version != s.elrs_rx_version:
            out.append(Finding("warn", "versions", f"ELRS TX {s.elrs_tx_version} and RX {s.elrs_rx_version} differ"))


def _f(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


RULES = [
    rule_versions,
    rule_channel_order,
    rule_arm,
    rule_mode,
    rule_switch_resolution,
    rule_aux,
    rule_duplicate_options,
    rule_rx,
    rule_telemetry,
    rule_battery,
    rule_fence_usb_only,
    rule_plain_crsf,
    rule_fc_drift,
    rule_radio_boot,
]
