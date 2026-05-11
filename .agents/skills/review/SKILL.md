---
name: review
description: Review Harness framework project changes against AGENTS.md, docs/ARCHITECTURE.md, docs/ADR.md, tests, and build requirements. Use when the user asks to review changes, validate a phase step output, or check whether work follows the repository guardrails.
---

# Review

Use this skill to review repository changes with the Harness guardrails. Prioritize actionable findings over summaries.

## Review Workflow

1. Read `/AGENTS.md`, `/docs/ARCHITECTURE.md`, and `/docs/ADR.md`.
2. Inspect changed files with `git status --short` and `git diff`.
3. Check whether the implementation follows the documented architecture and technology decisions.
4. Verify that new behavior has focused tests.
5. Run the relevant build, lint, and test commands when available.

## Checklist

Evaluate these items:

- Architecture compliance: Does the change follow the directory and module structure in `ARCHITECTURE.md`?
- Technology compliance: Does it stay within decisions recorded in `ADR.md`?
- Tests: Are new features or behavior changes covered?
- Critical rules: Does it comply with `AGENTS.md`, especially CRITICAL rules?
- Buildability: Do relevant validation commands pass?

## Output

Lead with findings, ordered by severity. Include file and line references when possible.

If the user asks for the original table format, use:

| 항목 | 결과 | 비고 |
|------|------|------|
| 아키텍처 준수 | pass/fail | {detail} |
| 기술 스택 준수 | pass/fail | {detail} |
| 테스트 존재 | pass/fail | {detail} |
| CRITICAL 규칙 | pass/fail | {detail} |
| 빌드 가능 | pass/fail | {detail} |

When no issues are found, state that clearly and mention any tests that could not be run.
