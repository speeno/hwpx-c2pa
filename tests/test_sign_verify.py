import io
import zipfile

from hwpx_c2pa import engine, zipbinding
from hwpx_c2pa.package import inspect_package


def test_signed_package_layout(signed_hwpx):
    z = zipbinding.parse_zip(signed_hwpx)
    assert z.entries[0].name == "mimetype" and z.entries[0].method == 0
    man = z.find(zipbinding.MANIFEST_PATH)
    assert man is not None and man.method == 0 and man.flags == 0
    assert inspect_package(signed_hwpx).problems == []


def test_verify_valid_and_component_linked(signed_hwpx):
    r = engine.verify(signed_hwpx)
    assert r.state == "Valid"
    assert r.integrity_ok
    assert "assertion.collectionHash.match" in r.success
    assert r.actions == ["c2pa.created"]
    assert {(i["title"], i["relationship"]) for i in r.ingredients} == {("BinData/image1.png", "componentOf")}
    assert r.binding["ok"]


def test_verify_trusted_with_anchor(signed_hwpx, certs):
    r = engine.verify(signed_hwpx, trust=certs["root"])
    assert r.state == "Trusted"


def test_independent_check_matches_every_entry(signed_hwpx):
    report = engine.independent_check(signed_hwpx)
    names = {e["uri"] for e in report["entries"]}
    with zipfile.ZipFile(io.BytesIO(signed_hwpx)) as zf:
        expected = {n for n in zf.namelist() if n != zipbinding.MANIFEST_PATH}
    assert names == expected  # every entry, directory entries included (C2PA 2.5 A.6.2.1)
    statuses = {e["uri"]: e["status"] for e in report["entries"]}
    assert all(s == "match" for n, s in statuses.items() if not n.endswith("/"))
    assert report["ok"] and report["central_directory"] == "match"


def test_unsigned_has_no_manifest(unsigned_hwpx):
    r = engine.verify(unsigned_hwpx)
    assert not r.has_manifest and r.state is None
    assert not engine.has_valid_binding(unsigned_hwpx)


def test_sign_file_in_place_and_extension_does_not_matter(tmp_path, unsigned_hwpx, signer):
    p = tmp_path / "문서.hwpx"
    p.write_bytes(unsigned_hwpx)
    out = engine.sign_file(p, signer)
    assert out == p
    assert engine.verify(p.read_bytes()).integrity_ok
