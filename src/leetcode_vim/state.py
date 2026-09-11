from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import Config
from .storage import SQLiteRepository, utc_now


DEFAULT_STATUS = "pulled"
ALLOWED_STATUSES = ("pulled", "in-progress", "tested", "solved", "submitted", "review")
LEGACY_STATE_NAME = ".leetcodevim-state.json"


@dataclass
class ProblemState:
    slug: str
    status: str = DEFAULT_STATUS
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ProblemState":
        status = str(data.get("status") or DEFAULT_STATUS)
        if status not in ALLOWED_STATUSES:
            status = DEFAULT_STATUS
        tags_raw = data.get("tags") or []
        tags = [str(tag) for tag in tags_raw if str(tag).strip()]
        return cls(
            slug=str(data.get("slug") or ""),
            status=status,
            notes=str(data.get("notes") or ""),
            tags=tags,
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
        )


@dataclass
class StateStore:
    version: int = 1
    problems: dict[str, ProblemState] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "StateStore":
        problems_raw = data.get("problems")
        if not isinstance(problems_raw, dict):
            problems_raw = {}
        problems = {
            slug: ProblemState.from_dict(item)
            for slug, item in problems_raw.items()
            if isinstance(item, dict)
        }
        return cls(version=int(data.get("version") or 1), problems=problems)


def state_path(config: Config) -> Path:
    """Compatibility path for the pre-SQLite state file."""

    return config.workspace / LEGACY_STATE_NAME


def repository(config: Config) -> SQLiteRepository:
    return SQLiteRepository(config.workspace)


def _import_legacy_state(config: Config, repo: SQLiteRepository) -> None:
    path = state_path(config)
    if not path.exists():
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(raw, dict):
        return
    legacy = StateStore.from_dict(raw)
    for problem in legacy.problems.values():
        if not problem.slug or repo.get_progress(problem.slug) is not None:
            continue
        repo.save_progress(asdict(problem))


def load_state(config: Config) -> StateStore:
    repo = repository(config)
    _import_legacy_state(config, repo)
    problems = {
        item["slug"]: ProblemState.from_dict(item)
        for item in repo.list_progress()
        if item.get("slug")
    }
    return StateStore(problems=problems)


def save_state(config: Config, store: StateStore) -> None:
    repo = repository(config)
    for problem in store.problems.values():
        repo.save_progress(asdict(problem))


def ensure_problem_state(config: Config, slug: str) -> ProblemState:
    repo = repository(config)
    _import_legacy_state(config, repo)
    current = repo.get_progress(slug)
    if current:
        return ProblemState.from_dict(current)
    problem = ProblemState(slug=slug)
    repo.save_progress(asdict(problem))
    return problem


def update_problem_state(
    config: Config,
    slug: str,
    *,
    status: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
) -> ProblemState:
    if status is not None and status not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    repo = repository(config)
    _import_legacy_state(config, repo)
    current = repo.get_progress(slug)
    problem = ProblemState.from_dict(current) if current else ProblemState(slug=slug)
    if status is not None:
        problem.status = status
    if notes is not None:
        problem.notes = notes.strip()
    if tags is not None:
        problem.tags = [tag.strip() for tag in tags if tag.strip()]
    problem.updated_at = utc_now()
    repo.save_progress(asdict(problem))
    return problem
