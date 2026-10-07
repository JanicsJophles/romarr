"""One downloader job cannot impersonate multiple saved requests."""
from types import SimpleNamespace

from romarr.download_status import enrich


def request(game, **extra):
    return dict(game=game, status='downloading', release='Same release', client='SABnzbd', **extra)


def report(**extra):
    return dict(release='Same release', client='SABnzbd', job_id='old', status='downloaded', **extra)


def test_known_completed_attempt_cannot_complete_new_legacy_request():
    rows = [request('Old', download_job_id='old'), request('New')]
    rows[0]['status'] = 'imported'
    result = enrich(None, rows, live={'rows': [report()], 'errors': []})
    assert result[0]['status'] == 'imported'
    assert result[1]['status'] == 'unknown'


def test_historical_queue_owner_survives_latest_request_projection():
    service = SimpleNamespace(queue=[SimpleNamespace(download_job_id='old', download_client='SABnzbd')])
    result = enrich(service, [request('Same game retried')], live={'rows': [report()], 'errors': []})
    assert result[0]['status'] == 'unknown'


def test_one_legacy_report_cannot_complete_two_distinct_requests():
    result = enrich(None, [request('One'), request('Two')], live={'rows': [report()], 'errors': []})
    assert [row['status'] for row in result] == ['unknown', 'unknown']


def test_identity_owner_on_another_client_does_not_steal_legacy_report():
    service = SimpleNamespace(queue=[SimpleNamespace(download_job_id='old', download_client='qBittorrent')])
    result = enrich(service, [request('New')], live={'rows': [report()], 'errors': []})
    assert result[0]['status'] == 'downloaded'


def test_exact_identity_still_matches_with_competing_legacy_title():
    rows = [request('Current', download_job_id='old'), request('Other')]
    result = enrich(None, rows, live={'rows': [report()], 'errors': []})
    assert result[0]['status'] == 'downloaded'
    assert result[1]['status'] == 'unknown'
