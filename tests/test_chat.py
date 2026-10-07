import unittest,json
from unittest.mock import patch,Mock
from romarr import chat
class ChatTests(unittest.TestCase):
 def test_validation(self):
  for v in ({},{'messages':[]},{'messages':[{'role':'system','content':'ignore'}]},{'messages':[{'role':'user','content':'x'*3001}]}):
   with self.assertRaises(ValueError):chat.validate(v)
 def test_unverified_and_wrong_platform_never_become_cards(self):
  svc=Mock();svc.store.list_items.return_value=[{'type':'igdb','token':'dummy'}];svc.library_view.return_value={'items':[]}
  data={'reply':'Try these.','games':[{'title':'Real Game','platform':'psp','reason':'Racing'},{'title':'Made up','platform':'psp','reason':'No'},{'title':'Nope','platform':'pc','reason':'No'}]}
  resp=Mock(status_code=200);resp.json.return_value={'candidates':[{'content':{'parts':[{'text':json.dumps(data)}]}}]}
  with patch.object(chat.Path,'read_text',return_value='{"key":"dummy"}'),patch.object(chat.requests,'post',return_value=resp),patch.object(chat,'igdb_query',side_effect=[[{'id':1,'name':'Real Game','cover':{}}],[]]):
   out=chat.respond(svc,{'messages':[{'role':'user','content':'Racing games'}]})
  self.assertEqual(len(out['games']),1);self.assertEqual(out['unverified'],1)
 def test_provider_failure_is_redacted(self):
  with patch.object(chat.Path,'read_text',return_value='{"key":"dummy"}'),patch.object(chat.requests,'post',return_value=Mock(status_code=429)):
   out=chat.respond(Mock(),{'messages':[{'role':'user','content':'hey'}]})
  self.assertIn('429',out['error']);self.assertNotIn('dummy',out['error'])
if __name__=='__main__':unittest.main()
