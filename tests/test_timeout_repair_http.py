"""Timeout repair is authenticated, explicit, bounded, and preview-first."""
from test_companion_http import server, call
import pytest


def test_timeout_repair_needs_auth(server):
    assert call(server[0], '/api/v1/blocklist/repair-timeouts', {'release_ids': []})[0] == 401


def test_timeout_repair_defaults_to_preview(server):
    status, body = call(server[0], '/api/v1/blocklist/repair-timeouts', {'release_ids': []}, 'fixture-key')
    assert status == 200
    assert body == {'eligible': [], 'repaired': [], 'count': 0, 'applied': False}


@pytest.mark.parametrize('payload', [
    [], None, 'invalid', 123, True, {}, {'release_ids': 'id'}, {'release_ids': [None]}, {'release_ids': ['']},
    {'release_ids': ['x' * 513]}, {'release_ids': ['a'] * 101},
    {'release_ids': [], 'apply': 'true'}, {'release_ids': [], 'apply': 1},
])
def test_timeout_repair_rejects_ambiguous_payload(server, payload):
    assert call(server[0], '/api/v1/blocklist/repair-timeouts', payload, 'fixture-key')[0] == 400
