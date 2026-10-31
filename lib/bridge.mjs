import {spawn} from 'node:child_process';
import {mkdirSync,existsSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
export const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export const runtime=process.env.GEMINI_WEB_ALL_RUNTIME||path.join(os.homedir(),'.local/share/gemini-web-all');
let ready;
function runSetup(args){return new Promise((resolve,reject)=>{const uv=existsSync(path.join(os.homedir(),'.local/bin/uv'))?path.join(os.homedir(),'.local/bin/uv'):'uv';const p=spawn(uv,args,{stdio:'ignore'});p.on('error',()=>reject(new Error('Install uv to initialize Gemini-web-all runtime')));p.on('close',code=>code?reject(new Error('Runtime dependency setup failed')):resolve());});}
async function ensureRuntime(){
 const py=path.join(runtime,'venv/bin/python');
 if(existsSync(py))return;
 ready??=(async()=>{mkdirSync(runtime,{recursive:true,mode:0o700});await runSetup(['venv',path.join(runtime,'venv'),'--python','3.12']);await runSetup(['pip','install','--python',py,'-r',path.join(root,'python/requirements.txt')]);})().catch(e=>{ready=null;throw e;});
 await ready;
}
export async function python(script,input,timeout=720000){
 await ensureRuntime();
 mkdirSync(runtime,{recursive:true,mode:0o700});
 return new Promise((resolve,reject)=>{
  const p=spawn(path.join(runtime,'venv/bin/python'),[path.join(root,'python',script)],{env:{...process.env,GEMINI_WEB_ALL_RUNTIME:runtime},stdio:['pipe','pipe','pipe']});
  let data='';let done=false;const timer=setTimeout(()=>{p.kill('SIGTERM');reject(new Error('Gemini website timed out. Do not automatically resubmit.'));},timeout);
  p.stdout.on('data',b=>{data+=b;if(data.length>80*1024*1024)p.kill();});
  p.stderr.on('data',()=>{});
  p.on('error',()=>{clearTimeout(timer);reject(new Error('Gemini-web-all runtime unavailable; run install.sh'));});
  p.on('close',code=>{clearTimeout(timer);try{const r=JSON.parse(data.trim());if(code||r.error)reject(new Error(r.error||'Website request failed'));else resolve(r);}catch{reject(new Error('Invalid backend response'));}});
  p.stdin.end(JSON.stringify(input));
 });
}
export async function imageFetch(input,init,account){
 const req=new Request(input,init);const body=await req.json();
 const parts=(body.contents||[]).flatMap(c=>c.parts||[]);
 const images=parts.filter(p=>p.inlineData||p.inline_data).map(p=>p.inlineData||p.inline_data);
 if(images.length>8)return Response.json({error:{message:'At most 8 reference images'}},{status:400});
 const prompt=parts.map(p=>p.text||'').join('\n');
 const aspect=body.generationConfig?.imageConfig?.aspectRatio;
 try{
  const r=await python('worker.py',{prompt:prompt+(aspect?`\nRequested composition aspect ratio: ${aspect}.`:''),images,account_id:account});
  const payload={candidates:[{content:{role:'model',parts:[{inlineData:{mimeType:r.mimeType,data:r.data}}]},finishReason:'STOP'}],modelVersion:'gemini-web-pro-image',geminiWebOriginal:{width:r.width,height:r.height,seconds:r.seconds}};
  return req.url.includes(':streamGenerateContent') ? new Response('data: '+JSON.stringify(payload)+'\n\n',{headers:{'Content-Type':'text/event-stream'}}) : Response.json(payload);
 }catch(e){return Response.json({error:{code:502,message:e.message}},{status:502});}
}
