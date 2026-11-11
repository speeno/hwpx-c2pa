# 동작 원리: OWPML에 C2PA를 어떻게 넣고, 출처를 어떻게 증명하는가

[English](how-it-works.md) | **한국어**

C2PA의 목적은 전자서명 자체가 아니다. **문서가 어디서 왔고, 판마다 누가 무엇으로 무엇을 했는지**를 문서와 함께 들고 다니게 하는 것이다. 서명과 해시는 그 기록이 나중에 바뀌지 않았음을 보이는 수단이다.

| 질문 | C2PA 기록의 어느 부분이 답하는가 |
|---|---|
| 누가 기록했는가 | 서명 인증서의 주체 |
| 언제 | 타임스탬프(TSA), 없으면 기록자가 밝힌 시각 |
| 무엇으로 만들고 고쳤는가 | 동작의 `softwareAgent` |
| 무엇을 했는가 | 동작 목록 `c2pa.created`, `c2pa.opened`, `c2pa.edited` |
| 이전 판에서 무엇이 바뀌었는가 | 변경 요약 어서션 |
| 어느 판에서 나왔는가 | `parentOf` 재료 |
| 안에 든 그림은 어디서 왔는가 | `componentOf` 재료(그림 자체의 기록) |
| 이 기록이 지금 이 문서의 것인가 | 해시 결속과 서명 |

## 1. OWPML 패키지 안의 위치

HWPX 파일은 ZIP 패키지다. 출처 기록(매니페스트 저장소)은 파트 하나로 추가된다. 본문, 머리, 설정 같은 OWPML 파트와 스키마는 바뀌지 않는다.

```mermaid
flowchart TB
  subgraph PKG["HWPX 파일 = OWPML 패키지 (ZIP)"]
    direction TB
    MT["mimetype<br/>application/hwp+zip"]
    VER["version.xml<br/>편집 프로그램 이름과 버전"]
    subgraph CON["Contents/"]
      HPF["content.hpf<br/>메타데이터, 파트 목록"]
      HEAD["header.xml<br/>글꼴, 스타일"]
      SEC["section0.xml …<br/>본문"]
    end
    subgraph BIN["BinData/"]
      PIC["image1.png<br/>그림. 자체 C2PA 기록을 가질 수 있다"]
    end
    subgraph META["META-INF/"]
      CXML["container.xml, manifest.xml"]
      C2PA["content_credential.c2pa<br/>C2PA 매니페스트 저장소<br/>(추가되는 유일한 파트)"]
    end
    CD["ZIP 중앙 디렉터리"]
  end
  C2PA -. "해시" .-> MT
  C2PA -. "해시" .-> VER
  C2PA -. "해시" .-> CON
  C2PA -. "해시" .-> BIN
  C2PA -. "해시" .-> CXML
  C2PA -. "해시" .-> CD
  style C2PA fill:#e6f4ec,stroke:#1a7f4b,stroke-width:2px
```

- 근거: C2PA 기술 규격 2.5 부속서 A.6(ZIP 기반 형식). 파트 이름은 `META-INF/content_credential.c2pa`이고 압축하지 않고 넣는다.
- 해시는 파트의 "내용"이 아니라 ZIP 항목 전체(로컬 헤더, 압축된 데이터)에 건다. 그래서 내용이 같아도 ZIP을 다시 쓰면 기록과 맞지 않게 된다.

## 2. 기록 안에 무엇이 들어 있는가

저장소에는 판마다 매니페스트가 하나씩 들어간다. 가장 새 것이 "활성 매니페스트"이고, 이전 판과 그림의 매니페스트는 재료로 따라 들어온다.

