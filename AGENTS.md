# 프로젝트: Python PDF Parser

## 기술 스택
- Python 3.11+
- PyMuPDF: PDF 메타데이터, 페이지, 텍스트 블록 추출
- pdfplumber: 표 추출
- pytest: 테스트
- ruff: 린트

## 아키텍처 규칙
- CRITICAL: CLI는 입력 검증, 옵션 파싱, 출력만 담당하고 핵심 파싱 로직은 `src/pdf_parser/` 라이브러리 API에 둔다.
- CRITICAL: 외부 PDF 백엔드 의존성은 백엔드 모듈 내부에서 lazy import하여, 모델/CLI 테스트가 의존성 설치 없이 import 가능해야 한다.
- 공개 API는 `parse_pdf(path, options=None)`를 중심으로 유지한다.
- 파싱 결과는 명시적 도메인 모델에서 `to_dict()`/`to_json()`으로 직렬화한다.
- 부분 실패는 가능하면 전체 실패로 만들지 말고 `ParseWarning`으로 표현한다.
- OCR은 MVP 범위에서 제외하고 스캔형 PDF 감지만 수행한다.

## 개발 프로세스
- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성할 것 (TDD)
- 커밋 메시지는 conventional commits 형식을 따를 것 (feat:, fix:, docs:, refactor:)

## 명령어
python3 -m pip install -e ".[dev]"  # 개발 의존성 설치
python3 -m pytest                   # 테스트
python3 -m ruff check .             # 린트
pdf-parser input.pdf                # CLI 실행
