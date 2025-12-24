from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    workspace: Path
    language: str
    session: str | None = None
    csrf: str | None = None


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "leetcode-vim"


def config_path() -> Path:
    return _config_dir() / "config.json"


def load_config() -> Config | None:
    path = config_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Config(
        workspace=Path(data["workspace"]),
        language=data["language"],
        session=data.get("session"),
        csrf=data.get("csrf"),
    )


def save_config(config: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "workspace": str(config.workspace),
        "language": config.language,
        "session": config.session,
        "csrf": config.csrf,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
