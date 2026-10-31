"""Retry download of a saved generation; never calls generate_content."""
import asyncio,json,sys,fcntl
from pathlib import Path
from gemini_webapi.types import GeneratedImage
from core import STATE,connect,full_download,generation_result,record
async def recover(job_id):
 job=await generation_result(job_id)
 if job.get('status')=='completed' and Path(job.get('image',{}).get('path','')).is_file():return {'status':'completed','image':job['image']}
 saved=json.loads((STATE/'recovery'/(job_id+'.json')).read_text())
 lock=(STATE/f"generation-{int(saved['account_id'])}.lock").open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:
  lock.close();raise ValueError('Account busy; retry download later')
 client=None
 try:
  _,client=await connect(saved['account_id'])
  directory=STATE/'originals'/job_id;directory.mkdir(parents=True,exist_ok=True)
  image=GeneratedImage(**{k:saved[k] for k in ['cid','rid','rcid','image_id','url']})
  result=await full_download(client,image,directory,saved['account_id'])
  job.update(status='completed',image=result);record(job)
  return {'status':'completed','image':result}
 finally:
  if client:await client.close()
  fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
if __name__=='__main__':
 try:print(json.dumps(asyncio.run(recover(json.load(sys.stdin)['job_id']))))
 except Exception as e:print(json.dumps({'error':str(e) if isinstance(e,ValueError) else type(e).__name__}));sys.exit(1)
