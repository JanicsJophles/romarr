"""Client failure truth must not turn connectivity trouble into replacement grabs."""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from romarr.app import ROMarr
from romarr.store import QueueItem
from romarr.downloaders import SABnzbd, SabConfig
from romarr import download_status


def service(tmp_path):
    return ROMarr({'ROMARR_DATA':str(tmp_path/'state.json')})


def client(history):
    sab=SABnzbd(SabConfig('https://example.invalid',api_key='fixture-key'))
    sab._call=Mock(return_value=history)
    return sab


def queued(svc, **kwargs):
    row=QueueItem('Example Homebrew','nds','Example Homebrew Release',0,'grabbed',release_id='fixture-id',indexer='Fixture indexer',**kwargs)
    svc.store.enqueue(row)
    return row


def test_explicit_sab_failure_reconciles_and_persists_without_retry(tmp_path):
    svc=service(tmp_path);row=queued(svc)
    svc.clients=[client({'history':{'slots':[{'name':row.release,'status':'Failed','cat':'romarr','fail_message':'https://private.invalid?apikey=fixture-secret'}]}})]
    svc.request=Mock()
    assert svc.reconcile_client_failures()==1
    assert row.state=='failed' and row.download_client=='SABnzbd'
    assert row.release_fault is False and row.indexer=='Fixture indexer' and row.release_id=='fixture-id'
    assert 'fixture-secret' not in row.detail
    assert svc.retire_dead_downloads()['blocklisted']==0
    svc.request.assert_not_called()
    assert svc.reconcile_client_failures()==0
    loaded=service(tmp_path).queue[0]
    assert loaded.state=='failed' and loaded.download_client=='SABnzbd'


def test_unavailable_client_and_elapsed_timer_do_not_blame_release(tmp_path):
    svc=service(tmp_path)
    row=queued(svc,at=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat())
    svc.clients=[client(None)];svc.request=Mock()
    assert svc.reconcile_client_failures()==0
    assert svc.retire_dead_downloads()['blocklisted']==0
    assert row.state=='grabbed' and not row.release_fault
    svc.request.assert_not_called()


def test_failed_history_is_category_scoped_and_not_a_completed_import():
    sab=client({'history':{'slots':[{'name':'Other app','status':'Failed','cat':'other'}, {'name':'Homebrew','status':'Failed','cat':'romarr'}]}})
    assert [r['name'] for r in sab.failed()]==['Homebrew']
    assert sab.completed()==[]


def test_ambiguous_legacy_rows_and_other_client_are_not_guessed(tmp_path):
    svc=service(tmp_path);row=queued(svc);other=queued(svc)
    svc.clients=[client({'history':{'slots':[{'name':row.release,'status':'Failed'}]}})]
    assert svc.reconcile_client_failures()==0
    other.download_client='Other client'
    assert svc.reconcile_client_failures()==1
    assert other.state=='grabbed'


def test_failed_telemetry_never_exposes_client_error_text():
    row=download_status.sab_row({'status':'Failed','fail_message':'secret-key-in-provider-url'})
    assert 'secret-key' not in str(row)
    assert row['status']=='failed'


@pytest.mark.parametrize('detail',['stalled: no import after 180 minutes','SABnzbd rejected the release'])
def test_legacy_release_fault_from_outage_never_retries(tmp_path,detail):
    svc=service(tmp_path);row=queued(svc);row.state='failed';row.release_fault=True;row.detail=detail
    svc.request=Mock()
    assert svc.retire_dead_downloads()['blocklisted']==0
    assert not row.release_fault
    svc.request.assert_not_called()


def test_client_failure_pauses_scheduled_retries_but_allows_manual_review(tmp_path):
    svc=service(tmp_path); row=queued(svc)
    svc.store.want(row.game,row.platform)
    svc.clients=[client({'history':{'slots':[{'name':row.release,'status':'Failed'}]}})]
    svc.reconcile_client_failures()
    svc.request=Mock(return_value={'ok':False})
    svc.prowlarr.search=Mock(side_effect=AssertionError('No RSS network while held'))
    assert svc.search_missing(auto=True)['searched']==0
    assert svc.rss_sync()=='nothing wanted eligible for automatic search'
    svc.request.assert_not_called()
    assert service(tmp_path).queue[0].review_required is True
    assert svc.search_missing(auto=False)['searched']==1
    svc.request.assert_called_once()


def test_active_download_is_not_duplicated_by_scheduled_search(tmp_path):
    svc=service(tmp_path);row=queued(svc)
    svc.store.want(row.game,row.platform);svc.request=Mock()
    assert svc.search_missing(auto=True)['searched']==0
    svc.request.assert_not_called()


