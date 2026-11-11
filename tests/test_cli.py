import json

from hwpx_c2pa.cli import main

from zipedit import rebuild


def test_cli_sign_verify_check(tmp_path, unsigned_hwpx, certs, capsys):
    doc = tmp_path / "doc.hwpx"
    doc.write_bytes(unsigned_hwpx)
    assert main(["verify", str(doc)]) == 2  # no credentials yet
    assert main(["sign", str(doc), "--cert", str(certs["chain"]), "--key", str(certs["key"])]) == 0
    capsys.readouterr()
    assert main(["verify", str(doc), "--json", "--trust", str(certs["root"])]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["state"] == "Trusted" and out["integrity_ok"]
    assert main(["check", str(doc)]) == 0


def test_cli_verify_detects_change(tmp_path, signed_hwpx):
    doc = tmp_path / "doc.hwpx"
    doc.write_bytes(rebuild(signed_hwpx, comment=b"x"))
    assert main(["verify", str(doc)]) == 1
    assert main(["check", str(doc)]) == 1


def test_cli_signer_from_environment(tmp_path, unsigned_hwpx, certs, monkeypatch):
    doc = tmp_path / "doc.hwpx"
    doc.write_bytes(unsigned_hwpx)
    monkeypatch.setenv("HWPX_C2PA_CERT", str(certs["chain"]))
    monkeypatch.setenv("HWPX_C2PA_KEY", str(certs["key"]))
    assert main(["sign", str(doc)]) == 0
    assert main(["verify", str(doc)]) == 0


def test_cli_report_writes_verification_page(tmp_path, signed_hwpx, certs):
    doc, page = tmp_path / "doc.hwpx", tmp_path / "result.html"
    doc.write_bytes(signed_hwpx)
    assert main(["report", str(doc), "-o", str(page), "--trust", str(certs["root"])]) == 0
    html = page.read_text(encoding="utf-8")
    assert "Trusted" in html and "신뢰됨" in html and "Contents/section0.xml" in html
    doc.write_bytes(rebuild(signed_hwpx, comment=b"x"))
    assert main(["report", str(doc), "-o", str(page)]) == 1
    assert "Invalid" in page.read_text(encoding="utf-8")
