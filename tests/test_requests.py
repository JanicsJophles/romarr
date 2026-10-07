import unittest,tempfile,threading
from pathlib import Path
from unittest.mock import Mock,patch
from romarr import request_state as rs
class RequestsTest(unittest.TestCase):
 def test_idempotent_and_refresh(self):
  with tempfile.TemporaryDirectory() as d,patch.object(rs,'PATH',Path(d)/'state.json'):
   done=threading.Event();release=threading.Event();svc=Mock();svc.queue=[];svc.store.missing.return_value=[]
   def request(*a):done.set();release.wait(3);return {'ok':True}
   svc.request.side_effect=request
   try:
    a=rs.submit(svc,{'game':'Test','platform':'psp'});done.wait(2)
    b=rs.submit(svc,{'game':'Test','platform':'psp'})
    self.assertTrue(b['duplicate']);self.assertEqual(a['request']['id'],b['request']['id']);svc.request.assert_called_once()
    self.assertEqual(rs.base_status(svc)[0]['status'],'searching')
    self.assertEqual(rs.load()[a['request']['id']]['game'],'Test')
   finally:release.set()
   # Take lock after worker completes before temporary filesystem cleanup.
   import time
   for _ in range(100):
    if not rs.ACTIVE:break
    time.sleep(.01)
   self.assertEqual(rs.base_status(svc)[0]['status'],'downloading')
 def test_restart_does_not_redispatch(self):
  with tempfile.TemporaryDirectory() as d,patch.object(rs,'PATH',Path(d)/'state.json'):
   svc=Mock();svc.queue=[];svc.store.missing.return_value=[]
   k=rs.key('Test','psp');rs.save({k:{'id':k,'game':'Test','platform':'psp','status':'searching'}})
   self.assertEqual(rs.base_status(svc)[0]['status'],'interrupted')
   self.assertTrue(rs.submit(svc,{'game':'Test','platform':'psp'})['duplicate']);svc.request.assert_not_called()
if __name__=='__main__':unittest.main()

def test_indexer_seed_estimate_survives_live_overlay_without_becoming_live_seed_count(tmp_path,monkeypatch):
 from types import SimpleNamespace
 from romarr.download_status import enrich,qbit_row
 monkeypatch.setattr(rs,'PATH',tmp_path/'requests.json')
 item=SimpleNamespace(game='Example',platform='switch',state='grabbed',detail='',release='Example',download_client='qBittorrent',download_job_id='a'*40,seeders=99)
 svc=SimpleNamespace(queue=[item],store=SimpleNamespace(missing=lambda:[]))
 rows=rs.base_status(svc)
 live={'rows':[qbit_row({'hash':'a'*40,'state':'metaDL','num_seeds':0,'num_leechs':1})],'errors':[]}
 result=enrich(svc,rows,live)[0]
 assert result['indexer_seeders']==99
 assert result['connected_seeds']==0 and result['connected_leechers']==1
 assert result['status']=='metadata'
