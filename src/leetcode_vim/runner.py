from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


class RunnerError(RuntimeError):
    pass


def run_python(solution_path: Path, input_text: str) -> tuple[str, str]:
    import json
    from .execution import process
    payload = {'legacy': True, 'cases': [{'input': input_text}]}
    stdout, stderr = process([sys.executable, str(Path(__file__).with_name('solution_worker.py')),
                              str(solution_path.resolve())], json.dumps(payload))
    response = json.loads(stdout)
    if response.get('error'):
        raise RunnerError(response['error'])
    result = response['results'][0]
    return result['stdout'], result['stderr'] or stderr


def run_python_cases(solution_path: Path, method_name: str | None, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from .execution import run_cases
    results = run_cases(solution_path, 'python', method_name, cases)
    for result in results:
        if not result['passed']:
            raise RunnerError(f"Example {result['index']} failed: expected {result['expected']!r}, "
                              f"received {result['actual']!r}.")
    return [{k: result[k] for k in ('index', 'actual', 'expected', 'passed')} for result in results]
