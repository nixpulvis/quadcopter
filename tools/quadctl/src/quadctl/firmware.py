"""Firmware: the lock file, flash status, embedded FC defaults, flashing."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

CACHE = Path(os.environ.get("QUADCTL_CACHE", Path.home() / ".cache" / "quadctl"))

# Embedded defaults area in ArduPilot images (AP_Param.cpp; same layout
# Tools/scripts/apj_tool.py edits): "PARMDEF", 8 magic bytes, then
# uint16 max_len, uint16 length, then the defaults text.
PARMDEF = b"PARMDEF"
PARAM_MAGIC = bytes([0x55, 0x37, 0xF4, 0xA0, 0x38, 0x5D, 0x48, 0x5B])

REQUIRED = "FLASH REQUIRED"
STALE = "defaults stale"
OK = "ok"
UNKNOWN = "unknown"
UNPINNED = "unpinned"


class FirmwareError(Exception):
    pass


# --- lock file --------------------------------------------------------------

def load_lock(path: Path) -> dict:
    data = YAML(typ="rt").load(Path(path).read_text())
    return data or {}


def save_lock(path: Path, lock: dict) -> None:
    y = YAML(typ="rt")
    with open(path, "w") as f:
        y.dump(lock, f)


def fetch(url: str, sha256: str | None) -> Path:
    """Download (or reuse from cache) and verify against sha256 if given."""
    CACHE.mkdir(parents=True, exist_ok=True)
    if sha256:
        cached = CACHE / f"{sha256}{Path(url).suffix}"
        if cached.exists() and _sha(cached.read_bytes()) == sha256:
            return cached
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    digest = _sha(data)
    if sha256 and digest != sha256:
        raise FirmwareError(f"{url}: sha256 {digest} doesn't match firmware.lock ({sha256})")
    out = CACHE / f"{digest}{Path(url).suffix}"
    out.write_bytes(data)
    return out


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def lock_hashes(lock: dict) -> list[str]:
    """Fill missing sha256 (and the FC git hash) by downloading. Returns notes."""
    notes = []
    for chip, entry in lock.items():
        if not isinstance(entry, dict) or not entry.get("url"):
            continue
        if entry.get("sha256"):
            continue
        path = fetch(entry["url"], None)
        entry["sha256"] = _sha(path.read_bytes())
        notes.append(f"{chip}: sha256 {entry['sha256']}")
        if chip == "fc":
            entry["git_hash"] = Apj.load(path).git_hash
            notes.append(f"fc: git hash {entry['git_hash']}")
    return notes


# --- .apj and embedded defaults ---------------------------------------------

@dataclass
class Apj:
    meta: dict
    image: bytes

    @classmethod
    def load(cls, path: Path) -> "Apj":
        meta = json.loads(Path(path).read_text())
        return cls(meta, zlib.decompress(base64.b64decode(meta["image"])))

    @property
    def git_hash(self) -> str | None:
        return self.meta.get("git_identity")

    def save(self, path: Path) -> None:
        meta = dict(self.meta)
        meta["image"] = base64.b64encode(zlib.compress(self.image, 9)).decode("ascii")
        meta["image_size"] = len(self.image)
        Path(path).write_text(json.dumps(meta, indent=4))

    def _defaults_offset(self) -> int:
        start = 0
        while True:
            i = self.image.find(PARMDEF, start)
            if i < 0:
                raise FirmwareError("no embedded-defaults area in this firmware")
            if self.image[i + 8:i + 16] == PARAM_MAGIC:
                return i
            start = i + 8

    def defaults(self) -> str:
        o = self._defaults_offset()
        _max, length = struct.unpack("<HH", self.image[o + 16:o + 20])
        return self.image[o + 20:o + 20 + length].decode("ascii").replace("\r", "")

    def set_defaults(self, text: str) -> None:
        data = text.encode("ascii")
        o = self._defaults_offset()
        max_len, _ = struct.unpack("<HH", self.image[o + 16:o + 20])
        if len(data) > max_len:
            raise FirmwareError(f"defaults are {len(data)} bytes; this firmware has room for {max_len}")
        self.image = self.image[:o + 18] + struct.pack("<H", len(data)) + data + self.image[o + 20 + len(data):]


def defaults_digest(text: str) -> str:
    return _sha(text.encode())


# --- status -----------------------------------------------------------------

@dataclass
class ChipStatus:
    chip: str
    status: str
    detail: str

    def __str__(self) -> str:
        return f"{self.chip:8} {self.status:15} {self.detail}"


def fc_status(lock: dict, version: str | None, git_hash: str | None,
              stamp: dict | None, want_defaults: str | None) -> ChipStatus:
    e = lock.get("fc") or {}
    if not e.get("version"):
        return ChipStatus("fc", UNPINNED, "no fc entry in firmware.lock")
    if version is None:
        return ChipStatus("fc", UNKNOWN, "FC not connected")
    if version != e["version"]:
        return ChipStatus("fc", REQUIRED, f"runs {version}, lock says {e['version']}")
    locked_hash = (e.get("git_hash") or "")[:8]
    if locked_hash and git_hash and not locked_hash.startswith(git_hash[:8]):
        return ChipStatus("fc", REQUIRED, f"runs build {git_hash}, lock says {locked_hash}")
    if want_defaults is not None:
        have = (stamp or {}).get("defaults_sha256")
        if have != defaults_digest(want_defaults):
            why = "no stamp from quadctl" if have is None else "quad.yaml changed since the last flash"
            return ChipStatus("fc", STALE, f"embedded defaults out of date ({why}); params are still applied normally")
    return ChipStatus("fc", OK, f"ArduCopter {version}")


def simple_status(chip: str, lock: dict, running: str | None, how: str) -> ChipStatus:
    want = (lock.get(chip) or {}).get("version")
    if not want:
        return ChipStatus(chip, UNPINNED, f"no version in firmware.lock ({how})")
    if running is None:
        return ChipStatus(chip, UNKNOWN, f"can't read the running version ({how})")
    if running != str(want):
        return ChipStatus(chip, REQUIRED, f"runs {running}, lock says {want}")
    return ChipStatus(chip, OK, running)


def elrs_status(lock: dict, tx: str | None, rx: str | None) -> list[ChipStatus]:
    want = (lock.get("elrs") or {}).get("version")
    out = [simple_status("elrs", lock, tx, "TX module, from the boot script")]
    out[0].chip = "elrs-tx"
    if want and rx is not None and rx != str(want):
        out.append(ChipStatus("elrs-rx", REQUIRED, f"runs {rx}, lock says {want}"))
    elif rx is None:
        out.append(ChipStatus("elrs-rx", UNKNOWN, "RP1 version: check its WiFi page"))
    else:
        out.append(ChipStatus("elrs-rx", OK, rx))
    if any(s.status == REQUIRED for s in out):
        for s in out:
            if s.status != REQUIRED:
                s.status, s.detail = REQUIRED, s.detail + " (TX and RX are flashed as a pair)"
    return out


# --- flashing ---------------------------------------------------------------

def build_fc_image(lock: dict, defaults_text: str | None, out: Path) -> Path:
    e = lock["fc"]
    if not e.get("sha256"):
        raise FirmwareError("firmware.lock has no sha256 for fc; run `quadctl lock` first")
    apj = Apj.load(fetch(e["url"], e["sha256"]))
    if defaults_text is not None:
        apj.set_defaults(defaults_text)
    apj.save(out)
    return out


def flash_fc(lock: dict, image: Path, port: str | None) -> None:
    u = lock.get("fc_uploader") or {}
    uploader = fetch(u["url"], u.get("sha256"))
    cmd = [sys.executable, str(uploader)]
    if port:
        cmd += ["--port", port]
    cmd.append(str(image))
    subprocess.run(cmd, check=True)


STM32_DFU = "0483:df11"
# DfuSe flash layouts: the Pocket is an STM32F4 (16K sectors first); the LUX
# F765 is an STM32F7 (32K sectors first). Used to never flash the wrong chip.
F4_LAYOUT = re.compile(r"/0x08000000/04\*016K")


def dfu_devices() -> list[str]:
    try:
        out = subprocess.run(["dfu-util", "-l"], capture_output=True, text=True, check=False).stdout
    except FileNotFoundError:
        raise FirmwareError("dfu-util not found (brew install dfu-util)")
    return [l for l in out.splitlines() if STM32_DFU in l and "alt=0" in l]


def flash_edgetx(lock: dict) -> None:
    e = lock.get("edgetx") or {}
    if not (e.get("url") and e.get("sha256")):
        raise FirmwareError("firmware.lock has no EdgeTX url/sha256")
    devs = dfu_devices()
    pocket = [d for d in devs if F4_LAYOUT.search(d)]
    if len(devs) != 1 or len(pocket) != 1:
        raise FirmwareError(
            "need exactly one STM32 DFU device and it must be the Pocket: "
            "unplug the FC, switch the Pocket off, then plug it into USB")
    fw = fetch(e["url"], e["sha256"])
    subprocess.run(["dfu-util", "-d", STM32_DFU, "-a", "0", "-s", "0x08000000:leave", "-D", str(fw)], check=True)
