"""Client history must not hide import failures or impersonate another request."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from romarr import download_status as ds


def enrich(row, reports):
    with patch.object(ds, 'snapshot', return_value={'rows': reports, 'errors': []}):
        return ds.enrich(None, [row])[0]


def report(client='SABnzbd', status='downloaded'):
    return {'release': 'Homebrew release', 'client': client, 'status': status,
            'detail': 'Completed', 'progress': 100}


@pytest.mark.parametrize('status', ['imported', 'failed', 'import-failed', 'searching'])
def test_durable_outcomes_survive_completed_client_history(status):
    row = {'status': status, 'release': 'Homebrew release', 'client': 'SABnzbd',
           'detail': 'Library destination is unavailable'}
    result = enrich(row, [report()])
    assert result['status'] == status
    assert result['detail'] == 'Library destination is unavailable'
    assert 'progress' not in result


def test_telemetry_is_scoped_to_recorded_client():
    row = {'status': 'downloading', 'release': 'Homebrew release', 'client': 'qBittorrent'}
    result = enrich(row, [report('qBittorrent', 'stalled'), report()])
    assert result['client'] == 'qBittorrent'
    assert result['status'] == 'stalled'


@pytest.mark.parametrize('client', ['', 'SABnzbd'])
def test_same_title_reports_are_not_guessed(client):
    row = {'status': 'downloading', 'release': 'Homebrew release', 'client': client}
    result = enrich(row, [report(), report(status='failed')])
    assert result['status'] == 'unknown'
    assert 'Multiple matching' in result['detail']


def test_other_clients_completed_history_does_not_complete_request():
    result = enrich({'status': 'downloading', 'release': 'Homebrew release',
                     'client': 'qBittorrent'}, [report()])
    assert result['status'] == 'unknown'


def test_empty_release_does_not_match_anonymous_client_report():
    result = enrich({'status': 'queued', 'release': ''}, [{'release': '', 'status': 'downloaded'}])
    assert result['status'] == 'unknown'


def test_cache_is_not_shared_between_service_instances():
    first = SimpleNamespace(clients=[])
    second = SimpleNamespace(clients=[])
    with patch.dict(ds.CACHE, {'at': ds.time.monotonic(), 'rows': [report()],
                              'errors': [], 'service': first}):
        assert ds.snapshot(first)['rows']
        assert ds.snapshot(second)['rows'] == []


def test_failed_tracking_and_live_download_are_separate_facts():
    result = enrich({'status': 'failed', 'release': 'Homebrew release',
                     'client': 'qBittorrent', 'detail': 'stalled: no import after 180 minutes'},
                    [report('qBittorrent', 'metadata')])
    assert result['status'] == 'failed'
    assert result['detail'] == 'stalled: no import after 180 minutes'
    assert result['client_status'] == 'metadata'
    assert 'still waiting for metadata' in result['client_detail']
    assert 'progress' not in result


def test_existing_failed_request_gets_safe_current_failure_explanation():
    live = ds.sab_row({'name': 'Homebrew release', 'status': 'Failed',
                       'fail_message': 'Aborted, cannot be completed https://private?apikey=secret'})
    result = enrich({'status': 'failed', 'release': 'Homebrew release',
                     'client': 'SABnzbd', 'detail': 'Old failure'}, [live])
    assert result['detail'] == 'Old failure'
    assert 'provider could not supply' in result['client_detail']
    assert 'secret' not in str(result) and 'private' not in str(result)
