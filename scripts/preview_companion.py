#!/usr/bin/env python3
"""Loopback-only visual fixture. No providers, credentials, downloads, or mutations.

Run from the repository root: python scripts/preview_companion.py
Open http://127.0.0.1:8792/#requests. All titles and statuses below are synthetic.
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from romarr.ui import page

ROWS = [
    {'id':'preview-1','game':'Cloud Garden Demo','platform':'nds','status':'downloading','client':'Fixture client','release':'Cloud Garden Demo 1.0','progress':68.4,'speed':2100000,'peers':8,'size':104857600,'detail':'Receiving the selected release.'},
    {'id':'preview-2','game':'Pocket Orchard Homebrew','platform':'gba','status':'imported','release':'Pocket Orchard Homebrew','progress':100,'detail':'Added to the library.'},
    {'id':'preview-3','game':'Moonlit Circuit Demo','platform':'psp','status':'metadata','client':'Fixture client','release':'Moonlit Circuit Demo','progress':0,'peers':0,'detail':'Waiting for metadata from peers; no game data yet.'},
    {'id':'preview-4','game':'Tiny Island Homebrew','platform':'nds','status':'failed','client':'Fixture client','release':'Tiny Island Homebrew','progress':12,'detail':'The selected release was incomplete. Review another result.'},
    {'id':'preview-5','game':'Paper Comet Demo','platform':'psx','status':'verifying','client':'Fixture client','release':'Paper Comet Demo','progress':100,'detail':'Checking the completed files before import.'},
]


class Preview(BaseHTTPRequestHandler):
    def respond(self, status, payload, content_type='application/json'):
        body = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            return self.respond(200, page(), 'text/html; charset=utf-8')
        if path == '/api/v1/game-requests':
            return self.respond(200, {'items': [dict(row, checked_at=time.time()) for row in ROWS]})
        if path == '/api/platforms':
            return self.respond(200, [{'slug':slug,'name':name} for slug,name in [('nds','Nintendo DS'),('gba','Game Boy Advance'),('psp','Sony PSP'),('psx','PlayStation')]])
        if path == '/api/v1/config':
            return self.respond(200, {})
        if path == '/api/v1/system/counts':
            return self.respond(200, {'games':1,'queue':4,'missing':0})
        if path in ('/api/v1/game', '/api/v1/queue'):
            return self.respond(200, {'items':[]})
        return self.respond(404, {'error':'This synthetic preview only serves the companion pages.'})

    def do_POST(self):
        self.respond(405, {'error':'Read-only synthetic preview: actions are disabled.'})
    do_PUT = do_POST
    do_DELETE = do_POST
    do_PATCH = do_POST

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    print('Read-only synthetic preview: http://127.0.0.1:8792/#requests', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8792), Preview).serve_forever()
