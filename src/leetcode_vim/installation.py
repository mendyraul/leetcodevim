from __future__ import annotations

import os
import sys
from pathlib import Path


def runtime_path():
    source = Path(__file__).resolve().parents[2]
    if (source / 'plugin' / 'leetcodevim.vim').exists():
        return source
    installed = Path(sys.prefix) / 'share' / 'leetcodevim'
    if not (installed / 'plugin' / 'leetcodevim.vim').exists():
        raise ValueError('Editor runtime files missing. Reinstall the package.')
    return installed


def command(args):
    runtime = runtime_path()
    if args.command == 'plugin-path':
        print(runtime)
        return 0
    if args.path:
        targets = [Path(args.path).expanduser()]
    else:
        targets = []
        if args.editor in ('vim', 'both'):
            targets.append(Path.home() / '.vim/pack/local/start/leetcodevim')
        if args.editor in ('nvim', 'both'):
            targets.append(Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) /
                           'nvim/pack/local/start/leetcodevim')
    for target in targets:
        if target.exists() or target.is_symlink():
            if target.resolve() == runtime:
                print('Already installed: ' + str(target))
                continue
            raise ValueError('An installation already exists at ' + str(target) + '. It was left untouched.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(runtime, target_is_directory=True)
        print('Installed: ' + str(target))
    return 0
