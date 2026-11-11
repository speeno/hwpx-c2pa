"""Every change after signing must be detected (C2PA A.6 collection hash)."""
import pytest

from hwpx_c2pa import engine, zipbinding

from zipedit import read_part, rebuild

SECTION = "Contents/section0.xml"
PACKAGE_DOC = "Contents/content.hpf"


def _cases(signed, other_signed):
    section = read_part(signed, SECTION)
    hpf = read_part(signed, PACKAGE_DOC)
    return {
        "body text": rebuild(signed, replace={SECTION: section.replace(b"reference", b"altered!!")}),
        "package metadata": rebuild(signed, replace={PACKAGE_DOC: hpf.replace(b"tester", b"someone")}),
        "part added": rebuild(signed, add=[("BinData/extra.bin", b"extra")]),
        "part removed": rebuild(signed, drop={"Preview/PrvText.txt"}),
        "zip comment": rebuild(signed, comment=b"edited"),
        "repacked": _repack_keep_manifest(signed),
        "manifest swapped": rebuild(signed, replace={
            zipbinding.MANIFEST_PATH: read_part(other_signed, zipbinding.MANIFEST_PATH)}),
    }


def _repack_keep_manifest(buf):
    """Same entries, same order, recompressed (content unchanged)."""
    import io
    import zipfile
    src = zipfile.ZipFile(io.BytesIO(buf))
    dst = io.BytesIO()
    with zipfile.ZipFile(dst, "w") as out:
        for info in src.infolist():
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            out.writestr(zi, src.read(info), compresslevel=1 if info.compress_type == 8 else None)
    return dst.getvalue()


@pytest.fixture(scope="module")
def other_signed(signer):
    from conftest import PARTS, build_package
    parts = dict(PARTS, **{SECTION: PARTS[SECTION].replace("reference", "different")})
    return engine.sign(build_package(parts, None), signer)


@pytest.mark.parametrize("case", ["body text", "package metadata", "part added", "part removed",
                                  "zip comment", "repacked", "manifest swapped"])
def test_tampering_is_detected(case, signed_hwpx, other_signed):
    tampered = _cases(signed_hwpx, other_signed)[case]
    r = engine.verify(tampered)
    assert r.has_manifest
    assert r.state == "Invalid"
    assert any(f.startswith("assertion.collectionHash.mismatch") for f in r.failure)
    assert not r.integrity_ok
    assert r.binding is not None and not r.binding["ok"]


def test_manifest_removed(signed_hwpx):
    stripped = rebuild(signed_hwpx, drop={zipbinding.MANIFEST_PATH})
    assert not engine.verify(stripped).has_manifest
