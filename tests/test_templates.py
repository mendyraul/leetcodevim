import pytest

from leetcode_vim.templates import get_template


def test_get_template_python_contains_solution_class():
    tpl = get_template('python')
    assert 'class Solution' in tpl


def test_get_template_cpp_contains_solution_class():
    tpl = get_template('cpp')
    assert 'class Solution' in tpl


def test_get_template_rejects_unknown_language():
    with pytest.raises(ValueError):
        get_template('go')
