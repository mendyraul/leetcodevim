"""Bounded subprocess execution shared by the CLI and editor worker."""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .runner import RunnerError

LIMIT = 1024 * 1024


def process(command, input_text='', timeout=5, cancel=None, cwd=None):
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err, text=True,
                                cwd=cwd, start_new_session=True)
        # Case payloads are small; write through a separate file to avoid a pipe deadlock.
        import threading
        def feed():
            try:
                proc.stdin.write(input_text)
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        writer = threading.Thread(target=feed, daemon=True)
        writer.start()
        deadline = time.monotonic() + timeout
        reason = None
        while proc.poll() is None:
            if cancel and cancel.is_set():
                reason = 'Cancelled.'
            elif time.monotonic() > deadline:
                reason = f'Time limit exceeded ({timeout}s).'
            elif os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > LIMIT:
                reason = 'Output limit exceeded (1 MiB).'
            if reason:
                break
            time.sleep(0.02)
        # Kill descendants as well, including ones left after the parent exits.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        if reason:
            raise RunnerError(reason)
        if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > LIMIT:
            raise RunnerError('Output limit exceeded (1 MiB).')
        out.seek(0)
        err.seek(0)
        stdout, stderr = out.read(LIMIT).decode(errors='replace'), err.read(LIMIT).decode(errors='replace')
        if proc.returncode:
            raise RunnerError(stderr.strip() or f'Process exited with status {proc.returncode}.')
        return stdout, stderr


def compare(actual, expected, mode='exact'):
    if mode in ('unordered', 'unordered_nested'):
        if not isinstance(actual, list) or not isinstance(expected, list):
            return False
        def canonical(value):
            if mode == 'unordered_nested' and isinstance(value, list):
                value = sorted(value, key=lambda item: json.dumps(item, sort_keys=True))
            return json.dumps(value, sort_keys=True)
        return sorted(canonical(v) for v in actual) == sorted(canonical(v) for v in expected)
    if mode == 'float':
        import math
        return isinstance(actual, (float, int)) and math.isclose(actual, expected, rel_tol=1e-5, abs_tol=1e-5)
    if mode != 'exact':
        raise RunnerError('Unsupported comparison rule. Use remote judging for this problem.')
    return actual == expected


def run_cases(path, language, method, cases, metadata=None, timeout=5, cancel=None):
    if not cases:
        raise RunnerError('No parseable examples. Add custom cases or use remote run.')
    metadata = metadata or {}
    if not method and not metadata.get('systemdesign'):
        raise RunnerError('Problem metadata has no Solution method. Pull again or use remote run.')
    with tempfile.TemporaryDirectory(prefix='leetcodevim-run-') as root:
        if language == 'python':
            command = [sys.executable, str(Path(__file__).with_name('solution_worker.py')), str(Path(path).resolve())]
        else:
            command = compile_cpp(path, method, root, metadata, cancel)
        payload = json.dumps({'method': method, 'cases': cases, 'metadata': metadata})
        stdout, stderr = process(command, payload, timeout=timeout, cancel=cancel, cwd=str(Path(path).parent))
    try:
        response = json.loads(stdout)
    except ValueError:
        raise RunnerError('The harness returned invalid output. Use remote judging for this problem.') from None
    if response.get('error'):
        raise RunnerError(response['error'])
    if not isinstance(response.get('results'), list) or len(response['results']) != len(cases):
        raise RunnerError('The harness did not return a result for every case.')
    results = []
    for index, (case, result) in enumerate(zip(cases, response['results']), 1):
        actual = result['actual']
        passed = compare(actual, case.get('expected'), case.get('comparison', 'exact'))
        results.append({'index': index, 'actual': actual, 'expected': case.get('expected'), 'passed': passed,
                        'stdout': result.get('stdout', ''), 'stderr': result.get('stderr', '') or stderr})
    return results


