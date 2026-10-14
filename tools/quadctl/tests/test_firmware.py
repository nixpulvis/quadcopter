import base64
import json
import struct
import zlib

import pytest

from quadctl import firmware as fw


def fake_apj(path, max_len=256):
    area = fw.PARMDEF + b"\0" + fw.PARAM_MAGIC + struct.pack("<HH", max_len, 0) + b"\0" * max_len
    image = b"\x01" * 1000 + area + b"\x02" * 500
    meta = {"board_id": 1, "git_identity": "abcdef12", "image": base64.b64encode(zlib.compress(image)).decode(),
            "image_size": len(image)}
    path.write_text(json.dumps(meta))
    return path


def test_embed_defaults_roundtrip(tmp_path):
    p = fake_apj(tmp_path / "a.apj")
    a = fw.Apj.load(p)
    size = len(a.image)
    a.set_defaults("SERIAL7_PROTOCOL 23\n")
    a.save(tmp_path / "b.apj")
    b = fw.Apj.load(tmp_path / "b.apj")
    assert b.defaults() == "SERIAL7_PROTOCOL 23\n"
    assert len(b.image) == size and b.git_hash == "abcdef12"


def test_embed_too_big(tmp_path):
    a = fw.Apj.load(fake_apj(tmp_path / "a.apj", max_len=8))
    with pytest.raises(fw.FirmwareError, match="room for 8"):
        a.set_defaults("SERIAL7_PROTOCOL 23\n")


LOCK = {"fc": {"version": "4.7.2", "git_hash": "abcdef1234"}, "elrs": {"version": "3.6.0"}, "edgetx": {"version": None}}


def test_fc_required_vs_stale():
    d = "X 1\n"
    good = {"defaults_sha256": fw.defaults_digest(d)}
    assert fw.fc_status(LOCK, "4.7.1", "abcdef12", good, d).status == fw.REQUIRED
    assert fw.fc_status(LOCK, "4.7.2", "99999999", good, d).status == fw.REQUIRED
    assert fw.fc_status(LOCK, "4.7.2", "abcdef12", good, d).status == fw.OK
    stale = fw.fc_status(LOCK, "4.7.2", "abcdef12", good, "X 2\n")
    assert stale.status == fw.STALE and "params are still applied" in stale.detail
    assert fw.fc_status(LOCK, "4.7.2", "abcdef12", None, d).status == fw.STALE


def test_elrs_pair_flashes_together():
    s = fw.elrs_status(LOCK, "3.6.0", "3.5.3")
    assert [x.status for x in s] == [fw.REQUIRED, fw.REQUIRED]
    s = fw.elrs_status(LOCK, "3.6.0", None)
    assert [x.status for x in s] == [fw.OK, fw.UNKNOWN]


def test_unpinned_edgetx():
    assert fw.simple_status("edgetx", LOCK, "2.10.5", "x").status == fw.UNPINNED


def test_dfu_layout_picks_only_the_pocket():
    f4 = 'Found DFU: [0483:df11] ver=2200, devnum=5, cfg=1, intf=0, path="1-1", alt=0, name="@Internal Flash  /0x08000000/04*016Kg,01*064Kg,07*128Kg", serial="1"'
    f7 = 'Found DFU: [0483:df11] ver=2200, devnum=6, cfg=1, intf=0, path="1-2", alt=0, name="@Internal Flash  /0x08000000/04*032Kg,01*128Kg,03*256Kg", serial="2"'
    assert fw.F4_LAYOUT.search(f4) and not fw.F4_LAYOUT.search(f7)


def test_fetch_verifies_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(fw, "CACHE", tmp_path)
    src = tmp_path / "x.bin"
    src.write_bytes(b"hello")
    url = src.as_uri()
    with pytest.raises(fw.FirmwareError, match="doesn't match"):
        fw.fetch(url, "0" * 64)
    good = fw.fetch(url, None)
    assert fw.fetch(url, good.stem).read_bytes() == b"hello"
