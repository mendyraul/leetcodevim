from pathlib import Path

import pytest

from leetcode_vim.runner import ENTRYPOINT_ERROR, RunnerError, run_python


def test_run_python_uses_top_level_solve(tmp_path: Path):
    p = tmp_path / 'solution.py'
    p.write_text('def solve():\n    print(input().strip()[::-1])\n', encoding='utf-8')
    out, err = run_python(p, 'abc\n')
    assert out.strip() == 'cba'
    assert err == ''


def test_run_python_uses_solution_class(tmp_path: Path):
    p = tmp_path / 'solution.py'
    p.write_text('class Solution:\n    def solve(self):\n        print(42)\n', encoding='utf-8')
    out, err = run_python(p, '')
    assert out.strip() == '42'
    assert err == ''


def test_run_python_raises_without_entrypoint(tmp_path: Path):
    p = tmp_path / 'solution.py'
    p.write_text('x = 1\n', encoding='utf-8')
    with pytest.raises(RunnerError, match=r'Expected a `solve\(\)` function'):
        run_python(p, '')


def test_run_python_wraps_solution_exception(tmp_path: Path):
    p = tmp_path / 'solution.py'
    p.write_text('def solve():\n    raise ValueError("boom")\n', encoding='utf-8')
    with pytest.raises(RunnerError, match='Solution raised ValueError: boom'):
        run_python(p, '')


def test_runner_entrypoint_error_constant_is_specific():
    assert 'sample.txt' in ENTRYPOINT_ERROR or 'stdin' in ENTRYPOINT_ERROR
