"""Real upload → normalization → review → export → persistence integration."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request
import urllib.error


class APILifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); cls.port=sock.getsockname()[1]
        cls.env=dict(os.environ,DATA_DIR=str(cls.root/'data'),APP_TOKEN='integration-test-token-never-use-in-production',PORT=str(cls.port),HOST='127.0.0.1')
        cls.source=cls.root/'source.mp4'
        subprocess.run([os.environ.get('FFMPEG_PATH','ffmpeg'),'-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=320x180:rate=30','-t','5','-c:v','libx264','-pix_fmt','yuv420p',str(cls.source)],check=True)
        cls.start_server()

    @classmethod
    def start_server(cls):
        cls.process=subprocess.Popen([os.sys.executable,'-m','server.main'],env=cls.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                cls.call('/api/sessions'); return
            except Exception: time.sleep(.1)
        raise RuntimeError('Test API did not start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate(); cls.process.communicate(timeout=10); cls.temp.cleanup()

    @classmethod
    def call(cls,path,method='GET',payload=None,token=True,headers=None):
        req=urllib.request.Request(f'http://127.0.0.1:{cls.port}'+path,method=method,data=payload)
        if token: req.add_header('Authorization','Bearer '+cls.env['APP_TOKEN'])
        for key,value in (headers or {}).items(): req.add_header(key,value)
        with urllib.request.urlopen(req,timeout=30) as response:
            data=response.read()
            return json.loads(data) if 'application/json' in response.headers['Content-Type'] else data

    def wait_for_job(self,ident):
        for _ in range(300):
            item=self.call('/api/sessions/'+ident)
            if not item['busy']:
                self.assertFalse(item['error'],item['error']); return item
            time.sleep(.1)
        self.fail('Media job timed out')

    def test_full_lifecycle(self):
        with self.assertRaises(urllib.error.HTTPError) as error: self.call('/api/sessions',token=False)
        self.assertEqual(error.exception.code,401)
        item=self.call('/api/upload?title=Integration&date=2026-09-26','POST',self.source.read_bytes())
        ident=item['id']; base='/api/sessions/'+ident
        item=self.wait_for_job(ident)
        self.assertTrue(item['previewReady'])
        self.assertIsNone(item['stats']['percentage'])
        preview=self.call(base+'/preview')
        self.assertEqual(self.call(base+'/preview',headers={'Range':'bytes=0-31'}),preview[:32])
        self.assertEqual(self.call(base+'/preview',headers={'Range':'bytes=-20'}),preview[-20:])
        shots=[dict(id='a',start=.3,release=1,end=2,outcome='made',reviewed=True,note=''),dict(id='b',start=2,release=3,end=4,outcome='missed',reviewed=True,note='')]
        body=json.dumps(dict(revision=0,shots=shots)).encode()
        item=self.call(base,'PUT',body)
        self.assertEqual(item['stats']['percentage'],50)
        with self.assertRaises(urllib.error.HTTPError) as error: self.call(base,'PUT',body)
        self.assertEqual(error.exception.code,409)
        self.call(base+'/render','POST',b'{}')
        item=self.wait_for_job(ident)
        self.assertTrue(item['highlightReady']); self.assertFalse(item['highlightStale'])
        export=self.root/'result.mp4'; export.write_bytes(self.call(base+'/highlight'))
        subprocess.run([os.environ.get('FFMPEG_PATH','ffmpeg'),'-v','error','-i',str(export),'-f','null','-'],check=True,timeout=30)
        self.process.terminate(); self.process.communicate(timeout=10); self.start_server()
        item=self.call(base)
        self.assertEqual(item['stats']['attempts'],2)
        shots[0]['outcome']='missed'
        item=self.call(base,'PUT',json.dumps(dict(revision=1,shots=shots)).encode())
        self.assertTrue(item['highlightStale']); self.assertEqual(item['stats']['percentage'],0)


if __name__=='__main__': unittest.main()
