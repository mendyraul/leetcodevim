from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 2
DATABASE_RELATIVE_PATH = Path(".leetcodevim") / "state.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ProblemRecord:
    slug: str
    title: str
    title_slug: str
    question_id: str
    difficulty: str
    language: str
    content: str
    method_name: str | None
    parameter_names: tuple[str, ...]
    code: str
    examples: tuple[dict[str, Any], ...]
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SubmissionRecord:
    slug: str
    language: str
    remote_id: str
    status: str
    runtime: str | None
    memory: str | None
    submitted_at: str


class StorageError(RuntimeError):
    pass


class SQLiteRepository:
    """Small repository over the workspace-local SQLite database."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.expanduser().resolve()
        self.path = self.workspace / DATABASE_RELATIVE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        try:
            with self._connect() as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > SCHEMA_VERSION:
                    raise StorageError(
                        f"Database schema {version} is newer than this leetcodevim version ({SCHEMA_VERSION})."
                    )
                if version == 1:
                    backup_path = self.path.with_suffix('.v1.backup.db')
                    if not backup_path.exists():
                        with sqlite3.connect(backup_path) as backup:
                            connection.backup(backup)
                        os.chmod(backup_path, 0o600)
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS problems (
                        slug TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        title_slug TEXT NOT NULL,
                        question_id TEXT NOT NULL,
                        difficulty TEXT NOT NULL,
                        language TEXT NOT NULL,
                        content TEXT NOT NULL DEFAULT '',
                        method_name TEXT,
                        parameter_names_json TEXT NOT NULL DEFAULT '[]',
                        code TEXT NOT NULL DEFAULT '',
                        examples_json TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS progress (
                        slug TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        notes TEXT NOT NULL DEFAULT '',
                        tags_json TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS submissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        slug TEXT NOT NULL,
                        language TEXT NOT NULL,
                        remote_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        runtime TEXT,
                        memory TEXT,
                        submitted_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS submissions_slug_idx ON submissions(slug);
                    """
                )
                connection.execute('''CREATE TABLE IF NOT EXISTS companion_cache (
                    account TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL,
                    payload TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(account, kind, key))''')
                connection.execute('''CREATE TABLE IF NOT EXISTS companion_drafts (
                    slug TEXT NOT NULL, language TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(slug, language))''')
                connection.execute('''CREATE TABLE IF NOT EXISTS companion_operations (
                    account TEXT NOT NULL, remote_id TEXT NOT NULL, slug TEXT NOT NULL,
                    kind TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(account, remote_id))''')
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            os.chmod(self.path, 0o600)
        except sqlite3.Error as exc:
            raise StorageError(f"Could not initialize {self.path}: {exc}") from exc

    @staticmethod
    def _decode_json(raw: str, fallback: Any) -> Any:
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return fallback

    def save_problem(self, record: ProblemRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO problems (
                    slug, title, title_slug, question_id, difficulty, language, content,
                    method_name, parameter_names_json, code, examples_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title=excluded.title,
                    title_slug=excluded.title_slug,
                    question_id=excluded.question_id,
                    difficulty=excluded.difficulty,
                    language=excluded.language,
                    content=excluded.content,
                    method_name=excluded.method_name,
                    parameter_names_json=excluded.parameter_names_json,
                    code=excluded.code,
                    examples_json=excluded.examples_json,
                    updated_at=excluded.updated_at
                """,
                (
                    record.slug,
                    record.title,
                    record.title_slug,
                    record.question_id,
                    record.difficulty,
                    record.language,
                    record.content,
                    record.method_name,
                    json.dumps(list(record.parameter_names)),
                    record.code,
                    json.dumps(list(record.examples)),
                    record.created_at,
                    record.updated_at,
                ),
            )

    def get_problem(self, slug: str) -> ProblemRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM problems WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            return None
        return ProblemRecord(
            slug=row["slug"],
            title=row["title"],
            title_slug=row["title_slug"],
            question_id=row["question_id"],
            difficulty=row["difficulty"],
            language=row["language"],
            content=row["content"],
            method_name=row["method_name"],
            parameter_names=tuple(self._decode_json(row["parameter_names_json"], [])),
            code=row["code"],
            examples=tuple(self._decode_json(row["examples_json"], [])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_problems(self) -> list[ProblemRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT slug FROM problems ORDER BY slug").fetchall()
        return [problem for row in rows if (problem := self.get_problem(row["slug"])) is not None]

    def get_progress(self, slug: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM progress WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            return None
        return {
            "slug": row["slug"],
            "status": row["status"],
            "notes": row["notes"],
            "tags": self._decode_json(row["tags_json"], []),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_progress(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM progress ORDER BY slug").fetchall()
        return [
            {
                "slug": row["slug"],
                "status": row["status"],
                "notes": row["notes"],
                "tags": self._decode_json(row["tags_json"], []),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def save_progress(self, data: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO progress (slug, status, notes, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    status=excluded.status,
                    notes=excluded.notes,
                    tags_json=excluded.tags_json,
                    updated_at=excluded.updated_at
                """,
                (
                    data["slug"],
                    data["status"],
                    data.get("notes", ""),
                    json.dumps(data.get("tags", [])),
                    data["created_at"],
                    data["updated_at"],
                ),
            )

    def save_submissions(self, records: Iterable[SubmissionRecord]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO submissions (slug, language, remote_id, status, runtime, memory, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record.slug,
                        record.language,
                        record.remote_id,
                        record.status,
                        record.runtime,
                        record.memory,
                        record.submitted_at,
                    )
                    for record in records
                ],
            )

    def list_submissions(self, slug: str | None = None) -> list[SubmissionRecord]:
        query = "SELECT * FROM submissions"
        parameters: tuple[str, ...] = ()
        if slug:
            query += " WHERE slug = ?"
            parameters = (slug,)
        query += " ORDER BY submitted_at DESC, id DESC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            SubmissionRecord(
                slug=row["slug"],
                language=row["language"],
                remote_id=row["remote_id"],
                status=row["status"],
                runtime=row["runtime"],
                memory=row["memory"],
                submitted_at=row["submitted_at"],
            )
            for row in rows
        ]
