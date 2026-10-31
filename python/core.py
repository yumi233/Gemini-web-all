"""Local Gemini website images with private per-account browser sessions."""
import asyncio, fcntl, hashlib, json, os, sqlite3, uuid, time
from pathlib import Path
from http.cookies import SimpleCookie
from urllib.parse import urlparse
from PIL import Image as PILImage
from gemini_webapi import GeminiClient
from gemini_webapi.types import GeneratedImage
from gemini_webapi.constants import Headers
from loguru import logger
from mcp.server.mcpserver import MCPServer
logger.remove()
ROOT=Path(__file__).resolve().parent
STATE=Path(os.environ['GEMINI_WEB_ALL_RUNTIME'])/'state'; STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
os.umask(0o077)
DB=Path(os.environ.get('GEMINI_WEB_DATA_DIR',str(Path.home()/'.local/share/magpie-gemini-web')))/'gemini.db'
mcp=MCPServer('gemini-web-images',instructions='Generate images using Gemini WEBSITE, not AI Studio. Full-size RPC download is mandatory. Use only for user-authorized image tasks; one job at a time. Never resubmit a pending job. Headless browser sessions are used for authentication and original download. Output paths are local.',log_level='ERROR')
tasks={}

def credentials(account_id):
 with sqlite3.connect(f'file:{DB}?mode=ro',uri=True) as conn:
  row=conn.execute("select id,cookie,proxy_id from accounts where status='enabled' and (? is null or id=?) order by id limit 1",(account_id,account_id)).fetchone()
  if not row:raise ValueError('No enabled Gemini Web account')
  proxy=conn.execute('select url from proxies where id=? and enabled=1',(row[2],)).fetchone() if row[2] else None
 jar=SimpleCookie();jar.load(row[1]);cookies={k:v.value for k,v in jar.items()}
 if not cookies.get('__Secure-1PSID'):raise ValueError('Missing Gemini Web session')
 return row[0],cookies,proxy[0] if proxy else None

class ReadOnlySessionClient(GeminiClient):
 async def close(self):
  self._running=False
  await super().close()

async def connect(account_id=None):
 aid,cookies,proxy=credentials(account_id)
 from profiles import registry
 if str(aid) in registry():
  from browser_download import session_cookies
  cookies=await asyncio.wait_for(session_cookies(aid,proxy),timeout=90)
 client=ReadOnlySessionClient(cookies['__Secure-1PSID'],cookies.get('__Secure-1PSIDTS'),proxy=proxy)
 for k,v in cookies.items():client.cookies.set(k,v,domain='.google.com',secure=True)
 try:
  await client.init(timeout=300,auto_refresh=False,verbose=False,watchdog_timeout=300)
  if client.account_status.name == 'UNAUTHENTICATED':
   raise ValueError('Gemini website session is not authenticated. Re-login in Gemini-web-all; existing account records are preserved. Flash Lite in this state is not proof of account entitlement.')
  if not client.list_models():raise ValueError('Authenticated models unavailable')
  return aid,client
 except BaseException:
  await client.close();raise

def record(job):
 tmp=STATE/(job['id']+'.tmp');tmp.write_text(json.dumps(job,ensure_ascii=False,indent=2));tmp.replace(STATE/(job['id']+'.json'))

def safe_url(url):
 parsed=urlparse(url);host=parsed.hostname or ''
 if parsed.scheme!='https' or not any(host==d or host.endswith('.'+d) for d in ['google.com','googleusercontent.com']):
  raise ValueError('Unexpected image download host')
 return url

async def full_download(client,img,directory,account_id=None):
 if not all([img.cid,img.rid,img.rcid,img.image_id]):raise ValueError('Missing full-size image metadata')
 url=await client._get_full_size_image(cid=img.cid,rid=img.rid,rcid=img.rcid,image_id=img.image_id)
 if not url:raise ValueError('Full-size RPC unavailable; preview was NOT substituted')
 url=safe_url(url)+'=d-I?alr=yes'
 try:
  for _ in range(4):
   response=await client.client.get(safe_url(url),headers=Headers.REFERER.value)
   response.raise_for_status()
   if response.headers.get('content-type','').startswith('image/'):
    data=response.content;break
   url=response.text.strip()
  else:raise ValueError('Full-size download did not return image bytes')
  method='website-full-size-rpc'
 except Exception:
  if account_id is None:raise
  from browser_download import download
  data=await asyncio.wait_for(download(account_id,safe_url(await client._get_full_size_image(cid=img.cid,rid=img.rid,rcid=img.rcid,image_id=img.image_id))+'=d-I?alr=yes',client.proxy),timeout=180)
  method='website-full-size-rpc-persistent-browser'
 import io
 with PILImage.open(io.BytesIO(data)) as pic:
  pic.verify()
 with PILImage.open(io.BytesIO(data)) as pic:
  width,height=pic.size;ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}.get(pic.format)
 if not ext:raise ValueError('Unsupported returned image format')
 file=directory/('original'+ext)
 with file.open('xb') as stream:stream.write(data)
 return {'path':str(file),'width':width,'height':height,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'download':method,'upscaled_locally':False}

