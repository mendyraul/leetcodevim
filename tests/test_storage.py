import json
from pathlib import Path

from leetcode_vim.config import Config
from leetcode_vim.state import load_state, update_problem_state
from leetcode_vim.storage import DATABASE_RELATIVE_PATH, SQLiteRepository


def test_workspace_repository_creates_versioned_database(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / 'workspace')
    assert repository.path == tmp_path / 'workspace' / DATABASE_RELATIVE_PATH
    with repository._connect() as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 2


def test_legacy_json_is_imported_without_being_deleted(tmp_path: Path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    legacy = workspace / '.leetcodevim-state.json'
    legacy.write_text(
        json.dumps({'version': 1, 'problems': {
            'two-sum': {
                'slug': 'two-sum',
                'status': 'solved',
                'notes': 'done',
                'tags': ['array'],
                'created_at': '2026-01-01T00:00:00Z',
                'updated_at': '2026-01-02T00:00:00Z',
            }
        }}),
        encoding='utf-8',
    )
    config = Config(workspace=workspace, language='python')
    store = load_state(config)
    assert store.problems['two-sum'].status == 'solved'
    assert store.problems['two-sum'].tags == ['array']
    assert legacy.exists()
    assert (workspace / DATABASE_RELATIVE_PATH).exists()


def test_progress_updates_are_stored_in_sqlite(tmp_path: Path):
    config = Config(workspace=tmp_path / 'workspace', language='python')
    update_problem_state(config, 'two-sum', status='tested', notes='good', tags=['array'])
    loaded = load_state(config).problems['two-sum']
    assert loaded.status == 'tested'
    assert loaded.notes == 'good'
    assert loaded.tags == ['array']
