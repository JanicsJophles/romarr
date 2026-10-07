"""Submission receipts correlate attempts without fetching real downloads."""
import base64
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from romarr.app import ROMarr
from romarr.clients import QBittorrent, QbitConfig
from romarr.downloaders import SABnzbd, SabConfig, hand_off_receipt
from romarr.download_identity import magnet_job_id, safe_job_id, matches_job
from romarr.store import QueueItem
from romarr import download_status, request_state


def test_sab_receipt_submits_once_and_boolean_api_still_works():
    client = SABnzbd(SabConfig('https://fixture.invalid', 'fixture-key'))
    client._call = Mock(return_value={'status': True, 'nzo_ids': ['SABnzbd_nzo_NEW']})
    receipt = hand_off_receipt(client, 'https://fixture.invalid/item?apikey=private', name='Homebrew')
    assert receipt.accepted and receipt.job_id == 'SABnzbd_nzo_NEW'
    client._call.assert_called_once()
    assert client._call.call_args.kwargs['nzbname'] == 'Homebrew'
    assert client.add('fixture') is True


@pytest.mark.parametrize('ids', [[], ['one', 'two'], ['https://private.invalid?apikey=secret'], 'not-a-list'])
def test_sab_does_not_guess_or_persist_unsafe_receipt(ids):
    client = SABnzbd(SabConfig('https://fixture.invalid', 'fixture'))
    client._call = Mock(return_value={'status': True, 'nzo_ids': ids})
    receipt = client.add_receipt('fixture')
    assert receipt.accepted and receipt.job_id == ''


def test_magnet_hash_and_base32_normalize_without_tracking_urls():
    value = 'ab' * 20
    encoded = base64.b32encode(bytes.fromhex(value)).decode()
    assert magnet_job_id('magnet:?xt=urn:btih:' + value.upper()) == value
    assert magnet_job_id('magnet:?xt=urn:btih:' + encoded) == value
    assert magnet_job_id('https://private.invalid?xt=urn:btih:' + value) == ''
    assert magnet_job_id('magnet:?xt=urn:btih:' + value + '&xt=urn:btih:' + 'cd'*20) == ''
    assert safe_job_id('https://private.invalid?key=secret') == ''


def test_qbit_receipt_calls_add_once_and_does_not_invent_url_hash():
    client = QBittorrent(QbitConfig('https://fixture.invalid'))
    client.add = Mock(return_value=True)
    receipt = client.add_receipt('magnet:?xt=urn:btih:' + 'ab'*20)
    assert receipt.accepted and receipt.job_id == 'ab'*20
    client.add.assert_called_once()
    assert client.add_receipt('https://fixture.invalid/file.torrent').job_id == ''
    client.add.return_value = False
    assert client.add_receipt('magnet:?xt=urn:btih:' + 'ab'*20).job_id == ''


def test_legacy_plugin_clients_keep_boolean_submission_contract():
    class Legacy:
        def add(self, url):
            return True
    assert hand_off_receipt(Legacy(), 'fixture').accepted
    assert hand_off_receipt(Legacy(), 'fixture').job_id == ''


def service(tmp_path):
    return ROMarr({'ROMARR_DATA': str(tmp_path/'state.json')})


def test_receipt_survives_grab_restart_and_request_projection(tmp_path, monkeypatch):
    svc = service(tmp_path)
    sab = SABnzbd(SabConfig('https://fixture.invalid', 'fixture'))
    sab._call = Mock(return_value={'status': True, 'nzo_ids': ['SABnzbd_nzo_NEW']})
    svc.clients = [sab]
    release = SimpleNamespace(protocol='usenet', title='Homebrew', seeders=0, download_url='https://fixture.invalid/nzb', size=1, indexer='Fixture')
    assert svc.grab(release, 'Homebrew', 'nds')['ok']
    assert svc.queue[0].download_job_id == 'SABnzbd_nzo_NEW'
    loaded = service(tmp_path)
    assert loaded.queue[0].download_job_id == 'SABnzbd_nzo_NEW'
    monkeypatch.setattr(request_state, 'PATH', tmp_path/'requests.json')
    assert request_state.base_status(loaded)[0]['download_job_id'] == 'SABnzbd_nzo_NEW'


def test_legacy_queue_loads_without_identity(tmp_path):
    svc = service(tmp_path)
    svc.store.enqueue(QueueItem('Homebrew','nds','Release',0,'grabbed'))
    path = tmp_path/'state.json'
    raw = json.loads(path.read_text())
    del raw['queue'][0]['download_job_id']
    path.write_text(json.dumps(raw))
    assert service(tmp_path).queue[0].download_job_id == ''


