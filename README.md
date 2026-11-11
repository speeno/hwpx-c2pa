# hwpx-c2pa

**HWPX(아래한글, OWPML · KS X 6101) 문서의 출처와 수정 이력을 C2PA 콘텐츠 자격 증명으로 기록하고 확인하는 엔진과 한글 애드온**
**Engine and Hangul add-ons that record and show the provenance and edit history of HWPX (OWPML, KS X 6101) documents as C2PA Content Credentials**

개발 / Author: Dongsun Nam (speeno) · 라이선스 / License: MIT · 상태 / Status: alpha (0.1.0)

![출처와 수정 이력 창 / provenance and history window](docs/screenshots/04-view-edit-history.png)

- 동작 원리(블록 다이어그램) / How it works, with block diagrams: [docs/how-it-works.md](docs/how-it-works.md)
- 적용 사례와 화면 / Worked example with screens: [docs/case-study.md](docs/case-study.md)
- 한국어·영어 샘플 / Korean and English samples: [samples/](samples/)
- 한글의 C2PA 지원 문제점과 개선점 / Problems and improvements for C2PA support in Hangul: [docs/hangul-c2pa-support.md](docs/hangul-c2pa-support.md)

---

## 한국어

### 무엇을 하나

C2PA는 전자서명 기능이 아니라 **출처(provenance) 기록**이다. 문서가 어디서 왔고, 판마다 누가 어떤 프로그램으로 무엇을 했는지를 문서 안에 넣어 함께 다니게 한다. 서명과 해시는 그 기록이 나중에 바뀌지 않았음을 보이는 수단이다.

이 도구가 판마다 기록하는 것:

- **누가, 언제**: 기록 주체(인증서)와 시각(타임스탬프, 없으면 기록자가 밝힌 시각).
- **무엇으로**: 문서를 만들거나 고친 프로그램(패키지의 `version.xml`에 적힌 이름과 버전).
- **무엇을 했는가**: 만듦(`c2pa.created`), 이전 판을 열어 편집함(`c2pa.opened`, `c2pa.edited`), 기록자가 적은 메모(`--note`).
- **무엇이 바뀌었는가**: 이전 판과 비교한 변경 요약(본문 문단 수정·추가·삭제 수, 글자 수, 바뀐 파트). 개수와 파트 이름만 넣고 본문은 넣지 않는다.
- **어느 판에서 나왔는가**: 이전 판의 기록을 `parentOf`로 이어, 마지막 파일 하나로 전체 이력을 볼 수 있다.
- **안에 든 그림의 출처**: 그림이 자체 C2PA 기록(카메라, 그림 도구, 생성형 AI 등)을 가지고 있으면 `componentOf`로 연결한다.

확인할 때는 `history`와 `view`가 이 이력을 판별로 보여 주고, 기록 이후 문서가 바뀌었으면 어느 파트가 달라졌는지 알려 준다.

기술 바탕: C2PA 기술 규격 2.5 부속서 A.6(ZIP 기반 형식). 기록은 `META-INF/content_credential.c2pa` 파트 하나로 들어가며 OWPML 스키마는 바꾸지 않는다. 기록 작성과 서명은 공식 C2PA SDK(c2pa-rs, c2pa-python)가 하고, 해시는 SDK와 별개로 다시 계산해 대조한다(`check`). 한글은 저장할 때 이 파트를 지우므로, 애드온이 저장할 때마다 새 판을 기록한다. 자세한 구조는 [docs/how-it-works.md](docs/how-it-works.md).

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

