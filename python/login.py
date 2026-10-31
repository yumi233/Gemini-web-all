"""Interactive login only; captures cookies from its own isolated browser context."""
import asyncio,json,os,tempfile,time
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
 async with async_playwright() as pw:
  with tempfile.TemporaryDirectory(prefix='gemini-login-',dir=os.environ['GEMINI_WEB_ALL_RUNTIME']) as profile:
   browser=await pw.chromium.launch_persistent_context(profile,executable_path=executable(),headless=False,args=['--disable-blink-features=AutomationControlled'],ignore_default_args=['--enable-automation'])
   try:
    page=browser.pages[0] if browser.pages else await browser.new_page()
    await page.goto('https://gemini.google.com/app',wait_until='domcontentloaded')
    for _ in range(285):
     if not browser.pages:raise ValueError('Login window closed')
     cookies=await browser.cookies(['https://gemini.google.com','https://accounts.google.com'])
     values={c['name']:c['value'] for c in cookies if c['domain'].lstrip('.') in ['google.com','gemini.google.com','accounts.google.com']}
     if values.get('__Secure-1PSID') and any('gemini.google.com/app' in p.url for p in browser.pages):
      await asyncio.sleep(3)
      cookies=await browser.cookies(['https://gemini.google.com'])
      values={c['name']:c['value'] for c in cookies if c['domain'].lstrip('.') in ['google.com','gemini.google.com']}
      print(json.dumps({'cookie':'; '.join(f'{k}={v}' for k,v in values.items())}),flush=True);return
     await asyncio.sleep(2)
    raise ValueError('Login timed out; existing accounts were kept')
   finally:await browser.close()
if __name__=='__main__':
 try:asyncio.run(main())
 except Exception as e:
  print(json.dumps({'error':str(e) if isinstance(e,ValueError) else type(e).__name__}));raise SystemExit(1)
