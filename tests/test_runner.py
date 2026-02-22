from pathlib import Path

import pytest

from leetcode_vim.runner import RunnerError, run_python


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
    with pytest.raises(RunnerError):
        run_python(p, '')
