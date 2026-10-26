import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const workflows={customers:'sync-tencent.yml',logs:'read-worklogs.yml'};
export function createSyncService({env=process.env,fetcher=fetch,now=Date.now}={}){
 for(const k of ['GITHUB_TOKEN','SYNC_ACCESS_CODE','SYNC_SESSION_SECRET','ALLOWED_ORIGIN'])if(!env[k])throw Error('Missing configuration: '+k);
 if(env.SYNC_SESSION_SECRET.length<32||env.SYNC_ACCESS_CODE.length<12)throw Error('Use a session secret of at least 32 characters and an access code of at least 12 characters');
 const repo=env.GITHUB_REPOSITORY||'changemkl/-1-',ref=env.GITHUB_REF||'customer-workspace';
 if(!/^[\w.-]+\/[\w.-]+$/.test(repo))throw Error('Invalid repository');
 const dir=env.DATA_DIR||path.resolve('sync-service/data');fs.mkdirSync(dir,{recursive:true,mode:0o700});const store=path.join(dir,'jobs.json');
 let jobs=fs.existsSync(store)?JSON.parse(fs.readFileSync(store,'utf8')):[];const attempts=new Map();
 const save=()=>{jobs=jobs.filter(j=>now()-j.createdAt<86400000).slice(-100);fs.writeFileSync(store+'.tmp',JSON.stringify(jobs),{mode:0o600});fs.renameSync(store+'.tmp',store);};
 const sign=s=>crypto.createHmac('sha256',env.SYNC_SESSION_SECRET).update(s).digest('base64url');
 const equal=(a,b)=>{const aa=crypto.createHash('sha256').update(a).digest(),bb=crypto.createHash('sha256').update(b).digest();return crypto.timingSafeEqual(aa,bb);};
 const issue=()=>{const p=Buffer.from(JSON.stringify({exp:now()+3600000})).toString('base64url');return p+'.'+sign(p);};
 const authorized=req=>{try{const token=(req.headers.authorization||'').replace(/^Bearer /,'');const [p,s]=token.split('.');return Boolean(p&&s&&equal(s,sign(p))&&JSON.parse(Buffer.from(p,'base64url')).exp>now());}catch{return false;}};
 async function github(endpoint,init={}){const response=await fetcher('https://api.github.com/repos/'+repo+'/actions/'+endpoint,{...init,signal:AbortSignal.timeout(20000),headers:{Accept:'application/vnd.github+json',Authorization:'Bearer '+env.GITHUB_TOKEN,'X-GitHub-Api-Version':'2022-11-28','User-Agent':'CustomerWorkspaceSync','Content-Type':'application/json'}});if(!response.ok)throw Error('GitHub request failed ('+response.status+')');return response.status===204?null:response.json();}
 async function body(req){let text='';for await(const chunk of req){text+=chunk;if(text.length>4096)throw Object.assign(Error('Request too large'),{status:413});}try{return JSON.parse(text||'{}');}catch{throw Object.assign(Error('Invalid JSON'),{status:400});}}
 return http.createServer(async(req,res)=>{
  const origin=req.headers.origin;res.setHeader('Vary','Origin');res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
  const json=(data,status=200)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(data));};
  if(origin&&origin!==env.ALLOWED_ORIGIN)return json({error:'Origin not allowed'},403);
  if(origin){res.setHeader('Access-Control-Allow-Origin',origin);res.setHeader('Access-Control-Allow-Headers','Authorization, Content-Type');res.setHeader('Access-Control-Allow-Methods','GET, POST, OPTIONS');}
  if(req.method==='OPTIONS'){res.writeHead(204);return res.end();}
  const url=new URL(req.url,'http://localhost');
  if(req.method==='GET'&&url.pathname==='/health')return json({ok:true});
  try{
   if(req.method==='POST'&&url.pathname==='/api/sync/session'){
    const ip=req.socket.remoteAddress||'unknown';if(attempts.size>10000)attempts.clear();let rate=attempts.get(ip);if(!rate||now()-rate.at>60000){rate={at:now(),count:0};attempts.set(ip,rate);}if(++rate.count>10)return json({error:'Too many login attempts; try again later'},429);
    const data=await body(req);if(typeof data.accessCode!=='string'||!equal(data.accessCode,env.SYNC_ACCESS_CODE))return json({error:'Invalid sync access code'},401);
    return json({token:issue(),expiresIn:3600});
   }
   if(!authorized(req))return json({error:'Sync authorization required'},401);
   if(req.method==='POST'&&url.pathname==='/api/sync/jobs'){
    const data=await body(req);if(typeof data.kind!=='string'||!Object.hasOwn(workflows,data.kind))return json({error:'Unsupported sync operation'},400);
    const active=jobs.find(j=>j.kind===data.kind&&!['completed','failed'].includes(j.status)&&now()-j.createdAt<1800000);if(active)return json({id:active.id,status:active.status},202);
    const recent=jobs.find(j=>j.kind===data.kind&&now()-j.createdAt<30000);if(recent)return json({error:'Please wait before starting another sync'},429);
    const job={id:crypto.randomUUID(),kind:data.kind,createdAt:now(),status:'queued'};jobs.push(job);save();
    try{await github('workflows/'+workflows[job.kind]+'/dispatches',{method:'POST',body:JSON.stringify({ref,inputs:{request_id:job.id}})});}catch(e){job.status='failed';save();throw e;}
    return json({id:job.id,status:job.status},202);
   }
   const match=url.pathname.match(/^\/api\/sync\/jobs\/([a-zA-Z0-9-]+)$/);
   if(req.method==='GET'&&match){
    const job=jobs.find(j=>j.id===match[1]);if(!job)return json({error:'Sync task not found'},404);
    if(!['completed','failed'].includes(job.status)&&(!job.checkedAt||now()-job.checkedAt>10000)){
     const result=await github('workflows/'+workflows[job.kind]+'/runs?event=workflow_dispatch&per_page=50');
     const run=result.workflow_runs?.find(r=>typeof r.display_title==='string'&&r.display_title.includes(job.id));
     if(run){job.runId=run.id;job.status=run.status==='completed'?(run.conclusion==='success'?'completed':'failed'):run.status==='in_progress'?'in_progress':'queued';}
     else if(now()-job.createdAt>1800000)job.status='failed';
     job.checkedAt=now();save();
    }
    return json({id:job.id,kind:job.kind,status:job.status,createdAt:job.createdAt});
   }
   return json({error:'Not found'},404);
  }catch(e){return json({error:e.status?e.message:'Sync service unavailable; existing website data is retained'},e.status||502);}
 });
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))createSyncService().listen(Number(process.env.PORT||8788),'0.0.0.0');
