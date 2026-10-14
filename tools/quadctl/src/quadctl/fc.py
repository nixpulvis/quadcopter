"""ArduPilot FC over USB serial (MAVLink, via pymavlink)."""

from __future__ import annotations

import glob
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from pymavlink import mavutil

USB_PRODUCT = "LumenierLUXF765_NDAA"
STAMP_PATH = "/APM/quadctl.json"

# Params ArduPilot only reads at boot.
REBOOT_PREFIXES = ("SERIAL", "RCMAP_", "BATT_MONITOR", "BATT_VOLT_PIN", "BATT_CURR_PIN", "RC_OPTIONS")


class FCError(Exception):
    pass


@dataclass
class FCInfo:
    version: str | None
    git_hash: str | None
    board: str | None
    armed: bool


def candidate_ports() -> list[str]:
    ports = sorted(glob.glob("/dev/cu.usbmodem*")) + sorted(glob.glob("/dev/ttyACM*"))
    try:
        from serial.tools import list_ports
        named = [p.device for p in list_ports.comports() if USB_PRODUCT in (p.product or "")]
        ports = named + [p for p in ports if p not in named]
    except Exception:
        pass
    return ports


def usb_product(port: str) -> str | None:
    try:
        from serial.tools import list_ports
        for p in list_ports.comports():
            if p.device == port:
                return p.product
    except Exception:
        pass
    return None


def needs_reboot(name: str) -> bool:
    return name.startswith(REBOOT_PREFIXES)


class FC:
    def __init__(self, conn, port: str | None = None):
        self.conn = conn
        self.port = port
        self.param_types: dict[str, int] = {}

    @classmethod
    def connect(cls, port: str | None = None, timeout: float = 5) -> "FC":
        ports = [port] if port else candidate_ports()
        if not ports:
            raise FCError("no FC found: plug the LUX F765 into USB (no /dev/cu.usbmodem* port)")
        last = None
        for p in ports:
            try:
                conn = mavutil.mavlink_connection(p, baud=115200, source_system=254, source_component=190)
                hb = conn.wait_heartbeat(timeout=timeout)
                if hb is None:
                    last = f"{p}: no heartbeat"
                    conn.close()
                    continue
                return cls(conn, p)
            except Exception as e:  # serial errors, permission denied
                last = f"{p}: {e}"
        raise FCError(f"no MAVLink FC answered ({last})")

    def close(self) -> None:
        self.conn.close()

    # --- identity -------------------------------------------------------

    def info(self, timeout: float = 3) -> FCInfo:
        c = self.conn
        hb = c.recv_match(type="HEARTBEAT", blocking=True, timeout=timeout)
        armed = bool(hb and hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        c.mav.command_long_send(c.target_system, c.target_component,
                                mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 0,
                                mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION, 0, 0, 0, 0, 0, 0)
        av = c.recv_match(type="AUTOPILOT_VERSION", blocking=True, timeout=timeout)
        version = git = None
        if av is not None:
            v = av.flight_sw_version
            version = f"{v >> 24 & 0xFF}.{v >> 16 & 0xFF}.{v >> 8 & 0xFF}"
            git = bytes(av.flight_custom_version).rstrip(b"\0").decode("ascii", "replace") or None
        board = usb_product(self.port) if self.port else None
        return FCInfo(version=version, git_hash=git, board=board, armed=armed)

    def require_disarmed(self) -> None:
        if self.info().armed:
            raise FCError("FC is armed; refusing to change it")

    # --- params ---------------------------------------------------------

    def fetch_params(self, timeout: float = 30) -> dict[str, float]:
        c = self.conn
        c.mav.param_request_list_send(c.target_system, c.target_component)
        params: dict[str, float] = {}
        seen: set[int] = set()
        total = None
        deadline = time.time() + timeout
        quiet_since = time.time()
        while time.time() < deadline:
            m = c.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
            if m is None:
                if total is not None and time.time() - quiet_since > 1.0:
                    missing = [i for i in range(total) if i not in seen]
                    if not missing:
                        break
                    for i in missing[:20]:
                        c.mav.param_request_read_send(c.target_system, c.target_component, b"", i)
                    quiet_since = time.time()
                continue
            quiet_since = time.time()
            name = _name(m.param_id)
            params[name] = float(m.param_value)
            self.param_types[name] = m.param_type
            total = m.param_count
            if 0 <= m.param_index < 0xFFFF:
                seen.add(m.param_index)
            if total is not None and len(seen) >= total:
                break
        if total is None:
            raise FCError("FC sent no parameters")
        if len(seen) < total:
            raise FCError(f"only got {len(seen)} of {total} parameters")
        return params

    def set_param(self, name: str, value: float, retries: int = 3) -> float:
        c = self.conn
        ptype = self.param_types.get(name, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        for _ in range(retries):
            c.mav.param_set_send(c.target_system, c.target_component, name.encode(), float(value), ptype)
            deadline = time.time() + 2
            while time.time() < deadline:
                m = c.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
                if m is not None and _name(m.param_id) == name:
                    if abs(m.param_value - value) <= 1e-3 * max(1.0, abs(value)):
                        return float(m.param_value)
                    break
        raise FCError(f"{name} didn't take value {value}")

    def reboot(self) -> None:
        c = self.conn
        c.mav.command_long_send(c.target_system, c.target_component,
                                mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, 0,
                                1, 0, 0, 0, 0, 0, 0)

    # --- stamp on the FC's SD card (MAVLink FTP) -------------------------

    def _ftp(self):
        from pymavlink import mavftp
        return mavftp.MAVFTP(self.conn, self.conn.target_system, self.conn.target_component)

    def read_stamp(self) -> dict | None:
        ftp = self._ftp()
        with tempfile.TemporaryDirectory() as d:
            local = os.path.join(d, "stamp.json")
            ftp.cmd_get([STAMP_PATH, local])
            ret = ftp.process_ftp_reply("get", timeout=10)
            if ret.error_code != 0 or not os.path.exists(local):
                return None
            try:
                return json.loads(Path(local).read_text())
            except ValueError:
                return None

    def write_stamp(self, stamp: dict) -> None:
        ftp = self._ftp()
        with tempfile.TemporaryDirectory() as d:
            local = os.path.join(d, "stamp.json")
            Path(local).write_text(json.dumps(stamp, indent=2, sort_keys=True))
            ftp.cmd_put([local, STAMP_PATH])
            ret = ftp.process_ftp_reply("put", timeout=10)
            if ret.error_code != 0:
                raise FCError(f"couldn't write {STAMP_PATH} over MAVLink FTP ({ret.error_code})")


def _name(param_id) -> str:
    if isinstance(param_id, bytes):
        param_id = param_id.decode("ascii", "replace")
    return param_id.rstrip("\0")


# --- param files (Mission Planner .param format: NAME,VALUE) -------------

def write_param_file(path: Path, params: dict[str, float]) -> None:
    lines = [f"{k},{_fmt(v)}" for k, v in sorted(params.items())]
    path.write_text("\n".join(lines) + "\n")


def read_param_file(path: Path) -> dict[str, float]:
    out = {}
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.replace("\t", ",").replace(" ", ",").split(",")
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            out[parts[0]] = float(parts[1])
    return out


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else repr(float(v))
