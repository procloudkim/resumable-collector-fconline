# Contributing

> This repository welcomes documentation-first contributions. Please avoid changing code/DB unless requested.

## Ground rules
- Encoding: Use UTF-8 (no BOM). Avoid CP949/ANSI artifacts.
- Style: Keep Korean docs concise and task-oriented. Prefer bullet points with bolded keywords.
- Scope: When in doubt, update docs only; do not change code or DB schemas.
- Tests: If you touch code (only when requested), run `pytest -q` and keep changes minimal.

## Where to start
- Read: `docs/INDEX.md` and `docs/LOCAL_ARCHITECTURE_OVERVIEW_KR.md`.
- For 출전 랭킹 (project2): see `docs/PROJECT2_RUNBOOK_KR.md` and `docs/PROJECT2_PRD_KR.md`.
- For BestPrice: see root `project/` and docs `PRD.md` and `ERD.md`.

## Documentation checklist
- Add cross-links (README ↔ pipeline docs ↔ ERD/PRD/BDD).
- Verify paths and commands exist (clickable in editor).
- Confirm encoding is clean on Windows and GitHub Web.
- Update `CHANGELOG.md` with a short “Docs” entry.

## Commit messages
- Use conventional types: `docs:`, `chore:`, `ci:`, `test:`, `feat:` (only if code changes are intended), `fix:`.
- Keep subject lines short; add context in body if needed.

## PR review checklist
- [ ] Docs render correctly in GitHub
- [ ] Links are valid
- [ ] No PII/API keys in examples
- [ ] No code/DB changes unless requested
- [ ] CHANGELOG updated
