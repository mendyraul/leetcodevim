"""Verify the built wheel, bundled harness, runtime, and plugin installer offline."""
import json
import os
import subprocess
import tempfile
import venv
from pathlib import Path

wheel = max(Path('dist').glob('*.whl'), key=lambda p: p.stat().st_mtime).resolve()
with tempfile.TemporaryDirectory(prefix='leetcodevim-wheel-') as directory:
    root = Path(directory)
    env = dict(os.environ, XDG_CONFIG_HOME=str(root / 'config'))
    venv.create(root / 'venv', with_pip=True)
    python = root / 'venv/bin/python'
    cli = root / 'venv/bin/leetcodevim'
    subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', str(wheel)], check=True, env=env)
    subprocess.run([str(cli), '--help'], check=True, stdout=subprocess.DEVNULL, env=env)
    subprocess.run([str(cli), 'init', '--workspace', str(root / 'workspace')], check=True, env=env)
    runtime = Path(subprocess.check_output([str(cli), 'plugin-path'], text=True, env=env).strip())
    for filename in ['plugin/leetcodevim.vim', 'autoload/leetcodevim.vim', 'lua/leetcodevim/transport.lua',
                     'doc/leetcodevim.txt', 'syntax/leetcodevim.vim']:
        assert (runtime / filename).is_file(), filename
    subprocess.run([str(cli), 'install-plugin', '--path', str(root / 'plugin')], check=True, env=env)
    report = json.loads(subprocess.check_output([str(cli), 'doctor', '--format', 'json'], text=True, env=env))
    assert report['workspace'] == str(root / 'workspace')
    subprocess.run([str(python), '-c', '''
from pathlib import Path
import leetcode_vim.execution as execution
assert (Path(execution.__file__).parent / 'vendor/json.hpp').is_file()
assert (Path(execution.__file__).parent / 'cpp_harness.hpp').is_file()
'''], check=True, env=env)
print('Installed wheel, editor runtime, installer, diagnostics, and bundled C++ files passed.')
