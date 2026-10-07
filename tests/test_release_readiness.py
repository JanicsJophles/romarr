"""Release gates for the optional request/chat adapters. All services/transports are fake.

Run with unittest; failing cases represent release blockers, not expected failures.
"""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romarr import request_state as rs, download_status as ds, chat


class DurableRequestGates(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'requests.json'
        p = patch.object(rs, 'PATH', self.path)
        p.start(); self.addCleanup(p.stop)
        p = patch.object(rs, 'ACTIVE', set())
        p.start(); self.addCleanup(p.stop)
        self.service = Mock()
        self.service.queue = []
        self.service.store.missing.return_value = []

    def test_duplicate_after_restart_never_redispatches(self):
        ident = rs.key('Example Game', 'psp')
        rs.save({ident: {'id': ident, 'game': 'Example Game', 'platform': 'psp', 'status': 'searching'}})
        result = rs.submit(self.service, {'game': ' example game ', 'platform': 'psp'})
        self.assertTrue(result['duplicate'])
        self.assertEqual(result['request']['status'], 'interrupted')
        self.service.request.assert_not_called()

    def test_invalid_body_is_validation_error(self):
        for body in (None, [], 'game', 7):
            with self.subTest(body=body), self.assertRaises(ValueError):
                rs.submit(self.service, body)
        self.service.request.assert_not_called()

    def test_non_string_game_is_not_coerced_into_request(self):
        with patch.object(rs.threading, 'Thread'):
            for game in (None, {}, [], True):
                with self.subTest(game=game), self.assertRaises(ValueError):
                    rs.submit(self.service, {'game': game, 'platform': 'psp'})

    def test_corrupt_history_fails_closed_without_new_request(self):
        self.path.write_text('{broken')
        with self.assertRaises(ValueError):
            rs.submit(self.service, {'game': 'Example', 'platform': 'psp'})
        self.service.request.assert_not_called()
        self.assertEqual(self.path.read_text(), '{broken')

    def test_failed_provider_result_does_not_expose_credential(self):
        with patch.object(rs.threading, 'Thread') as thread:
            result = rs.submit(self.service, {'game': 'Example', 'platform': 'psp'})
            worker = thread.call_args.kwargs['target']
        self.service.request.return_value = {'ok': False, 'error': 'https://example.invalid?apikey=secret'}
        worker()
        self.assertNotIn('secret', json.dumps(rs.load()))
        self.assertEqual(rs.load()[result['request']['id']]['status'], 'failed')

    def test_two_active_limit_never_dispatches_third(self):
        rs.ACTIVE.update(('first', 'second'))
        with patch.object(rs.threading, 'Thread') as thread:
            result = rs.submit(self.service, {'game': 'Third', 'platform': 'psp'})
        self.assertIn('error', result)
        thread.assert_not_called()
        self.assertEqual(rs.load(), {})

    def test_request_persisted_before_worker_starts(self):
        with patch.object(rs.threading, 'Thread') as thread:
            result = rs.submit(self.service, {'game': 'Example', 'platform': 'psp'})
            ident = result['request']['id']
            self.assertEqual(rs.load()[ident]['status'], 'searching')
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
            thread.return_value.start.assert_called_once()

    def test_worker_write_failure_releases_active_slot(self):
        with patch.object(rs.threading, 'Thread') as thread:
            result = rs.submit(self.service, {'game': 'Example', 'platform': 'psp'})
            worker = thread.call_args.kwargs['target']
        self.service.request.return_value = {'ok': True}
        with patch.object(rs, 'save', side_effect=OSError('disk full')):
            try:
                worker()
            except OSError:
                pass
        self.assertNotIn(result['request']['id'], rs.ACTIVE)

    def test_worker_exception_does_not_expose_provider_secret(self):
        with patch.object(rs.threading, 'Thread') as thread:
            result = rs.submit(self.service, {'game': 'Example', 'platform': 'psp'})
            worker = thread.call_args.kwargs['target']
        self.service.request.side_effect = RuntimeError('https://private.invalid?apikey=secret')
        worker()
        row = rs.load()[result['request']['id']]
        self.assertEqual(row['status'], 'failed')
        self.assertNotIn('secret', json.dumps(row))
        self.assertFalse(rs.ACTIVE)


class TelemetryGates(unittest.TestCase):
    def test_imported_state_is_not_downgraded_by_client_history(self):
        rows = [{'game':'Example', 'status':'imported', 'release':'Example'}]
        with patch.object(ds, 'snapshot', return_value={'rows':[{'release':'Example','status':'failed'}], 'errors':[]}):
            self.assertEqual(ds.enrich(Mock(), rows)[0]['status'], 'imported')

    def test_missing_download_is_unknown_not_falsely_downloading(self):
        with patch.object(ds, 'snapshot', return_value={'rows':[], 'errors':[]}):
            row = ds.enrich(Mock(), [{'status':'downloading', 'release':'Example'}])[0]
        self.assertEqual(row['status'], 'unknown')

    def test_nullable_client_fields_do_not_break_telemetry(self):
        row = ds.qbit_row({'progress':None, 'eta':None, 'num_seeds':None, 'num_leechs':None})
        self.assertIsNone(row['eta_seconds'])
        self.assertEqual(row['peers'], 0)

    def test_progress_is_bounded(self):
        self.assertLessEqual(ds.qbit_row({'progress':4})['progress'], 100)
        self.assertGreaterEqual(ds.sab_row({'percentage':-5})['progress'], 0)


class ChatFailureGates(unittest.TestCase):
    def test_malformed_success_responses_are_safe_errors_and_release_slot(self):
        service = Mock()
        service.store.list_items.return_value = []
        service.library_view.return_value = {"items": []}
        for payload in ({'candidates':[]}, {'candidates':[{'content':{'parts':[{'text':'null'}]}}]}):
            response = Mock(status_code=200)
            response.json.return_value = payload
            semaphore = threading.BoundedSemaphore(2)
            with self.subTest(payload=payload), patch.object(chat, 'LOCK', semaphore), \
                 patch.object(chat.Path, 'read_text', return_value='{"key":"dummy-secret"}'), \
                 patch.object(chat.requests, 'post', return_value=response):
                result = chat.respond(service, {'messages':[{'role':'user','content':'Hello'}]})
                self.assertIn('error', result)
                self.assertNotIn('dummy-secret', json.dumps(result))
                self.assertTrue(semaphore.acquire(blocking=False))
                self.assertTrue(semaphore.acquire(blocking=False))

    def test_chat_limit_does_not_call_provider(self):
        semaphore = threading.BoundedSemaphore(2)
        semaphore.acquire(); semaphore.acquire()
        with patch.object(chat, 'LOCK', semaphore), patch.object(chat.requests, 'post') as post:
            result = chat.respond(Mock(), {'messages':[{'role':'user','content':'Hello'}]})
        self.assertIn('error', result)
        post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
