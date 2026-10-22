# Capability and acceptance checklist

## Implemented

| Capability | Delivery | Verification |
| --- | --- | --- |
| Catalog search, difficulty/topic/status filters, pagination | Native | Public catalog live check; fixture filter tests; account statuses need login |
| Problem descriptions, metadata and templates | Native | Live Two Sum fetch; recovery and draft-preservation tests |
| Daily question | Native | Public endpoint live check |
| Random question | Native | Uses verified catalog pagination; no account mutation |
| Python and C++ local tests | Native | Arrays, nodes, design classes, errors, bounds and cancellation tests |
| Vim workspace and async transport | Native Vimscript | Headless open/close/reopen integration |
| Neovim workspace and async transport | Shared UI + Lua adapter | Headless Neovim integration |
| Session verification, keychain/session storage, logout | Native | Credential and cache-isolation tests; real browser/account acceptance pending |
| Remote run, submit, verdict polling and resume | Native adapters | Fixture persistence/account tests; live account acceptance pending |
| Profile | Native | Public profile endpoint live check; own-account acceptance pending |
| Submission history/details and draft restoration | Native adapters with fallback | Backup/confirmation fixture tests; live account acceptance pending |
| Accessible editorial | Native adapter with fallback | Live account acceptance pending; premium access checked by LeetCode |
| Hints, notes, progress, discussion drafts | Native local views/files | Cached problem/state tests |
| Upcoming contest list | Native | Public endpoint live check |
| Study plans, website favorites, public discussion writes/votes | Explicit browser fallback | No unverified write endpoint is invoked |
| Contest registration, participation and standings | Explicit browser fallback | Selected contest opens on LeetCode |
| Billing/security, videos and complex interactive content | Browser | Normal website behavior |

[Anonymous live-check results](public-verification.json) record the last public verification run.

`leetcodevim doctor` reports these boundaries too. A native adapter backed only by fixtures is not advertised as live-account verified.

## Manual account acceptance still required

1. Sign in with `:LeetCodeLogin`, verify the username, restart with keychain storage, then verify logout and account switching.
2. Pull a public question with both languages and confirm signed-in solved-status filters.
3. Run a deliberately wrong solution remotely; check per-case output and verdict.
4. Submit a chosen Python solution, explicitly confirming the action; inspect verdict, runtime, memory and history.
5. Repeat with C++; confirm local example success is never reported as official acceptance.
6. Cancel polling after sending, reopen the workspace, and resume the recorded ID.
7. Read an accessible editorial; check locked content uses the website fallback.
8. Verify profile/history under the signed-in account and confirm private views disappear on logout.
9. Select each browser-only feature and verify its destination. Publish discussion drafts or register contests only through normal website confirmation.

CI never performs these account writes. No browser credentials are included in fixtures.

## Compatibility and recovery

Target macOS/Linux, Python 3.9+, Vim 8.2+ with +job/+channel, and Neovim 0.9+. Local C++ needs a C++17 compiler. Unsupported argument types, interactive tasks, and custom judges direct users to remote judging.

Before schema v1 -> v2 migration, the repository creates `state.v1.backup.db`. To inspect an older release, use a copied workspace with that backup rather than opening a newer database in an older binary. Solution files and notes remain ordinary files.

The initial implementation has browser fallbacks for the broader website features above. Native study-plan management, discussion publication/voting, contest participation, and richer image rendering remain future extensions; this release does not claim native website parity.
