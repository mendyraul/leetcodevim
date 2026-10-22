from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import asdict
from html.parser import HTMLParser
from pathlib import Path

from .auth import AuthImportError, clear_auth, import_from_browser, load_auth, save_auth
from .config import Config, load_config, save_config
from .leetcode_api import (
    LeetCodeError,
    LeetCodeSession,
    fetch_problem,
    fetch_user,
)
from .problem_model import build_problem_record
from .runner import RunnerError
from .state import (
    ALLOWED_STATUSES,
    DEFAULT_STATUS,
    ensure_problem_state,
    load_state,
    repository,
    update_problem_state,
)
from .templates import SUPPORTED_LANGUAGES, get_template

LANGUAGE_SUPPORT_MATRIX: dict[str, dict[str, str]] = {
    "init": {
        "python": "full",
        "cpp": "full",
    },
    "pull": {
        "python": "full",
        "cpp": "full",
    },
    "list": {
        "python": "full",
        "cpp": "full",
    },
    "test": {
        "python": "full",
        "cpp": "full",
    },
    "submit": {
        "python": "full",
        "cpp": "full",
    },
    "vim": {
        "python": "matches-cli",
        "cpp": "matches-cli",
    },
}
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


def _normalize_language(language: str) -> str:
    normalized = language.lower()
    if normalized not in SUPPORTED_LANGUAGES:
        supported = ", ".join(SUPPORTED_LANGUAGES)
        raise SystemExit(f"Unsupported language: {language}. Supported languages: {supported}.")
    return normalized


def _command_support(command: str, language: str) -> str:
    try:
        return LANGUAGE_SUPPORT_MATRIX[command][language]
    except KeyError as exc:
        raise SystemExit(f"Support matrix missing for command={command!r}, language={language!r}") from exc


