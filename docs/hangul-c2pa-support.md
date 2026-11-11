# 한글의 C2PA 지원: 문제점과 개선점 / C2PA support in Hangul: problems and improvements

확인 환경 / Checked with: Hancom Office HWP 12.30.0 (build 6544, macOS), C2PA Technical Specification 2.5, c2pa-rs 0.90.23 and 0.91.11, KS X 6101:2024, Hancom public documents (HWP Automation manual 2504, Addon Action guide, hwpx-owpml-model source). Windows 한글은 시험하지 못했다 / Hangul for Windows was not tested.

---

## 한국어

### 1. 문제점

| 번호 | 문제 | 확인 내용 | 영향 |
|---|---|---|---|
| P1 | 저장하면 자격 증명이 사라진다 | 한글 12.30(Mac)은 서명된 HWPX를 오류 없이 연다. 한 글자 고치고 저장하면 패키지를 새로 쓰면서 `META-INF/content_credential.c2pa`를 지운다 | 문서 수준 자격 증명과 판 이력이 끊긴다. 사용자에게 알림도 없다 |
| P2 | 모르는 파트의 처리 규칙이 없다 | KS X 6101에는 처리기가 모르는 파트를 보존할지 버릴지에 대한 조문이 없다. 한컴 공개 모델도 알려진 파트만 쓴다 | 자격 증명뿐 아니라 다른 확장 파트도 같은 일을 겪는다 |
| P3 | 저장할 때 그림 파트 이름이 바뀐다 | `BinData/BIN0001.jpg` → `BinData/image1.jpeg`. 바이트는 그대로다 | 그림 자체의 자격 증명은 남는다. 그러나 이전 판 매니페스트의 URI 목록과 이름이 달라져 판 사이 대조가 어렵다 |
| P4 | 열 때 자격 증명을 보여 주지 않는다 | 서명된 문서를 열어도 표시가 없다 | 받는 사람이 출처를 볼 방법이 없다 |
| P5 | 저장 후 처리 지점이 플랫폼마다 다르다 | Windows는 오토메이션 이벤트(`DocumentAfterSave`)가 있다. Mac에는 오토메이션도 애드인도 없다 | Mac에서는 앱 밖의 폴더 감시만 가능하다 |
| P6 | 저장 직후 파일이 잠긴다(Windows) | 저장·열기 선택 사항 `lock`의 기본값이 TRUE다(오토메이션 매뉴얼). HWPX에도 적용되는지는 확인하지 못했다 | 외부 서명기가 저장 직후 파일을 고쳐 쓸 수 없을 수 있다 |
| P7 | 미디어 타입이 등록되어 있지 않다 | `application/hwp+zip`은 파일 안에만 있고 IANA에 없다. C2PA SDK의 형식 목록에도 `.hwpx`가 없다 | 도구가 HWPX를 직접 인식하지 못한다 |
| P8 | 기존 전자 서명과의 관계가 정해져 있지 않다 | 한컴 모델 소스는 `META-INF/signatures.xml`을 정의하지만 KS X 6101 스키마에는 없다. Mac판은 공인인증서 유효성 검사 문서를 지원하지 않는다 | 두 서명을 함께 쓸 때 순서와 범위가 불분명하다 |
| P9 | 외부에서 고친 HWPX의 손상·변조 경고 | 한컴 포럼에 수동 편집한 HWPX가 경고로 막힌 사례가 있다. 이 도구의 서명본은 Mac에서 경고 없이 열렸다. Windows는 확인하지 못했다 | 서명본이 열리지 않을 위험 |
| P10 | 애드인 인터페이스 문서가 오래됐다 | User Action 모듈 문서는 2008년판이다. 저장 이벤트가 없다. 2024의 새 애드온 방식은 가이드가 공개되지 않았다 | 제3자가 안정적으로 확장하기 어렵다 |
| P11 | 재압축만으로 자격 증명이 깨진다 | C2PA A.6은 압축된 바이트를 해시한다 | 한글 문제는 아니다. 그러나 저장할 때마다 반드시 다시 서명해야 한다는 뜻이다 |

### 2. 개선점

**가. 한글(제품)**