async def run_job(job,prompt,refs,output,account_id,lock):
 client=None
 try:
  aid,client=await connect(account_id)
  available={str(m):m for m in client.list_models()}
  if job['model'] not in available:raise ValueError('Requested website model not available')
  job.update(status='generating',account_id=aid);record(job)
  started=time.monotonic()
  response=await asyncio.wait_for(client.generate_content(prompt='Generate ONE image now. '+prompt,files=refs or None,model=available[job['model']]),timeout=600)
  images=[img for img in response.images if isinstance(img,GeneratedImage)]
  if not images:
   diagnostics=STATE/'diagnostics';diagnostics.mkdir(exist_ok=True,mode=0o700)
   (diagnostics/(job['id']+'.json')).write_text(json.dumps({'metadata':response.metadata,'text':response.text}))
   raise ValueError('Website returned no generated image; response saved locally for diagnosis, no automatic resubmission')
  job['generation_seconds']=round(time.monotonic()-started,2)
  recovery={'account_id':aid,**{k:getattr(images[0],k) for k in ['cid','rid','rcid','image_id','url']}}
  recovery_dir=STATE/'recovery';recovery_dir.mkdir(exist_ok=True,mode=0o700)
  (recovery_dir/(job['id']+'.json')).write_text(json.dumps(recovery))
  job['status']='downloading';record(job)
  directory=Path(output)/job['id'];directory.mkdir(parents=True,exist_ok=False)
  started=time.monotonic()
  job['image']=await full_download(client,images[0],directory,aid)
  job['download_seconds']=round(time.monotonic()-started,2)
  job['status']='completed';record(job)
 except BaseException as e:
  job.update(failed_stage=job.get('status'),http_status=getattr(getattr(e,'response',None),'status_code',None),status='failed',error_type=type(e).__name__,error=str(e) if isinstance(e,ValueError) else 'Website request failed; details suppressed to protect session data. No automatic resubmission.');record(job)
 finally:
  if client:await client.close()
  fcntl.flock(lock,fcntl.LOCK_UN);lock.close()

@mcp.tool()
async def status(check_connection:bool=False)->dict:
 """Inspect availability without exposing cookies or account names. Optional connection check lists actual website model aliases."""
 try:
  with sqlite3.connect(f'file:{DB}?mode=ro',uri=True) as conn:
   accounts=[{'id':r[0],'enabled':r[1]=='enabled'} for r in conn.execute('select id,status from accounts')]
  result={'transport':'background-http','browser_required':True,'accounts':accounts,'full_size_required':True}
  if check_connection:
   _,client=await connect()
   try:result['models']=[str(m) for m in client.list_models()]
   finally:await client.close()
  return result
 except Exception as e:return {'status':'unavailable','error_type':type(e).__name__}

@mcp.tool()
async def generate_image(prompt:str,output_dir:str,reference_images:list[str]|None=None,model:str='gemini-pro',account_id:int|None=None)->dict:
 """Start ONE Gemini website image job. References must be local absolute image paths. output_dir must be absolute. model is a website alias from status, not an API image model. Uses existing Magpie Gemini Web accounts with isolated headless browser sessions. Returns job ID; poll generation_result. Native resolution is determined by the website; no fake size/quality switches."""
 if not prompt.strip() or len(prompt)>20000:raise ValueError('Prompt must be 1–20000 characters')
 output=Path(output_dir).expanduser()
 if not output.is_absolute():raise ValueError('output_dir must be absolute')
 refs=[]
 if len(reference_images or [])>8:raise ValueError('At most 8 references')
 for name in reference_images or []:
  p=Path(name).expanduser()
  if not p.is_absolute() or not p.is_file():raise ValueError('Reference must be an existing absolute local file')
  if p.stat().st_size>30*1024*1024:raise ValueError('Reference exceeds 30 MiB')
  with PILImage.open(p) as im:im.verify()
  refs.append(str(p.resolve()))
 if account_id is None:raise ValueError('Select an explicit image account')
 from profiles import lookup
 lookup(account_id)  # Fail before spending image quota if browser login is missing.
 lock=(STATE/f'generation-{int(account_id)}.lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:
  lock.close();return {'status':'busy','message':'Another generation is active. Poll its job; do not resubmit.'}
 job={'id':uuid.uuid4().hex,'status':'queued','model':model,'reference_count':len(refs),'account_id':account_id};record(job)
 tasks[job['id']]=asyncio.create_task(run_job(job,prompt,refs,str(output),account_id,lock))
 return dict(job)

@mcp.tool()
async def generation_result(id:str)->dict:
 """Read job progress or completed original-image path and measured pixels. Does not submit another generation."""
 if len(id)!=32 or any(c not in '0123456789abcdef' for c in id):raise ValueError('Invalid job ID')
 path=STATE/(id+'.json')
 if not path.exists():raise ValueError('Unknown job')
 job=json.loads(path.read_text())
 if job['status'] in ['queued','generating','downloading'] and id not in tasks:
  with (STATE/(f"generation-{int(job['account_id'])}.lock" if job.get("account_id") is not None else "generation.lock")).open('a') as lock:
   try:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    job['status']='interrupted';job['error']='Worker ended. Do not blindly resubmit; inspect Gemini history first.'
   except BlockingIOError:pass
 return job

if __name__=='__main__':mcp.run()
