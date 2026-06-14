from argparse import Namespace
from pathlib import Path

from leetcode_vim import cli
from leetcode_vim.config import Config


def test_slugify_basic():
    assert cli._slugify('Two Sum') == 'two-sum'


def test_slugify_sanitizes_symbols():
    assert cli._slugify('Best Time to Buy & Sell Stock!') == 'best-time-to-buy--sell-stock'


def test_language_slug_python():
    assert cli._language_slug('python') == 'python3'


def test_language_slug_cpp():
    assert cli._language_slug('cpp') == 'cpp'


def test_problem_entries_include_status(tmp_path):
    workspace = tmp_path / 'workspace'
    alpha = workspace / 'alpha'
    beta = workspace / 'beta'
    alpha.mkdir(parents=True)
    beta.mkdir(parents=True)
    (alpha / 'solution.py').write_text(cli.get_template('python'), encoding='utf-8')
    (beta / 'solution.py').write_text('print("done")\n', encoding='utf-8')
    config = Config(workspace=workspace, language='python')

    entries = cli._problem_entries(config)

    assert [(entry['slug'], entry['status']) for entry in entries] == [
        ('alpha', 'template'),
        ('beta', 'started'),
    ]


def test_cmd_recent_returns_latest_solution_path(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / 'workspace'
    older = workspace / 'older'
    newer = workspace / 'newer'
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    old_solution = older / 'solution.py'
    new_solution = newer / 'solution.py'
    old_solution.write_text(cli.get_template('python'), encoding='utf-8')
    new_solution.write_text('print("hi")\n', encoding='utf-8')
    config = Config(workspace=workspace, language='python')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)

    cli.cmd_recent(Namespace())

    assert capsys.readouterr().out.strip() == str(new_solution)


def test_cmd_next_returns_first_template_solution_path(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / 'workspace'
    started = workspace / 'started'
    todo = workspace / 'todo'
    started.mkdir(parents=True)
    todo.mkdir(parents=True)
    (started / 'solution.py').write_text('print("done")\n', encoding='utf-8')
    todo_solution = todo / 'solution.py'
    todo_solution.write_text(cli.get_template('python'), encoding='utf-8')
    config = Config(workspace=workspace, language='python')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)

    cli.cmd_next(Namespace())

    assert capsys.readouterr().out.strip() == str(todo_solution)


def test_cmd_status_summarizes_workspace(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / 'workspace'
    one = workspace / 'alpha'
    two = workspace / 'beta'
    one.mkdir(parents=True)
    two.mkdir(parents=True)
    (one / 'solution.py').write_text(cli.get_template('python'), encoding='utf-8')
    (two / 'solution.py').write_text('print("done")\n', encoding='utf-8')
    config = Config(workspace=workspace, language='python')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)

    cli.cmd_status(Namespace())
    output = capsys.readouterr().out

    assert f'Workspace: {workspace}' in output
    assert 'Problems: 2' in output
    assert 'Started: 1' in output
    assert 'Template-only: 1' in output
    assert 'Next unsolved: alpha -> ' in output


def test_cmd_test_accepts_slug_from_anywhere(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / 'workspace'
    problem_dir = workspace / 'two-sum'
    problem_dir.mkdir(parents=True)
    (problem_dir / 'sample.txt').write_text('input\n', encoding='utf-8')
    solution_path = problem_dir / 'solution.py'
    solution_path.write_text('print("ok")\n', encoding='utf-8')
    config = Config(workspace=workspace, language='python')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)
    monkeypatch.setattr(cli, 'run_python', lambda path, text: ('ok\n', ''))

    exit_code = cli.cmd_test(Namespace(slug='two sum'))

    output = capsys.readouterr().out
    assert exit_code == 0
    assert 'ok' in output
    assert f'Tested two-sum -> {solution_path}' in output
