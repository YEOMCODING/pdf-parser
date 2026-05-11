---
name: harness
description: Codex로 Harness 프레임워크의 단계 계획을 설계, 생성, 실행합니다. 사용자가 구현 단계 계획, phases/index.json 또는 phases/{task}/stepN.md 파일 생성, scripts/execute.py로 Harness 작업 실행, 이 저장소의 단계 기반 워크플로 관리를 요청할 때 사용합니다.
---

# Harness

이 스킬은 저장소의 Harness 워크플로를 운영할 때 사용합니다. 프로젝트 문서를 읽고, 불명확한 구현 결정을 논의하고, 단계 파일을 만들고, `scripts/execute.py`를 실행해 Codex로 단계를 수행합니다.

## 워크플로

1. `/AGENTS.md`, `/docs/PRD.md`, `/docs/ARCHITECTURE.md`, `/docs/ADR.md`, 그리고 관련 있는 다른 `/docs/*.md` 파일을 읽습니다.
2. 단계 파일을 작성하기 전에 불명확한 제품 결정이나 기술 결정을 식별합니다.
3. 사용자가 구현 계획을 요청하면 작고 독립적인 단계 초안을 만들고, 파일을 생성하기 전에 피드백을 요청합니다.
4. 승인 후 `phases/index.json`, `phases/{task-name}/index.json`, 그리고 각 단계의 `phases/{task-name}/step{N}.md`를 생성하거나 업데이트합니다.
5. 작업 실행을 요청받으면 다음을 실행합니다.

```bash
python3 scripts/execute.py {task-name}
```

사용자가 결과 브랜치 푸시를 명시적으로 원할 때만 `--push`를 사용합니다.

## 단계 설계 규칙

- 각 단계는 하나의 계층이나 모듈에 집중하게 합니다. 서로 관련 없는 여러 영역을 건드리는 단계는 나눕니다.
- 모든 단계는 자체 완결적이어야 합니다. 이전 채팅 맥락에 의존하지 말고, 필요한 모든 파일 경로와 지침을 단계 파일에 포함합니다.
- Codex 단계 세션이 수정 전에 반드시 읽어야 할 파일을 나열합니다.
- 인터페이스, 파일 경로, 불변 조건, 인수 기준을 명시합니다. 유효한 구현 방식이 여러 개라면 세부 구현은 실행하는 에이전트에게 맡깁니다.
- 인수 기준은 `npm run build`, `npm test`처럼 실행 가능한 명령으로 작성합니다.
- 금지사항은 "X를 하지 마세요. 이유: Y."처럼 구체적으로 작성합니다.
- 단계 이름은 `project-setup`, `api-layer`, `auth-flow`처럼 kebab-case를 사용합니다.

## 파일 템플릿

최상위 `phases/index.json`:

```json
{
  "phases": [
    {
      "dir": "0-mvp",
      "status": "pending"
    }
  ]
}
```

작업 수준 `phases/{task-name}/index.json`:

```json
{
  "project": "<project-name>",
  "phase": "<task-name>",
  "steps": [
    { "step": 0, "name": "project-setup", "status": "pending" }
  ]
}
```

단계 파일 골격:

````markdown
# 단계 {N}: {이름}

## 읽어야 할 파일

- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md`
- `/AGENTS.md`
- {이전-단계-출력-파일}

## 작업

{구체적인-작업-지침}

## 인수 기준

```bash
{검증-명령}
```

## 검증 절차

1. 인수 기준 명령을 실행한다.
2. ARCHITECTURE.md, ADR, AGENTS.md 규칙을 위반하지 않았는지 확인한다.
3. `phases/{task-name}/index.json`의 해당 단계를 업데이트한다.

## 금지사항

- {하지-말아야-할-일. 이유}
````

## 상태 의미

- `pending`: 아직 실행되지 않았습니다.
- `completed`: 이후 단계에 유용한 파일과 결정을 담은 `summary`를 포함합니다.
- `error`: 재시도 실패 후 `error_message`를 포함합니다.
- `blocked`: 사용자 조치가 필요할 때 `blocked_reason`을 포함합니다.

`scripts/execute.py`는 타임스탬프를 기록하고, 완료된 단계 요약을 다음 단계로 전달하며, 실패한 단계를 최대 세 번 재시도하고, 기능 커밋과 메타데이터 커밋을 분리합니다.
