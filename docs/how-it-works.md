# 동작 원리: OWPML에 C2PA를 어떻게 넣고, 출처를 어떻게 증명하는가
# How it works: C2PA in an OWPML package, and how provenance is shown

C2PA의 목적은 전자서명 자체가 아니다. **문서가 어디서 왔고, 판마다 누가 무엇으로 무엇을 했는지**를 문서와 함께 들고 다니게 하는 것이다. 서명과 해시는 그 기록이 나중에 바뀌지 않았음을 보이는 수단이다.

C2PA is not a signing feature. Its purpose is that a document carries **where it came from and who did what, with which tool, at each version**. The signature and the hashes are only the means of showing that this record has not been altered.

| 질문 / Question | C2PA 기록의 어느 부분이 답하는가 / Answered by |
|---|---|
| 누가 기록했는가 / Who recorded it | 서명 인증서의 주체 / subject of the signing certificate |
| 언제 / When | 타임스탬프(TSA), 없으면 기록자가 밝힌 시각 / time-stamp, else the time stated by the recorder |
| 무엇으로 만들고 고쳤는가 / Made and edited with what | 동작의 `softwareAgent` / `softwareAgent` of each action |
| 무엇을 했는가 / What was done | 동작 목록 `c2pa.created`, `c2pa.opened`, `c2pa.edited` / the actions |
| 이전 판에서 무엇이 바뀌었는가 / What changed since the previous version | 변경 요약 어서션 / change summary assertion |
| 어느 판에서 나왔는가 / Which version it derives from | `parentOf` 재료 / `parentOf` ingredient |
| 안에 든 그림은 어디서 왔는가 / Where the pictures inside come from | `componentOf` 재료(그림 자체의 기록) / `componentOf` ingredients |
| 이 기록이 지금 이 문서의 것인가 / Does the record belong to this document as it is now | 해시 결속과 서명 / hash binding and signature |

## 1. OWPML 패키지 안의 위치 / Where it sits in the OWPML package

HWPX 파일은 ZIP 패키지다. 출처 기록(매니페스트 저장소)은 파트 하나로 추가된다. 본문, 머리, 설정 같은 OWPML 파트와 스키마는 바뀌지 않는다.

An HWPX file is a ZIP package. The provenance record (manifest store) is added as one part. The OWPML parts and schema are not changed.

```mermaid
flowchart TB
  subgraph PKG["HWPX 파일 = OWPML 패키지 (ZIP) / HWPX file = OWPML package (ZIP)"]
    direction TB
    MT["mimetype<br/>application/hwp+zip"]
    VER["version.xml<br/>편집 프로그램 이름과 버전 / editor name and version"]
    subgraph CON["Contents/"]
      HPF["content.hpf<br/>메타데이터, 파트 목록 / metadata, part list"]
      HEAD["header.xml<br/>글꼴, 스타일 / fonts, styles"]
      SEC["section0.xml …<br/>본문 / body text"]
    end
    subgraph BIN["BinData/"]
      PIC["image1.png<br/>그림. 자체 C2PA 기록을 가질 수 있다<br/>picture, may carry its own C2PA record"]
    end
    subgraph META["META-INF/"]
      CXML["container.xml, manifest.xml"]
      C2PA["content_credential.c2pa<br/>C2PA 매니페스트 저장소 (추가되는 유일한 파트)<br/>C2PA manifest store (the only part added)"]
    end
    CD["ZIP 중앙 디렉터리 / ZIP central directory"]
  end
  C2PA -. "해시 / hash" .-> MT
  C2PA -. "해시 / hash" .-> VER
  C2PA -. "해시 / hash" .-> CON
  C2PA -. "해시 / hash" .-> BIN
  C2PA -. "해시 / hash" .-> CXML
  C2PA -. "해시 / hash" .-> CD
  style C2PA fill:#e6f4ec,stroke:#1a7f4b,stroke-width:2px
```

- 근거: C2PA 기술 규격 2.5 부속서 A.6(ZIP 기반 형식). 파트 이름은 `META-INF/content_credential.c2pa`이고 압축하지 않고 넣는다.
- 해시는 파트의 "내용"이 아니라 ZIP 항목 전체(로컬 헤더, 압축된 데이터)에 건다. 그래서 내용이 같아도 ZIP을 다시 쓰면 기록과 맞지 않게 된다.
- Basis: C2PA Technical Specification 2.5, Annex A.6 (ZIP-based formats). The part is `META-INF/content_credential.c2pa`, stored without compression.
- The hashes cover whole ZIP entries (local header and compressed data), not the decoded content. Rewriting the ZIP therefore breaks the match even if the content is the same.

