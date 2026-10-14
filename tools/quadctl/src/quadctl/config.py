"""Load and validate quad.yaml."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

# ArduCopter FLTMODEn values (ArduCopter/Parameters.cpp, Copter-4.7.2).
COPTER_MODES = {
    "Stabilize": 0, "Acro": 1, "AltHold": 2, "Auto": 3, "Guided": 4,
    "Loiter": 5, "RTL": 6, "Circle": 7, "Land": 9, "Drift": 11, "Sport": 13,
    "Flip": 14, "AutoTune": 15, "PosHold": 16, "Brake": 17, "Throw": 18,
    "Smart_RTL": 21, "Auto RTL": 27,
}

# RCx_OPTION aux functions quad.yaml may use (RC_Channel.cpp, Copter-4.7.2).
# Fence (11) is deliberately absent: no switch may touch the fence.
AUX_OPTIONS = {"Brake": 33}

CHANNEL_ORDERS = {"AETR", "TAER", "AERT", "RETA"}
FAILSAFE_ACTIONS = {"rtl", "land"}
FENCE_TYPES = {"altitude": 1, "circle": 2, "polygon": 4}


class ConfigError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass
class Switch:
    role: str
    channel: int | None
    switch: str
    positions: int
    modes: list[str] = field(default_factory=list)


@dataclass
class QuadConfig:
    raw: dict[str, Any]
    path: Path | None
    digest: str

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    @property
    def switches(self) -> dict[str, Switch]:
        out = {}
        for role, s in self.raw["switches"].items():
            if role == "overrides":
                continue
            ch = s.get("channel")
            out[role] = Switch(role, int(ch) if ch is not None else None, str(s["switch"]),
                               int(s["positions"]), list(s.get("modes", [])))
        return out

    @property
    def overrides(self) -> list[Switch]:
        """Mode overrides, lowest priority first (a later one wins)."""
        return [Switch(f"override{i}", None, str(s["switch"]), int(s["positions"]), list(s["modes"]))
                for i, s in enumerate(self.raw["switches"].get("overrides") or [])]

    @property
    def aux(self) -> list[dict]:
        return list(self.raw.get("aux") or [])

    @property
    def elrs(self) -> dict[str, str]:
        return {str(k): str(v) for k, v in (self.raw.get("elrs") or {}).items()}


def _yaml() -> YAML:
    y = YAML(typ="safe")
    return y


def load(path: str | Path) -> QuadConfig:
    path = Path(path)
    text = path.read_bytes()
    return loads(text, path)


def loads(text: bytes | str, path: Path | None = None) -> QuadConfig:
    if isinstance(text, str):
        text = text.encode()
    raw = _yaml().load(text)
    if not isinstance(raw, dict):
        raise ConfigError(["quad.yaml: top level must be a mapping"])
    validate(raw)
    return QuadConfig(raw=raw, path=path, digest=hashlib.sha256(text).hexdigest())


def _need(raw: dict, dotted: str, errors: list[str], kind=None) -> Any:
    cur: Any = raw
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            errors.append(f"missing {dotted}")
            return None
        cur = cur[part]
    if kind is not None and cur is not None and not isinstance(cur, kind):
        errors.append(f"{dotted}: expected {kind.__name__ if isinstance(kind, type) else kind}, got {cur!r}")
        return None
    return cur


def validate(raw: dict) -> None:
    e: list[str] = []
    if raw.get("version") != 1:
        e.append("version: only version 1 is supported")
    for k in ("firmware.ardupilot", "firmware.board", "firmware.edgetx", "firmware.elrs"):
        _need(raw, k, e, str)
    _need(raw, "model.name", e, str)
    order = _need(raw, "model.channel_order", e, str)
    if order and order not in CHANNEL_ORDERS:
        e.append(f"model.channel_order: {order} not one of {sorted(CHANNEL_ORDERS)}")

    sw = _need(raw, "switches", e, dict) or {}
    used: dict[int, str] = {}
    names: dict[str, str] = {}
    for role in ("arm", "mode"):
        if role not in sw:
            e.append(f"missing switches.{role}")
    entries = [(role, s) for role, s in sw.items() if role != "overrides"]
    ovr = sw.get("overrides") or []
    if not isinstance(ovr, list):
        e.append("switches.overrides: expected a list")
        ovr = []
    entries += [(f"overrides[{i}]", s) for i, s in enumerate(ovr)]
    for role, s in entries:
        is_override = role.startswith("overrides")
        if not is_override and role not in ("arm", "mode"):
            e.append(f"switches.{role}: unknown role (arm, mode, overrides)")
            continue
        if not isinstance(s, dict):
            e.append(f"switches.{role}: expected a mapping")
            continue
        ch = s.get("channel")
        if is_override:
            if ch is not None:
                e.append(f"switches.{role}: has no channel; overrides are mixed onto the mode channel")
        elif not isinstance(ch, int) or not 5 <= ch <= 16:
            e.append(f"switches.{role}.channel: must be 5..16 (1-4 are sticks)")
        elif ch in used:
            e.append(f"switches.{role}.channel: CH{ch} already used by {used[ch]}")
        else:
            used[ch] = role
        if s.get("positions") not in (2, 3):
            e.append(f"switches.{role}.positions: must be 2 or 3")
        name = s.get("switch")
        if not isinstance(name, str) or not re.fullmatch(r"S[A-Z]", name):
            e.append(f"switches.{role}.switch: EdgeTX switch name like SA")
        elif name in names:
            e.append(f"switches.{role}.switch: {name} already used by {names[name]}")
        else:
            names[name] = role
        if role == "arm":
            continue
        modes = s.get("modes") or []
        if len(modes) != s.get("positions"):
            e.append(f"switches.{role}.modes: one mode per switch position")
        for i, m in enumerate(modes):
            if is_override and i == 0:
                if m != "Fly":
                    e.append(f"switches.{role}.modes: first position must be Fly (the switch below it decides)")
            elif m not in COPTER_MODES:
                e.append(f"switches.{role}.modes: unknown ArduCopter mode {m!r}")
    extra = sum(max(len(s.get("modes") or []) - 1, 0) for s in ovr if isinstance(s, dict))
    if extra + 3 > 6:
        e.append(f"switches.overrides: {extra} override modes plus the mode switch need more than ArduPilot's 6 FLTMODE slots")
    if "arm" in sw and isinstance(sw["arm"], dict):
        if sw["arm"].get("channel") != 5:
            e.append("switches.arm.channel: ELRS treats CH5 (AUX1) as the arm channel; keep arm on CH5")
        if sw["arm"].get("positions") != 2:
            e.append("switches.arm.positions: arm needs a 2-position switch")

    aux = raw.get("aux") or []
    if not isinstance(aux, list):
        e.append("aux: expected a list")
        aux = []
    for i, a in enumerate(aux):
        where = f"aux[{i}]"
        if not isinstance(a, dict):
            e.append(f"{where}: expected a mapping")
            continue
        ch = a.get("channel")
        if not isinstance(ch, int) or not 5 <= ch <= 16:
            e.append(f"{where}.channel: must be 5..16")
        elif ch in used:
            e.append(f"{where}.channel: CH{ch} already used by {used[ch]}")
        else:
            used[ch] = where
        name = a.get("switch")
        if not isinstance(name, str) or not re.fullmatch(r"S[A-Z]", name):
            e.append(f"{where}.switch: EdgeTX switch name like SE")
        elif name in names:
            e.append(f"{where}.switch: {name} already used by {names[name]}")
        else:
            names[name] = where
        if a.get("option") not in AUX_OPTIONS:
            e.append(f"{where}.option: one of {sorted(AUX_OPTIONS)}")
        off = a.get("disabled_by")
        if off is not None and (not isinstance(off, str) or not re.fullmatch(r"S[A-Z]\d", off)):
            e.append(f"{where}.disabled_by: a switch position like SD1")

    if _need(raw, "rx.protocol", e, str) not in (None, "crsf"):
        e.append("rx.protocol: only crsf is supported (security rule: plain CRSF)")
    ser = _need(raw, "rx.serial", e, int)
    if ser is not None and not 1 <= ser <= 8:
        e.append("rx.serial: SERIAL1..SERIAL8")

    cells = _need(raw, "battery.cells", e, int)
    cap = _need(raw, "battery.capacity_mah", e, int)
    low = _need(raw, "battery.low_volt_per_cell", e, (int, float))
    crt = _need(raw, "battery.critical_volt_per_cell", e, (int, float))
    if low is not None and crt is not None and not crt < low:
        e.append("battery: critical_volt_per_cell must be below low_volt_per_cell")
    if cells is not None and not 1 <= cells <= 12:
        e.append("battery.cells: 1..12")
    if cap is not None and cap <= 0:
        e.append("battery.capacity_mah: must be positive")
    if raw.get("battery", {}).get("monitor") not in ("pm02_v3",):
        e.append("battery.monitor: only pm02_v3 is supported")

    for k in ("rc", "battery_low", "battery_critical"):
        v = _need(raw, f"failsafe.{k}", e, str)
        if v is not None and v not in FAILSAFE_ACTIONS:
            e.append(f"failsafe.{k}: one of {sorted(FAILSAFE_ACTIONS)}")

    _need(raw, "fence.enable", e, bool)
    for t in _need(raw, "fence.type", e, list) or []:
        if t not in FENCE_TYPES:
            e.append(f"fence.type: unknown {t!r}")
        if t == "polygon":
            e.append("fence.type: polygon fences aren't supported yet")
    _need(raw, "fence.alt_max_m", e, (int, float))
    _need(raw, "fence.radius_m", e, (int, float))
    if _need(raw, "fence.action", e, str) not in (None, "rtl", "land", "report"):
        e.append("fence.action: rtl, land or report")

    elrs = raw.get("elrs") or {}
    if not isinstance(elrs, dict):
        e.append("elrs: expected a mapping of field label to option text")
    else:
        lm = elrs.get("Link Mode")
        if lm is not None and str(lm) != "Normal":
            e.append("elrs.Link Mode: must be Normal (security rule: no MAVLink over ELRS)")
        for k, v in elrs.items():
            if any(c in f"{k}{v}" for c in "=\n"):
                e.append(f"elrs.{k}: '=' and newlines aren't allowed")
    if e:
        raise ConfigError(e)
