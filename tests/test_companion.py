import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from leetcode_vim import auth
from leetcode_vim.companion_store import CompanionStore
from leetcode_vim.config import Config
from leetcode_vim.execution import run_cases
from leetcode_vim.leetcode_api import Problem
from leetcode_vim.provider import Provider, ProviderError
from leetcode_vim.runner import RunnerError
from leetcode_vim.service import Service


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(Service, 'auth', lambda self: None)
    cfg = Config(tmp_path / 'workspace', 'python')
    return Service(cfg)


def seed(service, monkeypatch, cpp=False):
    from leetcode_vim import service as module
    problem = Problem('Add', 'add', '1', '<p>Example 1:</p><pre>Input: a = 2, b = 3\nOutput: 5</pre>',
                      'Easy', '2\n3', [
                          {'langSlug': 'python3', 'code': ('class Solution:\n'
                          '    def add(self, a: int, b: int) -> int:\n        pass')},
                          {'langSlug': 'cpp', 'code': 'class Solution { public: int add(int a,int b){return a+b;} };'}],
                      metadata={'name': 'add', 'params': [{'name': 'a', 'type': 'integer'}, {'name': 'b', 'type': 'integer'}]})
    monkeypatch.setattr(module, 'fetch_problem', lambda *args: problem)
    return service.dispatch('open', {'slug': 'add', 'language': 'cpp' if cpp else 'python'})


def test_drafts_preserve_user_work_and_separate_languages(service, monkeypatch):
    py = seed(service, monkeypatch)
    Path(py['path']).write_text('my unfinished work')
    cpp = service.dispatch('open', {'slug': 'add', 'language': 'cpp'})
    assert cpp['path'].endswith('solution.cpp')
    assert service.store().draft('add', 'cpp')['method_name'] == 'add'
    assert service.store().draft('add', 'python')['language'] == 'python'
    service.dispatch('open', {'slug': 'add', 'refresh': True})
    assert Path(py['path']).read_text() == 'my unfinished work'


def test_cached_open_is_offline_and_custom_cases_work(service, monkeypatch):
    opened = seed(service, monkeypatch)
    Path(opened['path']).write_text('class Solution:\n    def add(self,a,b):\n        return a+b\n')
    monkeypatch.setattr('leetcode_vim.service.fetch_problem', lambda *a: pytest.fail('unexpected network'))
    cases = service.dispatch('cases', {'slug': 'add'})
    Path(cases['path']).write_text(json.dumps([{'args': [9, 4], 'expected': 13}]))
    result = service.dispatch('test', {'slug': 'add'})
    assert result['passed']
    assert service.store().get_progress('add')['status'] == 'tested'
    Path(cases['path']).write_text('{broken json')
    with pytest.raises(ValueError):
        service.dispatch('test', {'slug': 'add'})


def test_catalog_cache_and_refresh_failure(service, monkeypatch):
    monkeypatch.setattr(Provider, 'browse', lambda *a, **kw: {'total': 1, 'questions': [{'titleSlug': 'add'}]})
    assert not service.dispatch('browse', {})['cached']
    def offline(*a, **kw):
        raise ProviderError('offline', 'offline')
    monkeypatch.setattr(Provider, 'browse', offline)
    result = service.dispatch('browse', {'refresh': True})
    assert result['stale'] and result['warning']


def test_public_writes_require_confirmation(service, monkeypatch):
    def unsupported(*args):
        raise ProviderError('unsupported', 'unsupported')
    monkeypatch.setattr(Provider, 'contests', unsupported)
    with pytest.raises(ProviderError, match='Confirm submission'):
        service.dispatch('submit', {'slug': 'add'})
    assert service.dispatch('discuss')['mode'] == 'browser'
    assert service.dispatch('contests')['mode'] == 'browser'


def test_migration_backup_and_newer_schema(tmp_path):
    path = tmp_path / '.leetcodevim' / 'state.db'
    path.parent.mkdir()
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA user_version=1')
        db.execute('CREATE TABLE keep_me (value TEXT)')
        db.execute("INSERT INTO keep_me VALUES ('work')")
    store = CompanionStore(tmp_path)
    with store._connect() as db:
        assert db.execute('SELECT value FROM keep_me').fetchone()[0] == 'work'
        assert db.execute('PRAGMA user_version').fetchone()[0] == 2
    assert path.with_suffix('.v1.backup.db').exists()
    with store._connect() as db:
        db.execute('PRAGMA user_version=999')
    from leetcode_vim.storage import StorageError
    with pytest.raises(StorageError, match='newer'):
        CompanionStore(tmp_path)


def test_private_cache_purge_preserves_local_work(service, monkeypatch):
    opened = seed(service, monkeypatch)
    store = service.store()
    store.cache('editorial', 'add', 'secret', 'alice')
    store.cache('catalog', '', 'public')
    store.operation('alice', '1', 'add', 'submit', {'state': 'PENDING'})
    assert store.operations('bob') == []
    store.clear_private()
    assert store.cached('editorial', 'add', 'alice') is None
    assert store.cached('catalog')['data'] == 'public'
    assert store.operations('alice') == []
    assert Path(opened['path']).exists()


