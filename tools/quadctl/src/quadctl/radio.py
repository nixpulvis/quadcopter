"""The Pocket's SD card over USB storage: EdgeTX model files and our scripts.

EdgeTX reads its YAML with its own small parser, not a full YAML library, so
quadctl never re-serialises a whole file. It parses with a YAML library to
read, and edits the text of the few entries it owns in place, keeping
EdgeTX's own layout for everything else.

Key names below come from EdgeTX's YAML model format as far as I know it
(marked "assumed"); milestone 0 checks them against a file pulled from the
Pocket, and `apply` refuses a model file whose layout it doesn't recognise.
"""

from __future__ import annotations

import glob
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

from .compile import Mix

STICK_SOURCES = {"Ail": "roll", "Ele": "pitch", "Thr": "throttle", "Rud": "yaw"}  # assumed
BOOT_SCRIPT = "qelrs"
SCRIPT_DIR = "SCRIPTS/QUAD"
ELRS_CFG = f"{SCRIPT_DIR}/elrs.cfg"
ELRS_STATE = f"{SCRIPT_DIR}/state.txt"
STAMP = f"{SCRIPT_DIR}/stamp.txt"


class RadioError(Exception):
    pass


def find_volume(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        if not (p / "RADIO" / "radio.yml").exists():
            raise RadioError(f"{p} doesn't look like an EdgeTX SD card (no RADIO/radio.yml)")
        return p
    found = [Path(p).parent.parent for p in
             glob.glob("/Volumes/*/RADIO/radio.yml") + glob.glob("/media/*/*/RADIO/radio.yml")]
    found = [p for p in found if (p / "MODELS").is_dir()]
    if not found:
        raise RadioError("Pocket not found: plug it in and pick USB Storage on the radio")
    if len(found) > 1:
        raise RadioError(f"several EdgeTX cards mounted ({', '.join(map(str, found))}); pass --volume")
    return found[0]


def _load(text: str) -> dict:
    data = YAML(typ="safe").load(text)
    return data if isinstance(data, dict) else {}


def edgetx_version(volume: Path) -> str | None:
    data = _load((volume / "RADIO" / "radio.yml").read_text())
    v = data.get("semver")
    return str(v) if v is not None else None


@dataclass
class ModelFile:
    path: Path
    text: str

    @property
    def data(self) -> dict:
        return _load(self.text)

    @property
    def name(self) -> str | None:
        h = self.data.get("header") or {}
        return h.get("name")

    def check_layout(self) -> list[str]:
        """Reasons this file doesn't match the layout quadctl knows how to edit."""
        d = self.data
        problems = []
        if "semver" not in d:
            problems.append("no semver key")
        if not isinstance(d.get("header"), dict):
            problems.append("no header mapping")
        mixes = d.get("mixData")
        if mixes is not None and not isinstance(mixes, list):
            problems.append("mixData isn't a list")
        for m in mixes or []:
            if not isinstance(m, dict) or "destCh" not in m or "srcRaw" not in m:
                problems.append("mixData entry without destCh/srcRaw")
                break
        return problems

    # --- reading --------------------------------------------------------

    def mixes(self) -> dict[int, list[Mix]]:
        out: dict[int, list[Mix]] = {}
        for m in self.data.get("mixData") or []:
            ch = int(m["destCh"]) + 1
            sw = m.get("swtch")
            sw = None if sw in (None, "", "NONE") else str(sw)
            out.setdefault(ch, []).append(
                Mix(ch, str(m["srcRaw"]), _num(m.get("weight", 100)), _num(m.get("offset", 0)),
                    sw, str(m.get("mltpx", "ADD"))))
        return out

    def sticks(self) -> dict[int, str]:
        d = self.data
        inputs: dict[int, str] = {}
        for e in d.get("expoData") or []:
            src = str(e.get("srcRaw"))
            if src in STICK_SOURCES and "chn" in e:
                inputs.setdefault(int(e["chn"]), STICK_SOURCES[src])
        out = {}
        for ch, lines in self.mixes().items():
            if ch > 4 or len(lines) != 1:
                continue
            src = lines[0].source
            if src in STICK_SOURCES:
                out[ch] = STICK_SOURCES[src]
            elif re.fullmatch(r"I\d+", src) and int(src[1:]) in inputs:
                out[ch] = inputs[int(src[1:])]
        return out

    def module_is_crsf(self) -> bool | None:
        mods = self.data.get("moduleData") or {}
        internal = mods.get(0) if isinstance(mods, dict) else None
        if not isinstance(internal, dict) or "type" not in internal:
            return None
        return "CROSSFIRE" in str(internal["type"]).upper()  # assumed: TYPE_CROSSFIRE

    def has_boot_script(self) -> bool:
        fns = self.data.get("customFn") or {}
        items = fns.values() if isinstance(fns, dict) else fns
        for f in items:
            if isinstance(f, dict) and "SCRIPT" in str(f.get("func", "")).upper() \
                    and BOOT_SCRIPT in str(f.get("def", "")):
                return True
        return False

    # --- editing --------------------------------------------------------

    def plan_mixes(self, want: list[Mix]) -> list[str]:
        """Human-readable changes set_mixes() would make.

        quadctl owns every channel it has mixes for: all of that channel's
        lines are replaced, lines on other channels are left alone.
        """
        have = self.mixes()
        out = []
        for ch, lines in _by_channel(want).items():
            cur = have.get(ch, [])
            if [m.key() for m in cur] != [m.key() for m in lines]:
                old = "; ".join(_describe(m) for m in cur) or "nothing"
                new = "; ".join(_describe(m) for m in lines)
                out.append(f"CH{ch}: {old} -> {new}")
        return out

    def set_mixes(self, want: list[Mix]) -> None:
        if not self.plan_mixes(want):
            return
        lines = self.text.splitlines(keepends=True)
        start, end = _block(lines, "mixData")
        if start is None:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append("mixData:\n")
            start, end = len(lines) - 1, len(lines)
        owned = _by_channel(want)
        chunks: list[tuple[int, list[str]]] = []
        for s, e in _entries(lines, start + 1, end):
            ch = _entry_value(lines[s:e], "destCh")
            ch = int(ch) + 1 if ch is not None else -1
            if ch not in owned:
                chunks.append((ch, lines[s:e]))
        for ch, mixes in owned.items():
            for m in mixes:
                chunks.append((ch, _entry_text(m)))
        # EdgeTX keeps mixes sorted by channel; sorted() is stable, so line
        # order inside a channel (ADD before REPLACE) is kept.
        chunks.sort(key=lambda x: x[0])
        lines[start + 1:end] = [l for _, chunk in chunks for l in chunk]
        self.text = "".join(lines)

    def save(self) -> None:
        self.path.write_text(self.text)


def _by_channel(mixes: list[Mix]) -> dict[int, list[Mix]]:
    out: dict[int, list[Mix]] = {}
    for m in mixes:
        out.setdefault(m.channel, []).append(m)
    return out


def _describe(m: Mix) -> str:
    text = f"{m.source} {m.weight:g}%"
    if m.offset:
        text += f" {m.offset:+g}"
    if m.swtch:
        text += f" when {m.swtch}"
    if m.mltpx != "ADD":
        text += f" {m.mltpx}"
    return text


def _entry_text(m: Mix) -> list[str]:
    out = ["  -\n", f"    destCh: {m.channel - 1}\n", f"    srcRaw: {m.source}\n",
           f"    weight: {_fmt(m.weight)}\n", f"    offset: {_fmt(m.offset)}\n"]
    if m.swtch:
        out.append(f'    swtch: "{m.swtch}"\n')
    out.append(f"    mltpx: {m.mltpx}\n")
    return out


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        raise RadioError(f"mix value {v!r} isn't a plain number (global variable?); quadctl can't check it")


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _block(lines: list[str], key: str) -> tuple[int | None, int]:
    for i, l in enumerate(lines):
        if l.rstrip("\n") == f"{key}:" or l.startswith(f"{key}: "):
            j = i + 1
            while j < len(lines) and (lines[j].startswith((" ", "-")) or not lines[j].strip()):
                j += 1
            return i, j
    return None, len(lines)


def _entries(lines: list[str], start: int, end: int) -> list[tuple[int, int]]:
    starts = [i for i in range(start, end) if re.match(r"^\s{0,2}-(\s|$)", lines[i])]
    return [(s, starts[k + 1] if k + 1 < len(starts) else end) for k, s in enumerate(starts)]


def _entry_value(entry: list[str], key: str) -> str | None:
    for l in entry:
        m = re.match(rf"^\s*(?:-\s+)?{key}:\s*(.*?)\s*$", l)
        if m:
            return m.group(1).strip('"')
    return None


def find_model(volume: Path, name: str) -> ModelFile:
    matches = []
    for p in sorted((volume / "MODELS").glob("*.yml")):
        mf = ModelFile(p, p.read_text())
        if mf.name == name:
            matches.append(mf)
    if not matches:
        raise RadioError(f"no EdgeTX model named {name!r}: create an empty model with that name on the radio once")
    if len(matches) > 1:
        raise RadioError(f"several models named {name!r}: {', '.join(m.path.name for m in matches)}")
    return matches[0]


# --- our files on the SD card ----------------------------------------------

def write_elrs_cfg(volume: Path, elrs: dict[str, str], reset: str | None = None) -> None:
    path = volume / ELRS_CFG
    path.parent.mkdir(parents=True, exist_ok=True)
    old = read_kv(path) if path.exists() else {}
    token = reset if reset is not None else old.get("reset", "0")
    lines = [f"reset={token}"] + [f"{k}={v}" for k, v in elrs.items()]
    path.write_text("\n".join(lines) + "\n")


def read_kv(path: Path) -> dict[str, str]:
    out = {}
    for line in Path(path).read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


@dataclass
class ElrsState:
    tx_version: str | None
    rx_version: str | None
    actual: dict[str, str]
    applied: dict[str, str]
    overrides: dict[str, str]


def read_elrs_state(volume: Path) -> ElrsState | None:
    path = volume / ELRS_STATE
    if not path.exists():
        return None
    kv = read_kv(path)
    pick = lambda prefix: {k[len(prefix):]: v for k, v in kv.items() if k.startswith(prefix)}
    return ElrsState(kv.get("tx_version"), kv.get("rx_version"),
                     pick("actual."), pick("applied."), pick("override."))


def install_scripts(volume: Path, src: Path) -> list[str]:
    """Copy radio/SCRIPTS from the repo onto the card. Returns changed paths."""
    changed = []
    for f in sorted(src.rglob("*.lua")):
        rel = f.relative_to(src.parent)
        dst = volume / rel
        if dst.exists() and dst.read_bytes() == f.read_bytes():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
        changed.append(str(rel))
    return changed


def scripts_pending(volume: Path, src: Path) -> list[str]:
    out = []
    for f in sorted(src.rglob("*.lua")):
        rel = f.relative_to(src.parent)
        dst = volume / rel
        if not dst.exists() or dst.read_bytes() != f.read_bytes():
            out.append(str(rel))
    return out
