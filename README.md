# leetcode-vim

Minimal CLI + Vim plugin to work on LeetCode problems locally.

## Quick start

1) Install the CLI:

```bash
pip install leetcode-vim
```

2) Initialize config:

```bash
leetcodevim init --workspace ~/leetcode --language python
```

3) Pull a problem — auth is not required for this step:

```bash
leetcodevim pull two-sum
```

Or from Vim:

```vim
:LeetCodePull two-sum
```

This creates `solution.py`, `problem.txt`, and `sample.txt` in your workspace when LeetCode's public problem API is reachable.

4) Save your LeetCode session token only when you want account-specific actions like `submit` or `auth whoami`:

```bash
leetcodevim auth set --session "<LEETCODE_SESSION>" --csrf "<csrftoken>"
```

## Auth notes

- `pull`, `list`, and local file generation work without auth.
- `submit`, `auth whoami`, and other account-specific calls require `LEETCODE_SESSION` (and `LEETCODE_CSRF` for submit).
- The CLI reads `LEETCODE_SESSION` and `LEETCODE_CSRF` from the environment first.
- Tokens are stored in the OS keychain via `keyring` when available, otherwise in `~/.config/leetcode-vim/config.json`.
- Config files are written with `0600` permissions where supported.
- You can temporarily override without writing to disk:

```bash
LEETCODE_SESSION="<token>" LEETCODE_CSRF="<token>" leetcodevim submit
```

If you forget the steps, run:

```bash
leetcodevim auth login
```

To verify auth or clear it:

```bash
leetcodevim auth whoami
leetcodevim auth logout
```

You can also import cookies directly from your browser:

```bash
leetcodevim auth import-cookie --browser chrome --domain leetcode.com
```

## After pip install

1) Run `leetcodevim init --workspace ~/leetcode --language python`
2) Run `leetcodevim pull two-sum`
3) Optional: run `leetcodevim auth login`, then `leetcodevim auth set ...` before using `submit`
4) In Vim, run `:LeetCodePull two-sum`

## Testing and submitting

From a problem directory:

```bash
leetcodevim test
leetcodevim test --slug two-sum
leetcodevim submit
```

## Listing problems

CLI:

```bash
leetcodevim list
```

Vim:

```vim
:LeetCodeList
```

Fuzzy pickers:

```vim
:LeetCodeListFzf
:LeetCodeListTelescope
:LeetCodeListSmart
```

## Workflow helpers

Common local loop helpers:

```bash
leetcodevim status          # workspace summary + last touched + next template-only problem
leetcodevim recent          # print the most recently touched solution path
leetcodevim last            # alias for recent; handy when you want to reopen the last problem
leetcodevim next            # print the next template-only solution path
leetcodevim test --slug two-sum
```

In Vim:

```vim
:edit `leetcodevim recent`
:edit `leetcodevim next`
:LeetCodeLast
```

`leetcodevim list` now prints `slug`, `status`, and the solution path so you can grep/filter quickly from shell scripts.

## CI/tooling

The repo CI now does three lightweight checks beyond plain unit tests:

- bytecode/static sanity via `python -m compileall src tests`
- packaging verification via `python -m build`
- install smoke test from the built wheel to confirm the published CLI exposes the expected commands

