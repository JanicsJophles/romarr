from types import SimpleNamespace

from romarr.network_diagnostics import inspect_qbit, tracker_summary


def test_tracker_evidence_is_sanitized_and_ignores_dht():
    result = tracker_summary([
        {"url": "** [DHT] **", "status": 4, "msg": "DNS error"},
        {"url": "https://private.example/secret", "status": 4, "msg": "Host not found secret"},
        {"url": "udp://tracker.example", "status": 2, "msg": ""},
    ])
    assert result == {"trackers_checked": 2, "trackers_failed": 1, "tracker_dns_errors": 1}


class Client:
    _config = SimpleNamespace(category="romarr")

    def __init__(self, speed=0):
        self.calls = []
        self.speed = speed

    def _get(self, path, **kwargs):
        self.calls.append((path, kwargs))
        assert kwargs["timeout"] == 2
        if path == "torrents/info":
            data = [{"hash": "a" * 40, "progress": 0, "dlspeed": self.speed}] * 20
        else:
            data = [{"url": "https://tracker.example/secret", "status": 4, "msg": "Host not found"}]
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: data)


def test_read_only_probe_is_bounded_and_reports_dns_not_vpn_certainty():
    client = Client()
    result = inspect_qbit(client)
    assert result["status"] == "dns-errors"
    assert result["jobs_checked"] == 3
    assert len(client.calls) == 4
    assert client.calls[0][1]["params"] == {"category": "romarr"}
    assert "secret" not in str(result)


def test_actual_transfer_is_positive_evidence():
    client = Client(speed=100)
    assert inspect_qbit(client)["status"] == "transferring"
    assert len(client.calls) == 1


def test_failure_does_not_leak_private_exception():
    client = Client()
    def fail(*args, **kwargs):
        raise ValueError("https://private.example/token")
    client._get = fail
    result = inspect_qbit(client)
    assert result["status"] == "unknown"
    assert "private" not in str(result)


def test_snapshot_explains_dns_failure_on_waiting_metadata(monkeypatch):
    from romarr import download_status
    class QBittorrent(Client):
        configured = True
        def _get(self, path, **kwargs):
            if path == 'torrents/info':
                data = [{'hash': 'a' * 40, 'name': 'Example', 'state': 'metaDL', 'progress': 0}]
                return SimpleNamespace(raise_for_status=lambda: None, json=lambda: data)
            return super()._get(path, **kwargs)
    monkeypatch.setattr(download_status, 'CACHE', {'at': 0, 'service': None})
    result = download_status.snapshot(SimpleNamespace(clients=[QBittorrent()]))
    assert result['rows'][0]['status'] == 'metadata'
    assert result['rows'][0]['network_status'] == 'dns-errors'
    assert 'DNS failures' in result['rows'][0]['detail']
