import pytest

from leetcode_vim import cli


def test_language_slug_unsupported_exits():
    with pytest.raises(SystemExit):
        cli._language_slug('javascript')
