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
    assert "battery" in rules(f, "warn")  # amp_per_volt unset


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
    s.radio_mixes[6] = [Mix(6, "SB", weight=50)]  # positions at 1244/1500/1756
    errs = [f for f in checks.run(cfg, d, s) if f.rule == "mode"]
    assert errs


def test_fltmode_slot_changed_in_qgc():
    cfg, d, s = setup()
    s.fc_params["FLTMODE6"] = 0
    msgs = [f.message for f in checks.run(cfg, d, s) if f.rule == "mode"]
    assert any("expected RTL" in m for m in msgs)


def test_centre_position_near_band_edge_is_fine_when_slots_match():
    # 1500 us is 10 us above the 1490 edge, but slots 3 and 4 both hold Loiter.
    cfg, d, s = setup()
    assert not [f for f in checks.run(cfg, d, s) if f.rule == "mode"]
    s.fc_params["FLTMODE3"] = 0  # now the 1490 edge changes mode
    assert [f for f in checks.run(cfg, d, s) if f.rule == "mode" and "band edge" in f.message]


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