```mermaid
flowchart LR
  subgraph STORE["META-INF/content_credential.c2pa — 매니페스트 저장소"]
    direction LR
    subgraph M2["매니페스트: 판 2 (활성)"]
      direction TB
      A2["동작<br/>c2pa.opened → 이전 판<br/>c2pa.edited · softwareAgent: Hancom Office Hangul 12.30<br/>설명: 기록자가 적은 메모"]
      CH2["변경 요약<br/>본문 문단 수정 1, 바뀐 파트 7 …"]
      I2P["재료 parentOf<br/>→ 판 1"]
      I2C["재료 componentOf<br/>→ BinData/image1.png"]
      H2["해시 결속<br/>c2pa.hash.collection.data<br/>항목별 해시 + 중앙 디렉터리 해시"]
      CL2["클레임<br/>위 어서션들의 해시 목록, 기록 도구"]
      S2["서명 (COSE)<br/>기록자 인증서, 타임스탬프"]
      A2 --> CL2
      CH2 --> CL2
      I2P --> CL2
      I2C --> CL2
      H2 --> CL2
      CL2 --> S2
    end
    subgraph M1["매니페스트: 판 1"]
      direction TB
      A1["동작<br/>c2pa.created · softwareAgent: 만든 프로그램"]
      S1["클레임 + 서명"]
      A1 --> S1
    end
    subgraph MP["매니페스트: 그림"]
      direction TB
      AP["동작<br/>c2pa.created<br/>(카메라, 그림 도구, 생성형 AI …)"]
      SP["클레임 + 서명"]
      AP --> SP
    end
    I2P ==> M1
    I2C ==> MP
  end
```

- 클레임은 어서션들의 해시를 담고, 서명은 클레임에 붙는다. 그래서 동작 하나, 변경 요약 한 줄만 고쳐도 서명이 맞지 않는다.
- 이전 판의 매니페스트는 그 판을 기록한 주체의 서명을 그대로 가진 채 들어온다. 판마다 기록 주체가 달라도 된다(작성자, 검토자, 발행 기관).

## 3. 한 판을 기록하는 과정

```mermaid
sequenceDiagram
  autonumber
  actor U as 작성자
  participant H as 한글
  participant T as hwpx-c2pa (애드온)
  participant S as C2PA SDK (c2pa-rs)
  U->>H: 문서를 고치고 저장
  H->>H: 패키지를 새로 쓴다. 이전 기록 파트는 없어진다
  H-->>T: 저장 이벤트 또는 폴더 감시
  T->>T: version.xml에서 편집 프로그램을 읽는다
  T->>T: 보관해 둔 이전 판과 비교해 변경 요약을 만든다
  T->>T: 자체 기록을 가진 그림을 찾는다
  T->>S: 동작, 변경 요약, 재료(이전 판, 그림)를 넘긴다
  S->>S: 항목별 해시와 중앙 디렉터리 해시 계산, 클레임 작성, 서명
  S-->>T: 기록 파트가 들어간 패키지
  T->>H: 파일 교체 (잠겨 있으면 이름.c2pa.hwpx)
```

한글은 C2PA를 모르기 때문에 4~10단계를 애드온이 대신한다. 따라서 "편집 프로그램"과 "변경 요약"은 한글이 직접 증언한 것이 아니라, 기록 주체가 패키지를 보고 밝힌 내용이다(5절).

## 4. 판이 이어지는 방식

```mermaid
flowchart LR
  V1["판 1<br/>c2pa.created<br/>기록: 작성자 A"]
  E1(["한글에서 편집, 저장<br/>기록 파트 없어짐"])
  V2["판 2<br/>c2pa.opened + c2pa.edited<br/>변경 요약<br/>기록: 검토자 B"]
  E2(["다시 편집, 저장"])
  V3["판 3<br/>c2pa.opened + c2pa.edited<br/>변경 요약<br/>기록: 발행 기관 C"]
  P["그림<br/>자체 기록"]
  V1 --> E1 --> V2 --> E2 --> V3
  V2 -. "parentOf: 판 1의 매니페스트를 품는다" .-> V1
  V3 -. "parentOf" .-> V2
  P -. "componentOf" .-> V1
  P -. "componentOf" .-> V2
  P -. "componentOf" .-> V3
```

