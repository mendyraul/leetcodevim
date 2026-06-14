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
leetcodevim submit
```

### Local test runner contract

Current support matrix for `leetcodevim test`:

- `python`: supported locally today
- `cpp`: scaffold-only for now; local compile/run is intentionally not implemented yet

Python runner contract:

- `leetcodevim test` reads `sample.txt` and passes it to your solution on `stdin`
- your solution should expose either `def solve(): ...` or `class Solution: def solve(self): ...`
- write results to standard output with `print(...)`
- runner failures are surfaced as explicit CLI errors so missing entrypoints and raised exceptions are easier to diagnose

This keeps local runs deterministic and lightweight while the project is still small.

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