def cmd_init(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser()
    workspace.mkdir(parents=True, exist_ok=True)
    language = _normalize_language(args.language)
    config = Config(workspace=workspace, language=language)
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
    ext = "py" if config.language == "python" else "cpp"
    solution_path = problem_dir / f"solution.{ext}"
    metadata_path = problem_dir / "problem.txt"
    sample_path = problem_dir / "sample.txt"
    failed_metadata = metadata_path.exists() and re.match(
        rf"\AProblem: [^\n]*\nSlug: {re.escape(slug)}\n\nAPI error: ",
        metadata_path.read_text(encoding="utf-8"),
    ) is not None
    replace_placeholder = (
        failed_metadata
        and solution_path.exists()
        and solution_path.read_text(encoding="utf-8") == get_template(config.language)
    )
    repo = repository(config)
    record = repo.get_problem(slug)
    invalid_scaffold = record is not None and config.language == "python" and not record.method_name
    replace_placeholder = replace_placeholder or (
        invalid_scaffold
        and solution_path.exists()
        and solution_path.read_text(encoding="utf-8") == record.code
    )
    if record is None or not metadata_path.exists() or failed_metadata or invalid_scaffold:
        session = _effective_session(config)
        auth = LeetCodeSession(session=session, csrf=_effective_csrf(config)) if session else None
        try:
            problem = fetch_problem(slug, auth)
            record = build_problem_record(problem, slug, config.language, record)
            repo.save_problem(record)
            from .companion_store import CompanionStore
            CompanionStore(config.workspace).save_draft(record, problem.metadata, problem.hints)
            if not metadata_path.exists() or failed_metadata:
                metadata_path.write_text(_format_problem(problem), encoding="utf-8")
            if not sample_path.exists():
                sample_text = _sample_text(problem)
                if sample_text:
                    sample_path.write_text(sample_text.strip() + "\n", encoding="utf-8")
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
    if not solution_path.exists() or (record is not None and replace_placeholder):
        solution_path.write_text(record.code if record else get_template(config.language), encoding="utf-8")
    ensure_problem_state(config, slug)
    print(str(solution_path))
    return 0


def _companion_action(args, action):
    from .service import Service
    from .provider import ProviderError
    config = _ensure_config()
    slug = getattr(args, 'slug', None) or _resolve_problem_dir(config, None).name
    try:
        result = Service(config).dispatch(action, {
            'slug': slug, 'language': getattr(args, 'language', None) or config.language,
            'confirmed': getattr(args, 'confirm', False),
        })
    except (ProviderError, RunnerError, ValueError) as exc:
        print(f"{action.title()} failed: {exc}")
        return 1
    if getattr(args, 'format', 'text') == 'json':
        print(json.dumps(result, indent=2))
    elif action == 'test' and result.get('passed'):
        print(f"Passed {len(result['results'])} example(s) for {slug}.")
    else:
        print(json.dumps(result, indent=2))
    return 1 if result.get('passed') is False else 0


def cmd_test(args: argparse.Namespace) -> int:
    return _companion_action(args, 'test')


def cmd_submit(args: argparse.Namespace) -> int:
    return _companion_action(args, 'submit')


def _problem_entries(config: Config) -> list[dict[str, object]]:
    ext = "py" if config.language == "python" else "cpp"
    store = load_state(config)
    entries: list[dict[str, object]] = []
    if not config.workspace.exists():
        return entries
    for item in config.workspace.iterdir():
        if not item.is_dir():
            continue
        solution_path = item / f"solution.{ext}"
        if solution_path.exists():
            problem_state = store.problems.get(item.name)
            entries.append(
                {
                    "slug": item.name,
                    "status": problem_state.status if problem_state else DEFAULT_STATUS,
                    "path": str(solution_path),
                    "updated_at": problem_state.updated_at if problem_state else None,
                }
            )
    return sorted(entries, key=lambda entry: str(entry["slug"]))


def cmd_list(args: argparse.Namespace) -> int:
    config = _ensure_config()
    entries = _problem_entries(config)
    if getattr(args, "format", "text") == "json":
        print(json.dumps(entries, indent=2))
        return 0
    for entry in entries:
        print(f"{entry['slug']}\t{entry['status']}\t{entry['path']}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = _ensure_config()
    store = load_state(config)
    if args.slug:
        slug = _slugify(args.slug)
        problem = store.problems.get(slug)
        if not problem:
            if getattr(args, "format", "text") == "json":
                print(json.dumps({"slug": slug, "found": False}))
                return 1
            print(f"{slug}: no local state")
            return 1
        if getattr(args, "format", "text") == "json":
            print(json.dumps(asdict(problem), indent=2))
            return 0
        print(f"slug: {problem.slug}")
        print(f"status: {problem.status}")
        print(f"tags: {', '.join(problem.tags) if problem.tags else '-'}")
        print(f"notes: {problem.notes or '-'}")
        print(f"created_at: {problem.created_at}")
        print(f"updated_at: {problem.updated_at}")
        return 0

    if getattr(args, "format", "text") == "json":
        print(json.dumps([asdict(problem) for _, problem in sorted(store.problems.items())], indent=2))
        return 0
    for slug, problem in sorted(store.problems.items()):
        print(f"{slug}\t{problem.status}\t{','.join(problem.tags) or '-'}\t{problem.notes or '-'}")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    config = _ensure_config()
    entries = [entry for entry in _problem_entries(config) if entry["status"] not in {"solved", "submitted"}]
    entry = entries[0] if entries else None
    if getattr(args, "format", "text") == "json":
        print(json.dumps(entry or {}, indent=2))
    elif entry:
        print(f"{entry['slug']}\t{entry['status']}\t{entry['path']}")
    else:
        print("No unsolved local problems.")
    return 0 if entry else 1


def cmd_recent(args: argparse.Namespace) -> int:
    config = _ensure_config()
    entries = sorted(
        _problem_entries(config),
        key=lambda entry: str(entry.get("updated_at") or ""),
        reverse=True,
    )
    if getattr(args, "format", "text") == "json":
        print(json.dumps(entries, indent=2))
    else:
        for entry in entries:
            print(f"{entry['slug']}\t{entry['status']}\t{entry['path']}")
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    config = _ensure_config()
    slug = _slugify(args.slug)
    if not slug:
        raise SystemExit("Invalid slug. Provide a problem title or slug.")
    tags = []
    if args.tags:
        tags = [part.strip() for part in args.tags.split(',')]
    problem = update_problem_state(
        config,
        slug,
        status=args.status,
        notes=args.notes,
        tags=tags if args.tags is not None else None,
    )
    print(f"Updated {problem.slug}: status={problem.status}")
    return 0


def cmd_auth_set(args: argparse.Namespace) -> int:
    config = _ensure_config()
    save_auth(config, args.session, args.csrf, allow_file=getattr(args, 'allow_file', False))
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
    test_parser.add_argument("--slug", help="problem slug to test from any directory")
    test_parser.add_argument('--language', choices=('python', 'cpp'))
    test_parser.add_argument('--format', choices=('text', 'json'), default='text')
    test_parser.set_defaults(func=cmd_test)

    submit_parser = subparsers.add_parser("submit", help="submit solution")
    submit_parser.add_argument("--slug", help="problem slug to submit from any directory")
    submit_parser.add_argument('--language', choices=('python', 'cpp'))
    submit_parser.add_argument('--confirm', action='store_true', help='confirm sending this solution to LeetCode')
    submit_parser.add_argument('--format', choices=('text', 'json'), default='text')
    submit_parser.set_defaults(func=cmd_submit)

    list_parser = subparsers.add_parser("list", help="list local problems")
    list_parser.add_argument("--format", choices=("text", "json"), default="text")
    list_parser.set_defaults(func=cmd_list)

    status_parser = subparsers.add_parser("status", help="show local progress state")
    status_parser.add_argument("slug", nargs="?", help="problem slug or title")
    status_parser.add_argument("--format", choices=("text", "json"), default="text")
    status_parser.set_defaults(func=cmd_status)

    next_parser = subparsers.add_parser("next", help="show the next unsolved local problem")
    next_parser.add_argument("--format", choices=("text", "json"), default="text")
    next_parser.set_defaults(func=cmd_next)

    recent_parser = subparsers.add_parser("recent", help="list recently updated local problems")
    recent_parser.add_argument("--format", choices=("text", "json"), default="text")
    recent_parser.set_defaults(func=cmd_recent)

    mark_parser = subparsers.add_parser("mark", help="update local progress state")
    mark_parser.add_argument("slug", help="problem slug or title")
    mark_parser.add_argument("--status", required=True, choices=ALLOWED_STATUSES, help="new progress status")
    mark_parser.add_argument("--notes", help="replace notes text")
    mark_parser.add_argument("--tags", help="comma-separated tags")
    mark_parser.set_defaults(func=cmd_mark)

    auth_parser = subparsers.add_parser("auth", help="manage authentication")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)

    auth_set = auth_subparsers.add_parser("set", help="store LEETCODE_SESSION")
    auth_set.add_argument("--session", required=True, help="LEETCODE_SESSION cookie value")
    auth_set.add_argument("--csrf", help="csrftoken cookie value (recommended)")
    auth_set.add_argument('--allow-file', action='store_true', help='explicitly allow protected-file credential storage')
    auth_set.set_defaults(func=cmd_auth_set)

    auth_show = auth_subparsers.add_parser("show", help="show auth status")
    auth_show.set_defaults(func=cmd_auth_show)

    auth_login = auth_subparsers.add_parser("login", help="print login instructions")
    from .companion_cli import login
    auth_login.add_argument('--browser', choices=('chrome', 'chromium', 'brave', 'edge', 'firefox'))
    auth_login.add_argument('--cookies', action='store_true', help='enter cookies through hidden input')
    auth_login.add_argument('--open-browser', action='store_true')
    auth_login.set_defaults(func=login)

    auth_whoami = auth_subparsers.add_parser("whoami", help="verify auth and show username")
    auth_whoami.set_defaults(func=cmd_auth_whoami)

    auth_logout = auth_subparsers.add_parser("logout", help="clear stored credentials")
    auth_logout.set_defaults(func=cmd_auth_logout)

    auth_import = auth_subparsers.add_parser("import-cookie", help="import cookies from browser")
    auth_import.add_argument("--browser", default="chrome", help="chrome|chromium|brave|edge|firefox")
    auth_import.add_argument("--domain", default="leetcode.com", help="cookie domain to search")
    auth_import.set_defaults(func=cmd_auth_import)

    from .companion_cli import extend
    extend(subparsers)
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
    ext = "py" if language == "python" else "cpp"
    solution_path = problem_dir / f"solution.{ext}"
    if not solution_path.exists():
        raise SystemExit(f"Solution not found at {solution_path}")
    return solution_path


def _language_slug(language: str) -> str:
    mapping = {"python": "python3", "cpp": "cpp"}
    if language not in mapping:
        raise SystemExit(f"Unsupported language: {language}")
    return mapping[language]


class _ProblemHTMLFormatter(HTMLParser):
    _BLOCK_TAGS = {
        "p", "div", "section", "article", "header", "footer", "li",
        "ul", "ol", "pre", "blockquote", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._list_stack: list[str] = []
        self._in_pre = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self._parts.append("\n")
        elif tag in {"p", "div", "section", "article", "blockquote"}:
            self._parts.append("\n\n")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n\n")
        elif tag in {"ul", "ol"}:
            self._parts.append("\n")
            self._list_stack.append(tag)
        elif tag == "li":
            bullet = "- " if not self._list_stack or self._list_stack[-1] == "ul" else "1. "
            self._parts.append("\n" + bullet)
        elif tag == "pre":
            self._parts.append("\n\n")
            self._in_pre = True
        elif tag == "code" and not self._in_pre:
            self._parts.append("`")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "section", "article", "blockquote", "pre"}:
            self._parts.append("\n")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")
        elif tag in {"ul", "ol"}:
            if self._list_stack:
                self._list_stack.pop()
            self._parts.append("\n")
        elif tag == "code" and not self._in_pre:
            self._parts.append("`")
        elif tag == "pre":
            self._in_pre = False

    def handle_data(self, data: str) -> None:
        if not data:
            return
        if self._in_pre:
            self._parts.append(data)
            return
        normalized = re.sub(r"\s+", " ", data)
        if normalized.strip():
            self._parts.append(normalized)

    def get_text(self) -> str:
        text = "".join(self._parts)
        text = html.unescape(text)
        text = re.sub(r"[ 	]+\n", "\n", text)
        text = re.sub(r"\n[ 	]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"(?<!\n)(Example(?:s)? \d*:|Constraints:|Follow-up:)", r"\n\n\1", text)
        return text.strip()


def _render_problem_content(content: str) -> str:
    formatter = _ProblemHTMLFormatter()
    formatter.feed(content or "")
    formatter.close()
    return formatter.get_text()


def _extract_sample_input(rendered_content: str) -> str | None:
    match = re.search(
        r"(?:^|\n)Input:\s*(.+?)(?=\n(?:Output:|Explanation:|Constraints:|Example\s*\d*:)|\Z)",
        rendered_content,
        re.DOTALL,
    )
    if not match:
        return None
    sample = match.group(1).strip()
    return sample or None


def _sample_text(problem: object) -> str | None:
    from .leetcode_api import Problem

    if not isinstance(problem, Problem):
        return None
    if problem.sample_test_case and problem.sample_test_case.strip():
        return problem.sample_test_case.strip()
    return _extract_sample_input(_render_problem_content(problem.content))


def _format_problem(problem: object) -> str:
    from .leetcode_api import Problem

    if not isinstance(problem, Problem):
        return ""
    rendered_content = _render_problem_content(problem.content)
    lines = [
        f"Title: {problem.title}",
        f"Slug: {problem.title_slug}",
        f"Difficulty: {problem.difficulty}",
        "",
    ]
    if rendered_content:
        lines.extend(["Prompt:", rendered_content, ""])
    sample_text = _sample_text(problem)
    if sample_text:
        lines.extend(["Sample Input:", sample_text, ""])
        if not problem.sample_test_case or problem.sample_test_case.strip() != sample_text:
            lines.append("Note: sample.txt uses the first example input because LeetCode did not provide sampleTestCase.")
            lines.append("")
    if problem.code_snippets:
        lines.append("Available Templates:")
        for snippet in problem.code_snippets:
            lang = snippet.get("lang", "unknown")
            lines.append(f"- {lang}")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (AuthImportError, LeetCodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
