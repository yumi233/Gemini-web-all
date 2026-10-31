import asyncio,io,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from types import SimpleNamespace
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
os.environ.setdefault('GEMINI_WEB_ALL_RUNTIME',tempfile.mkdtemp(prefix='gemini-test-'))
import core
class DownloadTests(unittest.IsolatedAsyncioTestCase):
 async def test_403_uses_same_account_and_full_size(self):
  buffer=io.BytesIO();Image.new('RGB',(32,24)).save(buffer,format='JPEG')
  client=SimpleNamespace(_get_full_size_image=AsyncMock(return_value='https://lh3.googleusercontent.com/test'),client=SimpleNamespace(get=AsyncMock(side_effect=RuntimeError('403'))),proxy=None)
  img=SimpleNamespace(cid='c',rid='r',rcid='rc',image_id='i')
  with tempfile.TemporaryDirectory() as tmp,patch('browser_download.download',new_callable=AsyncMock,return_value=buffer.getvalue()) as fallback:
   result=await core.full_download(client,img,Path(tmp),4)
   self.assertEqual(fallback.await_args.args[0],4)
   self.assertTrue(fallback.await_args.args[1].endswith('=d-I?alr=yes'))
   self.assertEqual((result['width'],result['height']),(32,24))
   self.assertIn('persistent-browser',result['download'])
 async def test_failed_browser_is_not_preview_success(self):
  client=SimpleNamespace(_get_full_size_image=AsyncMock(return_value='https://lh3.googleusercontent.com/test'),client=SimpleNamespace(get=AsyncMock(side_effect=RuntimeError('403'))),proxy=None)
  img=SimpleNamespace(cid='c',rid='r',rcid='rc',image_id='i')
  with tempfile.TemporaryDirectory() as tmp,patch('browser_download.download',new_callable=AsyncMock,side_effect=ValueError('login required')):
   with self.assertRaisesRegex(ValueError,'login required'):await core.full_download(client,img,Path(tmp),4)
   self.assertEqual(list(Path(tmp).iterdir()),[])
if __name__=='__main__':unittest.main()
