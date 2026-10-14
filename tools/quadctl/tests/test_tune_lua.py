"""Runs fc/scripts/quadtune.lua (as quadctl renders it) against a mocked
ArduPilot scripting environment: param, arming, gcs and the CRSF menu API
from AP_Scripting (Copter-4.7.2 bindings.desc / docs.lua)."""

import struct

import pytest

lupa = pytest.importorskip("lupa")
from lupa import LuaRuntime  # noqa: E402

from conftest import ROOT
from quadctl import config
from quadctl.compile import compile_config, tune_script

MOCK = r"""
P = { TUNE = 0, TUNE_MIN = 0, TUNE_MAX = 0, ATC_RAT_RLL_P = 0.135, ATC_RAT_RLL_D = 0.0036, ACRO_RP_RATE = 360 }
SETS, TEXTS, RESP, EVENTS, PARAMS = {}, {}, {}, {}, {}
ARMED = false
param = {}
function param:get(n) return P[n] end
function param:set(n, v) if P[n] == nil then return false end; P[n] = v; SETS[#SETS + 1] = n; return true end
arming = {}
function arming:is_armed() return ARMED end
gcs = {}
function gcs:send_text(sev, t) TEXTS[#TEXTS + 1] = t end
local next_id = 1
local Menu = {}
Menu.__index = Menu
function Menu:add_parameter(data)
  next_id = next_id + 1
  local id = next_id
  PARAMS[id] = data
  return { id = function() return id end }
end
crsf = {}
function crsf:add_menu(name) MENU_NAME = name; return setmetatable({}, Menu) end
function crsf:peek_menu_event()
  local e = EVENTS[1]
  if not e then return 0, 0, "", 0 end
  return #EVENTS, e[1], e[2], e[3]
end
function crsf:pop_menu_event() table.remove(EVENTS, 1) end
function crsf:send_write_response(d) RESP[#RESP + 1] = d; return true end
function crsf:send_response() RESP[#RESP + 1] = false; return true end
"""

READ, WRITE = 1, 2


class FC:
    def __init__(self, **params):
        self.lua = LuaRuntime(unpack_returned_tuples=True, encoding=None)
        self.lua.execute(MOCK)
        for k, v in params.items():
            self.lua.globals().P[k.encode()] = v
        cfg = config.load(ROOT / "config" / "quad.yaml")
        text = tune_script((ROOT / "fc" / "scripts" / "quadtune.lua").read_text(), compile_config(cfg).tune_targets)
        chunk = self.lua.eval("load")(text.encode(), b"quadtune.lua")
        self.update = chunk()[0]
        ids = sorted(self.lua.globals().PARAMS.keys())
        self.target, self.value, self.status = ids

    def p(self, name):
        return self.lua.globals().P[name.encode()]

    def armed(self, on):
        self.lua.globals().ARMED = on

    def event(self, pid, payload, events):
        g = self.lua.globals()
        g.EVENTS[len(g.EVENTS) + 1] = self.lua.table(pid, payload, events)
        n = len(g.RESP)
        self.update = self.update()[0]
        return g.RESP[n + 1] if len(g.RESP) > n else None

    def write(self, idx):
        return self.event(self.target, bytes([idx]), WRITE)

    def read_target(self):
        data = self.event(self.target, b"", READ)
        t, rest = data[0], data[1:]
        name, rest = rest.split(b"\0", 1)
        options, rest = rest.split(b"\0", 1)
        value, lo, hi, default = struct.unpack(">BBBB", rest[:4])
        return t, name.decode(), options.decode().split(";"), value, hi

    def read_info(self, pid):
        data = self.event(pid, b"", READ)
        assert data[0] == 12
        return data[1:].split(b"\0")[1].decode()


def test_menu_lists_only_quad_yaml_targets():
    fc = FC()
    assert fc.lua.globals().MENU_NAME == b"Quad Tune"
    t, name, options, value, hi = fc.read_target()
    assert (t, name, options, value, hi) == (9, "Target", ["Off", "Rate P", "Rate D", "Acro rate"], 0, 3)
    assert fc.read_info(fc.value) == "-"


def test_pick_target_disarmed_sets_tune_and_range():
    fc = FC()
    assert fc.write(1) == b"\x01"
    assert (fc.p("TUNE"), fc.p("TUNE_MIN"), fc.p("TUNE_MAX")) == (4, 0.07, 0.2)
    assert fc.read_target()[3] == 1
    assert fc.read_info(fc.value) == "0.135"
    fc.write(3)
    assert (fc.p("TUNE"), fc.p("TUNE_MIN"), fc.p("TUNE_MAX")) == (25, 180, 540)
    assert set(fc.lua.globals().SETS.values()) == {b"TUNE", b"TUNE_MIN", b"TUNE_MAX"}


def test_armed_refuses_a_new_target_but_allows_off():
    fc = FC()
    fc.write(1)
    fc.armed(True)
    assert fc.write(2) == b"\x01"
    assert fc.p("TUNE") == 4
    assert fc.read_info(fc.status) == "Disarm to change"
    assert fc.write(0) == b"\x00"
    assert (fc.p("TUNE"), fc.p("TUNE_MIN"), fc.p("TUNE_MAX")) == (0, 0, 0)


def test_unknown_row_is_ignored():
    fc = FC()
    assert fc.write(9) == b"\x00"
    assert fc.p("TUNE") == 0
    assert fc.read_info(fc.status) == "Unknown target"


def test_boot_shows_what_the_fc_has():
    assert FC(TUNE=21, TUNE_MIN=0.0016, TUNE_MAX=0.0056).read_target()[3] == 2
    fc = FC(TUNE=5)
    assert fc.read_target()[3] == 0
    assert "TUNE=5" in fc.read_info(fc.status)
    assert fc.p("TUNE") == 5  # left alone until a choice is made


def test_other_scripts_events_are_left_queued():
    fc = FC()
    assert fc.event(99, b"\x01", WRITE) is None
    assert len(fc.lua.globals().EVENTS) == 1


def test_script_never_saves():
    text = (ROOT / "fc" / "scripts" / "quadtune.lua").read_text()
    assert "set_and_save" not in text and "save(" not in text
