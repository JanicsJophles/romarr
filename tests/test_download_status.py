import unittest
from romarr.download_status import qbit_row,sab_row
class StatusTest(unittest.TestCase):
 def test_metadata_is_not_downloading(self):
  r=qbit_row({'state':'metaDL','progress':0,'num_seeds':0,'num_leechs':0,'eta':8640000})
  self.assertEqual(r['status'],'metadata');self.assertIsNone(r['eta_seconds']);self.assertEqual(r['peers'],0)
 def test_complete_is_not_imported(self):self.assertEqual(qbit_row({'state':'uploading','progress':1})['status'],'downloaded')
 def test_failed_usenet(self):
  r=sab_row({'name':'game','status':'Failed','fail_message':'incomplete'},True)
  self.assertEqual(r['status'],'failed');self.assertIn('Review client history',r['detail'])
if __name__=='__main__':unittest.main()


def test_connected_leechers_are_not_evidence_of_available_complete_game():
 r=qbit_row({'state':'metaDL','num_seeds':0,'num_leechs':2,'num_complete':999})
 assert r['connected_seeds']==0 and r['connected_leechers']==2 and r['peers']==2
 assert r['availability']=='waiting-metadata'
 assert 'leechers' in r['detail'] and 'no connected seeds' in r['detail']
 assert '999' not in str(r)


def test_metadata_seed_connection_does_not_mean_metadata_received():
 r=qbit_row({'state':'forcedMetaDL','num_seeds':1,'num_leechs':0})
 assert r['status']=='metadata'
 assert 'not supplied the metadata' in r['detail']


def test_missing_or_malformed_seed_evidence_is_not_zero_seeds():
 for value in (None,-1,float('nan'),float('inf'),'bad',False):
  r=qbit_row({'state':'metaDL','num_seeds':value,'num_leechs':2})
  assert r['connected_seeds'] is None
  assert 'no connected seeds' not in r['detail']


def test_stalled_row_reports_only_connected_seed_evidence():
 r=qbit_row({'state':'stalledDL','num_seeds':0,'num_leechs':2})
 assert r['availability']=='no-connected-seeds'
 assert 'currently connected' in r['detail']
 assert 'dead' not in r['detail']


def test_failed_request_keeps_outcome_and_exposes_exact_job_peer_evidence():
 from types import SimpleNamespace
 from romarr.download_status import enrich
 live=qbit_row({'state':'metaDL','hash':'a'*40,'num_seeds':0,'num_leechs':2})
 live.update(network_status='dns-errors',network_detail='GLOBAL TRACKER WARNING')
 row={'status':'failed','detail':'Timed out','download_job_id':'a'*40,'client':'qBittorrent'}
 result=enrich(SimpleNamespace(queue=[]),[row],{'rows':[live],'errors':[]})[0]
 assert result['status']=='failed' and result['client_status']=='metadata'
 assert result['connected_seeds']==0 and result['connected_leechers']==2
 assert 'GLOBAL TRACKER WARNING' not in result['client_detail']