## 2. 기록 안에 무엇이 들어 있는가 / What the record contains

저장소에는 판마다 매니페스트가 하나씩 들어간다. 가장 새 것이 "활성 매니페스트"이고, 이전 판과 그림의 매니페스트는 재료로 따라 들어온다.

The store holds one manifest per recorded version. The newest is the active manifest; the manifests of the previous version and of the pictures come along as ingredients.

```mermaid
flowchart LR
  subgraph STORE["META-INF/content_credential.c2pa — 매니페스트 저장소 / manifest store"]
    direction LR
    subgraph M2["매니페스트: 판 2 (활성) / Manifest: version 2 (active)"]
      direction TB
      A2["동작 / actions<br/>c2pa.opened → 이전 판 / previous version<br/>c2pa.edited · softwareAgent: Hancom Office Hangul 12.30<br/>설명 / description: 고친 이유 / note"]
      CH2["변경 요약 / change summary<br/>본문 문단 수정 1, 바뀐 파트 7 …<br/>1 paragraph modified, 7 parts changed …"]
      I2P["재료 parentOf / ingredient parentOf<br/>→ 판 1 / version 1"]
      I2C["재료 componentOf / ingredient componentOf<br/>→ BinData/image1.png"]
      H2["해시 결속 / hard binding<br/>c2pa.hash.collection.data<br/>항목별 해시 + 중앙 디렉터리 해시<br/>hash per entry + central directory hash"]
      CL2["클레임 / claim<br/>위 어서션들의 해시 목록, 기록 도구<br/>hashes of the assertions above, recording tool"]
      S2["서명 / signature (COSE)<br/>기록자 인증서, 타임스탬프<br/>recorder's certificate, time-stamp"]
      A2 --> CL2
      CH2 --> CL2
      I2P --> CL2
      I2C --> CL2
      H2 --> CL2
      CL2 --> S2
    end
    subgraph M1["매니페스트: 판 1 / Manifest: version 1"]
      direction TB
      A1["동작 / actions<br/>c2pa.created · softwareAgent: 만든 프로그램 / authoring tool"]
      S1["클레임 + 서명 / claim + signature"]
      A1 --> S1
    end
    subgraph MP["매니페스트: 그림 / Manifest: picture"]
      direction TB
      AP["동작 / actions<br/>c2pa.created (카메라, 그림 도구, 생성형 AI …)<br/>(camera, drawing tool, generative AI …)"]
      SP["클레임 + 서명 / claim + signature"]
      AP --> SP
    end
    I2P ==> M1
    I2C ==> MP
  end
```

- 클레임은 어서션들의 해시를 담고, 서명은 클레임에 붙는다. 그래서 동작 하나, 변경 요약 한 줄만 고쳐도 서명이 맞지 않는다.
- 이전 판의 매니페스트는 그 판을 기록한 주체의 서명을 그대로 가진 채 들어온다. 판마다 기록 주체가 달라도 된다(작성자, 검토자, 발행 기관).
- The claim holds the hashes of the assertions, and the signature covers the claim. Changing one action or one line of the change summary breaks the signature.
- The manifest of an earlier version keeps the signature of whoever recorded that version. Each version may be recorded by a different party (author, reviewer, issuing body).

## 3. 한 판을 기록하는 과정 / Recording one version

