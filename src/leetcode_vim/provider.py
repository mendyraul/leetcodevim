"""LeetCode transport and read capabilities. Writes are never retried."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .leetcode_api import LeetCodeError, _build_headers

ROOT = 'https://leetcode.com'


class ProviderError(LeetCodeError):
    def __init__(self, message, code='remote_error'):
        super().__init__(message)
        self.code = code


class Provider:
    def __init__(self, auth=None):
        self.auth = auth

    def request(self, path, body=None, read=True):
        for attempt in range(3 if read else 1):
            request = urllib.request.Request(ROOT + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers=_build_headers(self.auth))
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    raw = response.read(8 * 1024 * 1024)
                data = json.loads(raw)
                if not isinstance(data, (dict, list)):
                    raise ValueError('Expected an object or list')
                return data
            except urllib.error.HTTPError as exc:
                if not read and exc.code >= 500:
                    raise ProviderError('LeetCode may have received this action. Check the website before retrying.',
                                        'uncertain_write') from None
                if exc.code in (429, 502, 503, 504) and read and attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                code = {401: 'auth_required', 403: 'access_restricted', 429: 'rate_limited'}.get(exc.code, 'remote_error')
                raise ProviderError(f'LeetCode returned HTTP {exc.code}.', code) from None
            except urllib.error.URLError:
                if not read:
                    raise ProviderError('The connection ended without an acknowledgement. '
                                        'Check LeetCode before retrying this action.', 'uncertain_write') from None
                if read and attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise ProviderError('Cannot reach LeetCode. Check your connection or use cached content.', 'offline') from None
            except (ValueError, TypeError):
                raise ProviderError('LeetCode returned an unexpected response.', 'invalid_response') from None

    def query(self, query, variables=None):
        response = self.request('/graphql/', {'query': query, 'variables': variables or {}})
        if response.get('errors'):
            raise ProviderError('This LeetCode query is unavailable for this session.', 'unsupported')
        if not isinstance(response.get('data'), dict):
            raise ProviderError('LeetCode returned no data.', 'invalid_response')
        return response['data']

    def identity(self):
        value = self.query('query { userStatus { username isSignedIn } }').get('userStatus') or {}
        if not value.get('isSignedIn') or not value.get('username'):
            raise ProviderError('Sign in to LeetCode to use this feature.', 'auth_required')
        return value['username']

    def browse(self, search='', difficulty='', topic='', status='', offset=0, limit=50):
        filters = {}
        for key, value in [('searchKeywords', search), ('difficulty', difficulty.upper()),
                           ('tags', [topic] if topic else []), ('status', status.upper())]:
            if value:
                filters[key] = value
        data = self.query('''query($skip:Int,$limit:Int,$filters:QuestionListFilterInput) {
          problemsetQuestionList: questionList(categorySlug:"",skip:$skip,limit:$limit,filters:$filters) {
            total: totalNum questions: data { questionFrontendId title titleSlug difficulty isPaidOnly status
              topicTags { name slug } } } }''', {'skip': offset, 'limit': limit, 'filters': filters})
        return data['problemsetQuestionList']

    def daily(self):
        return self.query('''query { activeDailyCodingChallengeQuestion {
          date link question { title titleSlug difficulty } } }''')['activeDailyCodingChallengeQuestion']

    def profile(self, username):
        return self.query('''query($username:String!) { matchedUser(username:$username) {
          username profile { ranking reputation realName userAvatar }
          submitStatsGlobal { acSubmissionNum { difficulty count submissions } }
          submissionCalendar } }''', {'username': username})['matchedUser']

    def submissions(self, slug, offset=0):
        return self.query('''query($slug:String!,$offset:Int!) {
          submissionList(questionSlug:$slug,offset:$offset,limit:20) {
            hasNext submissions { id title titleSlug statusDisplay lang runtime timestamp url } } }''',
                          {'slug': slug, 'offset': offset})['submissionList']

    def editorial(self, slug):
        return self.query('''query($slug:String!) { question(titleSlug:$slug) {
          solution { id title content paidOnly } } }''', {'slug': slug})['question']['solution']

    def submission(self, remote_id):
        if not str(remote_id).isdigit():
            raise ProviderError('Invalid submission ID.', 'invalid_request')
        return self.query('''query($id:Int!) { submissionDetails(submissionId:$id) {
          code lang { name } question { titleSlug } } }''', {'id': int(remote_id)})['submissionDetails']

    def contests(self):
        return self.query('query { topTwoContests { title titleSlug startTime duration } }')['topTwoContests']

    def execute(self, slug, question_id, code, language, cases=None, submit=False):
        if not self.auth or not self.auth.csrf:
            raise ProviderError('A verified session and CSRF cookie are required.', 'auth_required')
        body = {'lang': 'python3' if language == 'python' else 'cpp', 'question_id': question_id, 'typed_code': code}
        if not submit:
            body['data_input'] = cases or ''
        action = 'submit' if submit else 'interpret_solution'
        result = self.request(f'/problems/{slug}/{action}/', body, read=False)
        remote_id = result.get('submission_id' if submit else 'interpret_id')
        if remote_id is None:
            raise ProviderError('LeetCode did not acknowledge this operation. Check the website before retrying.',
                                'uncertain_write')
        return str(remote_id)

    def verdict(self, remote_id):
        if not str(remote_id).isdigit():
            raise ProviderError('Invalid operation ID.', 'invalid_request')
        return self.request(f'/submissions/detail/{remote_id}/check/')
