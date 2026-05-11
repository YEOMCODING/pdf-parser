# 아키텍처

## 디렉토리 구조

```text
.
├── pyproject.toml
├── src/
│   └── pdf_parser/
│       ├── __init__.py
│       ├── cli.py
│       ├── models.py
│       ├── parser.py
│       ├── pymupdf_backend.py
│       ├── pdfplumber_backend.py
│       └── warnings.py
└── tests/
    ├── fixtures/
    ├── test_cli.py
    ├── test_models.py
    └── test_parser.py
```

## 패턴

- `CLI + 라이브러리` 구조를 기본으로 한다.
- CLI는 입력 검증, 옵션 파싱, 출력만 담당하고 핵심 로직은 라이브러리 API로 위임한다.
- 공개 API는 `parse_pdf(path, options=None)`를 중심으로 유지한다.
- 대용량 처리는 `parse_pdf_stream(path, options=None)`와 JSONL 출력 경로로 제공한다.
- 파싱 결과는 `ParsedDocument`, `ParsedPage`, `TextBlock`, `Table`, `ParseWarning`, `ParseOptions` 같은 명시적 도메인 모델로 표현한다.
- 구현 파일을 추가하거나 변경할 때는 대응 테스트를 먼저 작성한다.

## 데이터 흐름

```text
사용자 CLI/API 호출
  -> ParseOptions 생성
  -> parse_pdf(path, options)
  -> PyMuPDF 백엔드로 메타데이터/페이지/텍스트 블록 추출
  -> pdfplumber 백엔드로 표 추출
  -> 스캔형 PDF 감지 및 warning 수집
  -> ParsedDocument 생성
  -> dict/JSON 직렬화
```

대용량 JSONL 모드는 전체 `ParsedDocument`를 만들지 않고 페이지 단위 record를 순차 처리한다.

```text
사용자 CLI/API 호출
  -> ParseOptions 생성
  -> parse_pdf_stream(path, options)
  -> document record 출력
  -> PyMuPDF 백엔드로 페이지를 하나씩 추출
  -> 선택적으로 페이지별 표 추출
  -> page/warning record 즉시 출력
  -> summary record 출력
```

## 파싱 엔진 역할

- PyMuPDF
  - PDF 열기와 기본 유효성 검증
  - 문서 메타데이터 추출
  - 페이지 크기와 페이지 순서 보존
  - 텍스트 블록 추출
- pdfplumber
  - 페이지별 표 추출
  - 행/열 구조 보존
  - 표 추출 실패 시 전체 파싱을 중단하지 않고 page-level warning 기록

## 오류와 Warning 정책

- 입력 파일이 없거나 PDF를 열 수 없는 경우는 명확한 예외 또는 CLI non-zero exit code로 처리한다.
- 일부 페이지의 표 추출 실패처럼 문서 전체를 버릴 필요가 없는 문제는 warning으로 기록한다.
- JSONL 스트리밍 모드의 페이지 처리 실패는 warning record로 기록하고 다음 페이지를 계속 처리한다.
- 텍스트가 거의 없는 스캔형 PDF는 `scanned_pdf_detected` warning을 남긴다.
- OCR은 MVP에서 수행하지 않는다.

## JSON 출력 원칙

- 최상위에는 `metadata`, `pages`, `warnings`, `engine` 정보를 포함한다.
- 페이지 데이터는 페이지 번호, 크기, 텍스트 블록, 표, 페이지 warning을 포함한다.
- 좌표 정보는 페이지/블록 수준의 최소 정보만 보존한다.
- 단어 단위 좌표와 원본 레이아웃 재구성은 후속 기능으로 둔다.
- JSONL 출력은 `document`, `page`, `warning`, `summary` record를 한 줄에 하나씩 기록한다.
- JSONL record는 공개 도메인 모델을 추가하지 않고 `dict` 기반 전송 포맷으로 유지한다.

## 검증

- 기본 검증 명령은 `python -m pytest`와 `python -m ruff check .`이다.
- CLI 동작, JSON 직렬화, 텍스트 추출, 표 추출, 스캔 PDF warning을 테스트한다.
- 정확성을 우선하며 성능 최적화는 MVP 이후에 다룬다.
