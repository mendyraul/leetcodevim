"""Executed in a disposable child; never import a solution in the editor worker."""
from __future__ import annotations

import collections
import contextlib
import copy
import io
import json
import runpy
import sys
import typing


class ListNode:
    def __init__(self, val=0, next=None):
        self.val, self.next = val, next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val, self.left, self.right = val, left, right


def decode(value, kind):
    if 'ListNode' in str(kind):
        head = current = ListNode()
        for item in value or []:
            current.next = ListNode(item)
            current = current.next
        return head.next
    if 'TreeNode' in str(kind):
        if not value or value[0] is None:
            return None
        root = TreeNode(value[0])
        queue = collections.deque([root])
        values = iter(value[1:])
        while queue:
            node = queue.popleft()
            for side in ('left', 'right'):
                item = next(values, None)
                if item is not None:
                    child = TreeNode(item)
                    setattr(node, side, child)
                    queue.append(child)
        return root
    return value


def encode(value):
    if hasattr(value, 'next') and hasattr(value, 'val'):
        result, seen = [], set()
        while value is not None:
            if id(value) in seen:
                raise ValueError('Cyclic linked lists require remote judging.')
            seen.add(id(value))
            result.append(value.val)
            value = value.next
        return result
    if hasattr(value, 'left') and hasattr(value, 'right'):
        result, queue = [], collections.deque([value])
        while queue:
            node = queue.popleft()
            result.append(node.val if node else None)
            if node:
                queue.extend((node.left, node.right))
        while result and result[-1] is None:
            result.pop()
        return result
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    return value


class LimitedOutput(io.StringIO):
    def write(self, text):
        if self.tell() + len(text) > 512 * 1024:
            raise ValueError('Output limit exceeded.')
        return super().write(text)


def main():
    payload = json.load(sys.stdin)
    initial = {name: getattr(typing, name) for name in ('List', 'Optional', 'Tuple', 'Dict', 'Set', 'Any')}
    initial.update(ListNode=ListNode, TreeNode=TreeNode)
    startup, startup_err = LimitedOutput(), LimitedOutput()
    try:
        with contextlib.redirect_stdout(startup), contextlib.redirect_stderr(startup_err):
            scope = runpy.run_path(sys.argv[1], init_globals=initial, run_name='leetcodevim_solution')
        results = []
        captured = 0
        for index, case in enumerate(payload['cases'], 1):
            out, err = LimitedOutput(), LimitedOutput()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                if payload.get('legacy'):
                    sys.stdin = io.StringIO(case['input'])
                    fn = scope.get('solve')
                    if not callable(fn):
                        cls = scope.get('Solution')
                        fn = getattr(cls(), 'solve', None) if cls else None
                    if not callable(fn):
                        raise ValueError('No solve() function or Solution.solve() method found.')
                    fn()
                    actual = None
                elif payload.get('metadata', {}).get('systemdesign'):
                    operations, arguments = case['args']
                    obj = scope[operations[0]](*arguments[0])
                    actual = [None]
                    for op, args in zip(operations[1:], arguments[1:]):
                        actual.append(encode(getattr(obj, op)(*args)))
                else:
                    cls = scope.get('Solution')
                    if cls is None:
                        raise ValueError('Solution class not found in solution.py.')
                    fn = getattr(cls(), payload['method'], None)
                    if not callable(fn):
                        raise ValueError(f"Solution.{payload['method']}() not found in solution.py.")
                    raw_args = copy.deepcopy(case['args'])
                    parameters = payload.get('metadata', {}).get('params', [])
                    annotations = getattr(fn, '__annotations__', {})
                    kinds = [p.get('type', '') for p in parameters] or [v for k, v in annotations.items() if k != 'return']
                    args = [decode(v, kinds[i] if i < len(kinds) else '') for i, v in enumerate(raw_args)]
                    actual = fn(*args)
                    if actual is None and case.get('in_place'):
                        actual = args[0]
                    actual = encode(actual)
                    return_kind = payload.get('metadata', {}).get('return', {}).get('type') or annotations.get('return', '')
                    if actual is None and any(node in str(return_kind) for node in ('ListNode', 'TreeNode')):
                        actual = []
            captured += len(out.getvalue()) + len(err.getvalue())
            if captured > 512 * 1024:
                raise ValueError('Output limit exceeded.')
            results.append({'actual': actual, 'stdout': startup.getvalue() + out.getvalue(),
                            'stderr': startup_err.getvalue() + err.getvalue()})
        print(json.dumps({'results': results}))
    except BaseException as exc:
        print(json.dumps({'error': f'Example {locals().get("index", 1)} raised {type(exc).__name__}: {exc}'}))


if __name__ == '__main__':
    main()
