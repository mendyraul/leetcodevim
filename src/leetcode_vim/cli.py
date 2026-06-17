from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from .auth import AuthImportError, clear_auth, import_from_browser, load_auth, save_auth
from .config import Config, load_config, save_config
from .leetcode_api import (
    LeetCodeError,
    LeetCodeSession,
    fetch_problem,
    fetch_user,
    poll_submission,
    submit_solution,
)
from .runner import RunnerError, run_python
from .templates import get_template


def _ensure_config() -> Config:
    config = load_config()
    if not config:
        raise SystemExit("Config not found. Run: leetcodevim init --workspace <path> --language <lang>")
    return config


def _session_from_env() -> str | None:
    return os.environ.get("LEETCODE_SESSION")


def _csrf_from_env() -> str | None:
    return os.environ.get("LEETCODE_CSRF")


def _effective_session(config: Config) -> str | None:
    if _session_from_env():
        return _session_from_env()
    return load_auth(config).session


def _effective_csrf(config: Config) -> str | None:
    if _csrf_from_env():
        return _csrf_from_env()
    return load_auth(config).csrf


def _slugify(text: str) -> str:
    slug = text.strip().lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug


def cmd_init(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser()
    workspace.mkdir(parents=True, exist_ok=True)
    config = Config(workspace=workspace, language=args.language.lower())
    save_config(config)
    print(f"Initialized config at {workspace}")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    config = _ensure_config()
    slug = _slugify(args.slug)
    if not slug:
        raise SystemExit("Invalid slug. Provide a problem title or slug.")
    problem_dir = config.workspace / slug
    problem_dir.mkdir(parents=True, exist_ok=True)
    ext = _language_extension(config.language)
    solution_path = problem_dir / f"solution.{ext}"
    if not solution_path.exists():
        solution_path.write_text(get_template(config.language), encoding="utf-8")
    metadata_path = problem_dir / "problem.txt"
    sample_path = problem_dir / "sample.txt"
    if not metadata_path.exists() or not sample_path.exists():
        session = _effective_session(config)
        auth = LeetCodeSession(session=session, csrf=_effective_csrf(config)) if session else None
        try:
            problem = fetch_problem(slug, auth)
            if not metadata_path.exists():
                metadata_path.write_text(_format_problem(problem), encoding="utf-8")
            if problem.sample_test_case and not sample_path.exists():
                sample_path.write_text(problem.sample_test_case.strip() + "\n", encoding="utf-8")
        except LeetCodeError as exc:
            if not metadata_path.exists():
                metadata_path.write_text(
                    f"Problem: {args.slug}\nSlug: {slug}\n\nAPI error: {exc}\n",
                    encoding="utf-8",
                )
            if not session:
                print(
                    "Warning: could not fetch public problem metadata. "
                    "You can retry later or run with auth via `leetcodevim auth login`.",
                    file=sys.stderr,
                )
    print(str(solution_path))
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    config = _ensure_config()
    problem_dir = _resolve_problem_dir(config, args.slug)
    sample_path = problem_dir / "sample.txt"
    if not sample_path.exists():
        print(f"sample.txt not found in {problem_dir}. Pull the problem first.")
        return 1
    input_text = sample_path.read_text(encoding="utf-8")
    solution_path = _resolve_solution_path(problem_dir, config.language)
    if config.language != "python":
        print("Only python test runner is implemented.")
        return 1
    try:
        stdout, stderr = run_python(solution_path, input_text)
    except RunnerError as exc:
        print(f"Test failed: {exc}")
        return 1
    if stderr:
        print(stderr.rstrip())
    print(stdout.rstrip())
    if args.slug:
        print(f"Tested {problem_dir.name} -> {solution_path}")
    return 0


def cmd_submit(_: argparse.Namespace) -> int:
    config = _ensure_config()
    problem_dir = _resolve_problem_dir(config, None)
    slug = problem_dir.name
    session = _effective_session(config)
    if not session:
        print("LEETCODE_SESSION not set.")
        return 1
    auth = LeetCodeSession(session=session, csrf=_effective_csrf(config))
    try:
        problem = fetch_problem(slug, auth)
    except LeetCodeError as exc:
        print(f"Failed to fetch problem: {exc}")
        return 1
    solution_path = _resolve_solution_path(problem_dir, config.language)
    code = solution_path.read_text(encoding="utf-8")
    lang_slug = _language_slug(config.language)
    try:
        submission_id = submit_solution(slug, problem.question_id, lang_slug, code, auth)
    except LeetCodeError as exc:
        print(f"Submit failed: {exc}")
        return 1
    print(f"Submitted. ID: {submission_id}")
    result = _poll_submission(submission_id, auth)
    _print_submission_result(result)
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    config = _ensure_config()
    entries = _problem_entries(config)
    for entry in entries:
        print(f"{entry['slug']}\t{entry['status']}\t{entry['solution_path']}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    config = _ensure_config()
    entries = _problem_entries(config)
    solved = sum(1 for entry in entries if entry["status"] == "started")
    todo = sum(1 for entry in entries if entry["status"] == "template")
    print(f"Workspace: {config.workspace}")
    print(f"Language: {config.language}")
    print(f"Problems: {len(entries)}")
    print(f"Started: {solved}")
    print(f"Template-only: {todo}")
    recent = _most_recent_problem(entries)
    if recent:
        print(f"Last touched: {recent['slug']} -> {recent['solution_path']}")
    else:
        print("Last touched: none")
    next_problem = _next_template_problem(entries)
    if next_problem:
        print(f"Next unsolved: {next_problem['slug']} -> {next_problem['solution_path']}")
    else:
        print("Next unsolved: none")
    return 0


def cmd_recent(_: argparse.Namespace) -> int:
    config = _ensure_config()
    recent = _most_recent_problem(_problem_entries(config))
    if not recent:
        print("No local problems found.")
        return 1
    print(recent["solution_path"])
    return 0


def cmd_last(args: argparse.Namespace) -> int:
    return cmd_recent(args)


def cmd_next(_: argparse.Namespace) -> int:
    config = _ensure_config()
    next_problem = _next_template_problem(_problem_entries(config))
    if not next_problem:
        print("No template-only problems found. Pull a new problem first.")
        return 1
    print(next_problem["solution_path"])
    return 0


def cmd_auth_set(args: argparse.Namespace) -> int:
    config = _ensure_config()
    save_auth(config, args.session, args.csrf)
    print("Saved LEETCODE_SESSION token.")
    return 0


def cmd_auth_show(_: argparse.Namespace) -> int:
    config = _ensure_config()
    session = _effective_session(config)
    if not session:
        print("LEETCODE_SESSION not set.")
        return 1
    masked = "*" * max(0, len(session) - 4) + session[-4:]
    print(f"LEETCODE_SESSION={masked}")
    csrf = _effective_csrf(config)
    if csrf:
        masked_csrf = "*" * max(0, len(csrf) - 4) + csrf[-4:]
        print(f"LEETCODE_CSRF={masked_csrf}")
    return 0


def cmd_auth_login(_: argparse.Namespace) -> int:
    steps = [
        "1) Log in to LeetCode in your browser.",
        "2) Open DevTools -> Application/Storage -> Cookies -> https://leetcode.com.",
        "3) Copy the value for LEETCODE_SESSION.",
        "4) Optional but recommended: copy csrftoken.",
        "5) Run: leetcodevim auth set --session <LEETCODE_SESSION> --csrf <csrftoken>",
    ]
    print("\n".join(steps))
    return 0


def cmd_auth_whoami(_: argparse.Namespace) -> int:
    config = _ensure_config()
    session = _effective_session(config)
    if not session:
        print("LEETCODE_SESSION not set.")
        return 1
    auth = LeetCodeSession(session=session, csrf=_effective_csrf(config))
    try:
        username = fetch_user(auth)
    except LeetCodeError as exc:
        print(f"Auth failed: {exc}")
        return 1
    print(f"Signed in as {username}")
    return 0


def cmd_auth_logout(_: argparse.Namespace) -> int:
    config = _ensure_config()
    clear_auth(config)
    print("Cleared stored credentials.")
    return 0


def cmd_auth_import(args: argparse.Namespace) -> int:
    config = _ensure_config()
    try:
        result = import_from_browser(args.browser, args.domain)
    except AuthImportError as exc:
        print(f"Import failed: {exc}")
        return 1
    save_auth(config, result.session, result.csrf)
    print("Imported cookies from browser and saved credentials.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="leetcodevim")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize configuration")
    init_parser.add_argument("--workspace", required=True, help="workspace directory for problems")
    init_parser.add_argument("--language", default="python", help="language template to use")
    init_parser.set_defaults(func=cmd_init)

    pull_parser = subparsers.add_parser("pull", help="create a problem workspace")
    pull_parser.add_argument("slug", help="problem slug or title")
    pull_parser.set_defaults(func=cmd_pull)

    test_parser = subparsers.add_parser("test", help="run local tests")
    test_parser.add_argument("--slug", help="run tests for a specific local problem from anywhere")
    test_parser.set_defaults(func=cmd_test)

    submit_parser = subparsers.add_parser("submit", help="submit solution")
    submit_parser.set_defaults(func=cmd_submit)

    list_parser = subparsers.add_parser("list", help="list local problems")
    list_parser.set_defaults(func=cmd_list)

    status_parser = subparsers.add_parser("status", help="show local workspace status")
    status_parser.set_defaults(func=cmd_status)

    recent_parser = subparsers.add_parser("recent", help="print the most recently touched solution path")
    recent_parser.set_defaults(func=cmd_recent)

    last_parser = subparsers.add_parser("last", help="alias for recent; print the most recently touched solution path")
    last_parser.set_defaults(func=cmd_last)

    next_parser = subparsers.add_parser("next", help="print the next template-only solution path")
    next_parser.set_defaults(func=cmd_next)

    auth_parser = subparsers.add_parser("auth", help="manage authentication")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)

    auth_set = auth_subparsers.add_parser("set", help="store LEETCODE_SESSION")
    auth_set.add_argument("--session", required=True, help="LEETCODE_SESSION cookie value")
    auth_set.add_argument("--csrf", help="csrftoken cookie value (recommended)")
    auth_set.set_defaults(func=cmd_auth_set)

    auth_show = auth_subparsers.add_parser("show", help="show auth status")
    auth_show.set_defaults(func=cmd_auth_show)

    auth_login = auth_subparsers.add_parser("login", help="print login instructions")
    auth_login.set_defaults(func=cmd_auth_login)

    auth_whoami = auth_subparsers.add_parser("whoami", help="verify auth and show username")
    auth_whoami.set_defaults(func=cmd_auth_whoami)

    auth_logout = auth_subparsers.add_parser("logout", help="clear stored credentials")
    auth_logout.set_defaults(func=cmd_auth_logout)

    auth_import = auth_subparsers.add_parser("import-cookie", help="import cookies from browser")
    auth_import.add_argument("--browser", default="chrome", help="chrome|chromium|brave|edge|firefox")
    auth_import.add_argument("--domain", default="leetcode.com", help="cookie domain to search")
    auth_import.set_defaults(func=cmd_auth_import)

    return parser


def _resolve_problem_dir(config: Config, slug: str | None) -> Path:
    if slug:
        slug = _slugify(slug)
        if not slug:
            raise SystemExit("Invalid slug. Provide a problem title or slug.")
        return config.workspace / slug
    cwd = Path.cwd().resolve()
    workspace = config.workspace.resolve()
    try:
        cwd.relative_to(workspace)
    except ValueError:
        raise SystemExit("Run from a problem directory or pass a slug.")
    return cwd


def _resolve_solution_path(problem_dir: Path, language: str) -> Path:
    ext = _language_extension(language)
    solution_path = problem_dir / f"solution.{ext}"
    if not solution_path.exists():
        raise SystemExit(f"Solution not found at {solution_path}")
    return solution_path


def _language_slug(language: str) -> str:
    mapping = {"python": "python3", "cpp": "cpp"}
    if language not in mapping:
        raise SystemExit(f"Unsupported language: {language}")
    return mapping[language]


def _language_extension(language: str) -> str:
    mapping = {"python": "py", "cpp": "cpp"}
    if language not in mapping:
        raise SystemExit(f"Unsupported language: {language}")
    return mapping[language]


def _problem_entries(config: Config) -> list[dict[str, object]]:
    ext = _language_extension(config.language)
    entries: list[dict[str, object]] = []
    if not config.workspace.exists():
        return entries
    for item in config.workspace.iterdir():
        if not item.is_dir():
            continue
        solution_path = item / f"solution.{ext}"
        if not solution_path.exists():
            continue
        status = _solution_status(solution_path, config.language)
        entries.append(
            {
                "slug": item.name,
                "solution_path": solution_path,
                "status": status,
                "mtime": solution_path.stat().st_mtime,
            }
        )
    return sorted(entries, key=lambda entry: str(entry["slug"]))


def _solution_status(solution_path: Path, language: str) -> str:
    try:
        content = solution_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    template = get_template(language).strip()
    return "template" if content == template else "started"


def _most_recent_problem(entries: list[dict[str, object]]) -> dict[str, object] | None:
    if not entries:
        return None
    return max(entries, key=lambda entry: float(entry["mtime"]))


def _next_template_problem(entries: list[dict[str, object]]) -> dict[str, object] | None:
    for entry in entries:
        if entry["status"] == "template":
            return entry
    return None


def _poll_submission(submission_id: str, auth: LeetCodeSession) -> dict[str, object]:
    import time

    for _ in range(10):
        result = poll_submission(submission_id, auth)
        if result.get("state") == "SUCCESS":
            return result
        time.sleep(1)
    return result


def _print_submission_result(result: dict[str, object]) -> None:
    status = result.get("status_msg") or result.get("status_code")
    runtime = result.get("runtime")
    memory = result.get("memory")
    print(f"Result: {status}")
    if runtime:
        print(f"Runtime: {runtime}")
    if memory:
        print(f"Memory: {memory}")


def _format_problem(problem: object) -> str:
    from .leetcode_api import Problem

    if not isinstance(problem, Problem):
        return ""
    lines = [
        f"Title: {problem.title}",
        f"Slug: {problem.title_slug}",
        f"Difficulty: {problem.difficulty}",
        "",
        "Content (HTML):",
        problem.content,
        "",
    ]
    if problem.sample_test_case:
        lines.extend(["Sample Test Case:", problem.sample_test_case, ""])
    if problem.code_snippets:
        lines.append("Code Snippets:")
        for snippet in problem.code_snippets:
            lang = snippet.get("lang", "unknown")
            lines.append(f"- {lang}")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