```mermaid
sequenceDiagram
  autonumber
  actor U as 작성자 / Author
  participant H as 한글 / Hangul
  participant T as hwpx-c2pa (애드온 / add-on)
  participant S as C2PA SDK (c2pa-rs)
  U->>H: 문서를 고치고 저장 / edit and save
  H->>H: 패키지를 새로 쓴다. 이전 기록 파트는 없어진다<br/>rewrites the package, the old record part is dropped
  H-->>T: 저장 이벤트 또는 폴더 감시 / save event or folder watcher
  T->>T: version.xml에서 편집 프로그램을 읽는다<br/>read the editor from version.xml
  T->>T: 보관해 둔 이전 판과 비교해 변경 요약을 만든다<br/>compare with the kept previous version, build the change summary
  T->>T: 자체 기록을 가진 그림을 찾는다<br/>find pictures that carry their own records
  T->>S: 동작, 변경 요약, 재료(이전 판, 그림)를 넘긴다<br/>actions, change summary, ingredients (previous version, pictures)
  S->>S: 항목별 해시와 중앙 디렉터리 해시 계산, 클레임 작성, 서명<br/>hash every entry and the central directory, build the claim, sign
  S-->>T: 기록 파트가 들어간 패키지 / package with the record part
  T->>H: 파일 교체 (잠겨 있으면 이름.c2pa.hwpx)<br/>replace the file (name.c2pa.hwpx if it is locked)
```

한글은 C2PA를 모르기 때문에 5~10단계를 애드온이 대신한다. 따라서 "편집 프로그램"과 "변경 요약"은 한글이 직접 증언한 것이 아니라, 기록 주체가 패키지를 보고 밝힌 내용이다(5절).

Hangul does not know C2PA, so the add-on does steps 5 to 10 in its place. The editor name and the change summary are therefore statements made by the recording party from the package, not testimony of Hangul itself (see clause 5).

## 4. 판이 이어지는 방식 / How versions are chained

```mermaid
flowchart LR
  V1["판 1 / Version 1<br/>c2pa.created<br/>기록: 작성자 A / recorded by author A"]
  E1(["한글에서 편집, 저장<br/>edit and save in Hangul<br/>기록 파트 없어짐 / record part dropped"])
  V2["판 2 / Version 2<br/>c2pa.opened + c2pa.edited<br/>변경 요약 / change summary<br/>기록: 검토자 B / recorded by reviewer B"]
  E2(["다시 편집, 저장 / edit and save again"])
  V3["판 3 / Version 3<br/>c2pa.opened + c2pa.edited<br/>변경 요약 / change summary<br/>기록: 발행 기관 C / recorded by issuer C"]
  P["그림 / Picture<br/>자체 기록 / own record"]
  V1 --> E1 --> V2 --> E2 --> V3
  V2 -. "parentOf: 판 1의 매니페스트를 품는다<br/>carries the manifest of version 1" .-> V1
  V3 -. "parentOf" .-> V2
  P -. "componentOf" .-> V1
  P -. "componentOf" .-> V2
  P -. "componentOf" .-> V3
```

- ZIP 형식에는 C2PA의 "갱신 매니페스트"를 쓸 수 없다. 그래서 판마다 새 매니페스트를 만들고 이전 판을 `parentOf` 재료로 잇는다.
- 판 3의 파일 하나만 있으면 판 1, 2, 3의 기록과 그림의 기록을 모두 볼 수 있다. 이전 판의 본문은 들어 있지 않다. 들어 있는 것은 기록뿐이다.
- 이전 판 없이 저장본만 기록하면 그 판은 새 출발점(`c2pa.created`)이 되고 이력이 끊긴다. 애드온이 저장 전 판을 보관하는 이유다.
- ZIP formats cannot take C2PA update manifests, so each version gets a new manifest with the previous version as its `parentOf` ingredient.
- The file of version 3 alone shows the records of versions 1, 2 and 3 and of the picture. It does not contain the text of earlier versions, only their records.
- If a saved file is recorded without its previous version, it becomes a new starting point (`c2pa.created`) and the history is cut. This is why the add-ons keep the version from before the save.

## 5. 확인하는 과정과 알 수 있는 것 / Checking, and what can be concluded

