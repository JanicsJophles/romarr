#!/usr/bin/env python3
"""Harmless request/download/import acceptance stage, confined to a temp directory.

No real game, provider account, indexer, external host or production library is
used. A local in-memory catalogue supplies one generated fixture release. The
real authenticated request API, HTTP download client, importer, queue and
restart persistence do the rest. Suitable for a --network none container.
"""
import hashlib
import json
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from romarr.app import ROMarr, make_handler
from romarr.downloaders import SiteConfig, SiteDownloader
from romarr.selection import Release
from romarr import request_state

# A synthetic iNES header plus zero-filled test data, not a commercial ROM.
PAYLOAD = b'NES\x1a' + bytes([1, 0]) + bytes(10) + bytes(16384)


class FixtureSource(BaseHTTPRequestHandler):
    gets = 0
    def do_GET(self):
        if self.path == '/robots.txt':
            body = b'User-agent: *\nDisallow:\n'
        elif self.path == '/fixture.nes':
            body = PAYLOAD
            type(self).gets += 1
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Content-Type', 'application/octet-stream')
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args): pass


def run():
    with tempfile.TemporaryDirectory(prefix='romarr-stage-') as work:
        root = Path(work)
        (root/'library').mkdir()
        (root/'downloads').mkdir()
        request_state.PATH = root/'requests.json'
        source = ThreadingHTTPServer(('127.0.0.1',0),FixtureSource)
        source_thread = threading.Thread(target=source.serve_forever,daemon=True)
        source_thread.start()
        env = {'ROMARR_DATA':str(root/'state.json'),'ROMARR_API_KEY':'local-fixture-only',
               'LIBRARY_KIND':'folder','LIBRARY_PATH':str(root/'library')}
        service = ROMarr(env)
        service.clients = [SiteDownloader(SiteConfig(str(root/'downloads'),delay=0))]
        release = Release(title='Fixture Homebrew (World).nes',size=len(PAYLOAD),seeders=0,
                          categories=(1000,),protocol='direct',indexer='Local fixture catalogue',
                          download_url=f'http://127.0.0.1:{source.server_address[1]}/fixture.nes')
        service._search_releases = lambda game,platform: [release]
        api = ThreadingHTTPServer(('127.0.0.1',0),make_handler(service))
        api_thread = threading.Thread(target=api.serve_forever,daemon=True)
        api_thread.start()
        def call(path,body=None):
            req=urllib.request.Request(f'http://127.0.0.1:{api.server_address[1]}'+path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={'X-Api-Key':'local-fixture-only','Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as response:
                return json.loads(response.read())
        try:
            submitted=call('/api/v1/game-requests',{'game':'Fixture Homebrew','platform':'nes'})
            assert submitted['accepted'], submitted
            deadline=time.monotonic()+5
            while request_state.ACTIVE and time.monotonic()<deadline: time.sleep(.01)
            assert not request_state.ACTIVE
            assert len(service.queue)==1 and service.queue[0].state=='grabbed', [(r.state,r.detail) for r in service.queue]
            duplicate=call('/api/v1/game-requests',{'game':'Fixture Homebrew','platform':'nes'})
            assert duplicate['duplicate'] and len(service.queue)==1
            call('/api/v1/command',{'name':'ImportCompleted'})
            assert service.queue[0].state=='imported', service.queue[0].detail
            files=list((root/'library'/'nes').rglob('*.nes'))
            assert len(files)==1 and files[0].read_bytes()==PAYLOAD
            assert FixtureSource.gets==1, 'Duplicate file transfer'
            status=call('/api/v1/game-requests')['items'][0]
            assert status['status']=='imported', status
            restored=ROMarr(env)
            assert restored.queue[0].state=='imported'
            assert request_state.load()[submitted['request']['id']]['status']=='imported'
            call('/api/v1/command',{'name':'ImportCompleted'})
            assert FixtureSource.gets==1, 'Import replay fetched the file again'
            print(json.dumps({'ok':True,'checks':['authenticated request','idempotent duplicate','real loopback HTTP download','folder import','byte integrity','durable imported status','restart persistence','no repeat transfer'],
                              'fixture_sha256':hashlib.sha256(PAYLOAD).hexdigest(),'external_network':False}))
        finally:
            api.shutdown();api.server_close();api_thread.join(timeout=2)
            source.shutdown();source.server_close();source_thread.join(timeout=2)


if __name__ == '__main__': run()
