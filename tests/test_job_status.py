"""A running preparation job must stop looking queued, including on failure."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import fcntl
import json
import socket
import sqlite3


class JobStatus(unittest.TestCase):
    def test_failed_second_start_never_resets_running_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = dict(os.environ, DATA_DIR=temp, APP_TOKEN='isolated-test-token', HOST='127.0.0.1')
            with sqlite3.connect(root/'journal.sqlite3') as db:
                db.execute('create table sessions (id text primary key, document text not null)')
                db.execute('insert into sessions values (?,?)', ('running', json.dumps(dict(busy=True,status='正在处理',error=''))))
            with socket.socket() as occupied:
                occupied.bind(('127.0.0.1',0)); occupied.listen()
                env['PORT'] = str(occupied.getsockname()[1])
                result = subprocess.run([sys.executable,'-m','server.main'], env=env, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
            with (root/'.server.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                result = subprocess.run([sys.executable,'-m','server.main'], env=env, capture_output=True, text=True, timeout=10)
                self.assertIn('already running',result.stderr)
            with sqlite3.connect(root/'journal.sqlite3') as db:
                document = json.loads(db.execute('select document from sessions').fetchone()[0])
            self.assertTrue(document['busy'])
            self.assertEqual(document['status'], '正在处理')

    def test_preparation_reports_running_and_finishes_or_fails(self):
        # Import the server in a separate process, with isolated DB and media.
        code = '''
from unittest.mock import patch
from server import main as app
ident = '11111111-1111-4111-8111-111111111111'
folder = app.DATA/ident
folder.mkdir()
doc = dict(id=ident, busy=True, status='任务已排队', error='', turns=1)
app.save(doc)
def normalize(source, target, turns):
    running = app.get(ident)
    assert running['busy'] and running['status'] == '正在调整画面并生成预览…'
    target.write_bytes(b'new preview')
with patch.object(app.media, 'normalize', normalize):
    app.job(ident, 'prepare')
result = app.get(ident)
assert not result['busy'] and result['status'] == '可以核对出手' and not result['error']
assert (folder/'preview.mp4').read_bytes() == b'new preview'
app.update(ident, busy=True, status='任务已排队')
with patch.object(app.media, 'normalize', side_effect=ValueError('test failure')):
    app.job(ident, 'prepare')
result = app.get(ident)
assert not result['busy'] and result['status'] == '处理失败，可重试'
assert result['error'] == 'test failure'
assert (folder/'preview.mp4').read_bytes() == b'new preview'
'''
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, DATA_DIR=str(Path(temp)/'data'), APP_TOKEN='isolated-test-token')
            result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
