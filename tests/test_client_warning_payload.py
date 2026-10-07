"""Global client warnings survive latest-attempt changes without rewriting cause."""
from types import SimpleNamespace
from unittest.mock import Mock

from romarr import download_status as ds, request_state


def test_payload_samples_once_and_warns_even_when_request_has_no_release(monkeypatch):
    row={'game':'Homebrew','platform':'nds','status':'failed','release':'','detail':'No usable release found'}
    warning={'client':'qBittorrent','status':'dns-errors','detail':'Trackers report DNS failures.'}
    sample=Mock(return_value={'rows':[], 'errors':[], 'client_warnings':[warning]})
    monkeypatch.setattr(ds,'snapshot',sample)
    monkeypatch.setattr(request_state,'base_status',lambda service:[row])
    payload=request_state.status_payload(SimpleNamespace())
    sample.assert_called_once()
    assert payload['items']==[row] and row['detail']=='No usable release found'
    assert payload['client_warnings']==[warning]


def test_warning_payload_is_backward_compatible_with_empty_snapshot(monkeypatch):
    monkeypatch.setattr(ds,'snapshot',lambda service:{'rows':[],'errors':[]})
    monkeypatch.setattr(request_state,'base_status',lambda service:[])
    assert request_state.status_payload(SimpleNamespace())=={'items':[], 'client_warnings':[]}


def test_cached_qbit_network_warning_survives_no_matching_requests(monkeypatch):
    from romarr import network_diagnostics
    class QBittorrent:
        configured=True
        _config=SimpleNamespace(category='romarr')
        def _get(self,*a,**kw):
            return SimpleNamespace(raise_for_status=lambda:None,json=lambda:[])
    inspect=Mock(return_value={'status':'dns-errors','detail':'Trackers report DNS failures.'})
    monkeypatch.setattr(network_diagnostics,'inspect_qbit',inspect)
    monkeypatch.setattr(ds,'CACHE',{'at':0,'service':None})
    svc=SimpleNamespace(clients=[QBittorrent()])
    first=ds.snapshot(svc)
    assert first['rows']==[] and first['client_warnings'][0]['status']=='dns-errors'
    assert ds.snapshot(svc)['client_warnings']==first['client_warnings']
    inspect.assert_called_once()


def test_unavailable_client_does_not_expose_exception_or_custom_label(monkeypatch):
    class SABnzbd:
        configured=True
        name='https://private.invalid/credential'
        _config=SimpleNamespace(category='romarr')
        def _call(self,*a,**kw):
            raise RuntimeError('secret connection string')
    monkeypatch.setattr(ds,'CACHE',{'at':0,'service':None})
    snapshot=ds.snapshot(SimpleNamespace(clients=[SABnzbd()]))
    assert snapshot['client_warnings'][0]['client']=='SABnzbd'
    assert 'private' not in str(snapshot) and 'secret' not in str(snapshot)