@pytest.mark.parametrize(('message', 'expected'), [
    ('Aborted, cannot be completed - https://private.invalid?apikey=secret', 'provider could not supply'),
    ('No space left on device: /private/client/folder', 'insufficient disk space'),
    ('Repair failed: private-server', 'could not repair'),
    ('Password required: secret-name', 'needs a password'),
    ('Unpack failed: secret-path', 'could not unpack'),
])
def test_known_failure_reason_is_actionable_without_raw_provider_text(tmp_path, message, expected):
    svc = service(tmp_path)
    row = queued(svc)
    svc.clients = [client({'history': {'slots': [
        {'name': row.release, 'status': 'Failed', 'cat': 'romarr', 'fail_message': message}
    ]}})]
    assert svc.reconcile_client_failures() == 1
    assert expected in row.detail
    assert 'private' not in row.detail and 'secret' not in row.detail
    assert not row.release_fault and row.review_required


def legacy_timeout(svc, identity='fixture-id'):
    row = queued(svc)
    row.release_id = identity
    row.state = 'failed'
    row.release_fault = row.blocklisted = True
    row.detail = 'stalled: no import after 180 minutes'
    entry = svc.block_id(identity, title=row.release, reason=row.detail)
    entry.pop('source')  # Historical records did not distinguish operator/automatic.
    svc.store.put_item('blocklist', entry)
    svc.store.save()
    return row


def test_legacy_normalization_survives_restart_with_automation_disabled(tmp_path):
    svc = service(tmp_path)
    row = legacy_timeout(svc)
    svc.store.settings['blocklist_failed_downloads'] = False
    svc.retire_dead_downloads()
    restored = service(tmp_path)
    assert not restored.queue[0].release_fault
    assert restored.queue[0].review_required
    assert restored.queue[0].blocklisted  # Unreviewed historical decisions stay.
    assert len(restored.blocklist) == 1


def test_explicit_timeout_repair_preview_apply_idempotence_and_restart(tmp_path):
    svc = service(tmp_path)
    row = legacy_timeout(svc)
    svc.request = Mock(side_effect=AssertionError('Repair cannot download'))
    assert svc.repair_timeout_blocks([])['eligible'] == []
    preview = svc.repair_timeout_blocks([row.release_id])
    assert preview['eligible'] == [row.release_id] and preview['count'] == 0
    assert row.blocklisted and len(svc.blocklist) == 1
    assert svc.repair_timeout_blocks([row.release_id], apply=True)['count'] == 1
    assert svc.repair_timeout_blocks([row.release_id], apply=True)['count'] == 0
    restored = service(tmp_path)
    assert len(restored.blocklist) == 0
    assert not restored.queue[0].blocklisted and not restored.queue[0].release_fault
    assert restored.queue[0].review_required and restored.queue[0].state == 'failed'
    assert len([e for e in restored.store.history() if 'explicitly reviewed' in e['detail']]) == 1
    svc.request.assert_not_called()


@pytest.mark.parametrize('variation', ['manual', 'content', 'missing', 'mismatch', 'imported', 'other-id'])
def test_timeout_repair_preserves_unproven_and_manual_blocks(tmp_path, variation):
    svc = service(tmp_path)
    row = legacy_timeout(svc)
    approved = [row.release_id]
    if variation == 'manual':
        svc.block_id(row.release_id, title=row.release, reason=row.detail)
    elif variation == 'content':
        row.detail = 'no ROMs found in download'
    elif variation == 'missing':
        svc.queue = []
    elif variation == 'mismatch':
        row.detail = 'stalled: no import after 999 minutes'
    elif variation == 'imported':
        row.state = 'imported'
    elif variation == 'other-id':
        approved = ['another-id']
    assert svc.repair_timeout_blocks(approved, apply=True)['count'] == 0
    assert len(svc.blocklist) == 1


def test_timeout_repair_concurrent_calls_record_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    svc = service(tmp_path)
    row = legacy_timeout(svc)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: svc.repair_timeout_blocks([row.release_id], apply=True), range(8)))
    assert sum(result['count'] for result in results) == 1


def test_block_provenance_survives_policy_reload_and_restart(tmp_path):
    svc = service(tmp_path)
    row = legacy_timeout(svc)
    svc.block_id(row.release_id, title=row.release, reason=row.detail)
    svc.reload_policy()
    assert svc.blocklist.as_items()[0]['source'] == 'operator'
    assert svc.repair_timeout_blocks([row.release_id], apply=True)['count'] == 0
    restarted = service(tmp_path)
    assert restarted.blocklist.as_items()[0]['source'] == 'operator'
    assert restarted.repair_timeout_blocks([row.release_id], apply=True)['count'] == 0


def test_automatic_content_provenance_survives_reload_and_restart(tmp_path):
    svc = service(tmp_path)
    row = queued(svc)
    row.state = 'import-failed'
    row.release_fault = True
    row.detail = 'no ROMs found in download'
    svc.request = Mock(return_value={'ok': False})
    assert svc.retire_dead_downloads()['blocklisted'] == 1
    svc.reload_policy()
    assert svc.blocklist.as_items()[0]['source'] == 'automatic-content-failure'
    assert service(tmp_path).blocklist.as_items()[0]['source'] == 'automatic-content-failure'
