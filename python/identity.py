import asyncio,json,re,sys
from core import connect
async def main():
 aid=json.load(sys.stdin)['account_id'];_,client=await connect(aid)
 try:
  response=await client.client.get('https://gemini.google.com/app')
  match=re.search(r'"oPEP7c":"([^"@\s]+@[^"\s]+)"',response.text)
  print(json.dumps({'email':match.group(1) if match else None}))
 finally:await client.close()
try:asyncio.run(main())
except Exception as e:print(json.dumps({'error':type(e).__name__}));sys.exit(1)
