from argparse import Namespace
import json

from leetcode_vim import cli
from leetcode_vim.config import Config
from leetcode_vim.leetcode_api import Problem
from leetcode_vim.state import ALLOWED_STATUSES, load_state, update_problem_state


def test_pull_creates_default_state(tmp_path, monkeypatch):
    workspace = tmp_path / 'workspace'
    config = Config(workspace=workspace, language='python')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)
    monkeypatch.setattr(cli, '_effective_session', lambda _config: None)
    monkeypatch.setattr(
        cli,
        'fetch_problem',
        lambda slug, auth=None: Problem(
            title='Two Sum',
            title_slug=slug,
            question_id='1',
            content='<p>Example</p>',
            difficulty='Easy',
            sample_test_case='1 2',
            code_snippets=[],
        ),
    )

    assert cli.cmd_pull(Namespace(slug='Two Sum')) == 0

    store = load_state(config)
    assert store.problems['two-sum'].status == 'pulled'


def test_mark_updates_status_notes_and_tags(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / 'workspace'
    config = Config(workspace=workspace, language='python')
    workspace.mkdir(parents=True)
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)

    assert cli.cmd_mark(Namespace(slug='Two Sum', status='in-progress', notes='Need review', tags='array,two-pointers')) == 0

    store = load_state(config)
    problem = store.problems['two-sum']
    assert problem.status == 'in-progress'
    assert problem.notes == 'Need review'
    assert problem.tags == ['array', 'two-pointers']
    assert 'Updated two-sum: status=in-progress' in capsys.readouterr().out


def test_status_lists_all_tracked_problems(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / 'workspace'
    config = Config(workspace=workspace, language='python')
    workspace.mkdir(parents=True)
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)
    update_problem_state(config, 'two-sum', status='solved', notes='done', tags=['array'])
    update_problem_state(config, 'three-sum', status='review', tags=['two-pointers'])

    assert cli.cmd_status(Namespace(slug=None)) == 0

    output = capsys.readouterr().out.strip().splitlines()
    assert output[0].startswith('three-sum\treview\ttwo-pointers')
    assert output[1].startswith('two-sum\tsolved\tarray\tdone')


def test_status_single_problem(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / 'workspace'
    config = Config(workspace=workspace, language='python')
    workspace.mkdir(parents=True)
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)
    update_problem_state(config, 'two-sum', status='tested', notes='good', tags=['array'])

    assert cli.cmd_status(Namespace(slug='two-sum')) == 0

    output = capsys.readouterr().out
    assert 'status: tested' in output
    assert 'tags: array' in output
    assert 'notes: good' in output


def test_load_state_handles_missing_or_invalid_file(tmp_path):
    config = Config(workspace=tmp_path / 'workspace', language='python')
    config.workspace.mkdir(parents=True)
    assert load_state(config).problems == {}

    (config.workspace / '.leetcodevim-state.json').write_text(json.dumps(['bad']), encoding='utf-8')
    assert load_state(config).problems == {}


def test_mark_rejects_unknown_status(tmp_path):
    config = Config(workspace=tmp_path / 'workspace', language='python')
    config.workspace.mkdir(parents=True)

    try:
        update_problem_state(config, 'two-sum', status='wat' if 'wat' not in ALLOWED_STATUSES else 'bad')
    except ValueError as exc:
        assert 'Unsupported status' in str(exc)
    else:
        raise AssertionError('expected ValueError for invalid status')