def test_auth_fails_closed_without_keychain(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, '_keyring', lambda: None)
    cfg = Config(tmp_path, 'python')
    with pytest.raises(auth.AuthImportError):
        auth.save_auth(cfg, 'secret', 'csrf')
    assert cfg.session is None


def test_python_timeout_and_cancel(tmp_path):
    solution = tmp_path / 'solution.py'
    solution.write_text('class Solution:\n    def loop(self):\n        while True: pass\n')
    with pytest.raises(RunnerError, match='Time limit'):
        run_cases(solution, 'python', 'loop', [{'args': [], 'expected': 1}], timeout=0.1)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(RunnerError, match='Cancelled'):
        run_cases(solution, 'python', 'loop', [{'args': [], 'expected': 1}], cancel=cancel)


def test_python_isolation_and_node_adapters(tmp_path):
    p = tmp_path / 'solution.py'
    p.write_text('class Solution:\n    def echo(self, head: Optional[ListNode]):\n        print("debug")\n        return head\n')
    result = run_cases(p, 'python', 'echo', [{'args': [[1, 2]], 'expected': [1, 2]}])
    assert result[0]['passed'] and result[0]['stdout'] == 'debug\n'
    p.write_text('class Solution:\n    def echo(self, root: Optional[TreeNode]):\n        return root\n')
    assert run_cases(p, 'python', 'echo', [{'args': [[1, None, 2]], 'expected': [1, None, 2]}])[0]['passed']


def test_output_limit_and_syntax_error(tmp_path):
    p = tmp_path / 'solution.py'
    p.write_text('class Solution:\n    def echo(self):\n        print("x" * 1048576)\n')
    with pytest.raises(RunnerError, match='Output limit'):
        run_cases(p, 'python', 'echo', [{'args': [], 'expected': 1}])
    p.write_text('class Solution\n')
    with pytest.raises(RunnerError, match='SyntaxError'):
        run_cases(p, 'python', 'echo', [{'args': [], 'expected': 1}])


def test_design_class_python(tmp_path):
    p = tmp_path / 'solution.py'
    p.write_text('class Counter:\n    def __init__(self, n): self.n=n\n'
                 '    def add(self,x): self.n+=x\n    def get(self): return self.n\n')
    cases = [{'args': [['Counter', 'add', 'get'], [[2], [3], []]], 'expected': [None, None, 5]}]
    assert run_cases(p, 'python', None, cases, {'systemdesign': True})[0]['passed']


@pytest.mark.skipif(not (shutil.which('clang++') or shutil.which('g++')), reason='C++ compiler unavailable')
def test_cpp_array_and_compilation_failure(tmp_path):
    p = tmp_path / 'solution.cpp'
    p.write_text('class Solution { public: vector<int> echo(vector<int>& a) { return a; } };')
    assert run_cases(p, 'cpp', 'echo', [{'args': [[2, 3]], 'expected': [2, 3]}])[0]['passed']
    p.write_text('class Solution BROKEN')
    with pytest.raises(RunnerError):
        run_cases(p, 'cpp', 'echo', [{'args': [], 'expected': 1}])


