# HWPX 문서의 C2PA 적용 사례: 출처와 수정 이력

[English](case-study.md) | **한국어**

이 사례는 HWPX 문서가 "어디서 왔고, 판마다 누가 무엇으로 무엇을 했는지"를 C2PA 기록으로 들고 다니는 것을 보인다. 구조와 원리는 [how-it-works.ko.md](how-it-works.ko.md)에 블록 다이어그램으로 설명했다.

모든 화면과 결과는 `samples/`의 샘플과 이 저장소의 도구로 만든 것이다. 기록에 쓴 인증서는 시험용이다.

환경: macOS, Hancom Office HWP 12.30.0 (6544), hwpx-c2pa 0.1.0, c2pa-python 0.38.2 + C2PA 라이브러리 0.91.11.

## 1. 샘플

한국어(`samples/ko`)와 영어(`samples/en`) 문서가 같은 구성으로 있다.

| 파일 | 내용 | 결과 |
|---|---|---|
| `1-unsigned.hwpx` | 샘플 문서. 그림만 자체 출처 기록을 가진다 | 출처 기록 없음 |
| `2-signed.hwpx` | 판 1을 기록: 만듦(`c2pa.created`), 만든 프로그램, 메모, 그림의 출처 | 신뢰됨, 판 1개 |
| `3a-saved-in-hangul.hwpx` | 2번을 한글에서 열어 고치고 저장한 파일 | 출처 기록 없음(한글이 지움) |
| `3b-saved-in-hangul-resigned.hwpx` | 3a를 판 2로 기록: 이전 판(2번) 연결, 편집 프로그램 한글 12.30, 변경 요약 | 신뢰됨, 판 2개 |
| `4-tampered.hwpx` | 2번의 금액을 기록 없이 고친 파일 | 무효: 기록과 맞지 않음 |

`samples/test-root-ca.pem`을 신뢰 기준으로 주면 `Trusted`가 나오고, 주지 않으면 `Valid`가 나온다.

## 2. 기록과 이력 확인 (명령줄)

![명령줄](screenshots/01-cli-record-history.png)

- 기록 전: 출처 기록 없음(종료 코드 2).
- `sign --note`: 판 1을 기록한다.
- `sign --parent`: 한글에서 고쳐 저장한 파일을 판 2로 기록한다. 이전 판을 잇고 변경 요약을 넣는다.
- `history`: 판 1은 python-hwpx로 만듦, 판 2는 한글 12.30으로 편집, 본문 문단 1개 수정, 글자 수 403→405, 파트 7개 변경, 그림 파트는 이름만 바뀜. 그림은 두 판 모두 자체 기록을 가진다.
- 기록 없이 고친 파일: 무효(종료 코드 1).

이 그림은 실제 명령 출력을 그대로 옮겨 그린 것이다(터미널 창을 찍은 것이 아니다).

## 3. 출처와 이력 창

`hwpx-c2pa view 문서.hwpx`는 결과를 브라우저 창으로 연다. 창은 출처, 판별 수정 이력, 구성요소의 출처, 그 기록을 믿을 수 있는 근거(해시 대조) 순서로 보여 준다. 아래는 그 창을 그대로 찍은 것이다. 창의 표기는 한국어와 영어를 함께 쓴다.

### 3.1 판 1

누가 언제 무엇으로 만들었는지, 문서 안 그림이 어디서 왔는지가 나온다.

![판 1](screenshots/02-view-first-version.png)

### 3.2 한글에서 저장한 뒤

한글은 저장할 때 패키지를 새로 쓰고 기록 파트를 버린다. 이 상태로는 출처를 알 수 없다.

![출처 기록 없음](screenshots/03-view-after-hangul-save-no-record.png)

### 3.3 판 2 기록: 수정 이력

`hwpx-c2pa sign … --parent 2-signed.hwpx` 또는 폴더 감시(`watch`)가 저장된 파일을 판 2로 기록한다. 창에는 판 2(이전 판을 엶, 한글 12.30으로 편집, 이전 판과의 차이)와 판 1(만듦)이 차례로 나온다.

![수정 이력](screenshots/04-view-edit-history.png)

### 3.4 기록 없이 바뀐 문서

본문의 금액을 고치면 마지막 기록과 문서가 맞지 않는다. 창은 이력이 지금 문서를 설명하지 못한다고 알리고, 달라진 파트(`Contents/section0.xml`)를 표시한다.

![기록과 맞지 않음](screenshots/05-view-changed-after-record.png)

### 3.5 영어 샘플

![영어 샘플](screenshots/06-view-edit-history-en-sample.png)

## 4. 한글에서의 동작

Hancom Office HWP 12.30 (macOS)에서 확인했다.

| 단계 | 결과 |
|---|---|
| 기록된 파일 열기 | 경고 없이 열린다. 파일은 바뀌지 않는다 |
| 저장 | 패키지 전체를 새로 쓴다. `META-INF/content_credential.c2pa`가 없어진다. 그림 파트 이름이 바뀐다(`BIN0001.png` → `image1.png`) |
| 그림 자체의 기록 | 바이트가 그대로라 유지된다 |
| 새 판 기록 | 이전 판과 그림을 잇고 편집 프로그램과 변경 요약을 넣는다. `Trusted` |

### 아직 없는 화면

- 한글 프로그램 창과 애드온 등록 화면은 이 판에 넣지 못했다. 작업 환경에 화면 기록 권한이 없었고, Mac용 한글에는 애드인 기능이 없다(등록 화면은 Windows판 도구 메뉴에 있다).
- Windows 애드온(`addon/windows/`)은 아직 시험하지 못했다. Windows에서 확인한 화면과 결과를 환영한다.

## 5. 다시 만들기

```bash
pip install -e ".[dev]" python-hwpx && hwpx-c2pa fetch-lib
python samples/make_samples.py                      # 1, 2, 4번 (3a가 있으면 3b도)
# 2-signed.hwpx를 한글에서 열고 고쳐 저장 → 3a
hwpx-c2pa sign 3a.hwpx -o 3b.hwpx --parent 2-signed.hwpx --note "…" --cert … --key …
hwpx-c2pa history samples/ko/3b-saved-in-hangul-resigned.hwpx
hwpx-c2pa view samples/ko/2-signed.hwpx --trust samples/test-root-ca.pem
```

`make_samples.py`를 다시 돌리면 새 시험 인증서로 기록되므로 `test-root-ca.pem`도 바뀐다.

샘플 문서의 틀은 python-hwpx(Apache-2.0)의 빈 문서에서 왔다. 그림은 스크립트가 생성한 것이다.
