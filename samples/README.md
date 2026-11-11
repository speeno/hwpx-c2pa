# 샘플 / Samples

한국어(`ko/`)와 영어(`en/`) 샘플 문서. 설명은 [../docs/case-study.md](../docs/case-study.md).
Korean (`ko/`) and English (`en/`) sample documents; see [../docs/case-study.md](../docs/case-study.md).

```bash
hwpx-c2pa verify ko/2-signed.hwpx --trust test-root-ca.pem     # 신뢰됨 / Trusted
hwpx-c2pa view   ko/3b-saved-in-hangul-resigned.hwpx --trust test-root-ca.pem
hwpx-c2pa verify ko/4-tampered.hwpx                             # 무효 / Invalid
```

서명 인증서는 시험용이다. 개인 키는 저장소에 없다. / The signing certificates are for testing; the private key is not in the repository.
