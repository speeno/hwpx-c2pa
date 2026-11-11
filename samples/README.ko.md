# 샘플

[English](README.md) | **한국어**

한국어(`ko/`)와 영어(`en/`) 샘플 문서. 설명은 [../docs/case-study.ko.md](../docs/case-study.ko.md).

```bash
hwpx-c2pa history ko/3b-saved-in-hangul-resigned.hwpx           # 판 1(만듦) → 판 2(한글에서 편집)
hwpx-c2pa view    ko/3b-saved-in-hangul-resigned.hwpx --trust test-root-ca.pem
hwpx-c2pa verify  ko/2-signed.hwpx --trust test-root-ca.pem     # 신뢰됨
hwpx-c2pa verify  ko/4-tampered.hwpx                            # 무효: 기록 이후 바뀜
```

인증서는 시험용이다. 개인 키는 저장소에 없다.
