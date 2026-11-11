# 고지 사항

[English](NOTICE.md) | **한국어**

hwpx-c2pa — Copyright (c) 2026 Dongsun Nam (speeno). MIT 라이선스로 배포한다([LICENSE](LICENSE) 참조). MIT 라이선스는 이 프로젝트를 위해 만든 코드, 문서, 샘플 문서, 그림에 적용된다. 아래에 적은 제3자의 자료와 권리에는 적용되지 않는다.

## 독립성

이 프로젝트는 독립 프로젝트다. (주)한글과컴퓨터, C2PA(Coalition for Content Provenance and Authenticity), Content Authenticity Initiative, Adobe, Microsoft와 제휴, 보증, 후원 관계가 없다.

## 상표

"한글", "한컴오피스", "Hancom Office", "HWP", "HWPX"는 (주)한글과컴퓨터의 이름 또는 상표다. "C2PA"와 "Content Credentials"는 각 권리자의 표장이다. "Windows"와 "Microsoft Edge"는 Microsoft의 상표다. 이 이름들은 이 소프트웨어가 무엇과 함께 동작하는지 말하기 위해서만 썼다.

## 한글과컴퓨터

- 본 제품은 한글과컴퓨터의 한글 문서 파일(.hwp) 공개 문서를 참고하여 개발하였습니다.
- 애드온은 한컴의 공개 개발 문서(한글 오토메이션 매뉴얼, 2008년 외부 배포용 "Addon Action" 안내서)와 한글 2024의 동작을 관찰한 결과로 만들었다. 한컴의 소스 코드, 헤더 파일, 타입 라이브러리, 이미지, 문서는 들어 있지 않다. `addon/windows/useraction/src/HncUserAction.h`는 그 안내서에 설명된 User Action 모듈 인터페이스의 함수 네 개를 다시 선언한 것이며, 모듈이 한글에서 호출되려면 필요하다.
- 한글 오토메이션의 사용은 한컴의 조건을 따른다. 한컴은 개인의 비상업적 사용에 한해 무료이고 상업적 사용에는 한컴의 승인이 필요하다고 밝히고 있다. 이 프로젝트의 MIT 라이선스는 한컴의 소프트웨어나 인터페이스에 대한 어떤 권리도 주지 않는다. 애드온을 쓰는 사람이 한컴의 조건을 지킬 책임이 있다.
- `docs/screenshots/win-*.png`는 정품 한글 2024에서 찍었다. 그중 한 장은 애드온 버튼이 어디에 나타나는지 보이기 위해 한글 도구 모음의 일부를 담고 있다. 한글의 사용자 인터페이스는 (주)한글과컴퓨터의 자산이다.

## 규격

- C2PA 기술 규격 2.5, Copyright © Coalition for Content Provenance and Authenticity, CC BY 4.0. 이 프로젝트는 규격을 구현하고 인용할 뿐 본문을 옮겨 싣지 않았다.
- KS X 6101(OWPML)은 조항과 요소 이름만 인용했다. 표준 본문은 옮겨 싣지 않았다.

## 사용하지만 포함하지 않은 소프트웨어

| 소프트웨어 | 라이선스 | 사용 방식 |
|---|---|---|
| [c2pa-python](https://github.com/contentauth/c2pa-python) | MIT OR Apache-2.0 | pip이 설치하는 의존 패키지 |
| [c2pa-rs](https://github.com/contentauth/c2pa-rs) 네이티브 라이브러리 | MIT OR Apache-2.0 | `hwpx-c2pa fetch-lib`가 공식 릴리스에서 체크섬을 확인하며 내려받는다. 여기서 재배포하지 않는다 |
| [cryptography](https://github.com/pyca/cryptography) | Apache-2.0 OR BSD-3-Clause | 선택 사항, 시험용 인증서 |
| [pywin32](https://github.com/mhammond/pywin32) | PSF-2.0 | 선택 사항, Windows 오토메이션 |

릴리스에 올리는 애드온 DLL은 이 저장소의 소스만으로 빌드하며, Microsoft Visual C++ 런타임을 그 라이선스가 허용하는 대로 정적으로 링크한다.

## 샘플 문서

`samples/`의 파일은 `samples/make_samples.py`로 이 프로젝트를 위해 만들었다.

- 패키지의 틀(빈 문서의 스타일과 설정)은 [python-hwpx](https://github.com/airmang/python-hwpx)의 빈 문서에서 왔다. Copyright 2025-2026 airmang, Apache License 2.0(http://www.apache.org/licenses/LICENSE-2.0). 바꾼 점: 본문, 생성한 그림, C2PA 콘텐츠 자격 증명을 넣었고 `version.xml`에 생성 도구를 적었다.
- `3a-…`, `3b-…` 파일은 그 뒤 macOS용 한글 12.30에서 열어 고치고 저장한 것으로, 한글이 패키지를 다시 썼다.
- 그림은 스크립트가 생성한 것이다. 글꼴은 포함되어 있지 않고 이름만 지정되어 있다.
- 인증서는 이 샘플을 위해 만든 시험용이다. 루트 인증서만 공개한다. 어떤 것도 보증하지 않는다.

## 보증 없음

이 소프트웨어는 기록 주체가 문서에 대해 밝힌 내용을 기록하고, 그 기록이 바뀌면 드러나게 한다. 문서 내용이 사실임을 보증하지 않으며, LICENSE에 적힌 대로 어떤 보증도 없이 제공된다.
