"""Runs radio/SCRIPTS/QUAD/elrs.lua against a simulated ELRS TX module.

The simulator speaks the CRSF parameter frames the stock ExpressLRS Lua uses
(0x28/0x29/0x2C/0x2B/0x2D/0x2E), with small chunks to exercise reassembly.
EdgeTX's Lua APIs (io.*, crossfireTelemetry*, getTime) are mocked.
"""

from pathlib import Path

import pytest

lupa = pytest.importorskip("lupa")
from lupa import LuaRuntime  # noqa: E402

from conftest import ROOT

CORE = ROOT / "radio" / "SCRIPTS" / "QUAD" / "elrs.lua"

SELECT, FOLDER = 9, 11


class FakeModule:
    CHUNK = 12  # bytes of payload per 0x2B frame

    def __init__(self, version=(3, 6, 0), link_mode=True):
        self.fields = [
            (0, SELECT, "Packet Rate", ["50Hz", "100Hz Full", "150Hz", "250Hz", "333Hz Full", "500Hz"], 3),
            (0, SELECT, "Telem Ratio", ["Std", "Off", "1:128", "1:64", "1:32", "1:16", "1:8", "1:4", "1:2"], 0),
            (0, SELECT, "Switch Mode", ["Wide", "Hybrid"], 1),
            (0, FOLDER, "TX Power", None, None),
            (4, SELECT, "Max Power", ["10", "25", "50", "100", "250"], 1),
            (4, SELECT, "Dynamic", ["Off", "Dyn", "AUX9", "AUX10"], 0),
        ]
        if link_mode:
            self.fields.append((0, SELECT, "Link Mode", ["Normal", "MAVLink"], 0))
        self.version = version
        self.linked = False
        self.out = []      # frames to the radio: (cmd, [bytes])
        self.writes = []   # (label, option)
        self.flash_writes = 0

    def value(self, label):
        for parent, t, name, opts, v in self.fields:
            if name == label:
                return opts[v]

    def set_by_hand(self, label, option):
        for i, (parent, t, name, opts, v) in enumerate(self.fields):
            if name == label:
                self.fields[i] = (parent, t, name, opts, opts.index(option))

    def payload(self, fid):
        parent, t, name, opts, v = self.fields[fid - 1]
        p = [parent, t] + list(name.encode()) + [0]
        if t == SELECT:
            p += list(";".join(opts).encode()) + [0, v, 0, len(opts) - 1, 0] + list(b"mW" if name == "Max Power" else b"") + [0]
        return p

    def receive(self, cmd, data):
        if cmd == 0x28:
            name = list(b"ELRS 2400 TX") + [0]
            info = [0xEA, 0xEE] + name + list(b"ELRS") + [0, 0, 0, 0] + [0, *self.version] + [len(self.fields), 0]
            self.out.append((0x29, info))
        elif cmd == 0x2C:
            _dst, _org, fid, chunk = data
            p = self.payload(fid)
            chunks = [p[i:i + self.CHUNK] for i in range(0, len(p), self.CHUNK)]
            remain = len(chunks) - 1 - chunk
            self.out.append((0x2B, [0xEF, 0xEE, fid, remain] + chunks[chunk]))
        elif cmd == 0x2D:
            _dst, _org, fid, val = data
            if fid == 0:
                self.out.append((0x2E, [0xEF, 0xEE, 0, 0, 0, 1 if self.linked else 0, 0]))
            else:
                parent, t, name, opts, _ = self.fields[fid - 1]
                self.fields[fid - 1] = (parent, t, name, opts, val)
                self.writes.append((name, opts[val]))


class Radio:
    """Mocked EdgeTX Lua environment with an SD card directory."""

    def __init__(self, sd: Path, module: FakeModule):
        self.sd = sd
        self.module = module
        self.time = 0
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        g = self.lua.globals()
        files = {}

        def io_open(path, mode):
            real = sd / str(path).lstrip("/")
            mode = str(mode)
            if mode.startswith("r") and not real.exists():
                return None
            if mode.startswith("w"):
                real.parent.mkdir(parents=True, exist_ok=True)
            h = len(files) + 1
            files[h] = [real, mode, real.read_text() if mode.startswith("r") else "", 0]
            return h

        def io_read(h, n):
            f = files[h]
            s = f[2][f[3]:f[3] + int(n)]
            f[3] += len(s)
            return s

        def io_write(h, s):
            files[h][2] += str(s)

        def io_close(h):
            f = files.pop(h)
            if f[1].startswith("w"):
                f[0].write_text(f[2])

        def push(cmd, data):
            self.module.receive(int(cmd), [int(data[i + 1]) for i in range(len(data))])
            return True

        def pop():
            if not self.module.out:
                return None
            cmd, data = self.module.out.pop(0)
            return cmd, self.lua.table_from({i + 1: b for i, b in enumerate(data)})

        g.io = self.lua.table_from({"open": io_open, "read": io_read, "write": io_write, "close": io_close})
        g.crossfireTelemetryPush = push
        g.crossfireTelemetryPop = pop
        self.core = self.lua.execute(CORE.read_text())

    def boot(self, ticks=3000):
        state = self.core.new()
        for _ in range(ticks):
            self.time += 2
            state = self.core.step(state, self.time)
            if state.phase in ("idle", "error"):
                break
        return state

    def status(self):
        q = self.lua.globals().quadElrs
        return {k: v for k, v in q.status.items()}

    def state_file(self):
        out = {}
        for line in (self.sd / "SCRIPTS/QUAD/state.txt").read_text().splitlines():
            k, v = line.split("=", 1)
            out[k] = v
        return out


