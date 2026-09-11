import json
from argparse import Namespace
from pathlib import Path

from leetcode_vim import cli
from leetcode_vim.config import Config
from leetcode_vim.state import update_problem_state
from leetcode_vim.storage import ProblemRecord, SQLiteRepository


def _native_config(tmp_path: Path) -> Config:
    workspace = tmp_path / 'workspace'
    problem_dir = workspace / 'two-sum'
    problem_dir.mkdir(parents=True)
    (problem_dir / 'solution.py').write_text(
        'class Solution:\n'
        '    def twoSum(self, nums, target):\n'
        '        return [0, 1]\n',
        encoding='utf-8',
    )
    config = Config(workspace=workspace, language='python')
    SQLiteRepository(workspace).save_problem(
        ProblemRecord(
            slug='two-sum',
            title='Two Sum',
            title_slug='two-sum',
            question_id='1',
            difficulty='Easy',
            language='python',
            content='',
            method_name='twoSum',
            parameter_names=('nums', 'target'),
            code=(problem_dir / 'solution.py').read_text(encoding='utf-8'),
            examples=({'args': [[2, 7], 9], 'expected': [0, 1]},),
            created_at='2026-01-01T00:00:00Z',
            updated_at='2026-01-01T00:00:00Z',
        )
    )
    update_problem_state(config, 'two-sum')
    return config


def test_cmd_test_runs_cached_native_examples(tmp_path, monkeypatch, capsys):
    config = _native_config(tmp_path)
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)

    assert cli.cmd_test(Namespace(slug='two-sum')) == 0
    assert 'Passed 1 example(s)' in capsys.readouterr().out


def test_cmd_list_json_is_stable_for_vim_adapters(tmp_path, monkeypatch, capsys):
    config = _native_config(tmp_path)
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)

    assert cli.cmd_list(Namespace(format='json')) == 0
    entries = json.loads(capsys.readouterr().out)
    assert entries[0]['slug'] == 'two-sum'
    assert entries[0]['status'] == 'pulled'
    assert entries[0]['path'].endswith('two-sum/solution.py')
