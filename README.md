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

This creates a LeetCode-native `solution.py`, `problem.txt`, and `sample.txt` in your workspace when LeetCode's public problem API is reachable. The Python scaffold uses the returned `Solution` class and method signature. `problem.txt` is a readable plain-text prompt with examples/constraints preserved as best-effort terminal-friendly text, and `sample.txt` is retained as a human-readable copy of the first sample input.

4) Save your LeetCode session token only when you want account-specific actions like `submit` or `auth whoami`:

```bash
leetcodevim auth set --session "<LEETCODE_SESSION>" --csrf "<csrftoken>"
```

## Official language support matrix

`leetcodevim` currently has one fully supported language and one scaffold-only language:

| Command / flow | Python | C++ |
| --- | --- | --- |
| `init` | Full support | Scaffold-only |
| `pull` | Full support | Scaffold-only |
| `list` | Full support | Scaffold-only |
| `test` | Full support | Not supported |
| `submit` | Full support | Not supported |
| Vim commands (`:LeetCodePull`, `:LeetCodeList*`) | Matches CLI support | Matches CLI support |

### What “scaffold-only” means for C++

- `leetcodevim init --language cpp` is allowed.
- `leetcodevim pull ...` generates `solution.cpp` plus local metadata files.
- `leetcodevim list` will surface C++ problem folders.
- `leetcodevim test` and `leetcodevim submit` intentionally fail early with clear messages instead of pretending C++ is end-to-end supported.

If you want the smoothest local workflow today, use Python.

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

## Local progress tracking

`leetcodevim` keeps optional offline progress state, cached problem metadata, examples, and submission history in `WORKSPACE/.leetcodevim/state.db`.

The database is created automatically, uses a versioned SQLite schema, and is portable with the workspace. Existing `.leetcodevim-state.json` files are imported on first access and are never deleted.

Tracked fields per problem:
- `status`: one of `pulled`, `in-progress`, `tested`, `solved`, `submitted`, `review`
- `notes`: freeform text
- `tags`: simple comma-separated labels
- `created_at` / `updated_at`: UTC timestamps

Examples:

```bash
leetcodevim status
leetcodevim status two-sum
leetcodevim mark two-sum --status in-progress --notes "retry later" --tags array,two-pointers
leetcodevim mark two-sum --status solved --tags array
leetcodevim next
leetcodevim recent
```

The database is local-only, auth-free, and easy to ignore in git/workspaces.

## Testing and submitting

From a problem directory, or from anywhere with `--slug`:

```bash
leetcodevim test
leetcodevim test --slug two-sum
leetcodevim submit --slug two-sum
```

`test` runs the cached LeetCode examples against the generated `Solution.<method>()`. It reports missing methods, malformed examples, runtime exceptions, and incorrect results as failures. C++ remains scaffold-only until its compiler/runtime contract is implemented.

For C++ workspaces, `test` and `submit` are intentionally blocked until those flows are fully implemented.

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
:LeetCodeStatus [slug]
:LeetCodeNext
:LeetCodeRecent
:LeetCodeTest [slug]
```

## Architecture

- `leetcode_api.py` handles the public problem query and authenticated submission endpoints.
- `problem_model.py` turns API snippets and examples into a cached, executable problem definition.
- `storage.py` owns the versioned workspace SQLite repository.
- `runner.py` executes Python `Solution` methods against cached examples without network access.
- `plugin/leetcodevim.vim` is a thin editor adapter around the CLI and supports built-in Vim, fzf, and Telescope pickers.
