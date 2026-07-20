from argparse import Namespace
from pathlib import Path

from leetcode_vim import cli
from leetcode_vim.config import Config
from leetcode_vim.leetcode_api import Problem


def test_pull_fetches_problem_and_sample_without_auth(tmp_path, monkeypatch):
    workspace = tmp_path / 'workspace'
    config = Config(workspace=workspace, language='python')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)
    monkeypatch.setattr(cli, '_effective_session', lambda _config: None)
    monkeypatch.setattr(
        cli,
        'fetch_problem',
        lambda slug, auth=None: Problem(
            title='Two Sum',
            title_slug=slug,
            question_id='1',
            content='''
                <div>
                  <p>Given an array of integers <code>nums</code> and an integer <code>target</code>.</p>
                  <p><strong>Example 1:</strong></p>
                  <pre>Input: nums = [2,7,11,15], target = 9\nOutput: [0,1]</pre>
                  <p><strong>Constraints:</strong></p>
                  <ul><li>2 &lt;= nums.length &lt;= 10^4</li></ul>
                </div>
            ''',
            difficulty='Easy',
            sample_test_case='[2,7,11,15]\n9',
            code_snippets=[{'lang': 'Python3'}],
        ),
    )

    exit_code = cli.cmd_pull(Namespace(slug='Two Sum'))

    problem_dir = workspace / 'two-sum'
    assert exit_code == 0
    problem_text = (problem_dir / 'problem.txt').read_text(encoding='utf-8')
    assert problem_text.startswith('Title: Two Sum')
    assert 'Prompt:' in problem_text
    assert 'Given an array of integers `nums` and an integer `target`.' in problem_text
    assert 'Example 1:' in problem_text
    assert 'Constraints:' in problem_text
    assert 'Available Templates:' in problem_text
    assert (problem_dir / 'sample.txt').read_text(encoding='utf-8') == '[2,7,11,15]\n9\n'
    assert (problem_dir / 'solution.py').exists()


def test_pull_extracts_first_example_when_sample_test_case_missing(tmp_path, monkeypatch):
    workspace = tmp_path / 'workspace'
    config = Config(workspace=workspace, language='python')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)
    monkeypatch.setattr(cli, '_effective_session', lambda _config: None)
    monkeypatch.setattr(
        cli,
        'fetch_problem',
        lambda slug, auth=None: Problem(
            title='Merge Strings Alternately',
            title_slug=slug,
            question_id='1768',
            content='''
                <div>
                  <p>Merge two strings by adding letters in alternating order.</p>
                  <p><strong>Example 1:</strong></p>
                  <pre>Input: word1 = "abc", word2 = "pqr"\nOutput: "apbqcr"</pre>
                  <p><strong>Example 2:</strong></p>
                  <pre>Input: word1 = "ab", word2 = "pqrs"\nOutput: "apbqrs"</pre>
                </div>
            ''',
            difficulty='Easy',
            sample_test_case=None,
            code_snippets=[],
        ),
    )

    exit_code = cli.cmd_pull(Namespace(slug='merge-strings-alternately'))

    problem_dir = workspace / 'merge-strings-alternately'
    assert exit_code == 0
    assert (problem_dir / 'sample.txt').read_text(encoding='utf-8') == 'word1 = "abc", word2 = "pqr"\n'
    problem_text = (problem_dir / 'problem.txt').read_text(encoding='utf-8')
    assert 'Note: sample.txt uses the first example input because LeetCode did not provide sampleTestCase.' in problem_text
    assert 'Example 2:' in problem_text


def test_pull_preserves_existing_metadata_when_public_fetch_fails(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / 'workspace'
    problem_dir = workspace / 'two-sum'
    problem_dir.mkdir(parents=True)
    (problem_dir / 'problem.txt').write_text('existing metadata\n', encoding='utf-8')
    config = Config(workspace=workspace, language='python')
    monkeypatch.setattr(cli, '_ensure_config', lambda: config)
    monkeypatch.setattr(cli, '_effective_session', lambda _config: None)

    def fail_fetch(slug, auth=None):
        raise cli.LeetCodeError('network down')

    monkeypatch.setattr(cli, 'fetch_problem', fail_fetch)

    exit_code = cli.cmd_pull(Namespace(slug='two-sum'))

    assert exit_code == 0
    assert (problem_dir / 'problem.txt').read_text(encoding='utf-8') == 'existing metadata\n'
    assert 'could not fetch public problem metadata' in capsys.readouterr().err
