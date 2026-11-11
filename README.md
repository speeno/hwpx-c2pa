# hwpx-c2pa

**HWPX(아래한글, OWPML · KS X 6101) 문서용 C2PA 콘텐츠 자격 증명 생성·검증 엔진과 한글 애드온**
**C2PA Content Credentials engine and Hangul add-ons for HWPX (OWPML, KS X 6101) documents**

개발 / Author: Dongsun Nam (speeno) · 라이선스 / License: MIT · 상태 / Status: alpha (0.1.0)

![검증 창 / verification window](docs/screenshots/04-view-resigned-version-chain.png)

- 적용 사례와 화면 / Worked example with screens: [docs/case-study.md](docs/case-study.md)
- 한국어·영어 샘플 / Korean and English samples: [samples/](samples/)
- 한글의 C2PA 지원 문제점과 개선점 / Problems and improvements for C2PA support in Hangul: [docs/hangul-c2pa-support.md](docs/hangul-c2pa-support.md)

---

## 한국어

### 무엇을 하나

- HWPX 문서에 C2PA 자격 증명(누가, 언제, 무엇으로 만들었는지에 대한 서명된 기록)을 넣고 검증한다.
- C2PA 기술 규격 2.5 부속서 A.6(ZIP 기반 형식)을 따른다. 매니페스트는 `META-INF/content_credential.c2pa`에 들어가고, 패키지의 모든 항목과 ZIP 중앙 디렉터리가 해시로 묶인다. OWPML 스키마는 바꾸지 않는다.
- 한글은 저장할 때 패키지를 새로 쓰면서 자격 증명을 지운다. 그래서 저장할 때마다 다시 서명하고, 이전 판을 부모(`parentOf`)로 이어 판 이력을 남긴다.
- 문서 안 그림이 자체 C2PA 자격 증명을 가지고 있으면 문서 자격 증명에 구성요소(`componentOf`)로 연결한다.
- 서명은 공식 C2PA SDK(c2pa-rs, c2pa-python)가 한다. 해시는 SDK와 별개로 다시 계산해 대조한다(`check`).

### 설치

```bash
pip install git+https://github.com/speeno/hwpx-c2pa
hwpx-c2pa fetch-lib     # HWPX를 처리할 수 있는 C2PA 라이브러리(0.91.11)를 받는다
hwpx-c2pa info          # "supported: True"인지 확인
```

`fetch-lib`가 필요한 이유: c2pa-python 0.38.2에 들어 있는 라이브러리(0.91.6)는 Deflate로 압축된 ZIP 항목을 처리하지 못한다. HWPX는 모두 Deflate를 쓴다. `fetch-lib`는 c2pa-rs 공식 릴리스에서 라이브러리를 받고 SHA-256을 확인한 뒤 사용자 캐시에 둔다.

### 사용

```bash
# 시험용 인증서 만들기 (실제 문서에는 쓰지 말 것)
pip install "hwpx-c2pa[devcerts] @ git+https://github.com/speeno/hwpx-c2pa"
hwpx-c2pa dev-certs ./certs

hwpx-c2pa sign 문서.hwpx --cert certs/signer-chain.pem --key certs/signer.key
hwpx-c2pa verify 문서.hwpx --trust certs/root-ca.pem
hwpx-c2pa view 문서.hwpx --trust certs/root-ca.pem   # 검증 창(브라우저)
hwpx-c2pa check 문서.hwpx                 # SDK 없이 해시 재계산
hwpx-c2pa sign 새판.hwpx --parent 이전판.hwpx ...   # 판 이력 잇기
hwpx-c2pa watch ~/Documents/Signed        # 폴더 감시: 저장할 때마다 다시 서명
```

- `verify` 종료 코드: 0 온전함, 1 무효(변조), 2 자격 증명 없음, 3 오류.
- 상태: `Trusted`(신뢰 목록의 서명자), `Valid`(서명과 내용은 온전하나 서명자가 신뢰 목록에 없음), `Invalid`.
- 인증서와 키를 매번 주지 않으려면 설정 파일을 쓴다(`hwpx-c2pa info`가 위치를 알려 준다).

