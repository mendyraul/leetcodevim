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

3) Save your LeetCode session token (from browser cookies):

```bash
leetcodevim auth set --session "<LEETCODE_SESSION>" --csrf "<csrftoken>"
```

4) In Vim, pull a problem:

```vim
:LeetCodePull two-sum
```

This creates `solution.py` and a placeholder `problem.txt` in your workspace.

## Auth notes

- The CLI reads `LEETCODE_SESSION` and `LEETCODE_CSRF` from the environment first.
- Tokens are stored in the OS keychain via `keyring` when available, otherwise in `~/.config/leetcode-vim/config.json`.
- Config files are written with `0600` permissions where supported.
- You can temporarily override without writing to disk:

```bash
LEETCODE_SESSION="<token>" LEETCODE_CSRF="<token>" leetcodevim pull two-sum
```
leetcodevim auth import-cookie --browser chrome --domain leetcode.com

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
2) Run `leetcodevim auth login`, then `leetcodevim auth set ...`
3) In Vim, run `:LeetCodePull two-sum`

## Testing and submitting

From a problem directory:

```bash
leetcodevim test
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
