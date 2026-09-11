from __future__ import annotations

import io
import runpy
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any


class RunnerError(RuntimeError):
    pass


def run_python(solution_path: Path, input_text: str) -> tuple[str, str]:
    solution_path = solution_path.resolve()
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    stdin_buffer = io.StringIO(input_text)

    old_stdin = sys.stdin
    try:
        sys.stdin = stdin_buffer
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            scope = runpy.run_path(str(solution_path), run_name="__main__")
            if "solve" in scope and callable(scope["solve"]):
                scope["solve"]()
            elif "Solution" in scope and hasattr(scope["Solution"], "solve"):
                scope["Solution"]().solve()
            else:
                raise RunnerError("No solve() function or Solution.solve() method found.")
    finally:
        sys.stdin = old_stdin

    return stdout_buffer.getvalue(), stderr_buffer.getvalue()


def run_python_cases(
    solution_path: Path,
    method_name: str | None,
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Execute LeetCode-style Solution methods against cached example cases."""

    if not method_name:
        raise RunnerError("Problem metadata has no Python Solution method. Pull the problem again.")
    solution_path = solution_path.resolve()
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            scope = runpy.run_path(str(solution_path), run_name="leetcodevim_solution")
            solution_class = scope.get("Solution")
            if solution_class is None:
                raise RunnerError("Solution class not found in solution.py.")
            instance = solution_class()
            method = getattr(instance, method_name, None)
            if not callable(method):
                raise RunnerError(f"Solution.{method_name}() not found in solution.py.")
            results = []
            for index, case in enumerate(cases, start=1):
                args = case.get("args")
                if not isinstance(args, list):
                    raise RunnerError(f"Example {index} has invalid argument data.")
                try:
                    actual = method(*args)
                except Exception as exc:  # pragma: no cover - message asserted through the public error
                    raise RunnerError(f"Example {index} raised {type(exc).__name__}: {exc}") from exc
                expected = case.get("expected")
                passed = actual == expected
                results.append({"index": index, "actual": actual, "expected": expected, "passed": passed})
                if not passed:
                    raise RunnerError(
                        f"Example {index} failed: expected {expected!r}, received {actual!r}."
                    )
    finally:
        if stderr_buffer.getvalue():
            sys.stderr.write(stderr_buffer.getvalue())
    return results
