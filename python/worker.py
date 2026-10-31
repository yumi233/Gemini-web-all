import asyncio,base64,json,os,sys,tempfile,time
from pathlib import Path
os.umask(0o077)
import core
async def main():
 request=json.load(sys.stdin);start=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='image-',dir=os.environ['GEMINI_WEB_ALL_RUNTIME']) as tmp:
  refs=[]
  for i,item in enumerate(request.get('images',[])):
   raw=base64.b64decode(item['data'],validate=True)
   if len(raw)>30*1024*1024:raise ValueError('Reference too large')
   p=Path(tmp)/f'ref-{i}';p.write_bytes(raw);refs.append(str(p))
  job=await core.generate_image(request['prompt'],tmp,refs,'gemini-pro',request.get('account_id'))
  if 'id' not in job:raise ValueError('Image service busy')
  await core.tasks[job['id']]
  result=await core.generation_result(job['id'])
  if result['status']!='completed':raise ValueError(result.get('error','Generation failed'))
  image=result['image'];data=Path(image['path']).read_bytes()
  print(json.dumps({'data':base64.b64encode(data).decode(),'mimeType':'image/jpeg' if data[:2]==b'\xff\xd8' else 'image/png','width':image['width'],'height':image['height'],'seconds':round(time.monotonic()-start,2)}))
try:asyncio.run(main())
except BaseException as e:
 print(json.dumps({'error':str(e) if isinstance(e,ValueError) else type(e).__name__}));sys.exit(1)
