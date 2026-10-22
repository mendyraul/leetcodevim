"""Application services consumed by both the CLI and editor protocol."""
from __future__ import annotations

import json
import os
import platform
import random
import re
import shutil
import sys
import threading
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote

from .auth import AuthImportError, clear_auth, import_from_browser, load_auth, save_auth
from .companion_store import CompanionStore
from .config import load_config
from .execution import run_cases
from .leetcode_api import LeetCodeSession, fetch_problem
from .problem_model import build_problem_record, render_content
from .provider import Provider, ProviderError, ROOT
from .state import update_problem_state
from .storage import utc_now

FALLBACKS = {
    'study': ('Study plans', '/studyplan/'),
    'discuss': ('Discussions and public posts', '/discuss/'),
    'favorites': ('Favorites and list management', '/problemset/'),
    'contests': ('Contests, registration and standings', '/contest/'),
    'settings': ('Account and billing settings', '/profile/account/'),
}


class Service:
    def __init__(self, config=None):
        self.config = config
        self._identity = None
        self._token = None
        self._session_auth = None
        self._logged_out = False
        self._epoch = 0
        self._inflight = set()
        self._lock = threading.RLock()

    def configuration(self):
        config = self.config or load_config()
        if not config:
            raise ProviderError('Initialize first: leetcodevim init --workspace ~/leetcode --language python', 'config_required')
        return config

    def store(self):
        return CompanionStore(self.configuration().workspace)

    def auth(self):
        if self._logged_out:
            return None
        if self._session_auth:
            return self._session_auth
        config = self.configuration()
        saved = load_auth(config)
        session = os.environ.get('LEETCODE_SESSION') or saved.session
        csrf = os.environ.get('LEETCODE_CSRF') if os.environ.get('LEETCODE_SESSION') else saved.csrf
        if session:
            return LeetCodeSession(session, csrf)
        return None

    def provider(self, private=False):
        auth = self.auth()
        if private and not auth:
            raise ProviderError('Sign in first with :LeetCodeLogin or leetcodevim auth login.', 'auth_required')
        return Provider(auth)

    def account(self):
        auth = self.auth()
        if not auth:
            return ''
        if self._token != auth.session or not self._identity:
            self._identity = Provider(auth).identity()
            self._token = auth.session
        return self._identity

    @staticmethod
    def slug(value):
        if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value):
            raise ProviderError('Use a LeetCode problem slug, such as two-sum.', 'invalid_request')
        return value

    def cached_read(self, kind, params, fetch, private=False, refresh=False):
        epoch = self._epoch
        account = self.account() if self.auth() else ''
        if private and not account:
            raise ProviderError('Sign in to access this feature.', 'auth_required')
        key = json.dumps(params, sort_keys=True)
        stored = self.store().cached(kind, key, account)
        if stored and not refresh:
            return dict(stored, cached=True, stale=True)
        try:
            value = fetch()
            if epoch != self._epoch:
                raise ProviderError('Account changed during this request. Try again.', 'auth_changed')
            self.store().cache(kind, key, value, account)
            return {'data': value, 'cached': False, 'stale': False, 'updated_at': utc_now()}
        except Exception as exc:
            if isinstance(exc, ProviderError) and exc.code == 'auth_changed':
                raise
            if stored:
                return dict(stored, cached=True, stale=True, warning='Refresh failed; showing cached content.')
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError('LeetCode content is currently unavailable.', 'remote_error') from None

    def dispatch(self, method, params=None, cancel=None, emit=None):
        params = params or {}
        epoch = self._epoch
        cancel = cancel or threading.Event()
        emit = emit or (lambda value: None)
        if method == 'hello':
            return {'protocol': 1, 'languages': ['python', 'cpp'], 'capabilities': self.capabilities()}
        if method == 'doctor':
            return {'python': platform.python_version(), 'python_executable': sys.executable,
                    'cpp_compiler': shutil.which('clang++') or shutil.which('g++'),
                    'workspace': str(self.configuration().workspace), 'capabilities': self.capabilities()}
        if method == 'auth.status':
            return {'signed_in': bool(self.auth()), 'username': self.account() if self.auth() else None}
        if method == 'auth.login':
            return {'url': ROOT + '/accounts/login/', 'message':
                    'Sign in in your browser, then choose Import browser or enter cookies with hidden input.'}
        if method == 'auth.import':
            with self._lock:
                result = import_from_browser(params.get('browser', 'chrome'), 'leetcode.com')
                auth = LeetCodeSession(result.session, result.csrf)
                username = Provider(auth).identity()
                self._session_auth = auth
                self._logged_out = False
                self._epoch += 1
                try:
                    save_auth(self.configuration(), auth.session, auth.csrf)
                    storage = 'keychain'
                except AuthImportError:
                    storage = 'session only'
                self._identity, self._token = username, auth.session
            return {'signed_in': True, 'username': username, 'storage': storage}
        if method == 'auth.set':
            with self._lock:
                auth = LeetCodeSession(params.get('session', ''), params.get('csrf'))
                if not auth.session or not auth.csrf:
                    raise ProviderError('Both session and CSRF cookies are required.', 'invalid_request')
                username = Provider(auth).identity()
                self._session_auth = auth
                self._logged_out = False
                self._epoch += 1
                try:
                    save_auth(self.configuration(), auth.session, auth.csrf)
                    storage = 'keychain'
                except AuthImportError:
                    storage = 'session only'
                self._identity, self._token = username, auth.session
            return {'signed_in': True, 'username': username, 'storage': storage}
        if method == 'auth.logout':
            with self._lock:
                clear_auth(self.configuration())
                self.store().clear_private()
                self._session_auth = self._identity = self._token = None
                self._logged_out = True
                self._epoch += 1
            return {'signed_in': False, 'message': 'Stored credentials and private caches cleared. '
                                                  'Environment tokens remain external.'}
        if method == 'contests':
            try:
                result = self.cached_read('contests', {}, self.provider().contests, refresh=params.get('refresh', False))
                result['entries'] = [{'title': c['title'], 'url': ROOT + '/contest/' + c['titleSlug'] + '/'}
                                     for c in result['data']]
                result['message'] = 'Upcoming contests. Registration, contest participation and standings open in your browser.'
                return result
            except ProviderError:
                pass
        if method == 'favorites':
            return {'data': [dict(item, status='favorite') for item in self.store().favorites()], 'mode': 'browser',
                    'url': ROOT + '/problemset/',
                    'message': 'Local favorites are shown in the browser pane. Press o for website lists; these are not synced.'}
        if method in FALLBACKS:
            title, path = FALLBACKS[method]
            slug = params.get('slug')
            if method == 'discuss' and slug:
                path = '/problems/' + self.slug(slug) + '/description/'
            return {'title': title, 'mode': 'browser', 'url': ROOT + path,
                    'message': 'Native access is not verified. Open this feature in your browser.'}
        if method == 'browse':
            args = {k: params.get(k, '') for k in ('search', 'difficulty', 'topic', 'status')}
            args['offset'] = max(0, int(params.get('offset', 0)))
            args['limit'] = min(100, max(1, int(params.get('limit', 50))))
            return self.cached_read('catalog', args, lambda: self.provider().browse(**args), refresh=params.get('refresh', False))
        if method in ('daily', 'random'):
            if method == 'daily':
                return self.cached_read('daily', {'date': utc_now()[:10]}, self.provider().daily,
                                        refresh=params.get('refresh', False))
            total = self.provider().browse(limit=1)['total']
            if not total:
                raise ProviderError('No matching problems found.', 'not_found')
            return {'data': self.provider().browse(offset=random.randrange(total), limit=1)['questions'][0]}
        if method == 'local':
            store = self.store()
            return {'data': store.list_progress()}
        if method == 'profile':
            username = params.get('username') or self.account()
            if not username:
                raise ProviderError('Sign in or provide a username.', 'auth_required')
            result = self.cached_read('profile', {'username': username}, lambda: self.provider().profile(username),
                                      refresh=params.get('refresh', False))
            profile = result['data']
            if not profile:
                raise ProviderError('Profile not found.', 'not_found')
            result['lines'] = [profile['username'], 'Ranking: ' + str(profile['profile'].get('ranking', '')),
                               'Reputation: ' + str(profile['profile'].get('reputation', '')), '', 'Accepted problems:']
            for row in profile.get('submitStatsGlobal', {}).get('acSubmissionNum', []):
                result['lines'].append(f"  {row['difficulty']}: {row['count']}")
            result['url'] = ROOT + '/u/' + quote(username) + '/'
            return result
        if method in ('status', 'recent'):
            from .state import load_state
            data = [asdict(p) for p in load_state(self.configuration()).problems.values()]
            if params.get('slug'):
                data = [p for p in data if p['slug'] == self.slug(params['slug'])]
            return {'data': sorted(data, key=lambda p: p['updated_at'], reverse=True)}
        if method == 'mark':
            slug = self.slug(params['slug'])
            return {'data': asdict(update_problem_state(self.configuration(), slug, status=params.get('status'),
                                                        notes=params.get('notes'), tags=params.get('tags')))}
        if method in ('notes', 'compose'):
            slug = self.slug(params['slug'])
            directory = self.configuration().workspace / slug
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / ('discussion-draft.md' if method == 'compose' else 'notes.md')
            if not path.exists():
                path.write_text('# ' + ('Discussion draft' if method == 'compose' else 'Notes') + '\n\n')
            return {'path': str(path), 'language': 'markdown', 'url': ROOT + '/problems/' + slug + '/description/',
                    'message': 'Draft saved locally. Public posting is completed in your browser.' if method == 'compose' else ''}
        if method == 'open':
            return self.open(params)
        if method == 'cases':
            opened = self.open(params)
            path = Path(opened['path']).with_name('cases.json')
            if not path.exists():
                path.write_text(json.dumps(opened['problem']['examples'], indent=2) + '\n')
            return {'path': str(path), 'language': 'json'}
        if method == 'favorite':
            slug = self.slug(params['slug'])
            self.store().cache('local_favorite', slug, {'slug': slug, 'favorite': bool(params.get('favorite', True))})
            return {'message': 'Local favorite saved. Website lists are managed in your browser.', 'url': ROOT + '/problemset/'}
        if method == 'editorial':
            slug = self.slug(params['slug'])
            account = self.account()
            if not account:
                raise ProviderError('Sign in to check editorial access.', 'auth_required')
            try:
                result = self.cached_read('editorial', {'slug': slug}, lambda: self.provider(True).editorial(slug),
                                          private=True, refresh=params.get('refresh', False))
                if result['data'] and result['data'].get('content'):
                    result['text'] = render_content(result['data']['content'])
                    return result
            except ProviderError:
                pass
            return {'mode': 'browser', 'url': ROOT + '/problems/' + slug + '/editorial/',
                    'message': 'Editorial unavailable through this session; open the website.'}
        if method == 'submissions':
            slug = self.slug(params['slug'])
            account = self.account()
            if not account:
                raise ProviderError('Sign in to read your submissions.', 'auth_required')
            local = self.store().operations(account, slug)
            try:
                result = self.cached_read('submissions', {'slug': slug, 'offset': int(params.get('offset', 0))},
                    lambda: self.provider(True).submissions(slug, int(params.get('offset', 0))),
                    private=True, refresh=params.get('refresh', False))
                result['operations'] = local
                result['lines'] = [f"{s['id']}  {s['statusDisplay']}  {s['lang']}  {s.get('runtime', '')}"
                                   for s in (result['data'] or {}).get('submissions', [])]
                result['lines'] += [f"Recorded {op['kind']} ID {op['remote_id']}: "
                                    + str(op['payload'].get('status_msg', op['payload'].get('state', 'unknown'))) for op in local]
                result['lines'].append('Use :LeetCodePoll ID to resume or :LeetCodeRestore ID to restore submitted code.')
                return result
            except ProviderError:
                return {'data': {'submissions': []}, 'operations': local, 'mode': 'browser',
                        'url': ROOT + '/problems/' + slug + '/submissions/',
                        'message': 'Remote history unavailable; locally recorded operations are shown.'}
        if method in ('submission', 'restore'):
            remote_id = str(params['remote_id'])
            if not remote_id.isdigit():
                raise ProviderError('Invalid submission ID.', 'invalid_request')
            if method == 'restore' and not params.get('confirmed'):
                raise ProviderError('Confirm restoring this draft before proceeding.', 'confirmation_required')
            account = self.account()
            if not account:
                raise ProviderError('Sign in to read submitted code.', 'auth_required')
            try:
                result = self.cached_read('submission', {'id': remote_id},
                    lambda: self.provider(True).submission(remote_id), private=True)
            except ProviderError:
                if method == 'restore':
                    raise ProviderError('Submitted code unavailable. Open the submission on LeetCode.', 'unsupported') from None
                return {'mode': 'browser', 'url': ROOT + '/submissions/detail/' + remote_id + '/',
                        'message': 'Submission details unavailable through this session.'}
            details = result['data']
            if not details or not details.get('code'):
                raise ProviderError('No source is available for this submission.', 'not_found')
            slug = self.slug(details['question']['titleSlug'])
            if method == 'submission':
                result['text'] = details['code']
                return result
            if params.get('slug') and params['slug'] != slug:
                raise ProviderError('That submission belongs to a different problem.', 'invalid_request')
            language_name = details.get('lang', {}).get('name', '').lower()
            language = 'python' if 'python' in language_name else 'cpp' if language_name in ('cpp', 'c++') else None
            if not language:
                raise ProviderError('This submission language is not supported.', 'unsupported')
            import uuid
            with self._lock:
                if epoch != self._epoch or cancel.is_set():
                    raise ProviderError('Restore cancelled because the request or account changed.', 'cancelled')
                extension = 'py' if language == 'python' else 'cpp'
                directory = self.configuration().workspace / slug
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / ('solution.' + extension)
                backup = None
                if path.exists():
                    backup = directory / ('.solution-before-restore-' + uuid.uuid4().hex + '.' + extension)
                    backup.write_bytes(path.read_bytes())
                temporary = directory / ('.restoring-' + uuid.uuid4().hex + '.' + extension)
                temporary.write_text(details['code'])
                temporary.replace(path)
                return {'path': str(path), 'backup': str(backup) if backup else None, 'language': language, 'slug': slug,
                        'message': 'Submitted source restored. Previous draft backed up; unsaved editor buffers are retained.'}
        if method == 'test':
            opened = self.open(params)
            problem = opened['problem']
            cases = problem['examples']
            custom = Path(opened['path']).with_name('cases.json')
            if custom.exists():
                cases = json.loads(custom.read_text())
            if not isinstance(cases, list) or not all(isinstance(c, dict) and isinstance(c.get('args'), list)
                                                     and 'expected' in c for c in cases):
                raise ProviderError('cases.json must be an array of {args: [...], expected: ...} objects.', 'invalid_cases')
            rules = {'two-sum': 'unordered', 'three-sum': 'unordered_nested', 'four-sum': 'unordered_nested',
                     'group-anagrams': 'unordered_nested', 'subsets': 'unordered', 'permutations': 'unordered'}
            metadata = problem.get('metadata', {})
            if metadata.get('manual') and not metadata.get('systemdesign') and opened['slug'] not in rules:
                raise ProviderError('This problem uses a custom judge. Use remote run or submit.', 'unsupported_checker')
            cases = [dict(c, comparison=c.get('comparison', rules.get(opened['slug'], 'exact')),
                          in_place=c.get('in_place', metadata.get('return', {}).get('type') == 'void')) for c in cases]
            results = run_cases(opened['path'], opened['language'], problem['method_name'], cases,
                                problem.get('metadata'), timeout=float(params.get('timeout', 5)), cancel=cancel)
            passed = all(case['passed'] for case in results)
            if passed:
                update_problem_state(self.configuration(), opened['slug'], status='tested')
            return {'passed': passed, 'results': results, 'message': 'Examples only; official acceptance requires submission.'}
        if method in ('run', 'submit'):
            key = (self.account(), params.get('slug'), method)
            with self._lock:
                if key in self._inflight:
                    raise ProviderError('This operation is already in progress.', 'operation_pending')
                pending = [op for op in self.store().operations(key[0], key[1]) if op['kind'] == method
                           and op['payload'].get('state') != 'SUCCESS']
                if pending:
                    raise ProviderError('An operation is still pending. Resume remote ID ' + pending[0]['remote_id']
                                        + ' before sending another.', 'operation_pending')
                self._inflight.add(key)
            try:
                return self.remote(method, params, cancel, emit)
            finally:
                with self._lock:
                    self._inflight.discard(key)
        if method == 'poll':
            account = self.account()
            operation = next((op for op in self.store().operations(account) if op['remote_id'] == str(params['remote_id'])), None)
            if not operation:
                raise ProviderError('Operation not recorded for this account.', 'not_found')
            return self.poll(operation['remote_id'], account, operation['slug'], operation['kind'], cancel, emit)
        raise ProviderError(f'Unknown operation: {method}', 'invalid_request')

    def remote(self, method, params, cancel, emit):
        if method == 'submit' and not params.get('confirmed'):
            raise ProviderError('Confirm submission before sending it.', 'confirmation_required')
        opened = self.open(params)
        account = self.account()
        if not account:
            raise ProviderError('Sign in before remote execution.', 'auth_required')
        code = Path(opened['path']).read_text()
        cases = params.get('input')
        if cases is None:
            custom = Path(opened['path']).with_name('cases.json')
            examples = json.loads(custom.read_text()) if custom.exists() else opened['problem']['examples']
            cases = '\n'.join(json.dumps(arg) for case in examples for arg in case['args'])
        provider = self.provider(True)
        if cancel.is_set():
            raise ProviderError('Cancelled before sending.', 'cancelled')
        remote_id = provider.execute(opened['slug'], opened['problem']['question_id'], code,
                                     opened['language'], cases, submit=method == 'submit')
        self.store().operation(account, remote_id, opened['slug'], method,
                               {'state': 'PENDING', 'language': opened['language']})
        emit({'event': 'operation', 'remote_id': remote_id, 'kind': method,
              'message': 'Sent to LeetCode. Cancelling stops polling, not the remote operation.'})
        return self.poll(remote_id, account, opened['slug'], method, cancel, emit)

    def poll(self, remote_id, account, slug, kind, cancel, emit):
        epoch = self._epoch
        for _ in range(60):
            if epoch != self._epoch or self.account() != account:
                raise ProviderError('Account changed while polling. Sign in again to resume.', 'auth_changed')
            if cancel.is_set():
                return {'remote_id': remote_id, 'state': 'PENDING', 'message': 'Polling cancelled. Resume with poll.'}
            verdict = self.provider(True).verdict(remote_id)
            if epoch != self._epoch:
                raise ProviderError('Account changed while polling.', 'auth_changed')
            self.store().operation(account, remote_id, slug, kind, verdict)
            if verdict.get('state') == 'SUCCESS':
                if kind == 'submit' and verdict.get('status_msg') == 'Accepted':
                    update_problem_state(self.configuration(), slug, status='submitted')
                return {'remote_id': remote_id, 'data': verdict}
            emit({'event': 'progress', 'remote_id': remote_id, 'state': verdict.get('state', 'PENDING')})
            cancel.wait(1)
        return {'remote_id': remote_id, 'state': 'PENDING', 'message': 'Still pending. Resume polling; do not resubmit.'}

    def open(self, params):
        slug = self.slug(params['slug'])
        language = params.get('language') or self.configuration().language
        if language not in ('python', 'cpp'):
            raise ProviderError('Supported languages: python, cpp.', 'invalid_request')
        store = self.store()
        draft = store.draft(slug, language)
        epoch = self._epoch
        account = self.account() if self.auth() and (not draft or draft.get('account')) else ''
        if draft and draft.get('account', '') not in ('', account):
            draft = None
        if not draft and not params.get('refresh'):
            legacy = store.get_problem(slug)
            if legacy and legacy.language == language and legacy.method_name:
                draft = store.save_draft(legacy)
        if not draft or params.get('refresh'):
            try:
                problem = fetch_problem(slug, self.auth())
                if not problem.content:
                    raise ProviderError('Problem content unavailable for this account. Open ' + ROOT + '/problems/' + slug + '/',
                                        'access_restricted' if problem.paid_only else 'not_found')
                if epoch != self._epoch:
                    raise ProviderError('Account changed during this request. Try again.', 'auth_changed')
                # Metadata describes Python signatures even for C++; reuse it to parse examples.
                native = build_problem_record(problem, slug, 'python')
                if language == 'cpp':
                    snippet = next((s.get('code') for s in problem.code_snippets if s.get('langSlug') == 'cpp'), None)
                    if not snippet:
                        raise ProviderError('No C++ template available for this problem.', 'unsupported')
                    record = asdict(native)
                    record.update(language='cpp', code=snippet)
                    from .storage import ProblemRecord
                    native = ProblemRecord(**record)
                draft = store.save_draft(native, problem.metadata, [render_content(hint) for hint in problem.hints])
                draft['account'] = account
                with store._connect() as db:
                    db.execute('UPDATE companion_drafts SET payload=? WHERE slug=? AND language=?',
                               (json.dumps(draft), slug, language))
            except Exception as exc:
                if isinstance(exc, ProviderError) and (exc.code == 'auth_changed' or not draft):
                    raise
                if not draft:
                    legacy = store.get_problem(slug)
                    if legacy and legacy.language == language:
                        draft = store.save_draft(legacy)
                    else:
                        raise ProviderError('Cannot load this problem. Connect to LeetCode and try again.', 'offline') from None
        problem_dir = self.configuration().workspace / slug
        problem_dir.mkdir(parents=True, exist_ok=True)
        path = problem_dir / ('solution.py' if language == 'python' else 'solution.cpp')
        if not path.exists():
            path.write_text(draft['code'])
        update_problem_state(self.configuration(), slug)
        return {'slug': slug, 'language': language, 'path': str(path.resolve()), 'problem': draft,
                'description': render_content(draft['content']), 'url': ROOT + '/problems/' + quote(slug) + '/',
                'hints': draft.get('hints', [])}

    @staticmethod
    def capabilities():
        return {
            'browse': 'native; public endpoint verified',
            'open': 'native', 'daily': 'native', 'random': 'native',
            'test_python': 'native', 'test_cpp': 'native methods and supported design classes',
            'run': 'native; authenticated live verification required',
            'submit': 'native; authenticated live verification required',
            'profile': 'native; public profile verified; own-account acceptance pending',
            'submissions': 'native with browser fallback', 'editorial': 'native with browser fallback',
            **{name: 'browser fallback; native access unverified' for name in FALLBACKS if name != 'contests'},
            'contests': 'native upcoming list; browser for participation and registration',
        }
