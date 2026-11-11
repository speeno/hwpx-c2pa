"""Version chain: re-sign after a word processor save, keeping the previous version as parent."""
from hwpx_c2pa import engine
from hwpx_c2pa.watch import scan_once

from zipedit import resave_like_a_word_processor


def test_resave_drops_credentials(signed_hwpx):
    resaved = resave_like_a_word_processor(signed_hwpx)
    assert not engine.verify(resaved).has_manifest


def test_resign_with_parent(signed_hwpx, signer):
    resaved = resave_like_a_word_processor(signed_hwpx)
    v2 = engine.sign(resaved, signer, title="test.hwpx", parent=signed_hwpx)
    r = engine.verify(v2)
    assert r.integrity_ok and r.state == "Valid"
    assert r.actions == ["c2pa.opened", "c2pa.edited"]
    rel = {i["relationship"] for i in r.ingredients}
    assert rel == {"parentOf", "componentOf"}
    parent = next(i for i in r.ingredients if i["relationship"] == "parentOf")
    assert parent["has_manifest"]
    assert r.manifests_in_store >= 3  # picture, v1, v2


def test_signing_a_signed_file_chains_automatically(signed_hwpx, signer):
    again = engine.sign(signed_hwpx, signer, title="test.hwpx")
    r = engine.verify(again)
    assert r.integrity_ok
    assert any(i["relationship"] == "parentOf" for i in r.ingredients)


def test_watcher_resigns_after_save(tmp_path, signed_hwpx, signer):
    doc = tmp_path / "report.hwpx"
    cache = tmp_path / ".hwpx-c2pa-cache"
    doc.write_bytes(signed_hwpx)
    state, logs = {}, []
    for _ in range(2):  # first pass records, second acts
        scan_once(tmp_path, signer, cache, state, log=logs.append)
    assert any(line.startswith("valid, cached") for line in logs)

    doc.write_bytes(resave_like_a_word_processor(signed_hwpx))  # the "save"
    for _ in range(2):
        scan_once(tmp_path, signer, cache, state, log=logs.append)
    assert any("chained to previous version" in line for line in logs)
    r = engine.verify(doc.read_bytes())
    assert r.integrity_ok and any(i["relationship"] == "parentOf" for i in r.ingredients)

    before = len(logs)
    for _ in range(2):  # nothing changed: no second signature
        scan_once(tmp_path, signer, cache, state, log=logs.append)
    assert len(logs) == before
