"""Version 1 newline-delimited JSON protocol over private stdio pipes."""
from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from .auth import AuthImportError
from .provider import ProviderError
from .runner import RunnerError
from .service import Service


def serve(input_stream=None, output_stream=None, service=None):
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    service = service or Service()
    write_lock, pending_lock = threading.Lock(), threading.Lock()
    pending = {}

    def send(value):
        with write_lock:
            output_stream.write(json.dumps(dict(value, v=1), ensure_ascii=True) + '\n')
            output_stream.flush()

    def error(request_id, code, message):
        send({'id': request_id, 'error': {'code': code, 'message': message}})

    def work(request, cancel):
        request_id = request['id']
        try:
            send({'id': request_id, 'event': 'started'})
            result = service.dispatch(request['method'], request.get('params', {}), cancel,
                                      lambda event: send(dict(event, id=request_id)))
            if cancel.is_set() and request['method'] not in ('run', 'submit', 'poll'):
                error(request_id, 'cancelled', 'Cancelled.')
            else:
                send({'id': request_id, 'result': result})
        except ProviderError as exc:
            error(request_id, exc.code, str(exc))
        except (RunnerError, AuthImportError) as exc:
            error(request_id, 'execution_error', str(exc))
        except (ValueError, KeyError, TypeError):
            error(request_id, 'invalid_request', 'Invalid request data or cached case format.')
        except Exception:
            error(request_id, 'internal_error', 'Operation failed. Run leetcodevim doctor for environment diagnostics.')
        finally:
            with pending_lock:
                pending.pop(request_id, None)

    executor = ThreadPoolExecutor(max_workers=4)
    try:
        for line in input_stream:
            request_id = None
            try:
                if len(line) > 1024 * 1024:
                    raise ValueError('Request exceeds 1 MiB.')
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError('Expected a JSON object.')
                request_id = request.get('id')
                if not isinstance(request_id, (str, int)) or isinstance(request_id, bool):
                    request_id = None
                    raise ValueError('A string or integer request ID is required.')
                if request.get('v') != 1:
                    raise ValueError('Protocol version v=1 is required.')
                if not isinstance(request.get('method'), str) or not isinstance(request.get('params', {}), dict):
                    raise ValueError('method must be a string and params an object.')
                if request['method'] == 'cancel':
                    target = request.get('params', {}).get('id')
                    with pending_lock:
                        cancellation = pending.get(target) if isinstance(target, (str, int)) else None
                        if cancellation:
                            cancellation.set()
                    send({'id': request_id, 'result': {'cancelled': bool(cancellation)}})
                    continue
                with pending_lock:
                    if request_id in pending:
                        raise ValueError('Request ID is already pending.')
                    if len(pending) >= 16:
                        raise ValueError('Too many pending requests.')
                    cancellation = threading.Event()
                    pending[request_id] = cancellation
                executor.submit(work, request, cancellation)
            except (ValueError, TypeError):
                error(request_id, 'invalid_request', 'Invalid protocol request. Expected {v:1,id,method,params:{}}.')
    finally:
        with pending_lock:
            for cancellation in pending.values():
                cancellation.set()
        executor.shutdown(wait=True)
    return 0
