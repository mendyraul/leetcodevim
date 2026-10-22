"""Explicit read-only checks against LeetCode. Never submits or logs in."""
import json
import tempfile
from pathlib import Path

from leetcode_vim.config import Config
from leetcode_vim.leetcode_api import fetch_problem
from leetcode_vim.provider import Provider
from leetcode_vim.service import Service

checks = []


def report(value):
    checks.append(value['ok'])
    print(json.dumps(value), flush=True)


provider = Provider()
for name, call in [
    ('browse', lambda: provider.browse(search='two sum', limit=2)),
    ('daily', provider.daily),
    ('problem', lambda: fetch_problem('two-sum').metadata),
    ('design', lambda: fetch_problem('min-stack').metadata),
    ('contests', provider.contests),
    ('profile', lambda: provider.profile('lee215')),
]:
    try:
        result = call()
        if name == 'profile':
            result = {'username': result['username'], 'ranking': result['profile']['ranking']}
        report({'check': name, 'ok': True, 'data': result})
    except Exception as exc:
        report({'check': name, 'ok': False, 'error': str(exc)})

with tempfile.TemporaryDirectory(prefix='leetcodevim-public-') as root:
    service = Service(Config(Path(root), 'python'))
    # Deliberately anonymous; never read local browser or account credentials.
    service.auth = lambda: None
    for language in ('python', 'cpp'):
        try:
            result = service.dispatch('open', {'slug': 'two-sum', 'language': language})
            report({'check': 'open_' + language, 'ok': True,
                              'method': result['problem']['method_name'],
                              'examples': len(result['problem']['examples'])})
        except Exception as exc:
            report({'check': 'open_' + language, 'ok': False, 'error': str(exc)})

# Exercise real downloaded design-class examples in a temporary workspace.
with tempfile.TemporaryDirectory(prefix='leetcodevim-design-') as root:
    service = Service(Config(Path(root), 'python'))
    service.auth = lambda: None
    sources = {
        'python': ('class MinStack:\n'
                   '    def __init__(self): self.values=[]\n'
                   '    def push(self,value): self.values.append(value)\n'
                   '    def pop(self): self.values.pop()\n'
                   '    def top(self): return self.values[-1]\n'
                   '    def getMin(self): return min(self.values)\n'),
        'cpp': ('class MinStack { vector<int> values; public: '
                'void push(int v){values.push_back(v);} void pop(){values.pop_back();} '
                'int top(){return values.back();} int getMin(){return *min_element(values.begin(),values.end());} };'),
    }
    for language, source in sources.items():
        try:
            opened = service.dispatch('open', {'slug': 'min-stack', 'language': language})
            Path(opened['path']).write_text(source)
            result = service.dispatch('test', {'slug': 'min-stack', 'language': language})
            report({'check': 'design_examples_' + language, 'ok': result['passed'],
                              'examples': len(result['results']),
                              'failures': [case for case in result['results'] if not case['passed']]})
        except Exception as exc:
            report({'check': 'design_examples_' + language, 'ok': False, 'error': str(exc)})

raise SystemExit(0 if all(checks) else 1)
