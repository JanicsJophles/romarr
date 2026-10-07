"""Retry reservations preserve evidence and avoid concurrent queue handoffs."""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from romarr.app import ROMarr, QueueItem


@pytest.fixture(autouse=True)
def client_snapshot(monkeypatch):
    monkeypatch.setattr("romarr.download_status.snapshot", lambda service: {
        "rows": [{"release": "old release", "client": "SABnzbd", "job_id": "old-job", "status": "failed"}],
        "errors": [],
    })


def service(tmp_path):
    s = ROMarr(env={"ROMARR_DATA": str(tmp_path / "state.json")})
    s.queue = [QueueItem("Persona", "psp", "old release", 0, "failed", "missing articles")]
    return s


def test_unsuccessful_retry_keeps_original_and_new_failure(tmp_path, monkeypatch):
    s = service(tmp_path)
    original = s.queue[0]
    def request(*args):
        s.store.enqueue(QueueItem("Persona", "psp", "", 0, "failed", "search unavailable"))
        return {"ok": False}
    monkeypatch.setattr(s, "request", request)
    assert not s.queue_action(0, "retry")["ok"]
    assert original in s.queue
    restored = ROMarr(env={"ROMARR_DATA": str(tmp_path / "state.json")})
    assert [q.detail for q in restored.queue] == ["missing articles", "search unavailable"]


def test_exception_keeps_failure_and_releases_reservation(tmp_path, monkeypatch):
    s = service(tmp_path)
    def request(*args):
        raise TimeoutError("offline")
    monkeypatch.setattr(s, "request", request)
    with pytest.raises(TimeoutError):
        s.queue_action(0, "retry")
    assert s.queue[0].detail == "missing articles"
    monkeypatch.setattr(s, "request", lambda *args: {"ok": True})
    assert s.queue_action(0, "retry")["ok"]


@pytest.mark.parametrize("state", ["queued", "searching", "grabbed", "import-failed", "imported"])
def test_active_or_local_import_cannot_be_redownloaded(tmp_path, monkeypatch, state):
    s = service(tmp_path)
    s.store.enqueue(QueueItem(" PERSONA ", "psp", "current", 0, state))
    monkeypatch.setattr(s, "request", lambda *a: pytest.fail("duplicate submission"))
    assert not s.queue_action(0, "retry")["ok"]
    assert not s.queue_action(1, "retry")["ok"]


def test_concurrent_retries_submit_once_despite_queue_removal(tmp_path, monkeypatch):
    s = service(tmp_path)
    entered, finish = threading.Event(), threading.Event()
    calls = []
    def request(*args):
        calls.append(args)
        entered.set()
        assert finish.wait(5)
        s.store.enqueue(QueueItem("Persona", "psp", "new release", 0, "grabbed"))
        return {"ok": True}
    monkeypatch.setattr(s, "request", request)
    with ThreadPoolExecutor(max_workers=1) as pool:
        retry = pool.submit(s.queue_action, 0, "retry")
        assert entered.wait(5)
        try:
            assert not s.queue_action(0, "retry")["ok"]
            # The original can be forgotten during the handoff. Its old index
            # will now identify another game and must not be used for deletion.
            assert s.queue_action(0, "remove")["ok"]
            s.store.enqueue(QueueItem("Other", "psp", "other", 0, "failed"))
        finally:
            finish.set()
        assert retry.result()["ok"]
    assert len(calls) == 1
    assert [q.game for q in s.queue] == ["Other", "Persona"]


def test_retry_retains_external_request_tracking(tmp_path, monkeypatch):
    s = service(tmp_path)
    s.queue[0].external_request_id = "request-123"
    calls = []
    def request(*args, **kwargs):
        calls.append(kwargs)
        return {"ok": True}
    monkeypatch.setattr(s, "request", request)
    assert s.queue_action(0, "retry")["ok"]
    assert calls == [{"external_request_id": "request-123"}]


def test_success_preserves_previous_job_ownership(tmp_path, monkeypatch):
    s = service(tmp_path)
    previous = s.queue[0]
    previous.download_job_id = "old-job"
    def request(*args):
        s.store.enqueue(QueueItem("Persona", "psp", "new release", 0, "grabbed",
                                 download_job_id="new-job"))
        return {"ok": True}
    monkeypatch.setattr(s, "request", request)
    assert s.queue_action(0, "retry")["ok"]
    assert [q.download_job_id for q in s.queue] == ["old-job", "new-job"]


@pytest.mark.parametrize("status", ["metadata", "downloading", "stalled", "paused", "verifying", "downloaded", "unknown"])
def test_failed_tracking_with_live_job_cannot_retry(tmp_path, monkeypatch, status):
    s = service(tmp_path)
    s.queue[0].download_job_id = "old-job"
    monkeypatch.setattr("romarr.download_status.snapshot", lambda _: {
        "rows": [{"client": "qBittorrent", "job_id": "old-job", "release": "renamed", "status": status}], "errors": []})
    monkeypatch.setattr(s, "request", lambda *a: pytest.fail("live job duplicated"))
    assert not s.queue_action(0, "retry")["ok"]


@pytest.mark.parametrize("snapshot", [
    {"rows": [], "errors": []},
    {"rows": [], "errors": ["SABnzbd unavailable"]},
    {"rows": [{"release": "old release", "status": "failed"}] * 2, "errors": []},
    {"rows": [{"release": "old release", "status": "failed"}], "errors": ["SABnzbd unavailable"]},
])
def test_unavailable_or_ambiguous_job_blocks_retry(tmp_path, monkeypatch, snapshot):
    s = service(tmp_path)
    monkeypatch.setattr("romarr.download_status.snapshot", lambda _: snapshot)
    monkeypatch.setattr(s, "request", lambda *a: pytest.fail("uncertain job duplicated"))
    assert not s.queue_action(0, "retry")["ok"]


def test_legacy_match_owned_by_another_attempt_blocks_retry(tmp_path, monkeypatch):
    s = service(tmp_path)
    s.store.enqueue(QueueItem("Persona", "psp", "old release", 0, "failed", download_job_id="old-job"))
    monkeypatch.setattr(s, "request", lambda *a: pytest.fail("wrong job ownership"))
    assert not s.queue_action(0, "retry")["ok"]


def test_legacy_timeout_release_fault_still_checks_live_job(tmp_path, monkeypatch):
    s = service(tmp_path)
    s.queue[0].release_fault = True
    s.queue[0].detail = "stalled: no import after 72 hours"
    monkeypatch.setattr("romarr.download_status.snapshot", lambda _: {
        "rows": [{"release": "old release", "status": "metadata"}], "errors": []})
    monkeypatch.setattr(s, "request", lambda *a: pytest.fail("legacy timeout duplicated"))
    assert not s.queue_action(0, "retry")["ok"]


def test_new_blank_failure_cannot_hide_old_live_torrent(tmp_path, monkeypatch):
    s = service(tmp_path)
    s.queue[0].release_fault = True
    s.queue[0].detail = "stalled: no import after 72 hours"
    s.store.enqueue(QueueItem("Persona", "psp", "", 0, "failed", "no usable release"))
    calls = []
    def snapshot(_):
        calls.append(True)
        return {"rows": [{"release": "old release", "status": "metadata"}], "errors": []}
    monkeypatch.setattr("romarr.download_status.snapshot", snapshot)
    monkeypatch.setattr(s, "request", lambda *a: pytest.fail("old torrent duplicated"))
    assert not s.queue_action(1, "retry")["ok"]
    assert calls == [True]
