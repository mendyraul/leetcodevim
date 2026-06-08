from argparse import Namespace
from pathlib import Path

from leetcode_vim import cli
from leetcode_vim.config import Config
from leetcode_vim.leetcode_api import Problem


def test_pull_fetches_problem_and_sample_without_auth(tmp_path, monkeypatch):
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
            sample_test_case='[2,7,11,15]\n9',
            code_snippets=[],
        ),
    )

    exit_code = cli.cmd_pull(Namespace(slug='Two Sum'))

    problem_dir = workspace / 'two-sum'
    assert exit_code == 0
    assert (problem_dir / 'problem.txt').read_text(encoding='utf-8').startswith('Title: Two Sum')
    assert (problem_dir / 'sample.txt').read_text(encoding='utf-8') == '[2,7,11,15]\n9\n'
    assert (problem_dir / 'solution.py').exists()


def test_pull_preserves_existing_metadata_when_public_fetch_fails(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / 'workspace'
    problem_dir = workspace / 'two-sum'
    problem_dir.mkdir(parents=True)
    (problem_dir / 'problem.txt').write_text('existing metadata\n', encoding='utf-8')
    config = Config(workspace=workspace, language='python')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)
    monkeypatch.setattr(cli, '_effective_session', lambda _config: None)

    def fail_fetch(slug, auth=None):
        raise cli.LeetCodeError('network down')

    monkeypatch.setattr(cli, 'fetch_problem', fail_fetch)

    exit_code = cli.cmd_pull(Namespace(slug='two-sum'))

    assert exit_code == 0
    assert (problem_dir / 'problem.txt').read_text(encoding='utf-8') == 'existing metadata\n'
    assert 'could not fetch public problem metadata' in capsys.readouterr().err
