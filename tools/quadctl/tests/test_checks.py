from conftest import ROOT
from quadctl import checks, config
from quadctl.compile import Mix, compile_config


def setup():
    cfg = config.load(ROOT / "config" / "quad.yaml")
    d = compile_config(cfg)
    return cfg, d, checks.desired_state(cfg, d)


def rules(findings, level="error"):
    return {f.rule for f in findings if f.level == level}


def test_desired_state_passes():
    cfg, d, s = setup()
    f = checks.run(cfg, d, s)
    assert rules(f) == set()


def test_unset_current_scale_warns():
    cfg, d, s = setup()
    cfg.raw["battery"]["amp_per_volt"] = None
    assert "battery" in rules(checks.run(cfg, d, s), "warn")


def test_fence_switch_is_a_security_error():
    cfg, d, s = setup()
    s.fc_params["RC8_OPTION"] = 11
    assert "security-fence" in rules(checks.run(cfg, d, s))


def test_fence_drift_is_a_security_error():
    cfg, d, s = setup()
    s.fc_params["FENCE_RADIUS"] = 500
    assert "security-fence" in rules(checks.run(cfg, d, s))


def test_mavlink_link_mode_is_an_error():
    cfg, d, s = setup()
    s.elrs_tx["Link Mode"] = "MAVLink"
    assert "security-crsf" in rules(checks.run(cfg, d, s))


def test_mode_switch_weight_change_lands_on_wrong_mode():
    cfg, d, s = setup()
    s.radio_mixes[6][0] = Mix(6, "SB", weight=100)  # plain -100/0/100 mix
    assert [f for f in checks.run(cfg, d, s) if f.rule == "mode"]


def test_override_line_missing_is_caught():
    cfg, d, s = setup()
    l = s.radio_mixes[6]
    s.radio_mixes[6] = [l[0], l[1], l[3]]  # Land line deleted on the radio
    msgs = [f.message for f in checks.run(cfg, d, s) if f.rule == "mode"]
    assert any("SC down" in m and "SD up" in m and "expected Land" in m for m in msgs)


def test_fltmode_slot_changed_in_qgc():
    cfg, d, s = setup()
    s.fc_params["FLTMODE6"] = 0
    msgs = [f.message for f in checks.run(cfg, d, s) if f.rule == "mode"]
    assert any("expected Acro" in m for m in msgs)


def test_override_order_swapped_on_radio():
    # SD line before the SC lines: RTL/Land would beat Acro.
    cfg, d, s = setup()
    l = s.radio_mixes[6]
    s.radio_mixes[6] = [l[0], l[3], l[1], l[2]]
    msgs = [f.message for f in checks.run(cfg, d, s) if f.rule == "mode"]
    assert any("SD down" in m and "expected Acro" in m for m in msgs)


def test_brake_must_be_gated_in_acro():
    cfg, d, s = setup()
    s.radio_mixes[7] = s.radio_mixes[7][:1]  # gate line removed
    msgs = [f.message for f in checks.run(cfg, d, s) if f.rule == "aux"]
    assert any("SD1 active" in m and "off" in m for m in msgs)


def test_brake_option_changed_in_qgc():
    cfg, d, s = setup()
    s.fc_params["RC7_OPTION"] = 11
    f = checks.run(cfg, d, s)
    assert {"aux", "security-fence"} <= rules(f)


def test_hybrid_switch_mode_is_an_error():
    cfg, d, s = setup()
    s.elrs_tx["Switch Mode"] = "Hybrid"
    assert any("use Wide" in f.message for f in checks.run(cfg, d, s))


def test_extra_land_switch_warns():
    cfg, d, s = setup()
    s.fc_params["RC8_OPTION"] = 18  # a stray Land switch
    assert "switches" in rules(checks.run(cfg, d, s), "warn")


def test_channel_order_mismatch():
    cfg, d, s = setup()
    s.fc_params["RCMAP_THROTTLE"] = 1
    assert "channel-order" in rules(checks.run(cfg, d, s))


def test_rc_options_missing_420k_bit():
    cfg, d, s = setup()
    s.fc_params["RC_OPTIONS"] = 32
    assert "rx" in rules(checks.run(cfg, d, s))


def test_elrs_major_mismatch():
    cfg, d, s = setup()
    s.elrs_tx_version, s.elrs_rx_version = "3.6.0", "2.4.0"
    assert "versions" in rules(checks.run(cfg, d, s))


def test_thin_telemetry_ratio_warns():
    cfg, d, s = setup()
    s.elrs_tx["Telem Ratio"] = "1:64"
    assert "telemetry" in rules(checks.run(cfg, d, s), "warn")


def test_avoidance_fence_bit_off_is_a_security_error():
    cfg, d, s = setup()
    s.fc_params["AVOID_ENABLE"] = 2  # proximity only
    assert "security-fence" in rules(checks.run(cfg, d, s))


def test_second_tuning_knob_is_an_error():
    cfg, d, s = setup()
    s.fc_params["RC9_OPTION"] = 220
    s.fc_params["TUNE2"] = 4
    msgs = [f.message for f in checks.run(cfg, d, s) if f.rule == "tuning"]
    assert any("RC9_OPTION=220" in m for m in msgs) and any("TUNE2=4" in m for m in msgs)


def test_tune_target_with_wrong_range_is_an_error():
    cfg, d, s = setup()
    s.fc_params.update(TUNE=21, TUNE_MIN=0.0016, TUNE_MAX=0.2)  # Rate D with Rate P's top
    assert "tuning" in rules(checks.run(cfg, d, s))


def test_tune_target_from_menu_is_info():
    cfg, d, s = setup()
    s.fc_params.update(TUNE=25, TUNE_MIN=180, TUNE_MAX=540)
    f = checks.run(cfg, d, s)
    assert rules(f) == set() and "tuning" in rules(f, "info")


def test_knob_moved_to_another_channel_is_an_error():
    cfg, d, s = setup()
    s.fc_params["RC8_OPTION"] = 0
    s.fc_params["RC10_OPTION"] = 219
    f = checks.run(cfg, d, s)
    assert "tuning" in rules(f) and "fc-params" in rules(f)
