from __future__ import annotations

import io
import runpy
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ENTRYPOINT_ERROR = (
    "Expected a `solve()` function or `Solution.solve()` method in the solution file. "
    "The local runner reads sample.txt from stdin and captures stdout for assertions."
)


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
            try:
                scope = runpy.run_path(str(solution_path), run_name="__main__")
                entrypoint = _resolve_entrypoint(scope)
                entrypoint()
            except RunnerError:
                raise
            except SystemExit as exc:
                code = exc.code if exc.code is not None else 0
                if code not in (0, "0"):
                    raise RunnerError(f"Solution exited early with status {code}.") from exc
            except Exception as exc:  # pragma: no cover - exercised in tests
                raise RunnerError(f"Solution raised {exc.__class__.__name__}: {exc}") from exc
    finally:
        sys.stdin = old_stdin

    return stdout_buffer.getvalue(), stderr_buffer.getvalue()


def _resolve_entrypoint(scope: dict[str, object]):
    solve = scope.get("solve")
    if callable(solve):
        return solve

    solution_cls = scope.get("Solution")
    if solution_cls and hasattr(solution_cls, "solve"):
        return solution_cls().solve

    raise RunnerError(ENTRYPOINT_ERROR)