```json
{"cert": "/path/signer-chain.pem", "key": "/path/signer.key", "tsa": "http://timestamp.example", "trust": "/path/anchors.pem"}
```

Python에서:

```python
from hwpx_c2pa import load_signer, sign, verify
signer = load_signer("signer-chain.pem", "signer.key")
signed = sign(open("문서.hwpx", "rb").read(), signer, title="문서.hwpx")
print(verify(signed).summary())
```

### 한글 애드온

| 애드온 | 플랫폼 | 하는 일 | 시험 상태 |
|---|---|---|---|
| `hwpx-c2pa watch`, `addon/macos/install-watch.sh` | macOS, Windows, Linux | 폴더를 감시해 저장된 `.hwpx`를 다시 서명한다. 한글 API가 필요 없다 | 시험함(한글 12.30 Mac이 저장한 파일 포함) |
| `addon/windows/automation/hwpx_c2pa_hangul.py` | Windows, 한글 2020 이상 | 실행 중인 한글에 붙어, 열 때 검증하고 저장 직후 서명한다(한글 오토메이션 이벤트) | **시험하지 않음** |
| `addon/windows/useraction/` (C++ DLL) | Windows | 한글 "추가 기능"(User Action 모듈). "C2PA 서명 저장", "C2PA 검증" 버튼 | CI에서 빌드됨. **한글에서 시험하지 않음** |

- Mac용 한글에는 애드인과 오토메이션 인터페이스가 없어 폴더 감시가 유일한 방법이다.
- 한글 오토메이션은 개인의 비상업적 사용에 한해 무료다. 상업적 사용은 한컴의 승인이 필요하다. 이 저장소의 MIT 라이선스는 이 저장소의 코드에만 적용된다.
- Windows 애드온은 한컴 공개 문서(한글 오토메이션 매뉴얼, Addon Action 안내서)를 보고 Mac에서 작성했다. Windows에서 시험해 주실 분의 보고를 기다린다.

### 알려진 제약

- 실제 신뢰를 얻으려면 C2PA 신뢰 목록의 인증 기관이나 기관 PKI가 발급한 인증서가 필요하다. 시험용 인증서는 `Valid`까지만 나온다.
- 내용이 같아도 ZIP을 다시 쓰면(다시 압축, 다른 프로그램으로 저장) 자격 증명이 무효가 된다. 규격이 그렇게 정했다.
- C2PA SDK는 `.hwpx`와 `application/hwp+zip`을 모른다. 이 도구가 일반 ZIP 형식으로 넘긴다. c2patool로 직접 볼 때는 확장자를 `.zip`으로 바꾼다.
- SDK 0.90 계열(c2patool 0.27.23)은 0.91이 서명한 파일을 읽지 못한다.
- 판이 쌓이면 이전 매니페스트가 함께 실려 파일이 커진다.
- ZIP64, 암호화된(배포용) 문서는 다루지 않는다.

한글이 C2PA를 직접 지원하는 데 필요한 문제점과 개선점은 [docs/hangul-c2pa-support.md](docs/hangul-c2pa-support.md)에 정리했다.

---

## English

### What it does

- Embeds and validates C2PA Content Credentials (a signed record of who made a document, when, and with what) in HWPX documents.
- Follows Annex A.6 (ZIP-based formats) of the C2PA Technical Specification 2.5. The manifest store is `META-INF/content_credential.c2pa`; every entry of the package and the ZIP central directory are bound by hashes. The OWPML schema is not changed.
- Hangul rewrites the package on save and removes the credentials. The document is therefore signed again after each save, with the previous version recorded as the `parentOf` ingredient, which keeps a version history.
- Pictures that carry their own C2PA credentials are linked to the document credentials as `componentOf` ingredients.
- Signing is done by the official C2PA SDK (c2pa-rs through c2pa-python). The hashes are recomputed independently of the SDK for cross-checking (`check`).

### Install

```bash
pip install git+https://github.com/speeno/hwpx-c2pa
hwpx-c2pa fetch-lib     # fetch a C2PA library (0.91.11) that can process HWPX
hwpx-c2pa info          # expect "supported: True"
```

