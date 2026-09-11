from pathlib import Path

import pytest

from leetcode_vim.runner import RunnerError, run_python, run_python_cases


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


def test_run_python_cases_invokes_native_method(tmp_path: Path):
    p = tmp_path / 'solution.py'
    p.write_text(
        'class Solution:\n'
        '    def add(self, left, right):\n'
        '        return left + right\n',
        encoding='utf-8',
    )
    results = run_python_cases(p, 'add', [{'args': [2, 3], 'expected': 5}])
    assert results == [{'index': 1, 'actual': 5, 'expected': 5, 'passed': True}]


def test_run_python_cases_reports_wrong_result(tmp_path: Path):
    p = tmp_path / 'solution.py'
    p.write_text(
        'class Solution:\n'
        '    def add(self, left, right):\n'
        '        return left - right\n',
        encoding='utf-8',
    )
    with pytest.raises(RunnerError, match='Example 1 failed'):
        run_python_cases(p, 'add', [{'args': [2, 3], 'expected': 5}])


def test_run_python_cases_requires_declared_method(tmp_path: Path):
    p = tmp_path / 'solution.py'
    p.write_text('class Solution:\n    pass\n', encoding='utf-8')
    with pytest.raises(RunnerError, match='not found'):
        run_python_cases(p, 'add', [{'args': [2, 3], 'expected': 5}])
