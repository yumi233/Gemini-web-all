import json,os,sys,tempfile,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import profiles
class ProfileTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=os.environ.get('GEMINI_WEB_ALL_RUNTIME');os.environ['GEMINI_WEB_ALL_RUNTIME']=self.tmp.name
 def tearDown(self):
  if self.old is None:os.environ.pop('GEMINI_WEB_ALL_RUNTIME',None)
  else:os.environ['GEMINI_WEB_ALL_RUNTIME']=self.old
  self.tmp.cleanup()
 def profile(self):
  token=uuid.uuid4().hex;profiles.profile_path(token).mkdir();return token
 def test_two_accounts_and_cross_binding_rejected(self):
  a,b=self.profile(),self.profile();profiles.bind(4,a,'a@example.com');profiles.bind(5,b,'b@example.com')
  self.assertNotEqual(profiles.lookup(4)['profile'],profiles.lookup(5)['profile'])
  with self.assertRaises(ValueError):profiles.bind(5,a,'b@example.com')
  with self.assertRaises(ValueError):profiles.bind(4,self.profile(),'b@example.com')
  self.assertEqual(profiles.lookup(4)['profile'],a)
 def test_missing_account_never_falls_back(self):
  profiles.bind(4,self.profile(),'a@example.com')
  for value in [None,5]:
   with self.assertRaises(ValueError):profiles.lookup(value)
 def test_path_traversal_and_lock(self):
  with self.assertRaises(ValueError):profiles.profile_path('../other')
  with profiles.locked('test'):
   with self.assertRaises(ValueError):
    with profiles.locked('test'):pass
 def test_account_lock_independence(self):
  with profiles.locked('account4'):
   with profiles.locked('account5'):pass
if __name__=='__main__':unittest.main()
