from __future__ import annotations

import io
import runpy
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


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