| 번호 | 개선 | 풀리는 문제 |
|---|---|---|
| I1 | 저장할 때 C2PA 매니페스트를 조용히 지우지 않는다. 최소한 "저장하면 콘텐츠 자격 증명이 제거됩니다"라고 알린다 | P1 |
| I2 | 서명 기능 내장: 저장 시 이전 매니페스트를 `parentOf` 재료로 넣고 새 매니페스트를 만든다. 한 일(`c2pa.opened`, `c2pa.edited`, AI 기능 사용 시 `digitalSourceType`)을 동작으로 기록한다 | P1, P11 |
| I3 | 열 때 검증하고 결과를 표시한다(문서 정보 또는 상태 표시줄). 무효이면 경고한다 | P4 |
| I4 | 그림을 넣을 때 그림의 자격 증명을 보존하고 `componentOf` 재료로 연결한다. 그림을 다시 인코딩하면 그 사실을 기록한다 | P3 |
| I5 | 저장할 때 파트 이름을 안정적으로 유지한다 | P3 |
| I6 | 내장 전까지: 저장 후 처리 지점을 모든 플랫폼에 둔다. 저장 완료 이벤트에서 파일 잠금이 풀린 상태를 보장하거나, 저장 직전에 패키지 바이트를 넘겨받아 고칠 수 있는 지점을 둔다. Mac에도 같은 인터페이스를 둔다 | P5, P6 |
| I7 | 애드인 문서를 현행 판 기준으로 갱신하고 새 애드온 가이드를 공개한다 | P10 |
| I8 | `META-INF/content_credential.c2pa`가 있는 패키지를 손상·변조로 판정하지 않는다 | P9 |
| I9 | PDF로 내보낼 때 HWPX의 자격 증명을 재료로 넣은 PDF 매니페스트를 만든다(C2PA A.4) | 출처가 변환 뒤에도 이어진다 |

**나. OWPML 표준(KS X 6101 개정)**

| 번호 | 개선 | 풀리는 문제 |
|---|---|---|
| S1 | `META-INF/content_credential.c2pa`(미디어 타입 `application/c2pa`)를 예약 파트로 정한다 | P1, P2 |
| S2 | 처리기 규칙: 모르는 파트는 보존하거나, 버릴 때 사용자에게 알린다. 자격 증명 파트는 다시 서명하거나, 이전 판을 이어 새로 서명하거나, 알리고 지운다 | P1, P2 |
| S3 | XML 서명 파트(`META-INF/signatures.xml`)를 표준에 넣고, C2PA와 함께 쓸 때 XML 서명을 먼저 하고 C2PA를 나중에 넣는다고 정한다(C2PA A.6.4와 같은 방식) | P8 |
| S4 | 매니페스트 파트를 `content.hpf`와 `manifest.xml`에 선언할지 정한다 | P2 |
| S5 | 미디어 타입 `application/hwp+zip`을 조문에 두고 IANA에 등록한다(표준 트리, RFC 6838) | P7 |

**다. C2PA 생태계**

| 번호 | 개선 | 풀리는 문제 |
|---|---|---|
| E1 | c2pa-rs의 ZIP 처리기 형식 목록에 `hwpx`와 `application/hwp+zip`을 넣는다 | P7 |
| E2 | c2pa-python이 0.91.11 이상 라이브러리를 싣는다 | `fetch-lib`가 필요 없어진다 |
| E3 | C2PA 규격 A.1 표에 OWPML을 넣는 것을 제안한다 | P7 |
| E4 | 국내 인증 기관이 C2PA 신뢰 목록에 들어가거나, 공공 문서용 신뢰 목록을 운영한다 | 실제 `Trusted` 판정 |

### 3. 이 저장소가 메우는 부분

- I2, I4의 대부분: 저장 후 다시 서명, 이전 판 잇기, 그림 자격 증명 연결.
- I3의 일부: 명령줄 검증, Windows 애드온의 열 때 검증(시험하지 않음).
- I1, I5, I8, I9와 표준·생태계 항목은 이 저장소로 풀 수 없다. 한컴과 표준 개정이 필요하다.

---

## English

### 1. Problems

