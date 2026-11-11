# Samples

**English** | [한국어](README.ko.md)

Korean (`ko/`) and English (`en/`) sample documents; see [../docs/case-study.md](../docs/case-study.md).

```bash
hwpx-c2pa history en/3b-saved-in-hangul-resigned.hwpx           # v1 created → v2 edited in Hangul
hwpx-c2pa view    en/3b-saved-in-hangul-resigned.hwpx --trust test-root-ca.pem
hwpx-c2pa verify  en/2-signed.hwpx --trust test-root-ca.pem     # Trusted
hwpx-c2pa verify  en/4-tampered.hwpx                            # Invalid: changed after the record
```

The certificates are for testing; the private key is not in the repository.

The package skeleton comes from python-hwpx (Apache-2.0); see [../NOTICE.md](../NOTICE.md).
