import io
import json
import queue
import threading
import urllib.error

import pytest

from leetcode_vim.protocol import serve
from leetcode_vim.provider import Provider, ProviderError
from leetcode_vim.service import Service


class Response:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return json.dumps(self.data).encode()


def test_catalog_query_and_filters(monkeypatch):
    requests = []
    def request(req, **kwargs):
        requests.append(json.loads(req.data))
        return Response({'data': {'problemsetQuestionList': {'total': 1, 'questions': [{'titleSlug': 'two-sum'}]}}})
    monkeypatch.setattr('urllib.request.urlopen', request)
    result = Provider().browse(search='two', difficulty='easy', topic='array', offset=50)
    assert result['questions'][0]['titleSlug'] == 'two-sum'
    assert requests[0]['variables']['filters'] == {'searchKeywords': 'two', 'difficulty': 'EASY', 'tags': ['array']}
    assert requests[0]['variables']['skip'] == 50
    assert 'questionList' in requests[0]['query']


def test_write_is_not_retried_and_credentials_are_redacted(monkeypatch):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise urllib.error.URLError('secret-token')
    monkeypatch.setattr('urllib.request.urlopen', fail)
    with pytest.raises(ProviderError) as error:
        Provider().request('/submit/', {}, read=False)
    assert len(calls) == 1
    assert 'secret-token' not in str(error.value)


def test_rate_limit_read_retry_is_bounded(monkeypatch):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise urllib.error.HTTPError('url', 429, 'rate', {}, io.BytesIO())
    monkeypatch.setattr('urllib.request.urlopen', fail)
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    with pytest.raises(ProviderError) as error:
        Provider().request('/graphql/', {})
    assert error.value.code == 'rate_limited'
    assert len(calls) == 3


def test_private_response_not_cached_after_logout(tmp_path, monkeypatch):
    from leetcode_vim.config import Config
    service = Service(Config(tmp_path, 'python'))
    monkeypatch.setattr(service, 'auth', lambda: None)
    def fetch():
        service._epoch += 1
        return 'private'
    with pytest.raises(ProviderError) as error:
        service.cached_read('profile', {}, fetch)
    assert error.value.code == 'auth_changed'
    assert service.store().cached('profile', '{}') is None


def test_remote_operation_persisted_before_poll_and_resumable(tmp_path, monkeypatch):
    from leetcode_vim.config import Config
    service = Service(Config(tmp_path, 'python'))
    path = tmp_path / 'solution.py'
    path.write_text('code')
    monkeypatch.setattr(service, 'account', lambda: 'alice')
    monkeypatch.setattr(service, 'open', lambda params: {'path': str(path), 'slug': 'two-sum', 'language': 'python',
        'problem': {'question_id': '1', 'examples': [{'args': [[1, 2], 3]}]}})
    class Remote:
        def execute(self, *args, **kwargs): return '123'
        def verdict(self, remote_id):
            assert service.store().operations('alice')[0]['remote_id'] == remote_id
            raise ProviderError('offline', 'offline')
    monkeypatch.setattr(service, 'provider', lambda *args: Remote())
    with pytest.raises(ProviderError, match='offline'):
        service.dispatch('submit', {'slug': 'two-sum', 'confirmed': True})
    assert service.store().operations('alice')[0]['payload']['state'] == 'PENDING'
    Remote.verdict = lambda self, remote_id: {'state': 'SUCCESS', 'status_msg': 'Accepted'}
    assert service.dispatch('poll', {'remote_id': '123'})['data']['status_msg'] == 'Accepted'
    assert service.store().get_progress('two-sum')['status'] == 'submitted'
    monkeypatch.setattr(service, 'account', lambda: 'bob')
    with pytest.raises(ProviderError, match='not recorded'):
        service.dispatch('poll', {'remote_id': '123'})


def test_protocol_cancellation_and_redacted_internal_errors():
    incoming, outgoing = queue.Queue(), queue.Queue()
    class Input:
        def __iter__(self):
            while True:
                value = incoming.get()
                if value is None:
                    return
                yield value
    class Output:
        def write(self, value): outgoing.put(json.loads(value))
        def flush(self): pass
    class Backend:
        def dispatch(self, method, params, cancel, emit):
            if method == 'slow':
                cancel.wait(3)
                return {'stopped': cancel.is_set()}
            raise RuntimeError('private-token')
    worker = threading.Thread(target=serve, args=(Input(), Output(), Backend()), daemon=True)
    worker.start()
    try:
        incoming.put(json.dumps({'v': 1, 'id': 'a', 'method': 'slow'}) + '\n')
        assert outgoing.get(timeout=3)['event'] == 'started'
        incoming.put(json.dumps({'v': 1, 'id': 'b', 'method': 'cancel', 'params': {'id': 'a'}}) + '\n')
        values = [outgoing.get(timeout=3), outgoing.get(timeout=3)]
        assert any(v.get('error', {}).get('code') == 'cancelled' for v in values)
        assert any(v.get('result', {}).get('cancelled') for v in values)
        incoming.put(json.dumps({'v': 1, 'id': 'c', 'method': 'bad'}) + '\n')
        assert outgoing.get(timeout=3)['event'] == 'started'
        result = outgoing.get(timeout=3)
        assert result['error']['code'] == 'internal_error'
        assert 'private-token' not in json.dumps(result)
    finally:
        incoming.put(None)
        worker.join(5)
    assert not worker.is_alive()


def test_restore_confirms_and_backs_up_draft(tmp_path, monkeypatch):
    from leetcode_vim.config import Config
    from leetcode_vim.leetcode_api import LeetCodeSession
    service = Service(Config(tmp_path, 'python'))
    monkeypatch.setattr(service, 'account', lambda: 'alice')
    monkeypatch.setattr(service, 'auth', lambda: LeetCodeSession('test-session', 'test-csrf'))
    class Remote:
        def submission(self, remote_id):
            return {'code': 'restored source', 'lang': {'name': 'Python3'}, 'question': {'titleSlug': 'two-sum'}}
    monkeypatch.setattr(service, 'provider', lambda *args: Remote())
    path = tmp_path / 'two-sum' / 'solution.py'
    path.parent.mkdir()
    path.write_text('my current draft')
    with pytest.raises(ProviderError, match='Confirm'):
        service.dispatch('restore', {'remote_id': '123'})
    assert path.read_text() == 'my current draft'
    restored = service.dispatch('restore', {'remote_id': '123', 'slug': 'two-sum', 'confirmed': True})
    assert path.read_text() == 'restored source'
    assert __import__('pathlib').Path(restored['backup']).read_text() == 'my current draft'
    with pytest.raises(ProviderError, match='different problem'):
        service.dispatch('restore', {'remote_id': '123', 'slug': 'add', 'confirmed': True})
