import pytest

from leetcode_vim.auth import AuthImportError, import_from_browser


def test_import_from_browser_rejects_unsupported_browser():
    with pytest.raises(AuthImportError):
        import_from_browser('safari', 'leetcode.com')
