from leetcode_vim import cli


def test_slugify_basic():
    assert cli._slugify('Two Sum') == 'two-sum'


def test_slugify_sanitizes_symbols():
    assert cli._slugify('Best Time to Buy & Sell Stock!') == 'best-time-to-buy--sell-stock'


def test_language_slug_python():
    assert cli._language_slug('python') == 'python3'


def test_language_slug_cpp():
    assert cli._language_slug('cpp') == 'cpp'
