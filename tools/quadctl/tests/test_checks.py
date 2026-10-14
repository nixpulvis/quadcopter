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
    s.radio_mixes[6] = s.radio_mixes[6][:3]  # Land line deleted on the radio
    msgs = [f.message for f in checks.run(cfg, d, s) if f.rule == "mode"]
    assert any("SC down" in m and "expected Land" in m for m in msgs)


def test_fltmode_slot_changed_in_qgc():
    cfg, d, s = setup()
    s.fc_params["FLTMODE6"] = 0
    msgs = [f.message for f in checks.run(cfg, d, s) if f.rule == "mode"]
    assert any("expected Land" in m for m in msgs)


def test_override_order_swapped_on_radio():
    # SC lines before the SD line: Acro would beat RTL/Land.
    cfg, d, s = setup()
    l = s.radio_mixes[6]
    s.radio_mixes[6] = [l[0], l[2], l[3], l[1]]
    msgs = [f.message for f in checks.run(cfg, d, s) if f.rule == "mode"]
    assert any("SD down" in m and "expected RTL" in m for m in msgs)


def test_hybrid_switch_mode_is_an_error():
    cfg, d, s = setup()
    s.elrs_tx["Switch Mode"] = "Hybrid"
    assert any("use Wide" in f.message for f in checks.run(cfg, d, s))


def test_extra_land_switch_warns():
    cfg, d, s = setup()
    s.fc_params["RC7_OPTION"] = 18  # left over from the bench plan
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
