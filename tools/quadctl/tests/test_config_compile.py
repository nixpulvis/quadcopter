import copy

import pytest
from ruamel.yaml import YAML

from conftest import ROOT
from quadctl import config
from quadctl.compile import channel_pct, compile_config, defaults_file, fltmode_slot, pct_to_pwm

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
    assert p["RC5_OPTION"] == 153 and p["RC6_OPTION"] == 0 and p["FLTMODE_CH"] == 6
    assert p["RC7_OPTION"] == 33  # SE: hold to brake
    assert p["SERIAL7_PROTOCOL"] == 23
    assert int(p["RC_OPTIONS"]) & (1 << 13)
    assert p["BATT_LOW_VOLT"] == 10.5 and p["BATT_CRT_VOLT"] == 9.9
    assert p["FENCE_TYPE"] == 3 and p["FENCE_ACTION"] == 3  # SmartRTL or RTL or Land
    assert int(p["AVOID_ENABLE"]) & 1 and p["AVOID_BACKUP_SPD"] == 0.75 and p["AVOID_MARGIN"] == 2


def test_every_switch_combination_lands_on_its_mode():
    d = compile_config(config.load(QUAD))
    lines = [m for m in d.radio_mixes if m.channel == 6]
    seen = {}
    for pos, mode in d.mode_outputs:
        pwm = pct_to_pwm(channel_pct(lines, pos))
        assert d.fc_params[f"FLTMODE{fltmode_slot(pwm)}"] == config.COPTER_MODES[mode]
        seen[(pos["SB"][0], pos["SD"][0], pos["SC"][0])] = mode
    # SD and SC up = Fly: SB decides. SC mid/down force RTL/Land; SD down
    # forces Acro and beats everything.
    assert [seen[(b, 0, 0)] for b in range(3)] == ["Loiter", "AltHold", "Stabilize"]
    assert {seen[(b, 0, 1)] for b in range(3)} == {"RTL"}
    assert {seen[(b, 0, 2)] for b in range(3)} == {"Land"}
    assert {seen[(b, 1, x)] for b in range(3) for x in range(3)} == {"Acro"}


def test_mode_channel_mix_lines():
    d = compile_config(config.load(QUAD))
    ch6 = [(m.source, m.weight, m.offset, m.swtch, m.mltpx) for m in d.radio_mixes if m.channel == 6]
    assert ch6 == [("SB", 25, -40, None, "ADD"), ("MAX", 11, 0, "SC1", "REPLACE"),
                   ("MAX", 36, 0, "SC2", "REPLACE"), ("MAX", 100, 0, "SD1", "REPLACE")]
    p = d.fc_params
    assert [p[f"FLTMODE{i}"] for i in range(1, 7)] == [5, 2, 0, 6, 9, 1]
    ch7 = [(m.source, m.weight, m.swtch, m.mltpx) for m in d.radio_mixes if m.channel == 7]
    assert ch7 == [("SE", 100, None, "ADD"), ("MAX", -100, "SD1", "REPLACE")]


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
    (lambda r: r["switches"]["mode"].update(channel=5), "already used"),
    (lambda r: r["switches"]["overrides"][1].update(switch="SB"), "already used"),
    (lambda r: r["switches"]["overrides"][1].update(modes=["RTL", "RTL", "Land"]), "must be Fly"),
    (lambda r: r["switches"]["overrides"][0].update(channel=7), "has no channel"),
    (lambda r: r["switches"]["overrides"].append({"switch": "SF", "positions": 2, "modes": ["Fly", "Sport"]}), "6 FLTMODE slots"),
    (lambda r: r["aux"][0].update(option="Fence"), "aux[0].option"),
    (lambda r: r["aux"][0].update(channel=6), "already used"),
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