- ZIP 형식에는 C2PA의 "갱신 매니페스트"를 쓸 수 없다. 그래서 판마다 새 매니페스트를 만들고 이전 판을 `parentOf` 재료로 잇는다.
- 판 3의 파일 하나만 있으면 판 1, 2, 3의 기록과 그림의 기록을 모두 볼 수 있다. 이전 판의 본문은 들어 있지 않다. 들어 있는 것은 기록뿐이다.
- 이전 판 없이 저장본만 기록하면 그 판은 새 출발점(`c2pa.created`)이 되고 이력이 끊긴다. 애드온이 저장 전 판을 보관하는 이유다.

## 5. 확인하는 과정과 알 수 있는 것

```mermaid
flowchart TB
  START(["문서를 받음"]) --> Q1{"기록 파트가 있는가?"}
  Q1 -- "없음" --> R0["출처 기록 없음<br/>출처를 알 수 없다. 변조라는 뜻은 아니다"]
  Q1 -- "있음" --> Q2{"서명이 클레임과 맞는가?"}
  Q2 -- "아니오" --> RX["무효<br/>기록이 손상되었거나 고쳐졌다"]
  Q2 -- "예" --> Q3{"모든 ZIP 항목과 중앙 디렉터리의<br/>해시가 기록과 맞는가?"}
  Q3 -- "아니오" --> RY["무효<br/>마지막 기록 이후 문서가 바뀌었다<br/>어느 파트가 다른지 표시된다"]
  Q3 -- "예" --> Q4{"이전 판과 그림의 기록도 온전한가?"}
  Q4 -- "아니오" --> RZ["그 단계에 문제 표시"]
  Q4 -- "예" --> Q5{"기록자의 인증서가<br/>신뢰 목록에 닿는가?"}
  RZ --> Q5
  Q5 -- "아니오" --> RV["유효 (Valid)<br/>기록은 온전하다<br/>기록자가 누구인지는 보증되지 않는다"]
  Q5 -- "예" --> RT["신뢰됨 (Trusted)<br/>기록은 온전하고 기록자가 확인된다"]
  RV --> OUT["출처와 수정 이력을 보여 준다"]
  RT --> OUT
  style RT fill:#e6f4ec,stroke:#1a7f4b
  style RV fill:#fdf3d7,stroke:#8a6100
  style RX fill:#fbe9e7,stroke:#b3261e
  style RY fill:#fbe9e7,stroke:#b3261e
  style R0 fill:#eceff3,stroke:#4a5565
```

기록이 온전할 때 말할 수 있는 것과 없는 것:

| 구분 | 내용 | 믿는 근거 |
|---|---|---|
| 암호로 확인됨 | 기록 이후 문서의 어떤 바이트도 바뀌지 않았다. 기록 자체도 바뀌지 않았다. 이전 판과 그림의 기록이 그 판의 것이다 | 해시, 서명 |
| 인증서로 확인됨 | 기록 주체가 누구인가 | 신뢰 목록, 인증 기관 |
| 타임스탬프로 확인됨 | 기록 시각(TSA를 쓴 경우) | 타임스탬프 기관 |
| 기록 주체의 진술 | 편집 프로그램, 동작, 변경 요약, 메모, TSA 없는 시각 | 기록 주체에 대한 신뢰 |
| 알 수 없음 | 본문 내용이 사실인가. 기록되지 않은 중간 저장에서 무슨 일이 있었는가 | — |

"기록 주체의 진술" 줄이 중요하다. 지금은 한글이 아니라 애드온이 기록하므로, 편집 프로그램 이름은 `version.xml`에 적힌 값을 옮긴 것이다. 한글이 저장할 때 직접 기록하게 되면 이 줄의 항목이 "편집 프로그램이 증언함"으로 올라간다. [hangul-c2pa-support.ko.md](hangul-c2pa-support.ko.md)의 개선점이 겨냥하는 것이 이것이다.

## 6. 이 도구에서 보기

```bash
hwpx-c2pa history samples/ko/3b-saved-in-hangul-resigned.hwpx   # 판별 이력
hwpx-c2pa view    samples/ko/3b-saved-in-hangul-resigned.hwpx --trust samples/test-root-ca.pem
```

![수정 이력](screenshots/04-view-edit-history.png)
