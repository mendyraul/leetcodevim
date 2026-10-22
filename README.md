# LeetCodeVim

A LeetCode workspace inside terminal Vim and Neovim: browse questions, read descriptions, edit Python or C++, run examples, and send solutions to LeetCode.

## Install

Python 3.9+, Vim 8.2+ with jobs/channels or Neovim 0.9+, and macOS or Linux are required. Local C++ tests also need `clang++` or `g++` with C++17 support.

From this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
leetcodevim init --workspace ~/leetcode --language python
leetcodevim install-plugin --editor both
vim
```

Then run `:LeetCode`. The workspace uses your existing colors and Vim editing keys.

Keep the CLI on your shell PATH when launching an editor. If you prefer not to activate the environment, set this in your vimrc/init.vim, using your real repository path:

```vim
let g:leetcodevim_command = ['/absolute/path/to/leetcodevim/.venv/bin/leetcodevim']
```

The wheel includes the Vimscript and Lua runtime too. After installing a wheel, `leetcodevim install-plugin --editor vim`, `--editor nvim`, or `--editor both` links those files into the editor's package directory. Existing installations are never overwritten. `leetcodevim plugin-path` prints the runtime directory.

## The workspace

Selecting a question collapses the problem browser to give the description and code more room. Press **F2** from a workspace pane or solution buffer to reopen it, or run `:LeetCodeBrowser`. The shortcut stays visible in the status line. Problem text highlights headings, inputs, outputs, numbers, strings, operators, links, and parameter names.

The problem browser defaults to 52 columns, capped at 45% of the terminal width. Customize it in your vimrc/init.vim:

```vim
let g:leetcodevim_browser_width = 60
```

`:LeetCode` opens a separate tab with a question browser, description, solution, and results pane. Closing it returns to your previous window. Narrow terminals collapse the sidebar and then the description; use `:LeetCodeBrowser`, `:LeetCodeDescription`, `:LeetCodeCode`, and `:LeetCodeResults` to reveal a view.

In the browser:

- `Enter` opens a question or dashboard action.
- `/` searches; `f` sets difficulty, topic, and solved-status filters.
- `[` / `]` change pages; `r` refreshes cached results.
- `?` displays commands; `q` closes the workspace.

Solutions remain ordinary files under `~/leetcode/<slug>/solution.py` and `solution.cpp`. Switching languages retains both drafts. Editing commands, completion, LSP, and other editor plugins continue to work in those files.

| Command | Action |
| --- | --- |
| `:LeetCodeBrowse [query]` | Search the catalog |
| `:LeetCodeOpen two-sum` | Open a problem; `LeetCodePull` remains an alias |
| `:LeetCodeDaily`, `:LeetCodeRandom` | Pick a question |
| `:LeetCodeLanguage python` / `cpp` | Switch drafts |
| `:LeetCodeCases` | Edit custom cases as JSON |
| `:LeetCodeTest [slug]` | Run local examples/custom cases |
| `:LeetCodeRun [slug]` | Run cases on LeetCode |
| `:LeetCodeSubmit [slug]` | Confirm and submit to the official judge |
| `:LeetCodeHistory` | Show available remote history and recorded operations |
| `:LeetCodeRestore ID` | Restore accessible submitted code after confirmation, backing up the current draft |
| `:LeetCodePoll ID` | Resume an interrupted remote operation |
| `:LeetCodeHints`, `:LeetCodeEditorial` | Read hints or accessible editorials |
| `:LeetCodeNotes`, `:LeetCodeMark [status]` | Keep notes and practice progress |
| `:LeetCodeProfile [username]` | Show profile statistics |
| `:LeetCodeStudy`, `:LeetCodeFavorites` | Open website study plans and lists |
| `:LeetCodeContests` | List upcoming contests and open a selected contest |
| `:LeetCodeDiscuss`, `:LeetCodeCompose` | Open discussions or prepare a local Markdown draft |
| `:LeetCodeLogin`, `:LeetCodeLogout` | Manage the signed-in session |
| `:LeetCodeCancel` | Cancel local work or stop remote polling |
| `:LeetCodeDoctor` | Inspect the environment without displaying credentials |

Local solution mappings use `<localleader>lt`, `<localleader>lr`, and `<localleader>ls` for test, run, and submit. The plugin asks to save modified solution/case files before execution. Submission has its own confirmation.

## Sign in

Public problem browsing and local practice do not require an account.

Use `:LeetCodeLogin` to open the normal browser login, import cookies from Chrome/Chromium/Brave/Edge/Firefox, or enter `LEETCODE_SESSION` and `csrftoken` using hidden input. The backend verifies the account before retaining credentials. Browser challenges stay in the browser.

Credentials are stored together in the OS keychain. If that is unavailable, editor login lasts only for the backend's lifetime; it does not silently write plaintext tokens. Logout removes stored credentials and private caches, while retaining your solutions and notes. Environment credentials remain external, but logout disables them for the current editor worker.

CLI alternatives:

```bash
leetcodevim auth login --open-browser
leetcodevim auth login --browser chrome
leetcodevim auth login --cookies
leetcodevim auth whoami
```

`LEETCODE_SESSION` and `LEETCODE_CSRF` environment variables remain supported. The low-level `auth set` command supports an explicit `--allow-file` option for protected-file storage when a keychain is unavailable. Prefer the hidden-input login flow to placing credentials in shell history.

## Language support

| Flow | Python | C++ |
| --- | --- | --- |
| Initialize, pull/show, list, edit | Supported | Supported |
| Local examples and custom cases | Supported types/checkers | Supported types/checkers; C++17 compiler required |
| Remote run and submit | Native adapter; login required | Native adapter; login required |
| Vim and Neovim commands | Same backend as CLI | Same backend as CLI |

Local runners support the argument types and comparison rules documented below. Unsupported local types and custom judges fail explicitly and direct you to remote judging. Authenticated run/submit adapters have fixture coverage; live account acceptance remains pending. This table does not claim that an unverified account operation has succeeded.

## Test and submit

```bash
leetcodevim pull two-sum
leetcodevim test --slug two-sum
leetcodevim show --slug two-sum --language cpp
leetcodevim test --slug two-sum --language cpp
leetcodevim run --slug two-sum
leetcodevim submit --slug two-sum --confirm
leetcodevim submissions --slug two-sum
leetcodevim poll --remote-id 123456789
```

Fill in a newly generated Python method before testing: its initial `pass` intentionally fails the examples.

`:LeetCodeCases` creates `cases.json` beside the solution. It is shared across both language drafts:

```json
[
  {"args": [[2, 7, 11, 15], 9], "expected": [0, 1]},
  {"args": [[3, 2, 4], 6], "expected": [1, 2]}
]
```

Local execution supports primitives, arrays/nested arrays, linked lists, binary trees, and supported design-class operation sequences. Design cases contain `[operations, arguments]` in `args`. Void methods can compare the mutated first argument with `"in_place": true`.

Cases use exact comparison unless a known problem rule or an explicit `comparison` overrides it. Supported overrides are `exact`, `unordered`, `unordered_nested`, and `float`. Problems with unsupported custom judges or argument types direct you to remote execution. Passing examples means **tested locally**, not **accepted by LeetCode**.

Solutions run as your user in separate child processes, not a security sandbox. Execution defaults to five seconds, compilation to thirty seconds, and captured output to one MiB. Cancelling kills the local process group. Cancelling a remote request stops polling; an operation already sent to LeetCode continues there. Its ID is recorded before polling and can be resumed. Pending operations block duplicate sends for the same account/problem/action.

## What runs here and what opens in a browser

The native workspace implements public browsing, descriptions/hints, Python/C++ editing, local tests, and the remote run/submit/history adapters. Profile and editorial adapters use your account's access. Authenticated live acceptance still requires a real signed-in session; mocked tests do not establish that those endpoints work for your account.

Upcoming contests appear natively. Study plans, website lists, discussion publication/voting, contest registration/participation/standings, billing, videos, and unsupported rich content open in the browser. Discussion drafts and local favorites are retained locally. These browser paths are explicit fallbacks, not native implementations of those actions. Premium access is never bypassed.

See [the capability checklist](docs/capabilities.md) for verification status and remaining acceptance checks.

## CLI and storage compatibility

Existing `init`, `pull`, `list`, `status`, `mark`, `next`, and `recent` commands remain available. New read commands include `browse`, `show`, `daily`, `random`, `profile`, `editorial`, `submissions`, `contests`, `study`, `discuss`, and `favorites`; use `--format json` for structured output. `list` remains the local problem list; `browse` searches LeetCode.

Workspace state lives in `.leetcodevim/state.db`. Schema v1 is backed up to `state.v1.backup.db` before migration to v2. Existing problem folders, drafts, progress, and legacy `.leetcodevim-state.json` files are preserved. Catalog data can be read offline after caching; private caches are separated by verified account and purged on logout. Old unscoped submission records remain in storage but are not mixed into an authenticated account's remote history.

## Development

```bash
python -m pytest -q
ruff check src tests scripts
python -m build
python scripts/smoke_wheel.py
python scripts/smoke_public.py  # explicit read-only network checks
```

Tests use temporary workspaces and fixtures. They do not submit solutions, publish discussions, register contests, or import your browser cookies. Set `LEETCODEVIM_NVIM=/path/to/nvim` if Neovim is not on PATH.

The editor protocol is documented in [docs/protocol.md](docs/protocol.md). The C++ harness bundles the MIT-licensed [nlohmann/json v3.12.0](https://github.com/nlohmann/json/tree/v3.12.0) header, license, and SHA-256 digest.
