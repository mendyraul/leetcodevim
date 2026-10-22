from leetcode_vim.leetcode_api import Problem
from leetcode_vim.problem_model import build_problem_record, parse_examples


def test_parse_examples_extracts_named_arguments_and_outputs():
    content = '''
    <div>
      <p><strong>Example 1:</strong></p>
      <pre>Input: nums = [2,7,11,15], target = 9
Output: [0,1]</pre>
    </div>
    '''
    assert parse_examples(content, ('nums', 'target')) == [
        {'args': [[2, 7, 11, 15], 9], 'expected': [0, 1]}
    ]


def test_build_problem_record_uses_leetcode_python_snippet():
    problem = Problem(
        title='Two Sum',
        title_slug='two-sum',
        question_id='1',
        content='''<p><strong>Example 1:</strong></p><pre>Input: nums = [2,7], target = 9
Output: [0,1]</pre>''',
        difficulty='Easy',
        sample_test_case='[2,7]\n9',
        code_snippets=[
            {
                'langSlug': 'python3',
                'code': 'from typing import List\n\nclass Solution:\n'
                        '    def twoSum(self, nums: List[int], target: int) -> List[int]:\n'
                        '        pass\n',
            }
        ],
    )
    record = build_problem_record(problem, 'two-sum', 'python')
    assert record.method_name == 'twoSum'
    assert record.parameter_names == ('nums', 'target')
    assert record.examples[0]['args'] == [[2, 7], 9]
    assert 'def twoSum' in record.code


def test_build_problem_record_completes_empty_leetcode_method_body():
    problem = Problem(
        title='Two Sum', title_slug='two-sum', question_id='1', difficulty='Easy',
        content='<p>Example 1:</p><pre>Input: nums = [2,7], target = 9\nOutput: [0,1]</pre>',
        sample_test_case='[2,7]\n9',
        code_snippets=[{'langSlug': 'python3', 'code':
            'class Solution:\n    def twoSum(self, nums: list[int], target: int) -> list[int]:\n        '}],
    )
    record = build_problem_record(problem, 'two-sum', 'python')
    assert record.method_name == 'twoSum'
    assert record.parameter_names == ('nums', 'target')
    assert record.examples == ({'args': [[2, 7], 9], 'expected': [0, 1]},)
    compile(record.code, 'solution.py', 'exec')