def compile_cpp(path, method, root, metadata, cancel):
    compiler = shutil.which('clang++') or shutil.which('g++')
    if not compiler:
        raise RunnerError('No C++ compiler found. Install clang++ or g++, or use remote run.')
    if not metadata.get('systemdesign') and not re.fullmatch(r'[A-Za-z_]\w*', method or ''):
        raise RunnerError('Invalid C++ method metadata.')
    source = Path(path).read_text()
    source = re.sub(r'^\s*#include\s*[<"]bits/stdc\+\+\.h[>"]\s*$', '', source, flags=re.M)
    harness = Path(__file__).with_name('cpp_harness.hpp').read_text()
    node_types = ''
    declarations = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    if not re.search(r'\b(?:struct|class)\s+ListNode\s*\{', declarations):
        node_types += ('struct ListNode { int val; ListNode* next; '
                       'ListNode(int x=0,ListNode* n=nullptr):val(x),next(n){} };\n')
    if not re.search(r'\b(?:struct|class)\s+TreeNode\s*\{', declarations):
        node_types += ('struct TreeNode { int val; TreeNode *left,*right; '
                       'TreeNode(int x=0,TreeNode* l=nullptr,TreeNode* r=nullptr):val(x),left(l),right(r){} };\n')
    includes = '\n'.join('#include <' + h + '>' for h in [
        'iostream', 'sstream', 'vector', 'string', 'algorithm', 'map', 'unordered_map', 'set', 'unordered_set',
        'queue', 'stack', 'deque', 'tuple', 'type_traits', 'functional', 'numeric', 'cmath', 'climits', 'memory'])
    generated = includes + '\n#include "json.hpp"\nusing namespace std;\n' + node_types + source + '\n' + harness
    if metadata.get('systemdesign'):
        generated += design_main(metadata)
    else:
        generated += '\nint main(){ return run(&Solution::' + method + '); }\n'
    main = Path(root) / 'main.cpp'
    main.write_text(generated)
    executable = Path(root) / 'solution'
    process([compiler, '-std=c++17', '-O0', '-I', str(Path(__file__).parent / 'vendor'), str(main), '-o', str(executable)],
            timeout=30, cancel=cancel)
    return [str(executable)]


def cpp_type(kind):
    if kind.endswith('[]'):
        return 'vector<' + cpp_type(kind[:-2]) + '>'
    types = {'integer': 'int', 'long': 'long long', 'long long': 'long long', 'double': 'double',
             'float': 'double', 'string': 'string', 'boolean': 'bool', 'character': 'char',
             'ListNode': 'ListNode*', 'TreeNode': 'TreeNode*'}
    if kind not in types:
        raise RunnerError('This design-class argument type requires remote judging: ' + str(kind))
    return types[kind]


def design_main(metadata):
    classname = metadata.get('classname') or metadata.get('className')
    if not re.fullmatch(r'[A-Za-z_]\w*', classname or ''):
        raise RunnerError('Missing design-class metadata; use remote run.')
    params = metadata.get('constructor', {}).get('params', [])
    ctor = ','.join('decode_arg<' + cpp_type(p['type']) + f'>(arguments.at(0).at({i}))' for i, p in enumerate(params))
    branches = []
    for method in metadata.get('methods', []):
        name = method['name']
        if not re.fullmatch(r'[A-Za-z_]\w*', name):
            raise RunnerError('Invalid design-class method metadata.')
        branches.append(f'if(op=="{name}") {{ actual.push_back(invoke_on(obj,&{classname}::{name},arguments.at(i))); }}')
    dispatch = ' else '.join(branches)
    return '''
int main() {
    try {
        json payload; cin >> payload; json results=json::array();
        for(auto& c:payload.at("cases")) {
            auto ops=c.at("args").at(0); auto arguments=c.at("args").at(1);
            Capture capture; auto old=cout.rdbuf(capture.rdbuf()); cout.exceptions(ios::badbit);
            json actual=json::array({nullptr});
            try {
                CLASSNAME obj{CTOR};
                for(size_t i=1;i<ops.size();++i) { string op=ops.at(i).get<string>();
                    DISPATCH else { throw runtime_error("Unknown design-class operation."); }
                }
            } catch(...) { cout.rdbuf(old); throw; }
            cout.rdbuf(old); results.push_back({{"actual",actual},{"stdout",capture.str()}});
        }
        cout << json{{"results",results}}.dump();
    } catch(const exception& e) { cout << json{{"error",e.what()}}.dump(); }
}
'''.replace('CLASSNAME', classname).replace('CTOR', ctor).replace('DISPATCH', dispatch or 'if(false) {}')