def test_failed_old_attempt_cannot_fail_current_same_title_attempt(tmp_path):
    svc = service(tmp_path)
    row = QueueItem('Homebrew','nds','Release',0,'grabbed',download_client='SABnzbd',download_job_id='new')
    svc.store.enqueue(row)
    sab = SABnzbd(SabConfig('https://fixture.invalid', 'fixture'))
    sab._call = Mock(return_value={'history': {'slots': [{'name': 'Release', 'status':'Failed','nzo_id':'old'}]}})
    svc.clients = [sab]
    assert svc.reconcile_client_failures() == 0
    assert row.state == 'grabbed'
    sab._call.return_value['history']['slots'][0].update(name='Renamed download', nzo_id='new')
    assert svc.reconcile_client_failures() == 1
    assert row.state == 'failed'


def test_telemetry_matches_current_attempt_even_when_renamed():
    row = {'status':'downloading','release':'Original','client':'SABnzbd','download_job_id':'new'}
    reports = [{'release':'Original','client':'SABnzbd','job_id':'old','status':'failed'},
               {'release':'Renamed','client':'SABnzbd','job_id':'new','status':'downloading','progress':12}]
    with patch.object(download_status, 'snapshot', return_value={'rows':reports,'errors':[]}):
        result = download_status.enrich(None,[row])[0]
    assert result['status'] == 'downloading' and result['progress'] == 12
    assert not matches_job('new','SABnzbd','Original',reports[0])
    assert not matches_job('new','Other client','Renamed',reports[1])


def test_import_prefers_current_id_not_old_same_title_record(tmp_path):
    svc = service(tmp_path)
    old = QueueItem('Old','nds','Release',0,'imported',download_client='SABnzbd',download_job_id='old')
    new = QueueItem('New','nds','Release',0,'grabbed',download_client='SABnzbd',download_job_id='new')
    svc.store.enqueue(old);svc.store.enqueue(new)
    svc.clients = [SimpleNamespace(name='SABnzbd', configured=True, completed=lambda:[{'name':'Renamed','job_id':'new','content_path':str(tmp_path/'fixture')}])]
    svc.library_for = Mock(return_value=None)
    svc.import_finished(retry_failed=False)
    assert old.state == 'imported'
    assert new.state == 'import-failed' # Correct record routed to missing-library review.
    svc.library_for.assert_called_once_with('nds')


def test_import_never_falls_back_to_title_for_mismatched_job_id(tmp_path):
    svc=service(tmp_path)
    row=QueueItem('New','nds','Release',0,'grabbed',download_client='SABnzbd',download_job_id='new')
    svc.store.enqueue(row)
    svc.clients=[SimpleNamespace(name='SABnzbd',configured=True,completed=lambda:[{'name':'Release','job_id':'old'}])]
    svc.library_for=Mock()
    svc.import_finished(retry_failed=False)
    svc.library_for.assert_not_called()
    assert row.state=='grabbed'


def test_ambiguous_legacy_imports_wait_for_review(tmp_path):
    svc=service(tmp_path)
    for game in ('One','Two'):
        svc.store.enqueue(QueueItem(game,'nds','Same release',0,'grabbed'))
    svc.clients=[SimpleNamespace(name='SABnzbd',configured=True,completed=lambda:[{'name':'Same release'}])]
    svc.library_for=Mock()
    svc.import_finished(retry_failed=False)
    svc.library_for.assert_not_called()
    assert all(row.state=='grabbed' for row in svc.queue)


def test_exact_failure_id_takes_precedence_over_legacy_title(tmp_path):
    svc=service(tmp_path)
    legacy=QueueItem('Old','nds','Release',0,'grabbed',download_client='SABnzbd')
    current=QueueItem('New','nds','Release',0,'grabbed',download_client='SABnzbd',download_job_id='new')
    svc.store.enqueue(legacy);svc.store.enqueue(current)
    sab=SABnzbd(SabConfig('https://fixture.invalid','fixture'))
    sab._call=Mock(return_value={'history':{'slots':[{'name':'Release','status':'Failed','nzo_id':'new'}]}})
    svc.clients=[sab]
    assert svc.reconcile_client_failures()==1
    assert current.state=='failed' and legacy.state=='grabbed'
    assert svc.reconcile_client_failures()==0
    assert legacy.state=='grabbed'
