"""FC side against a small simulated ArduPilot speaking MAVLink over UDP,
plus an end-to-end `quadctl apply` with that FC and a fake SD card."""

import shutil
import socket
import threading
import time

import pytest
from pymavlink import mavutil

from conftest import ROOT
from quadctl import cli
from quadctl.fc import FC, FCError
from test_radio import FIX

M = mavutil.mavlink


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


STOCK = {
    "RCMAP_ROLL": 1, "RCMAP_PITCH": 2, "RCMAP_THROTTLE": 3, "RCMAP_YAW": 4,
    "RC5_OPTION": 0, "RC6_OPTION": 0, "RC7_OPTION": 0, "RC8_OPTION": 0,
    "FLTMODE_CH": 5, **{f"FLTMODE{i}": 0 for i in range(1, 7)},
    "SERIAL7_PROTOCOL": 23, "RC_OPTIONS": 32, "RSSI_TYPE": 0,
    "BATT_MONITOR": 4, "BATT_VOLT_PIN": 12, "BATT_CURR_PIN": 13, "BATT_AMP_PERVLT": 17,
    "BATT_CAPACITY": 3300, "BATT_LOW_VOLT": 10.5, "BATT_CRT_VOLT": 0,
    "BATT_FS_LOW_ACT": 0, "BATT_FS_CRT_ACT": 0, "MOT_BAT_CURR_MAX": 0, "FS_THR_ENABLE": 1,
    "FENCE_ENABLE": 0, "FENCE_TYPE": 7, "FENCE_ALT_MAX": 100, "FENCE_RADIUS": 300, "FENCE_ACTION": 1,
    "INS_ACCOFFS_X": 0.0123,
}


class FakeFC(threading.Thread):
    def __init__(self, port, params=None, drop_index=3, refuse=()):
        super().__init__(daemon=True)
        self.params = dict(params or STOCK)
        self.names = list(self.params)
        self.drop_index = drop_index
        self.refuse = set(refuse)
        self.conn = mavutil.mavlink_connection(f"udpout:127.0.0.1:{port}", source_system=1, source_component=1)
        self.stop = False
        self.armed = False
        self.reboots = 0

    def pv(self, name):
        i = self.names.index(name)
        self.conn.mav.param_value_send(name.encode(), float(self.params[name]), M.MAV_PARAM_TYPE_REAL32, len(self.names), i)

    def run(self):
        last = 0
        while not self.stop:
            if time.time() - last > 0.2:
                mode = M.MAV_MODE_FLAG_SAFETY_ARMED if self.armed else 0
                self.conn.mav.heartbeat_send(M.MAV_TYPE_QUADROTOR, M.MAV_AUTOPILOT_ARDUPILOTMEGA, mode, 0, 0)
                last = time.time()
            m = self.conn.recv_match(blocking=True, timeout=0.05)
            if m is None:
                continue
            t = m.get_type()
            if t == "PARAM_REQUEST_LIST":
                for i, n in enumerate(self.names):
                    if i != self.drop_index:
                        self.pv(n)
                self.drop_index = None  # only lose it once
            elif t == "PARAM_REQUEST_READ":
                self.pv(self.names[m.param_index])
            elif t == "PARAM_SET":
                name = m.param_id.rstrip("\0") if isinstance(m.param_id, str) else m.param_id.decode().rstrip("\0")
                if name in self.params and name not in self.refuse:
                    self.params[name] = m.param_value
                if name in self.params:
                    self.pv(name)
            elif t == "COMMAND_LONG":
                if m.command == M.MAV_CMD_REQUEST_MESSAGE and int(m.param1) == M.MAVLINK_MSG_ID_AUTOPILOT_VERSION:
                    ver = (4 << 24) | (7 << 16) | (2 << 8) | 255
                    self.conn.mav.autopilot_version_send(0, ver, 0, 0, 0, list(b"1a2b3c4d"), [0] * 8, [0] * 8, 0, 0, 0)
                elif m.command == M.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN:
                    self.reboots += 1


@pytest.fixture
def fake():
    port = free_port()
    f = FakeFC(port)
    f.start()
    yield f, f"udpin:127.0.0.1:{port}"
    f.stop = True
    f.join(1)


def test_info_and_params(fake):
    f, port = fake
    fc = FC.connect(port)
    info = fc.info()
    assert info.version == "4.7.2" and info.git_hash == "1a2b3c4d" and not info.armed
    params = fc.fetch_params()
    assert params == pytest.approx({k: float(v) for k, v in STOCK.items()})  # dropped one re-requested
    assert fc.set_param("FLTMODE_CH", 6) == 6
    assert f.params["FLTMODE_CH"] == 6
    fc.close()


def test_refused_param_raises():
    port = free_port()
    f = FakeFC(port, refuse={"FENCE_RADIUS"})
    f.start()
    try:
        fc = FC.connect(f"udpin:127.0.0.1:{port}")
        fc.fetch_params()
        with pytest.raises(FCError, match="FENCE_RADIUS"):
            fc.set_param("FENCE_RADIUS", 150)
    finally:
        f.stop = True


def test_armed_refuses(fake):
    f, port = fake
    f.armed = True
    fc = FC.connect(port)
    with pytest.raises(FCError, match="armed"):
        fc.require_disarmed()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    shutil.copy(ROOT / "config" / "quad.yaml", root / "config" / "quad.yaml")
    shutil.copytree(ROOT / "radio", root / "radio")
    card = tmp_path / "card"
    (card / "RADIO").mkdir(parents=True)
    (card / "RADIO" / "radio.yml").write_text("semver: 2.10.5\n")
    (card / "MODELS").mkdir()
    shutil.copy(FIX, card / "MODELS" / "model01.yml")
    return root, card


def test_apply_end_to_end(fake, repo, monkeypatch, capsys):
    f, port = fake
    root, card = repo
    monkeypatch.setattr(FC, "read_stamp", lambda self: None)
    monkeypatch.setattr(FC, "write_stamp", lambda self, s: None)
    monkeypatch.setattr(cli, "eject", lambda v: None)
    base = ["--root", str(root), "--port", port, "--volume", str(card), "-y"]

    assert cli.main(base + ["apply"]) == 0
    out = capsys.readouterr().out
    assert "FC: FENCE_RADIUS = 150" in out
    assert f.params["RC5_OPTION"] == 153 and f.params["FLTMODE_CH"] == 6
    assert int(f.params["RC_OPTIONS"]) == 32 | (1 << 13) | (1 << 11) | (1 << 8)
    assert f.params["INS_ACCOFFS_X"] == pytest.approx(0.0123)  # unowned params untouched
    assert f.reboots == 1  # SERIAL/RCMAP/RC_OPTIONS-type change
    assert (card / "SCRIPTS/FUNCTIONS/qelrs.lua").exists()
    assert "Packet Rate=150Hz" in (card / "SCRIPTS/QUAD/elrs.cfg").read_text()
    assert list((root / "backups").iterdir())

    # verify: everything that can be checked now passes (no ELRS state yet).
    assert cli.main(base + ["verify"]) == 0
    out = capsys.readouterr().out
    assert "ERROR" not in out
    assert "not checked: ELRS" in out

    # A hand edit in QGC is caught.
    f.params["RC8_OPTION"] = 11
    assert cli.main(base + ["verify"]) == 1
    assert "security-fence" in capsys.readouterr().out


def test_apply_needs_both_devices(fake, repo, capsys):
    f, port = fake
    root, card = repo
    with pytest.raises(SystemExit, match="Pocket"):
        cli.main(["--root", str(root), "--port", port, "--volume", str(root / "nope"), "-y", "apply"])