CFG = {"Packet Rate": "150Hz", "Telem Ratio": "1:4", "Switch Mode": "Wide",
       "Max Power": "100", "Dynamic": "Dyn", "Link Mode": "Normal"}


def write_cfg(sd: Path, cfg=CFG, reset="0"):
    p = sd / "SCRIPTS/QUAD/elrs.cfg"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"reset={reset}\n" + "".join(f"{k}={v}\n" for k, v in cfg.items()))


@pytest.fixture
def setup(tmp_path):
    write_cfg(tmp_path)
    mod = FakeModule()
    return tmp_path, mod, Radio(tmp_path, mod)


def test_first_boot_applies_config(setup):
    sd, mod, r = setup
    s = r.boot()
    assert s.phase == "idle", s.message
    for k, v in CFG.items():
        assert mod.value(k) == v
    assert set(r.status().values()) == {"sync"}
    st = r.state_file()
    assert st["tx_version"] == "3.6.0"
    assert st["applied.Telem Ratio"] == "1:4" and "override.Telem Ratio" not in st


def test_second_boot_writes_nothing(setup):
    sd, mod, r = setup
    r.boot()
    mod.writes.clear()
    r.boot()
    assert mod.writes == []


def test_hand_change_is_an_override_and_kept(setup):
    sd, mod, r = setup
    r.boot()
    mod.writes.clear()
    mod.set_by_hand("Telem Ratio", "1:8")
    s = r.boot()
    assert mod.writes == []
    assert mod.value("Telem Ratio") == "1:8"
    assert r.status()["Telem Ratio"] == "override"
    assert r.state_file()["override.Telem Ratio"] == "1:8"
    assert "overridden" in s.message


def test_config_change_is_written(setup):
    sd, mod, r = setup
    r.boot()
    mod.writes.clear()
    write_cfg(sd, {**CFG, "Packet Rate": "250Hz"})
    r.boot()
    assert mod.writes == [("Packet Rate", "250Hz")]


def test_reset_token_drops_overrides(setup):
    sd, mod, r = setup
    r.boot()
    mod.set_by_hand("Telem Ratio", "1:8")
    r.boot()
    write_cfg(sd, reset="12345")
    mod.writes.clear()
    r.boot()
    assert mod.writes == [("Telem Ratio", "1:4")]


def test_tools_page_reapply(setup):
    sd, mod, r = setup
    r.boot()
    mod.set_by_hand("Max Power", "250")
    s = r.boot()
    mod.writes.clear()
    r.lua.globals().quadElrs.reapply = True
    for _ in range(3000):
        r.time += 2
        s = r.core.step(s, r.time)
        if s.phase == "idle" and mod.writes:
            break
    assert mod.writes == [("Max Power", "100")]


def test_waits_while_linked(setup):
    sd, mod, r = setup
    mod.linked = True
    s = r.boot(ticks=400)
    assert s.phase == "check_link"
    assert "power the quad off" in s.message
    assert mod.writes == []
    mod.linked = False
    for _ in range(400):
        r.time += 2
        s = r.core.step(s, r.time)
        if s.phase == "idle":
            break
    assert mod.value("Packet Rate") == "150Hz"


def test_unknown_option_is_reported_not_written(setup):
    sd, mod, r = setup
    write_cfg(sd, {**CFG, "Packet Rate": "999Hz"})
    s = r.boot()
    assert r.status()["Packet Rate"].startswith("error: unknown option")
    assert ("Packet Rate", "999Hz") not in mod.writes
    assert "not applied" in s.message


def test_old_elrs_without_link_mode(tmp_path):
    write_cfg(tmp_path)
    mod = FakeModule(version=(3, 3, 1), link_mode=False)
    r = Radio(tmp_path, mod)
    s = r.boot()
    assert s.phase == "idle"
    assert r.status()["Link Mode"] == "sync"
    assert r.state_file()["tx_version"] == "3.3.1"