Why `fetch-lib`: the library bundled with c2pa-python 0.38.2 (0.91.6) cannot process Deflate-compressed ZIP entries, and every HWPX file uses Deflate. `fetch-lib` downloads the library from the official c2pa-rs release, checks its SHA-256, and stores it in the user cache.

### Use

```bash
# test certificates (never use them for real documents)
pip install "hwpx-c2pa[devcerts] @ git+https://github.com/speeno/hwpx-c2pa"
hwpx-c2pa dev-certs ./certs

hwpx-c2pa sign report.hwpx --cert certs/signer-chain.pem --key certs/signer.key
hwpx-c2pa verify report.hwpx --trust certs/root-ca.pem
hwpx-c2pa view report.hwpx --trust certs/root-ca.pem   # verification window (browser)
hwpx-c2pa check report.hwpx                # recompute the hashes without the SDK
hwpx-c2pa sign v2.hwpx --parent v1.hwpx ...   # chain versions
hwpx-c2pa watch ~/Documents/Signed         # watch a folder, re-sign after each save
```

- `verify` exit codes: 0 intact, 1 invalid (tampered), 2 no credentials, 3 error.
- States: `Trusted` (signer on a trust list), `Valid` (signature and content intact, signer not on a trust list), `Invalid`.
- To avoid passing the certificate and key each time, use the config file shown above (`hwpx-c2pa info` prints its location).

### Hangul add-ons

| Add-on | Platform | What it does | Test status |
|---|---|---|---|
| `hwpx-c2pa watch`, `addon/macos/install-watch.sh` | macOS, Windows, Linux | Watches a folder and re-signs saved `.hwpx` files. Needs no Hangul API | Tested, including files saved by Hangul 12.30 for Mac |
| `addon/windows/automation/hwpx_c2pa_hangul.py` | Windows, Hangul 2020+ | Attaches to the running Hangul, verifies on open, signs right after save (HWP Automation events) | **Not tested** |
| `addon/windows/useraction/` (C++ DLL) | Windows | Hangul add-in (User Action Module) with "Save & Sign" and "Verify" buttons | Builds in CI. **Not tested in Hangul** |

- Hangul for Mac has no add-in or automation interface, so the folder watcher is the only route there.
- Hancom allows HWP Automation free of charge for personal, non-commercial use only; commercial use needs Hancom's approval. The MIT licence of this repository covers this repository's code only.
- The Windows add-ons were written on a Mac from Hancom's public documents (HWP Automation manual, Addon Action guide). Test reports from Windows users are welcome.

### Known limits

- Real trust needs a certificate from a CA on the C2PA trust list or from an organisational PKI. Test certificates reach `Valid` only.
- Rewriting the ZIP (recompressing, saving with another program) invalidates the credentials even if the content is the same. The specification defines it so.
- The C2PA SDK does not know `.hwpx` or `application/hwp+zip`; this tool passes packages as generic ZIP. To inspect a file with c2patool, rename it to `.zip`.
- SDK 0.90.x (c2patool 0.27.23) cannot read files signed by 0.91.
- Each version carries the earlier manifests, so files grow with the history.
- ZIP64 and encrypted (distribution) documents are not handled.

What Hangul itself would need in order to support C2PA is described in [docs/hangul-c2pa-support.md](docs/hangul-c2pa-support.md).

### Development

```bash
pip install -e ".[dev]" && hwpx-c2pa fetch-lib && pytest -q
```

The tests build a synthetic OWPML-shaped package; no Hancom software or sample documents are needed.

### References

- C2PA Technical Specification 2.5, Annex A.6: https://spec.c2pa.org/specifications/specifications/2.5/specs/C2PA_Specification.html
- c2pa-rs: https://github.com/contentauth/c2pa-rs · c2pa-python: https://github.com/contentauth/c2pa-python
- KS X 6101:2024 (OWPML)
- Hancom HWP Automation: https://developer.hancom.com/hwpautomation · manuals: https://github.com/hancom-io/devcenter-archive

"한글", "한컴오피스", "HWP", "HWPX" are names or trademarks of Hancom Inc. This project is independent of Hancom and of the C2PA.
