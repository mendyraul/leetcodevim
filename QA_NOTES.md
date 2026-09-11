# QA Notes

## Checks run
- `python -m compileall -q src tests` ✅
- `ruff check src tests` ✅
- `pytest -q` ✅
- `python -m build` ✅
- Installed-wheel `leetcodevim --help` smoke test ✅
- Headless Vim plugin load ✅

## Current architecture
- Workspace state, cached problem definitions, examples, and submission history live in `.leetcodevim/state.db`.
- Existing `.leetcodevim-state.json` files are imported without deletion.
- Python solutions use the LeetCode-provided `Solution` class/method scaffold.
- C++ remains scaffold-only until a compiler/runtime contract is implemented.

## Remaining manual QA
1. Pull a real problem with network access and confirm the generated method signature.
2. Solve the cached examples and run `leetcodevim test --slug <slug>` from outside the problem directory.
3. Verify keyring/browser-cookie auth and a real submission in a controlled account.
