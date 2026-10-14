import shutil

import pytest

from conftest import ROOT
from quadctl import radio
from quadctl.compile import Mix

FIX = ROOT / "tools" / "quadctl" / "tests" / "fixtures" / "model-synthetic.yml"
WANT = [Mix(5, "SA"), Mix(6, "SB"), Mix(7, "SD")]


@pytest.fixture
def card(tmp_path):
    (tmp_path / "RADIO").mkdir()
    (tmp_path / "RADIO" / "radio.yml").write_text("semver: 2.10.5\nboard: pocket\n")
    (tmp_path / "MODELS").mkdir()
    shutil.copy(FIX, tmp_path / "MODELS" / "model01.yml")
    return tmp_path


def test_reads_model(card):
    m = radio.find_model(card, "QUAD550")
    assert m.check_layout() == []
    assert m.sticks() == {1: "roll", 2: "pitch", 3: "throttle", 4: "yaw"}
    assert m.mixes()[6][0].source == "SC"
    assert m.module_is_crsf() is True
    assert m.has_boot_script() is True
    assert radio.edgetx_version(card) == "2.10.5"


def test_set_mixes_only_touches_owned_lines(card):
    m = radio.find_model(card, "QUAD550")
    before = m.text
    assert m.plan_mixes(WANT)
    m.set_mixes(WANT)
    m.save()
    again = radio.find_model(card, "QUAD550")
    assert again.plan_mixes(WANT) == []
    mixes = again.mixes()
    assert [(x.source, x.weight, x.offset) for x in mixes[6]] == [("SB", 100, 0)]
    assert mixes[5][0].source == "SA" and mixes[7][0].source == "SD"
    # Everything outside mixData is byte-identical.
    cut = lambda t: t.split("mixData:")[0] + t.split("moduleData:")[1]
    assert cut(before) == cut(again.text)
    # Mixes stay sorted by channel.
    dest = [int(l.split(":")[1]) for l in again.text.splitlines() if l.strip().startswith("destCh:")]
    assert dest == sorted(dest)


def test_refuses_multi_line_channel(card):
    m = radio.find_model(card, "QUAD550")
    m.text = m.text.replace("moduleData:", "  -\n    destCh: 5\n    srcRaw: SD\n    weight: 100\nmoduleData:")
    assert "can't edit" in " ".join(m.plan_mixes(WANT))
    with pytest.raises(radio.RadioError):
        m.set_mixes(WANT)


def test_missing_model(card):
    with pytest.raises(radio.RadioError, match="create an empty model"):
        radio.find_model(card, "NOPE")


def test_elrs_cfg_and_state(card):
    radio.write_elrs_cfg(card, {"Packet Rate": "150Hz"})
    assert radio.read_kv(card / radio.ELRS_CFG) == {"reset": "0", "Packet Rate": "150Hz"}
    radio.write_elrs_cfg(card, {"Packet Rate": "250Hz"})
    assert radio.read_kv(card / radio.ELRS_CFG)["reset"] == "0"
    (card / radio.ELRS_STATE).write_text(
        "reset=0\ntx_version=3.6.0\napplied.Telem Ratio=1:4\nactual.Telem Ratio=1:8\noverride.Telem Ratio=1:8\n")
    st = radio.read_elrs_state(card)
    assert st.tx_version == "3.6.0" and st.overrides == {"Telem Ratio": "1:8"}


def test_install_scripts(card):
    src = ROOT / "radio" / "SCRIPTS"
    assert "SCRIPTS/FUNCTIONS/qelrs.lua" in radio.install_scripts(card, src)
    assert radio.scripts_pending(card, src) == []
