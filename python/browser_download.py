"""Download only the full-size RPC result in the matching persistent browser."""
import base64
from playwright.async_api import async_playwright
from profiles import lookup,profile_path,locked,identity,launch_options

async def download(account_id,url,proxy=None):
 from core import safe_url
 account=lookup(account_id)
 with locked(account['profile']):
  async with async_playwright() as pw:
   context=await pw.chromium.launch_persistent_context(str(profile_path(account['profile'])),**launch_options(True,proxy))
   try:
    page=context.pages[0] if context.pages else await context.new_page()
    await page.goto('https://gemini.google.com/app',wait_until='domcontentloaded',timeout=60000)
    email=identity(await page.content()) or await page.evaluate('window.WIZ_global_data?.oPEP7c || null')
    if not email or email.casefold()!=account['email'].casefold():raise ValueError('Persistent browser account mismatch or expired login; no account fallback')
    cdp=await context.new_cdp_session(page)
    frame=(await cdp.send('Page.getFrameTree'))['frameTree']['frame']['id']
    for _ in range(5):
     result=await cdp.send('Network.loadNetworkResource',{'frameId':frame,'url':safe_url(url),'options':{'disableCache':True,'includeCredentials':True}})
     resource=result['resource'];handle=resource.get('stream')
     if not handle:raise ValueError('Original download failed in persistent browser (HTTP %s)'%resource.get('httpStatusCode'))
     data=bytearray()
     try:
      while True:
       part=await cdp.send('IO.read',{'handle':handle,'size':1048576})
       data.extend(base64.b64decode(part['data']) if part.get('base64Encoded') else part['data'].encode())
       if len(data)>64*1024*1024:raise ValueError('Original image exceeds download limit')
       if part.get('eof'):break
     finally:await cdp.send('IO.close',{'handle':handle})
     if resource.get('httpStatusCode')!=200:raise ValueError('Original download failed in persistent browser (HTTP %s)'%resource.get('httpStatusCode'))
     if data[:2]==b'\xff\xd8' or data[:8]==b'\x89PNG\r\n\x1a\n' or data[:4]==b'RIFF':return bytes(data)
     if len(data)>16384:raise ValueError('Original download returned unexpected content')
     url=data.decode().strip()
    raise ValueError('Too many original download steps')
   finally:await context.close()

async def session_cookies(account_id,proxy=None):
 """Read fresh cookies from this account's browser; never overwrite the old DB."""
 account=lookup(account_id)
 with locked(account['profile']):
  async with async_playwright() as pw:
   context=await pw.chromium.launch_persistent_context(str(profile_path(account['profile'])),**launch_options(True,proxy))
   try:
    page=context.pages[0] if context.pages else await context.new_page()
    await page.goto('https://gemini.google.com/app',wait_until='domcontentloaded',timeout=60000)
    email=identity(await page.content()) or await page.evaluate('window.WIZ_global_data?.oPEP7c || null')
    if not email or email.casefold()!=account['email'].casefold():raise ValueError('Persistent browser login expired or account mismatch; existing account retained')
    return {c['name']:c['value'] for c in await context.cookies(['https://gemini.google.com'])}
   finally:await context.close()
