from __future__ import annotations

import ast
import json
import re
from html.parser import HTMLParser
from typing import Any

from .leetcode_api import Problem
from .storage import ProblemRecord, utc_now
from .templates import get_template


class _PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.in_pre = False
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == 'img':
            self.parts.append('\n[Image: ' + (values.get('alt') or 'diagram') + '] ' + (values.get('src') or '') + '\n')
        elif tag == 'a':
            self.links.append(values.get('href') or '')
        elif tag == 'tr':
            self.parts.append('\n')
        elif tag in ('td', 'th'):
            self.parts.append(' | ')
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "pre":
            self.parts.append("\n\n")
            self.in_pre = True
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == 'a' and self.links:
            url = self.links.pop()
            if url:
                self.parts.append(' (' + url + ')')
        if tag == "pre":
            self.parts.append("\n")
            self.in_pre = False
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_pre:
            self.parts.append(data)
        else:
            normalized = re.sub(r"\s+", " ", data)
            if normalized.strip():
                self.parts.append(normalized)


def render_content(content: str) -> str:
    parser = _PlainTextParser()
    parser.feed(content or "")
    parser.close()
    rendered = "".join(parser.parts)
    rendered = re.sub(r"[ \t]+\n", "\n", rendered)
    rendered = re.sub(r"\n[ \t]+", "\n", rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip()


def _literal_value(raw: str) -> Any:
    value = raw.strip().rstrip(",")
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value


def _parse_named_values(input_text: str, parameter_names: tuple[str, ...]) -> list[Any] | None:
    matches = list(re.finditer(r"\b([A-Za-z_]\w*)\s*=\s*", input_text))
    if not matches:
        return None
    values: dict[str, Any] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(input_text)
        values[match.group(1)] = _literal_value(input_text[match.end():end].strip())
    if not all(name in values for name in parameter_names):
        return None
    return [values[name] for name in parameter_names]


def parse_input(input_text: str, parameter_names: tuple[str, ...]) -> list[Any]:
    named = _parse_named_values(input_text, parameter_names)
    if named is not None:
        return named
    lines = [line.strip() for line in input_text.splitlines() if line.strip()]
    if len(lines) == 1 and len(parameter_names) > 1:
        comma_values = [part.strip() for part in lines[0].split(",")]
        if len(comma_values) == len(parameter_names):
            return [_literal_value(value) for value in comma_values]
    values = [_literal_value(line) for line in lines]
    return values[: len(parameter_names)] if parameter_names else values


def parse_examples(content: str, parameter_names: tuple[str, ...]) -> list[dict[str, Any]]:
    rendered = render_content(content)
    blocks = re.split(r"(?=Example\s+\d+\s*:)", rendered, flags=re.IGNORECASE)
    examples: list[dict[str, Any]] = []
    for block in blocks:
        if not re.search(r"Example\s+\d+\s*:", block, re.IGNORECASE):
            continue
        input_match = re.search(
            r"Input\s*:?\s*(.+?)(?=\n\s*Output\s*:?|\Z)", block, flags=re.IGNORECASE | re.DOTALL
        )
        output_match = re.search(
            r"Output\s*:?\s*(.+?)(?=\n\s*(?:Explanation|Example\s+\d+|Constraints|Follow-up)\s*:?|\Z)",
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not input_match or not output_match:
            continue
        input_text = input_match.group(1).strip()
        output_text = output_match.group(1).strip()
        examples.append({"args": parse_input(input_text, parameter_names), "expected": _literal_value(output_text)})
    return examples


def _python_snippet(problem: Problem) -> str:
    for snippet in sorted(problem.code_snippets, key=lambda s: s.get('langSlug') != 'python3'):
        lang = (snippet.get("langSlug") or snippet.get("lang") or "").lower()
        if lang in {"python", "python3"} or "python" in lang:
            code = snippet.get("code")
            if code:
                lines, pending = [], None
                # Design-class templates can contain several empty methods.
                for line in code.rstrip().splitlines():
                    if line.strip() and not line.lstrip().startswith('#'):
                        indent = len(line) - len(line.lstrip())
                        if pending is not None and indent <= pending:
                            lines.append(' ' * (pending + 4) + 'pass')
                        pending = None
                        if re.match(r"\s*(?:async\s+)?def\s+.*:\s*$", line):
                            pending = indent
                    lines.append(line)
                if pending is not None:
                    lines.append(' ' * (pending + 4) + 'pass')
                return '\n'.join(lines) + '\n'
    return get_template("python")


def inspect_python_code(code: str) -> tuple[str | None, tuple[str, ...]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None, ()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "Solution":
            continue
        for method in node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) or method.name == "__init__":
                continue
            args = [*method.args.posonlyargs, *method.args.args]
            if args and args[0].arg == "self":
                args = args[1:]
            return method.name, tuple(arg.arg for arg in args)
    return None, ()


def build_problem_record(problem: Problem, slug: str, language: str, existing: ProblemRecord | None = None) -> ProblemRecord:
    python_code = _python_snippet(problem)
    code = python_code if language == "python" else next(
        (s['code'] for s in problem.code_snippets if s.get('langSlug') == 'cpp' and s.get('code')), get_template(language))
    method_name, parameter_names = inspect_python_code(python_code)
    if problem.metadata.get('name') and not problem.metadata.get('systemdesign'):
        method_name = problem.metadata['name']
        parameter_names = tuple(p['name'] for p in problem.metadata.get('params', [])) or parameter_names
    if problem.metadata.get('systemdesign'):
        method_name, parameter_names = None, ()
    examples = parse_examples(problem.content, parameter_names)
    if problem.sample_test_case and examples:
        examples[0]["args"] = parse_input(problem.sample_test_case, parameter_names)
    now = utc_now()
    return ProblemRecord(
        slug=slug,
        title=problem.title,
        title_slug=problem.title_slug,
        question_id=problem.question_id,
        difficulty=problem.difficulty,
        language=language,
        content=problem.content,
        method_name=method_name,
        parameter_names=parameter_names,
        code=code,
        examples=tuple(examples),
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
