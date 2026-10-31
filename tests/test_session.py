import os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
os.environ.setdefault('GEMINI_WEB_ALL_RUNTIME',tempfile.mkdtemp(prefix='gemini-test-'))
import core
class SessionTests(unittest.IsolatedAsyncioTestCase):
 def client(self,status):
  return SimpleNamespace(cookies=SimpleNamespace(set=MagicMock()),init=AsyncMock(),close=AsyncMock(),account_status=SimpleNamespace(name=status),list_models=lambda:['gemini-pro'])
 async def test_valid_original_session_is_preserved(self):
  client=self.client('AVAILABLE')
  with patch('core.credentials',return_value=(4,{'__Secure-1PSID':'test'},None)),patch('core.ReadOnlySessionClient',return_value=client),patch('browser_download.session_cookies',new_callable=AsyncMock) as browser:
   aid,result=await core.connect(4)
   self.assertIs(result,client);self.assertEqual(aid,4);browser.assert_not_awaited()
 async def test_expired_session_uses_only_same_account_profile(self):
  expired,valid=self.client('UNAUTHENTICATED'),self.client('AVAILABLE')
  with patch('core.credentials',return_value=(4,{'__Secure-1PSID':'old-test'},None)),patch('core.ReadOnlySessionClient',side_effect=[expired,valid]),patch('profiles.registry',return_value={'4':{}}),patch('browser_download.session_cookies',new_callable=AsyncMock,return_value={'__Secure-1PSID':'new-test'}) as browser:
   aid,result=await core.connect(4)
   self.assertIs(result,valid);browser.assert_awaited_once_with(4,None);expired.close.assert_awaited_once()
if __name__=='__main__':unittest.main()
