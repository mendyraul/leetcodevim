from __future__ import annotations

import getpass
import json
import sys
import webbrowser

from .auth import AuthImportError
from .provider import ProviderError
from .runner import RunnerError
from .service import Service


def command(args):
    if args.command == 'serve':
        from .protocol import serve
        return serve()
    service = Service()
    params = {k: v for k, v in vars(args).items() if k not in ('func', 'command', 'format', 'open_browser') and v is not None}
    method = {'show': 'open', 'submissions': 'submissions'}.get(args.command, args.command)
    try:
        result = service.dispatch(method, params)
        if getattr(args, 'open_browser', False) and result.get('url'):
            webbrowser.open(result['url'])
        if getattr(args, 'format', 'text') == 'json':
            print(json.dumps(result, indent=2))
        elif method == 'open':
            print(result['description'])
            print('\nSolution: ' + result['path'])
        else:
            print(json.dumps(result, indent=2))
        return 1 if result.get('passed') is False else 0
    except (ProviderError, RunnerError, AuthImportError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def login(args):
    service = Service()
    if args.browser:
        result = service.dispatch('auth.import', {'browser': args.browser})
    elif args.cookies:
        result = service.dispatch('auth.set', {'session': getpass.getpass('LEETCODE_SESSION: '),
                                               'csrf': getpass.getpass('csrftoken: ')})
    else:
        print('Sign in at https://leetcode.com/accounts/login/')
        print('Then run: leetcodevim auth login --browser chrome (or --cookies for hidden input).')
        if args.open_browser:
            webbrowser.open('https://leetcode.com/accounts/login/')
        return 0
    print('Signed in as ' + result['username'] + ' (' + result['storage'] + ').')
    if result['storage'] == 'session only':
        print('Keychain unavailable. Use :LeetCodeLogin for a session that lasts as long as the editor worker.')
    return 0


def extend(subparsers):
    from .installation import command as install
    for name in ('plugin-path', 'install-plugin'):
        parser = subparsers.add_parser(name, help='locate or install the editor runtime')
        parser.add_argument('--editor', choices=('vim', 'nvim', 'both'), default='vim')
        parser.add_argument('--path', help='explicit plugin destination')
        parser.set_defaults(func=install)
    parser = subparsers.add_parser('serve', help='editor protocol worker over stdio')
    parser.add_argument('--stdio', action='store_true', required=True)
    parser.set_defaults(func=command)
    for name in ('browse', 'show', 'daily', 'random', 'run', 'submissions', 'profile', 'favorites', 'favorite',
                 'study', 'discuss', 'contests', 'doctor', 'editorial', 'cases', 'notes', 'compose', 'poll',
                 'submission', 'restore', 'settings'):
        parser = subparsers.add_parser(name, help='companion ' + name)
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--refresh', action='store_true')
        parser.add_argument('--open-browser', action='store_true')
        if name in ('show', 'run', 'submissions', 'favorite', 'editorial', 'cases', 'notes', 'compose'):
            parser.add_argument('--slug', required=True)
        if name == 'discuss':
            parser.add_argument('--slug')
        if name in ('show', 'run', 'cases'):
            parser.add_argument('--language', choices=('python', 'cpp'))
        if name == 'browse':
            for field in ('search', 'difficulty', 'topic', 'status'):
                parser.add_argument('--' + field, default='')
            parser.add_argument('--offset', type=int, default=0)
            parser.add_argument('--limit', type=int, default=50)
        if name == 'profile':
            parser.add_argument('--username')
        if name == 'run':
            parser.add_argument('--input', help='raw LeetCode test-case input')
        if name == 'submissions':
            parser.add_argument('--offset', type=int, default=0)
        if name in ('poll', 'submission', 'restore'):
            parser.add_argument('--remote-id', required=True)
        if name == 'restore':
            parser.add_argument('--confirmed', action='store_true', help='confirm restoring source; existing draft is backed up')
            parser.add_argument('--slug')
        parser.set_defaults(func=command)
