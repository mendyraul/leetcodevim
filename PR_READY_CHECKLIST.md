# PR Ready Checklist (leetcodevim)

## Quality gates
- [x] `pytest -q` passes locally
- [x] GitHub Actions workflow present (`.github/workflows/python-ci.yml`)
- [ ] CI green on GitHub

## Security & hygiene
- [x] Remove editor swap/temp artifacts from tracking
- [x] Ignore `*.swp` / `*.swo`
- [ ] Review token/cookie handling paths before merge

## Merge plan
1. Merge `feature/initial-validation` -> `dev`
2. Smoke test install:
   - `pip install -e .`
   - `leetcodevim --help`
3. If green, merge `dev` -> `main` (Raul approval required)
