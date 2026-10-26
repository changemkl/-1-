const{test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
test('independent sync requires authorization, limits workflow selection and correlates its own run',async()=>{
 const{createSyncService}=await import('../sync-service/server.mjs');const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sync-service-test-'));let now=Date.now(),requestId,matching=false;const calls=[];
 const env={GITHUB_TOKEN:'private-github-test-token',SYNC_ACCESS_CODE:'test-access-code-1234',SYNC_SESSION_SECRET:'long-test-session-signing-secret-123456',ALLOWED_ORIGIN:'https://example.test',DATA_DIR:dir};
 const fetcher=async(url,init)=>{calls.push({url,init});if(init.method==='POST'){requestId=JSON.parse(init.body).inputs.request_id;return new Response(null,{status:204});}return Response.json({workflow_runs:[{id:1,display_title:'Other task',status:'completed',conclusion:'success'},...(matching?[{id:2,display_title:'Work log sync · '+requestId,status:'completed',conclusion:'success'}]:[])]});};
 const server=createSyncService({env,fetcher,now:()=>now});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base='http://127.0.0.1:'+server.address().port;
 try{
  let r=await fetch(base+'/api/sync/jobs',{method:'POST',headers:{Origin:'https://other.test'},body:'{}'});assert.equal(r.status,403);
  r=await fetch(base+'/api/sync/jobs',{method:'POST',body:'{"kind":"logs"}'});assert.equal(r.status,401);
  r=await fetch(base+'/api/sync/session',{method:'POST',body:JSON.stringify({accessCode:env.SYNC_ACCESS_CODE})});const{token}=await r.json();assert(token&&!token.includes(env.GITHUB_TOKEN));const headers={Authorization:'Bearer '+token};
  r=await fetch(base+'/api/sync/jobs',{method:'POST',headers,body:'{"kind":"arbitrary-workflow"}'});assert.equal(r.status,400);
  r=await fetch(base+'/api/sync/jobs',{method:'POST',headers,body:'{"kind":"logs"}'});assert.equal(r.status,202);const job=await r.json();assert.equal(job.id,requestId);assert.match(calls[0].url,/read-worklogs.yml\/dispatches$/);
  r=await fetch(base+'/api/sync/jobs/'+job.id,{headers});assert.equal((await r.json()).status,'queued');
  matching=true;now+=11000;r=await fetch(base+'/api/sync/jobs/'+job.id,{headers});assert.equal((await r.json()).status,'completed');
  const store=fs.readFileSync(path.join(dir,'jobs.json'),'utf8');assert(!store.includes(env.GITHUB_TOKEN));assert(!store.includes(env.SYNC_ACCESS_CODE));
  now+=3600000;r=await fetch(base+'/api/sync/jobs/'+job.id,{headers});assert.equal(r.status,401);
 }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));fs.rmSync(dir,{recursive:true});}
});
