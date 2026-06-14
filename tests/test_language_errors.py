from argparse import Namespace
from pathlib import Path

import pytest

from leetcode_vim import cli
from leetcode_vim.config import Config


def test_language_slug_unsupported_exits():
    with pytest.raises(SystemExit):
        cli._language_slug('javascript')


def test_normalize_language_rejects_unknown_language():
    with pytest.raises(SystemExit, match='Supported languages: python, cpp'):
        cli._normalize_language('javascript')


def test_command_support_matrix_declares_cpp_scaffold_only_for_pull_and_list():
    assert cli._command_support('pull', 'cpp') == 'scaffold-only'
    assert cli._command_support('list', 'cpp') == 'scaffold-only'


def test_cpp_test_fails_early_with_actionable_message(tmp_path: Path, monkeypatch):
    workspace = tmp_path / 'workspace'
    problem_dir = workspace / 'two-sum'
    problem_dir.mkdir(parents=True)
    (problem_dir / 'sample.txt').write_text('1\n', encoding='utf-8')
    (problem_dir / 'solution.cpp').write_text('// TODO\n', encoding='utf-8')
    config = Config(workspace=workspace, language='cpp')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)
    monkeypatch.chdir(problem_dir)

    with pytest.raises(SystemExit, match='Local test runner only supports python right now'):
        cli.cmd_test(Namespace())


def test_cpp_submit_fails_early_with_actionable_message(tmp_path: Path, monkeypatch):
    workspace = tmp_path / 'workspace'
    problem_dir = workspace / 'two-sum'
    problem_dir.mkdir(parents=True)
    (problem_dir / 'solution.cpp').write_text('// TODO\n', encoding='utf-8')
    config = Config(workspace=workspace, language='cpp')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)
    monkeypatch.chdir(problem_dir)

    with pytest.raises(SystemExit, match='Submit only supports python right now'):
        cli.cmd_submit(Namespace())
