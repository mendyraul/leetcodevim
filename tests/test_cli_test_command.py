from pathlib import Path

from leetcode_vim import cli
from leetcode_vim.config import Config, save_config


def _init_workspace(tmp_path: Path, language: str = 'python') -> Path:
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    problem_dir = workspace / 'two-sum'
    problem_dir.mkdir()
    save_config(Config(workspace=workspace, language=language))
    return problem_dir


def test_cmd_test_requires_sample_fixture(tmp_path: Path, monkeypatch, capsys):
    problem_dir = _init_workspace(tmp_path)
    (problem_dir / 'solution.py').write_text('def solve():\n    print(1)\n', encoding='utf-8')
    monkeypatch.chdir(problem_dir)

    code = cli.cmd_test(None)

    assert code == 1
    assert 'sample.txt not found' in capsys.readouterr().out


def test_cmd_test_reports_unsupported_cpp_cleanly(tmp_path: Path, monkeypatch, capsys):
    problem_dir = _init_workspace(tmp_path, language='cpp')
    (problem_dir / 'sample.txt').write_text('1 2\n', encoding='utf-8')
    (problem_dir / 'solution.cpp').write_text('// todo\n', encoding='utf-8')
    monkeypatch.chdir(problem_dir)

    code = cli.cmd_test(None)

    assert code == 1
    assert 'supports python only' in capsys.readouterr().out


def test_cmd_test_shows_hint_for_missing_entrypoint(tmp_path: Path, monkeypatch, capsys):
    problem_dir = _init_workspace(tmp_path)
    (problem_dir / 'sample.txt').write_text('abc\n', encoding='utf-8')
    (problem_dir / 'solution.py').write_text('x = 1\n', encoding='utf-8')
    monkeypatch.chdir(problem_dir)

    code = cli.cmd_test(None)
    output = capsys.readouterr().out

    assert code == 1
    assert 'Expected a `solve()` function' in output
    assert 'Hint: define `solve()`' in output
