from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import Config

DEFAULT_STATUS = "pulled"
ALLOWED_STATUSES = ("pulled", "in-progress", "tested", "solved", "submitted", "review")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class ProblemState:
    slug: str
    status: str = DEFAULT_STATUS
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

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
            created_at=str(data.get("created_at") or _utc_now()),
            updated_at=str(data.get("updated_at") or _utc_now()),
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
    return config.workspace / ".leetcodevim-state.json"


def load_state(config: Config) -> StateStore:
    path = state_path(config)
    if not path.exists():
        return StateStore()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return StateStore()
    return StateStore.from_dict(data)


def save_state(config: Config, store: StateStore) -> None:
    path = state_path(config)
    payload = {
        "version": store.version,
        "problems": {slug: asdict(problem) for slug, problem in sorted(store.problems.items())},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def ensure_problem_state(config: Config, slug: str) -> ProblemState:
    store = load_state(config)
    current = store.problems.get(slug)
    if current:
        return current
    problem = ProblemState(slug=slug)
    store.problems[slug] = problem
    save_state(config, store)
    return problem


def update_problem_state(
    config: Config,
    slug: str,
    *,
    status: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
) -> ProblemState:
    store = load_state(config)
    problem = store.problems.get(slug) or ProblemState(slug=slug)
    if status is not None:
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported status: {status}")
        problem.status = status
    if notes is not None:
        problem.notes = notes.strip()
    if tags is not None:
        problem.tags = [tag.strip() for tag in tags if tag.strip()]
    problem.updated_at = _utc_now()
    store.problems[slug] = problem
    save_state(config, store)
    return problem
