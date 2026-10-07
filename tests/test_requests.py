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
