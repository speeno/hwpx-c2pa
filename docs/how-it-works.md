# How it works: C2PA in an OWPML package, and how provenance is shown

**English** | [한국어](how-it-works.ko.md)

C2PA is not a signing feature. Its purpose is that a document carries **where it came from and who did what, with which tool, at each version**. The signature and the hashes are only the means of showing that this record has not been altered.

| Question | Answered by |
|---|---|
| Who recorded it | Subject of the signing certificate |
| When | Time-stamp (TSA), else the time stated by the recorder |
| Made and edited with what | `softwareAgent` of each action |
| What was done | The actions `c2pa.created`, `c2pa.opened`, `c2pa.edited` |
| What changed since the previous version | Change summary assertion |
| Which version it derives from | `parentOf` ingredient |
| Where the pictures inside come from | `componentOf` ingredients (the pictures' own records) |
| Does the record belong to this document as it is now | Hash binding and signature |

## 1. Where it sits in the OWPML package

An HWPX file is a ZIP package. The provenance record (manifest store) is added as one part. The OWPML parts and schema are not changed.

```mermaid
flowchart TB
  subgraph PKG["HWPX file = OWPML package (ZIP)"]
    direction TB
    MT["mimetype<br/>application/hwp+zip"]
    VER["version.xml<br/>editor name and version"]
    subgraph CON["Contents/"]
      HPF["content.hpf<br/>metadata, part list"]
      HEAD["header.xml<br/>fonts, styles"]
      SEC["section0.xml …<br/>body text"]
    end
    subgraph BIN["BinData/"]
      PIC["image1.png<br/>picture, may carry its own C2PA record"]
    end
    subgraph META["META-INF/"]
      CXML["container.xml, manifest.xml"]
      C2PA["content_credential.c2pa<br/>C2PA manifest store<br/>(the only part added)"]
    end
    CD["ZIP central directory"]
  end
  C2PA -. "hash" .-> MT
  C2PA -. "hash" .-> VER
  C2PA -. "hash" .-> CON
  C2PA -. "hash" .-> BIN
  C2PA -. "hash" .-> CXML
  C2PA -. "hash" .-> CD
  style C2PA fill:#e6f4ec,stroke:#1a7f4b,stroke-width:2px
```

- Basis: C2PA Technical Specification 2.5, Annex A.6 (ZIP-based formats). The part is `META-INF/content_credential.c2pa`, stored without compression.
- The hashes cover whole ZIP entries (local header and compressed data), not the decoded content. Rewriting the ZIP therefore breaks the match even if the content is the same.

## 2. What the record contains

The store holds one manifest per recorded version. The newest is the active manifest; the manifests of the previous version and of the pictures come along as ingredients.

```mermaid
flowchart LR
  subgraph STORE["META-INF/content_credential.c2pa — manifest store"]
    direction LR
    subgraph M2["Manifest: version 2 (active)"]
      direction TB
      A2["actions<br/>c2pa.opened → previous version<br/>c2pa.edited · softwareAgent: Hancom Office Hangul 12.30<br/>description: note from the recorder"]
      CH2["change summary<br/>1 paragraph modified, 7 parts changed …"]
      I2P["ingredient parentOf<br/>→ version 1"]
      I2C["ingredient componentOf<br/>→ BinData/image1.png"]
      H2["hard binding<br/>c2pa.hash.collection.data<br/>hash per entry + central directory hash"]
      CL2["claim<br/>hashes of the assertions above, recording tool"]
      S2["signature (COSE)<br/>recorder's certificate, time-stamp"]
      A2 --> CL2
      CH2 --> CL2
      I2P --> CL2
      I2C --> CL2
      H2 --> CL2
      CL2 --> S2
    end
    subgraph M1["Manifest: version 1"]
      direction TB
      A1["actions<br/>c2pa.created · softwareAgent: authoring tool"]
      S1["claim + signature"]
      A1 --> S1
    end
    subgraph MP["Manifest: picture"]
      direction TB
      AP["actions<br/>c2pa.created<br/>(camera, drawing tool, generative AI …)"]
      SP["claim + signature"]
      AP --> SP
    end
    I2P ==> M1
    I2C ==> MP
  end
```

- The claim holds the hashes of the assertions, and the signature covers the claim. Changing one action or one line of the change summary breaks the signature.
- The manifest of an earlier version keeps the signature of whoever recorded that version. Each version may be recorded by a different party (author, reviewer, issuing body).

## 3. Recording one version

```mermaid
sequenceDiagram
  autonumber
  actor U as Author
  participant H as Hangul
  participant T as hwpx-c2pa (add-on)
  participant S as C2PA SDK (c2pa-rs)
  U->>H: edit and save
  H->>H: rewrites the package, the old record part is dropped
  H-->>T: save event or folder watcher
  T->>T: read the editor from version.xml
  T->>T: compare with the kept previous version, build the change summary
  T->>T: find pictures that carry their own records
  T->>S: actions, change summary, ingredients (previous version, pictures)
  S->>S: hash every entry and the central directory, build the claim, sign
  S-->>T: package with the record part
  T->>H: replace the file (name.c2pa.hwpx if it is locked)
```

Hangul does not know C2PA, so the add-on does steps 4 to 10 in its place. The editor name and the change summary are therefore statements made by the recording party from the package, not testimony of Hangul itself (see clause 5).

## 4. How versions are chained

```mermaid
flowchart LR
  V1["Version 1<br/>c2pa.created<br/>recorded by author A"]
  E1(["edit and save in Hangul<br/>record part dropped"])
  V2["Version 2<br/>c2pa.opened + c2pa.edited<br/>change summary<br/>recorded by reviewer B"]
  E2(["edit and save again"])
  V3["Version 3<br/>c2pa.opened + c2pa.edited<br/>change summary<br/>recorded by issuer C"]
  P["Picture<br/>own record"]
  V1 --> E1 --> V2 --> E2 --> V3
  V2 -. "parentOf: carries the manifest of version 1" .-> V1
  V3 -. "parentOf" .-> V2
  P -. "componentOf" .-> V1
  P -. "componentOf" .-> V2
  P -. "componentOf" .-> V3
```

- ZIP formats cannot take C2PA update manifests, so each version gets a new manifest with the previous version as its `parentOf` ingredient.
- The file of version 3 alone shows the records of versions 1, 2 and 3 and of the picture. It does not contain the text of earlier versions, only their records.
- If a saved file is recorded without its previous version, it becomes a new starting point (`c2pa.created`) and the history is cut. This is why the add-ons keep the version from before the save.

## 5. Checking, and what can be concluded

```mermaid
flowchart TB
  START(["a document arrives"]) --> Q1{"is there a record part?"}
  Q1 -- "no" --> R0["No record<br/>origin unknown, which is not evidence of tampering"]
  Q1 -- "yes" --> Q2{"does the signature match the claim?"}
  Q2 -- "no" --> RX["Invalid<br/>the record is damaged or altered"]
  Q2 -- "yes" --> Q3{"do all entry hashes and the central<br/>directory hash match the record?"}
  Q3 -- "no" --> RY["Invalid<br/>the document changed after the last record,<br/>the differing part is shown"]
  Q3 -- "yes" --> Q4{"are the records of earlier versions<br/>and pictures intact?"}
  Q4 -- "no" --> RZ["the step is flagged"]
  Q4 -- "yes" --> Q5{"does the recorder's certificate<br/>chain to a trust list?"}
  RZ --> Q5
  Q5 -- "no" --> RV["Valid<br/>the record is intact,<br/>the recorder's identity is not vouched for"]
  Q5 -- "yes" --> RT["Trusted<br/>the record is intact<br/>and the recorder is identified"]
  RV --> OUT["show origin and edit history"]
  RT --> OUT
  style RT fill:#e6f4ec,stroke:#1a7f4b
  style RV fill:#fdf3d7,stroke:#8a6100
  style RX fill:#fbe9e7,stroke:#b3261e
  style RY fill:#fbe9e7,stroke:#b3261e
  style R0 fill:#eceff3,stroke:#4a5565
```

What an intact record does and does not establish:

| Kind | Content | Rests on |
|---|---|---|
| Cryptographically checked | No byte of the document or of the record changed since recording; the earlier records are the ones that were attached | Hashes, signature |
| Checked through certificates | Who recorded it | Trust list, CA |
| Checked through a time-stamp | Time of recording, if a TSA was used | Time-stamp authority |
| Statement of the recorder | Editor, actions, change summary, note, time without a TSA | Trust in the recorder |
| Not established | Whether the content is true; what happened in saves that were not recorded | — |

The row "statement of the recorder" matters. Today the add-on records, not Hangul, so the editor name is copied from `version.xml`. Once Hangul records at save time itself, these items become testimony of the editing program. That is what the improvements in [hangul-c2pa-support.md](hangul-c2pa-support.md) aim at.

## 6. Seeing it with this tool

```bash
hwpx-c2pa history samples/en/3b-saved-in-hangul-resigned.hwpx   # history per version
hwpx-c2pa view    samples/en/3b-saved-in-hangul-resigned.hwpx --trust samples/test-root-ca.pem
```

![Edit history](screenshots/06-view-edit-history-en-sample.png)
