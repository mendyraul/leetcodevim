# PR Ready Checklist (leetcodevim)

## Quality gates
- [x] `pytest -q` passes locally
- [x] GitHub Actions workflow present (`.github/workflows/python-ci.yml`)
- [ ] CI green on GitHub
- [x] Package build and installed CLI smoke test pass locally
- [x] SQLite migration and native Python runner tests pass locally

## Security & hygiene
- [x] Remove editor swap/temp artifacts from tracking
- [x] Ignore `*.swp` / `*.swo`
- [ ] Review token/cookie handling paths before merge

## Merge plan
1. Port the useful changes from stale PRs #9 and #10 into a fresh branch from current `main`.
2. Run the full CI workflow and review the generated wheel smoke test.
3. If green, merge the fresh implementation branch to `main`; close or supersede the conflicting PRs.
