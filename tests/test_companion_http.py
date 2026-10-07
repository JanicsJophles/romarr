"""Real socket authentication and validation; discovery/acquisition are mocked."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import Mock

import pytest
from romarr.app import ROMarr, make_handler
from romarr import chat, request_state


@pytest.fixture
def server(tmp_path, monkeypatch):
    service = ROMarr({'ROMARR_DATA': str(tmp_path / 'state.json'), 'ROMARR_API_KEY': 'fixture-key'})
    monkeypatch.setattr(request_state, 'PATH', tmp_path / 'requests.json')
    acquisition = Mock(side_effect=AssertionError('No acquisition allowed in HTTP tests'))
    monkeypatch.setattr(service, 'request', acquisition)
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(service))
    worker = threading.Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    yield f'http://127.0.0.1:{httpd.server_address[1]}', acquisition
    httpd.shutdown()
    httpd.server_close()
    worker.join(timeout=2)
    acquisition.assert_not_called()


def call(base, route, body=None, key=None, method='POST'):
    headers = {'Content-Type': 'application/json'}
    if key: headers['X-Api-Key'] = key
    req = urllib.request.Request(base + route, data=json.dumps(body).encode() if method == 'POST' else None,
                                 headers=headers, method=method)
    try:
        response = urllib.request.urlopen(req, timeout=3)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, json.loads(response.read())


def test_custom_routes_reject_unauthenticated_callers(server, monkeypatch):
    provider = Mock()
    monkeypatch.setattr(chat, 'respond', provider)
    for path, method in [('/api/v1/game-chat', 'POST'), ('/api/v1/game-requests', 'POST'), ('/api/v1/game-requests', 'GET')]:
        status, body = call(server[0], path, method=method)
        assert status == 401
    provider.assert_not_called()


def test_malformed_request_does_not_start_work(server):
    status, body = call(server[0], '/api/v1/game-requests', [], 'fixture-key')
    assert status == 400 and 'error' in body


def test_authorized_chat_returns_adapter_response(server, monkeypatch):
    provider = Mock(return_value={'reply': 'Example response', 'games': [], 'unverified': 0})
    monkeypatch.setattr(chat, 'respond', provider)
    payload = {'messages': [{'role': 'user', 'content': 'Puzzle suggestions'}]}
    status, body = call(server[0], '/api/v1/game-chat', payload, 'fixture-key')
    assert status == 200 and body['reply'] == 'Example response'
    assert provider.call_args.args[1] == payload


def test_unexpected_provider_failure_does_not_leak_to_http(server, monkeypatch):
    monkeypatch.setattr(chat, 'respond', Mock(side_effect=RuntimeError('fixture-sensitive-token')))
    status, body = call(server[0], '/api/v1/game-chat', {'messages': []}, 'fixture-key')
    assert status == 500
    assert 'fixture-sensitive-token' not in json.dumps(body)