# 첫 판 기록 (sign과 record는 같은 명령)
hwpx-c2pa sign 문서.hwpx --note "초안 작성" --cert certs/signer-chain.pem --key certs/signer.key
# 고친 판 기록: 이전 판을 잇고 변경 요약을 남긴다
hwpx-c2pa sign 새판.hwpx --parent 이전판.hwpx --note "3장 예산 수정" ...
hwpx-c2pa history 새판.hwpx               # 출처와 판별 수정 이력
hwpx-c2pa view 새판.hwpx --trust certs/root-ca.pem   # 출처와 이력 창(브라우저)
hwpx-c2pa verify 새판.hwpx --trust certs/root-ca.pem # 요약과 종료 코드
hwpx-c2pa check 새판.hwpx                 # SDK 없이 해시 재계산
hwpx-c2pa watch ~/Documents/Signed        # 폴더 감시: 저장할 때마다 새 판 기록
```

- `verify` 종료 코드: 0 온전함, 1 무효(변조), 2 자격 증명 없음, 3 오류.
- 상태: `Trusted`(기록이 온전하고 기록 주체가 신뢰 목록에 있음), `Valid`(기록은 온전하나 기록 주체가 신뢰 목록에 없음), `Invalid`(기록 이후 문서가 바뀌었거나 기록이 손상됨).
- 편집 프로그램과 변경 요약은 기록 주체가 밝힌 내용이다. 한글이 직접 기록한 것이 아니다([docs/how-it-works.md](docs/how-it-works.md) 5절).
- 인증서와 키를 매번 주지 않으려면 설정 파일을 쓴다(`hwpx-c2pa info`가 위치를 알려 준다).

```json
{"cert": "/path/signer-chain.pem", "key": "/path/signer.key", "tsa": "http://timestamp.example", "trust": "/path/anchors.pem"}
```

Python에서:

```python
from hwpx_c2pa import load_signer, sign, verify
signer = load_signer("signer-chain.pem", "signer.key")
v1 = sign(open("문서.hwpx", "rb").read(), signer, title="문서.hwpx", note="초안 작성")
v2 = sign(open("고친문서.hwpx", "rb").read(), signer, title="문서.hwpx", parent=v1, note="예산 수정")
for step in verify(v2).history:      # 최신 판부터 / newest first
    print(step["version"], step["time"], step["recorded_by"], step["actions"], step["changes"])
```

### 한글 애드온

| 애드온 | 플랫폼 | 하는 일 | 시험 상태 |
|---|---|---|---|
| `hwpx-c2pa watch`, `addon/macos/install-watch.sh` | macOS, Windows, Linux | 폴더를 감시해 저장된 `.hwpx`를 새 판으로 기록한다(이전 판 연결, 변경 요약). 한글 API가 필요 없다 | 시험함(한글 12.30 Mac이 저장한 파일 포함) |
| `addon/windows/automation/hwpx_c2pa_hangul.py` | Windows, 한글 2020 이상 | 실행 중인 한글에 붙어, 열 때 출처를 확인하고 저장 직후 새 판을 기록한다(한글 오토메이션 이벤트) | **시험하지 않음** |
| `addon/windows/useraction/` (C++ DLL) | Windows | 한글 "추가 기능"(User Action 모듈). "C2PA 기록 저장", "C2PA 출처 확인" 버튼 | CI에서 빌드됨. **한글에서 시험하지 않음** |

- Mac용 한글에는 애드인과 오토메이션 인터페이스가 없어 폴더 감시가 유일한 방법이다.
- 한글 오토메이션은 개인의 비상업적 사용에 한해 무료다. 상업적 사용은 한컴의 승인이 필요하다. 이 저장소의 MIT 라이선스는 이 저장소의 코드에만 적용된다.
- Windows 애드온은 한컴 공개 문서(한글 오토메이션 매뉴얼, Addon Action 안내서)를 보고 Mac에서 작성했다. Windows에서 시험해 주실 분의 보고를 기다린다.

### 알려진 제약

- 실제 신뢰를 얻으려면 C2PA 신뢰 목록의 인증 기관이나 기관 PKI가 발급한 인증서가 필요하다. 시험용 인증서는 `Valid`까지만 나온다.
- 내용이 같아도 ZIP을 다시 쓰면(다시 압축, 다른 프로그램으로 저장) 기록과 맞지 않게 된다. 규격이 그렇게 정했다.
- 기록하지 않고 넘어간 저장은 이력에 남지 않는다. 변경 요약은 기록된 두 판 사이의 차이다.
- 시각은 타임스탬프 기관(`--tsa`)을 쓸 때만 제3자가 보증한다. 쓰지 않으면 기록자가 밝힌 시각으로 표시된다.
- C2PA SDK는 `.hwpx`와 `application/hwp+zip`을 모른다. 이 도구가 일반 ZIP 형식으로 넘긴다. c2patool로 직접 볼 때는 확장자를 `.zip`으로 바꾼다.
- SDK 0.90 계열(c2patool 0.27.23)은 0.91이 서명한 파일을 읽지 못한다.
- 판이 쌓이면 이전 매니페스트가 함께 실려 파일이 커진다.
- ZIP64, 암호화된(배포용) 문서는 다루지 않는다.

한글이 C2PA를 직접 지원하는 데 필요한 문제점과 개선점은 [docs/hangul-c2pa-support.md](docs/hangul-c2pa-support.md)에 정리했다.

---

## English

### What it does

C2PA is a **provenance** record, not a signing feature. It lets a document carry where it came from and who did what, with which program, at each version. The signature and the hashes are the means of showing that this record has not been altered.

What this tool records for each version:

- **Who and when**: the recording party (certificate) and the time (time-stamp, else the time stated by the recorder).
- **With what**: the program that made or edited the document (name and version from `version.xml` in the package).
- **What was done**: created (`c2pa.created`), or previous version opened and edited (`c2pa.opened`, `c2pa.edited`), plus a note from the recorder (`--note`).
- **What changed**: a summary against the previous version (body paragraphs modified, added, removed; character count; parts changed). Counts and part names only, never the text.
- **Which version it derives from**: the record of the previous version is chained as `parentOf`, so the last file alone shows the whole history.
- **Where the pictures inside come from**: a picture that carries its own C2PA record (camera, drawing tool, generative AI and so on) is linked as `componentOf`.

For checking, `history` and `view` show this history version by version and, if the document changed after it was recorded, which part differs.

Technical basis: Annex A.6 (ZIP-based formats) of the C2PA Technical Specification 2.5. The record is one added part, `META-INF/content_credential.c2pa`; the OWPML schema is not changed. The record is built and signed by the official C2PA SDK (c2pa-rs through c2pa-python), and the hashes are recomputed independently for cross-checking (`check`). Hangul removes the part on save, so the add-ons record a new version after each save. See [docs/how-it-works.md](docs/how-it-works.md) for the structure.

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

# record the first version (sign and record are the same command)
hwpx-c2pa sign report.hwpx --note "First draft" --cert certs/signer-chain.pem --key certs/signer.key
# record an edited version: chains to the previous one and stores a change summary
hwpx-c2pa sign v2.hwpx --parent v1.hwpx --note "Budget in clause 3 revised" ...
hwpx-c2pa history v2.hwpx                  # origin and edit history per version
hwpx-c2pa view v2.hwpx --trust certs/root-ca.pem     # provenance and history window (browser)
hwpx-c2pa verify v2.hwpx --trust certs/root-ca.pem   # summary and exit code
hwpx-c2pa check v2.hwpx                    # recompute the hashes without the SDK
hwpx-c2pa watch ~/Documents/Signed         # watch a folder, record a new version after each save
```

