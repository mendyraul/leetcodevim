# QA notes

The companion adds a shared stdio backend, Vim workspace, Neovim Lua adapter,
account-scoped caches, local Python/C++ execution, and remote-operation adapters.

Verification commands and the current feature matrix are maintained in README.md
and docs/capabilities.md. Headless tests cover both editors, reopening the
workspace, narrow layouts, and late navigation replies. Unit/integration tests
cover schema backup/migration, draft preservation, nodes and design classes,
execution bounds, cancellation, credential storage, account isolation, operation
resume, and source restoration with backups.

Public live checks are explicitly invoked with scripts/smoke_public.py. Real
account login, remote execution/submission, history, and editorial acceptance
remain manual. Tests never import browser cookies or perform account writes.
