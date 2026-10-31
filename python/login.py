"""Interactive login only; captures cookies from its own isolated browser context."""
import asyncio,json,os,tempfile,time,re
from pathlib import Path
from playwright.async_api import async_playwright
os.umask(0o077)
def executable():
 roots=[Path('/Applications'),Path('/Volumes/1t扩展盘/Applications')]
 for root in roots:
  for app,exe in [('Google Chrome','Google Chrome'),('Microsoft Edge','Microsoft Edge')]:
   p=root/f'{app}.app/Contents/MacOS/{exe}'
   if p.is_file():return str(p)
 cache=Path.home()/'Library/Caches/ms-playwright'
 candidates=sorted(cache.glob('chromium-*/chrome-mac*/**/Contents/MacOS/*'))
 for p in reversed(candidates):
  if p.is_file() and p.name in ['Chromium','Google Chrome for Testing']:return str(p)
 return None
async def main():
 import sys,uuid
 from profiles import root,profile_path,locked,identity,launch_options,bind
 request=json.load(sys.stdin)
 token=uuid.uuid4().hex
 profile=profile_path(token);profile.mkdir(mode=0o700)
 expected=None
 if request.get('account_id') is not None:
  from core import connect
  _,client=await connect(request['account_id'])
  try:expected=identity((await client.client.get('https://gemini.google.com/app')).text)
  finally:await client.close()
  if not expected:raise ValueError('Cannot verify existing account identity; account unchanged')
 with locked(token):
  async with async_playwright() as pw:
   browser=await pw.chromium.launch_persistent_context(str(profile),**launch_options(False),args=['--disable-blink-features=AutomationControlled'],ignore_default_args=['--enable-automation'])
   try:
    page=browser.pages[0] if browser.pages else await browser.new_page()
    await page.goto('https://gemini.google.com/app',wait_until='domcontentloaded')
    for _ in range(285):
     if not browser.pages:raise ValueError('Login window closed; existing accounts retained')
     for page in list(browser.pages):
      if not re.match(r'https://gemini\.google\.com/(?:u/\d+/)?app(?:[/#?]|$)',page.url):continue
      email=identity(await page.content()) or await page.evaluate('window.WIZ_global_data?.oPEP7c || null')
      if not email:continue
      if expected and email.casefold()!=expected.casefold():raise ValueError('Signed into a different account; browser profile retained, existing account unchanged')
      cookies=await browser.cookies(['https://gemini.google.com'])
      values={c['name']:c['value'] for c in cookies if c['domain'].lstrip('.') in ['google.com','gemini.google.com']}
      if not values.get('__Secure-1PSID'):continue
      # Keep browser storage on disk; only emit cookie internally to the importer.
      result={'cookie':'; '.join(f'{k}={v}' for k,v in values.items()),'email':email,'profile':token}
      break
     else:
      await asyncio.sleep(2);continue
     break
    else:raise ValueError('Login timed out; existing accounts retained')
   finally:await browser.close()
  if request.get('account_id') is not None:
   bind(request['account_id'],token,result['email'])
   result={'ok':True,'account_id':request['account_id'],'profile':token}
  print(json.dumps(result),flush=True)
if __name__=='__main__':
 try:asyncio.run(main())
 except Exception as e:
  print(json.dumps({'error':str(e) if isinstance(e,ValueError) else type(e).__name__}));raise SystemExit(1)
