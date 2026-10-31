import {GeminiWebPlugin as Base} from './vendor/gemini-web/index.mjs';
import {imageFetch,python} from './lib/bridge.mjs';
import {ensureBackend} from './vendor/gemini-web/lib/native.mjs';
import {importCookie} from './vendor/gemini-web/lib/setup.mjs';
const IMAGE='gemini-web-pro-image';
export const GeminiWebAll=async(input,options={})=>{
 const p=await Base(input,options);
 const config=p.config;p.config=async c=>{await config(c);c.provider['gemini-web'].name='Gemini-web-all';};
 const models=p.provider.models;p.provider.models=async(provider,context)=>{
  const result=await models(provider,context);
  if(context?.auth?.type==='api')result[IMAGE]={id:IMAGE,providerID:'gemini-web',name:'Gemini 官网生图 · Pro（原图）',api:{id:IMAGE,url:context.auth.metadata?.baseURL||'http://127.0.0.1:8083/v1',npm:'@ai-sdk/google'},limit:{context:32768,output:8192},capabilities:{temperature:false,reasoning:false,attachment:true,toolcall:false,input:{text:true,image:true},output:{text:true,image:true}},cost:{input:0,output:0,cache:{read:0,write:0}},options:{},headers:{},variants:{},status:'active'};
  return result;
 };
 const loader=p.auth.loader;p.auth.loader=async(...args)=>{
  const loaded=await loader(...args);const original=loaded.fetch;
  loaded.fetch=async(input,init)=>{
   const url=typeof input==='string'?input:input.url||String(input);
   if(/\/models\/gemini-web-pro-image:(?:streamGenerateContent|generateContent)/.test(url)){
    const auth=await args[0]();return imageFetch(input,init,auth?.metadata?.account);
   }
   return original(input,init);
  };return loaded;
 };
 p.auth.methods.unshift({type:'oauth',label:'自动获取 Cookie（独立登录窗口）',async authorize(){return {url:'',method:'auto',instructions:'在独立窗口完成Google登录，插件自动接收登录态；无需复制Cookie。完成后窗口关闭。',async callback(){try{const local=await ensureBackend();const result=await python('login.py',{},600000);const added=await importCookie(local,result.cookie);return {type:'success',key:local.apiKey,metadata:{baseURL:local.baseURL,account:added.id,email:result.email||undefined}};}catch(e){return {type:'failed',error:e.message};}}};}});
 return p;
};
export {AIStudioPlugin} from './vendor/gemini-web/lib/studio.mjs';
export default GeminiWebAll;
