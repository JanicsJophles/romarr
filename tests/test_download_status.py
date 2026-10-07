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
