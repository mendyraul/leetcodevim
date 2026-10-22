"""Deterministic editor test peer: replies to older navigation last."""
import json
import os
import sys
import threading
import time
from pathlib import Path

lock = threading.Lock()
threads = []


def reply(request):
    slug = request['params']['slug']
    time.sleep(0.3 if slug == 'first' else 0.02)
    path = Path(os.environ['LEETCODEVIM_TEST_ROOT']) / (slug + '.py')
    path.write_text('# ' + slug + '\n')
    response = {'v': 1, 'id': request['id'], 'result': {
        'slug': slug, 'language': 'python', 'path': str(path), 'description': slug,
        'problem': {'title': slug, 'difficulty': 'Easy'}, 'hints': [],
        'url': 'https://leetcode.com/problems/' + slug + '/'}}
    with lock:
        print(json.dumps(response), flush=True)


for line in sys.stdin:
    request = json.loads(line)
    if request['method'] != 'open':
        continue
    thread = threading.Thread(target=reply, args=(request,))
    thread.start()
    threads.append(thread)
for thread in threads:
    thread.join()