| No. | Problem | What was observed | Effect |
|---|---|---|---|
| P1 | Saving removes the credentials | Hangul 12.30 (Mac) opens a signed HWPX without error. After one character is typed and the file saved, the package is rewritten and `META-INF/content_credential.c2pa` is gone | Document-level credentials and the version history are lost, with no notice to the user |
| P2 | No rule for unknown parts | KS X 6101 does not say whether a processor keeps or drops parts it does not know. Hancom's public model writes known parts only | Any extension part meets the same fate |
| P3 | Picture parts are renamed on save | `BinData/BIN0001.jpg` becomes `BinData/image1.jpeg`; the bytes are unchanged | The picture's own credentials survive, but names no longer match the URI list of the earlier manifest |
| P4 | Credentials are not shown on open | Nothing indicates that a document is signed | Recipients cannot see provenance |
| P5 | Post-save hooks differ by platform | Windows has automation events (`DocumentAfterSave`); the Mac version has neither automation nor add-ins | On Mac only an external folder watcher is possible |
| P6 | File lock after save (Windows) | The `lock` option of save/open defaults to TRUE (automation manual); whether it applies to HWPX was not verified | An external signer may be unable to rewrite the file right after the save |
| P7 | No registered media type | `application/hwp+zip` exists only inside the files, not at IANA; the C2PA SDK format list has no `.hwpx` | Tools do not recognise HWPX directly |
| P8 | Relation to the existing e-signature is undefined | Hancom's model source defines `META-INF/signatures.xml`, the KS X 6101 schemas do not. The Mac version does not support documents with certificate validation | Order and scope are unclear when both signatures are used |
| P9 | "Damaged or tampered" warnings | The Hancom forum reports a hand-edited HWPX being blocked. Files signed by this tool opened without warning on Mac; Windows was not checked | A signed file might fail to open |
| P10 | Add-in documentation is old | The User Action guide dates from 2008 and has no save event; the guide for the newer add-on method in 2024 is not public | Third parties cannot extend Hangul reliably |
| P11 | Recompression alone breaks credentials | C2PA A.6 hashes the compressed bytes | Not a Hangul defect, but it means every save must be followed by a new signature |

### 2. Improvements

**a. Hangul (product)**

| No. | Improvement | Addresses |
|---|---|---|
| I1 | Do not drop a C2PA manifest silently on save; at least warn that saving removes the Content Credentials | P1 |
| I2 | Built-in signing: on save, add the previous manifest as the `parentOf` ingredient and create a new manifest; record what was done as actions (`c2pa.opened`, `c2pa.edited`, a `digitalSourceType` when AI features are used) | P1, P11 |
| I3 | Validate on open and show the result (document information or status bar); warn when invalid | P4 |
| I4 | Keep the credentials of inserted pictures and link them as `componentOf` ingredients; record it when a picture is re-encoded | P3 |
| I5 | Keep part names stable across saves | P3 |
| I6 | Until signing is built in: provide a post-save hook on every platform, with the file unlocked when the event fires, or a pre-write hook that hands over the package bytes. Offer the same interface on Mac | P5, P6 |
| I7 | Update the add-in documentation for current versions and publish the new add-on guide | P10 |
| I8 | Do not treat a package containing `META-INF/content_credential.c2pa` as damaged or tampered | P9 |
| I9 | On export to PDF, create a PDF manifest (C2PA A.4) with the HWPX credentials as an ingredient | Provenance survives conversion |

**b. OWPML standard (revision of KS X 6101)**

| No. | Improvement | Addresses |
|---|---|---|
| S1 | Reserve the part `META-INF/content_credential.c2pa` (media type `application/c2pa`) | P1, P2 |
| S2 | Processor rules: unknown parts are kept, or the user is told when they are dropped. The credentials part is re-signed, or chained into a new manifest, or removed with notice | P1, P2 |
| S3 | Standardise the XML signature part (`META-INF/signatures.xml`) and state that, when both are used, the XML signature comes first and the C2PA manifest second (as C2PA A.6.4 does for EPUB and OOXML) | P8 |
| S4 | Decide whether the manifest part is declared in `content.hpf` and `manifest.xml` | P2 |
| S5 | Define the media type `application/hwp+zip` in the standard and register it with IANA (standards tree, RFC 6838) | P7 |

**c. C2PA ecosystem**

| No. | Improvement | Addresses |
|---|---|---|
| E1 | Add `hwpx` and `application/hwp+zip` to the ZIP handler format list of c2pa-rs | P7 |
| E2 | Ship library 0.91.11 or later with c2pa-python | Removes the need for `fetch-lib` |
| E3 | Propose OWPML for the format table in Annex A.1 of the C2PA specification | P7 |
| E4 | Korean certification authorities on the C2PA trust list, or a trust list for public-sector documents | Real `Trusted` results |

### 3. What this repository covers

- Most of I2 and I4: re-signing after save, chaining to the previous version, linking picture credentials.
- Part of I3: command-line validation, and validation on open in the Windows add-on (not tested).
- I1, I5, I8, I9 and the standard and ecosystem items cannot be solved here; they need Hancom and the standard's revision.
