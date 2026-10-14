import copy

import pytest
from ruamel.yaml import YAML

from conftest import ROOT
from quadctl import config
from quadctl.compile import compile_config, defaults_file, fltmode_slot, pct_to_pwm

QUAD = ROOT / "config" / "quad.yaml"


def raw():
    return YAML(typ="safe").load(QUAD.read_text())


def dump(d):
    import io
    buf = io.StringIO()
    YAML(typ="safe").dump(d, buf)
    return buf.getvalue()


def test_repo_config_compiles():
    d = compile_config(config.load(QUAD))
    p = d.resolve_params()
    assert (p["RCMAP_ROLL"], p["RCMAP_PITCH"], p["RCMAP_THROTTLE"], p["RCMAP_YAW"]) == (1, 2, 3, 4)
    assert p["RC5_OPTION"] == 153 and p["RC7_OPTION"] == 18 and p["FLTMODE_CH"] == 6
    assert p["SERIAL7_PROTOCOL"] == 23
    assert int(p["RC_OPTIONS"]) & (1 << 13)
    assert p["BATT_LOW_VOLT"] == 10.5 and p["BATT_CRT_VOLT"] == 9.9
    assert p["FENCE_TYPE"] == 3 and p["FENCE_ACTION"] == 1


def test_mode_switch_positions_land_on_their_modes():
    d = compile_config(config.load(QUAD))
    p = d.fc_params
    want = [config.COPTER_MODES[m] for m in ("Stabilize", "Loiter", "RTL")]
    for pct, mode in zip((-100, 0, 100), want):
        assert p[f"FLTMODE{fltmode_slot(pct_to_pwm(pct))}"] == mode


def test_rc_options_keeps_unowned_bits():
    d = compile_config(config.load(QUAD))
    merged = d.resolve_params({"RC_OPTIONS": 1 | 32})
    assert int(merged["RC_OPTIONS"]) & 33 == 33


def test_defaults_file_format():
    text = defaults_file(compile_config(config.load(QUAD)))
    assert "SERIAL7_PROTOCOL 23\n" in text
    assert "BATT_LOW_VOLT 10.5\n" in text


@pytest.mark.parametrize("edit,needle", [
    (lambda r: r["switches"]["arm"].update(channel=8), "arm channel"),
    (lambda r: r["switches"]["land"].update(channel=6), "already used"),
    (lambda r: r["elrs"].update({"Link Mode": "MAVLink"}), "security rule"),
    (lambda r: r["rx"].update(protocol="sbus"), "plain CRSF"),
    (lambda r: r["switches"]["mode"].update(modes=["Stabilize", "Loiter"]), "one mode per"),
    (lambda r: r["battery"].update(critical_volt_per_cell=3.6), "critical_volt"),
    (lambda r: r["fence"].update(type=["polygon"]), "polygon"),
])
def test_bad_configs_are_rejected(edit, needle):
    r = copy.deepcopy(raw())
    edit(r)
    with pytest.raises(config.ConfigError) as e:
        config.loads(dump(r))
    assert needle in str(e.value)