def test_protocol_invalid_input_and_real_request(tmp_path):
    env = dict(os.environ, XDG_CONFIG_HOME=str(tmp_path))
    proc = subprocess.Popen([sys.executable, '-m', 'leetcode_vim.cli', 'serve', '--stdio'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        proc.stdin.write('not json\n')
        proc.stdin.flush()
        assert json.loads(proc.stdout.readline())['error']['code'] == 'invalid_request'
        proc.stdin.write(json.dumps({'v': 1, 'id': 1, 'method': 'hello', 'params': {}}) + '\n')
        proc.stdin.flush()
        assert json.loads(proc.stdout.readline())['event'] == 'started'
        assert json.loads(proc.stdout.readline())['result']['protocol'] == 1
    finally:
        proc.stdin.close()
        proc.wait(timeout=10)


@pytest.mark.parametrize('editor', ['vim', 'nvim'])
def test_vim_workspace_async_open_and_reopen(service, monkeypatch, tmp_path, editor):
    executable = shutil.which(editor) or (os.environ.get('LEETCODEVIM_NVIM') if editor == 'nvim' else None)
    if not executable:
        pytest.skip(editor + ' unavailable')
    from leetcode_vim.config import save_config
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    save_config(service.config)
    opened = seed(service, monkeypatch)
    root = Path(__file__).resolve().parents[1]
    commands = tmp_path / 'smoke.vim'
    report = tmp_path / 'report.json'
    commands.write_text(f'''
set columns=140
set rtp^={root}
runtime plugin/leetcodevim.vim
let g:leetcodevim_command = ['{sys.executable}', '-m', 'leetcode_vim.cli']
LeetCodeOpen add
let attempts=0
while expand('%:p') !=# '{opened['path']}' && attempts < 100
  sleep 50m
  let attempts+=1
endwhile
let opened = expand('%:p') ==# '{opened['path']}'
let windows = winnr('$')
let shortcut = &l:statusline =~# 'F2 Problems'
LeetCodeBrowser
let restored_browser = expand('%:t') ==# 'LeetCode-browser'
LeetCodeClose
LeetCodeOpen add
let attempts=0
while expand('%:p') !=# '{opened['path']}' && attempts < 100
  sleep 50m
  let attempts+=1
endwhile
let reopened = expand('%:p') ==# '{opened['path']}'
let result = {{'opened': opened, 'windows': windows, 'reopened': reopened}}
let result.shortcut = shortcut
let result.restored_browser = restored_browser
call writefile([json_encode(result)], '{report}')
qa!
''')
    argv = [executable, '-u', 'NONE', '-i', 'NONE', '-n', '-V1' + str(tmp_path / 'vim.log')]
    argv += ['--headless'] if editor == 'nvim' else ['-es']
    result = subprocess.run(argv + ['-S', str(commands)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, (tmp_path / 'vim.log').read_text()
    assert json.loads(report.read_text()) == {
        'opened': True, 'windows': 3, 'reopened': True, 'shortcut': True, 'restored_browser': True,
    }


@pytest.mark.skipif(not (shutil.which('clang++') or shutil.which('g++')), reason='C++ compiler unavailable')
def test_cpp_design_class(tmp_path):
    p = tmp_path / 'solution.cpp'
    p.write_text('class Counter { int n; public: Counter(int x):n(x){} void add(int x){n+=x;} int get(){return n;} };')
    metadata = {'systemdesign': True, 'classname': 'Counter', 'constructor': {'params': [{'type': 'integer'}]},
                'methods': [{'name': 'add'}, {'name': 'get'}]}
    cases = [{'args': [['Counter', 'add', 'get'], [[2], [3], []]], 'expected': [None, None, 5]}]
    assert run_cases(p, 'cpp', None, cases, metadata)[0]['passed']


def test_design_template_and_examples_without_colons():
    from leetcode_vim.problem_model import build_problem_record
    problem = Problem('Counter', 'counter', '1',
                      '<p>Example 1:</p><pre>Input\n["Counter","get"]\n[[],[]]\nOutput\n[null,0]\n\n'
                      'Explanation\nCounter c = new Counter();\nc.get(); // return 0</pre>',
                      'Easy', '["Counter","get"]\n[[],[]]', [{'langSlug': 'python3', 'code':
                          'class Counter:\n    def __init__(self):\n\n    def get(self) -> int:\n\n# usage\n'}],
                      metadata={'systemdesign': True, 'classname': 'Counter'})
    record = build_problem_record(problem, 'counter', 'python')
    compile(record.code, '<solution>', 'exec')
    assert record.examples == ({'args': [['Counter', 'get'], [[], []]], 'expected': [None, 0]},)


@pytest.mark.parametrize('editor', ['vim', 'nvim'])
def test_editor_ignores_late_navigation(tmp_path, monkeypatch, editor):
    executable = shutil.which(editor) or (os.environ.get('LEETCODEVIM_NVIM') if editor == 'nvim' else None)
    if not executable:
        pytest.skip(editor + ' unavailable')
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv('LEETCODEVIM_TEST_ROOT', str(tmp_path))
    script, report = tmp_path / 'late.vim', tmp_path / 'late.json'
    script.write_text(f'''
set columns=70
set rtp^={root}
runtime plugin/leetcodevim.vim
let g:leetcodevim_command = ['{sys.executable}', '{root}/tests/fixtures/delayed_worker.py']
LeetCodeOpen first
LeetCodeOpen second
sleep 800m
let selected=expand('%:t')
let panes=winnr('$')
LeetCodeDescription
LeetCodeCode
let code=expand('%:t')
call writefile([json_encode({{'selected': selected, 'panes': panes, 'code': code}})], '{report}')
qa!
''')
    argv = [executable, '-u', 'NONE', '-i', 'NONE', '-n'] + (['--headless'] if editor == 'nvim' else ['-es'])
    result = subprocess.run(argv + ['-S', str(script)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(report.read_text()) == {'selected': 'second.py', 'panes': 2, 'code': 'second.py'}


@pytest.mark.skipif(not (shutil.which('clang++') or shutil.which('g++')), reason='C++ compiler unavailable')
@pytest.mark.parametrize(('source', 'value'), [
    ('class Solution { public: vector<vector<char>> echo(vector<vector<char>>& a){return a;} };', [['a', 'b']]),
    ('/** struct ListNode { int val; }; */ class Solution { public: ListNode* echo(ListNode* a){return a;} };', [1, 2]),
    ('/** struct TreeNode { int val; }; */ class Solution { public: TreeNode* echo(TreeNode* a){return a;} };',
     [1, None, 2]),
])
def test_cpp_character_and_node_adapters(tmp_path, source, value):
    path = tmp_path / 'solution.cpp'
    path.write_text(source)
    assert run_cases(path, 'cpp', 'echo', [{'args': [value], 'expected': value}])[0]['passed']