- `verify` exit codes: 0 intact, 1 invalid (tampered), 2 no credentials, 3 error.
- States: `Trusted` (record intact, recording party on a trust list), `Valid` (record intact, recording party not on a trust list), `Invalid` (the document changed after the record, or the record is damaged).
- The editor name and the change summary are statements of the recording party, not of Hangul itself ([docs/how-it-works.md](docs/how-it-works.md), clause 5).
- To avoid passing the certificate and key each time, use the config file shown above (`hwpx-c2pa info` prints its location).

### Hangul add-ons

| Add-on | Platform | What it does | Test status |
|---|---|---|---|
| `hwpx-c2pa watch`, `addon/macos/install-watch.sh` | macOS, Windows, Linux | Watches a folder and records each saved `.hwpx` as a new version (previous version chained, change summary). Needs no Hangul API | Tested, including files saved by Hangul 12.30 for Mac |
| `addon/windows/automation/hwpx_c2pa_hangul.py` | Windows, Hangul 2020+ | Attaches to the running Hangul, shows the provenance on open, records a new version right after save (HWP Automation events) | **Not tested** |
| `addon/windows/useraction/` (C++ DLL) | Windows | Hangul add-in (User Action Module) with "Save & Record" and "Show provenance" buttons | Builds in CI. **Not tested in Hangul** |

- Hangul for Mac has no add-in or automation interface, so the folder watcher is the only route there.
- Hancom allows HWP Automation free of charge for personal, non-commercial use only; commercial use needs Hancom's approval. The MIT licence of this repository covers this repository's code only.
- The Windows add-ons were written on a Mac from Hancom's public documents (HWP Automation manual, Addon Action guide). Test reports from Windows users are welcome.

### Known limits

- Real trust needs a certificate from a CA on the C2PA trust list or from an organisational PKI. Test certificates reach `Valid` only.
- Rewriting the ZIP (recompressing, saving with another program) breaks the match with the record even if the content is the same. The specification defines it so.
- A save that was not recorded leaves no trace in the history. The change summary is the difference between two recorded versions.
- The time is vouched for by a third party only when a time-stamp authority (`--tsa`) is used; otherwise it is shown as stated by the recorder.
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