```mermaid
flowchart TB
  START(["문서를 받음 / a document arrives"]) --> Q1{"기록 파트가 있는가?<br/>is there a record part?"}
  Q1 -- "없음 / no" --> R0["출처 기록 없음<br/>출처를 알 수 없다. 변조라는 뜻은 아니다<br/>No record: origin unknown, which is not evidence of tampering"]
  Q1 -- "있음 / yes" --> Q2{"서명이 클레임과 맞는가?<br/>does the signature match the claim?"}
  Q2 -- "아니오 / no" --> RX["무효: 기록이 손상되었거나 고쳐졌다<br/>Invalid: the record is damaged or altered"]
  Q2 -- "예 / yes" --> Q3{"모든 ZIP 항목과 중앙 디렉터리의<br/>해시가 기록과 맞는가?<br/>do all entry hashes and the central<br/>directory hash match the record?"}
  Q3 -- "아니오 / no" --> RY["무효: 마지막 기록 이후 문서가 바뀌었다<br/>어느 파트가 다른지 표시된다<br/>Invalid: the document changed after the last record,<br/>the differing part is shown"]
  Q3 -- "예 / yes" --> Q4{"이전 판과 그림의 기록도 온전한가?<br/>are the records of earlier versions<br/>and pictures intact?"}
  Q4 -- "아니오 / no" --> RZ["그 단계에 문제 표시<br/>the step is flagged"]
  Q4 -- "예 / yes" --> Q5{"기록자의 인증서가 신뢰 목록에 닿는가?<br/>does the recorder's certificate<br/>chain to a trust list?"}
  RZ --> Q5
  Q5 -- "아니오 / no" --> RV["유효 (Valid)<br/>기록은 온전하다. 기록자가 누구인지는 보증되지 않는다<br/>the record is intact, the recorder's identity is not vouched for"]
  Q5 -- "예 / yes" --> RT["신뢰됨 (Trusted)<br/>기록은 온전하고 기록자가 확인된다<br/>the record is intact and the recorder is identified"]
  RV --> OUT["출처와 수정 이력을 보여 준다<br/>show origin and edit history"]
  RT --> OUT
  style RT fill:#e6f4ec,stroke:#1a7f4b
  style RV fill:#fdf3d7,stroke:#8a6100
  style RX fill:#fbe9e7,stroke:#b3261e
  style RY fill:#fbe9e7,stroke:#b3261e
  style R0 fill:#eceff3,stroke:#4a5565
```

기록이 온전할 때 말할 수 있는 것과 없는 것 / What an intact record does and does not establish:

| 구분 / Kind | 내용 / Content | 믿는 근거 / Rests on |
|---|---|---|
| 암호로 확인됨 / Cryptographically checked | 기록 이후 문서의 어떤 바이트도 바뀌지 않았다. 기록 자체도 바뀌지 않았다. 이전 판과 그림의 기록이 그 판의 것이다 / no byte of the document or of the record changed since recording; earlier records are the ones that were attached | 해시, 서명 / hashes, signature |
| 인증서로 확인됨 / Checked through certificates | 기록 주체가 누구인가 / who recorded it | 신뢰 목록, 인증 기관 / trust list, CA |
| 타임스탬프로 확인됨 / Checked through a time-stamp | 기록 시각(TSA를 쓴 경우) / time of recording, if a TSA was used | 타임스탬프 기관 / time-stamp authority |
| 기록 주체의 진술 / Statement of the recorder | 편집 프로그램, 동작, 변경 요약, 메모, TSA 없는 시각 / editor, actions, change summary, note, time without a TSA | 기록 주체에 대한 신뢰 / trust in the recorder |
| 알 수 없음 / Not established | 본문 내용이 사실인가. 기록되지 않은 중간 저장에서 무슨 일이 있었는가 / whether the content is true; what happened in saves that were not recorded | — |

- "기록 주체의 진술" 줄이 중요하다. 지금은 한글이 아니라 애드온이 기록하므로, 편집 프로그램 이름은 `version.xml`에 적힌 값을 옮긴 것이다. 한글이 저장할 때 직접 기록하게 되면 이 줄의 항목이 "편집 프로그램이 증언함"으로 올라간다. [hangul-c2pa-support.md](hangul-c2pa-support.md)의 개선점이 겨냥하는 것이 이것이다.
- The row "statement of the recorder" matters. Today the add-on records, not Hangul, so the editor name is copied from `version.xml`. Once Hangul records at save time itself, these items become testimony of the editing program. That is what the improvements in [hangul-c2pa-support.md](hangul-c2pa-support.md) aim at.

## 6. 이 도구에서 보기 / Seeing it with this tool

```bash
hwpx-c2pa history samples/ko/3b-saved-in-hangul-resigned.hwpx   # 판별 이력 / history per version
hwpx-c2pa view    samples/ko/3b-saved-in-hangul-resigned.hwpx --trust samples/test-root-ca.pem
```

![수정 이력 / edit history](screenshots/04-view-edit-history.png)
