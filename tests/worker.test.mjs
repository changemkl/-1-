import test from 'node:test';
import assert from 'node:assert/strict';
import worker,{formatProfiles} from '../cloudflare/worker.mjs';
test('read API validates IDs and methods',async()=>{
 assert.equal((await worker.fetch(new Request('https://test/api/profiles'),{})).status,400);
 assert.equal((await worker.fetch(new Request('https://test/api/profiles?id=1',{method:'POST'}),{})).status,405);
 assert.equal((await worker.fetch(new Request('https://test/api/profiles?id=1'),{})).status,503);
});
test('public API groups evidence and uses parameter binding',async()=>{
 const results=[[{id:'1',name:'客户甲'}],[{customer_id:'1',category:'采购动态',status:'pending',url:'https://example.org/a',title:'采购公告'}],[{customer_id:'1',field:'痛点',value:'已核实业务问题',origin:'reviewed'}],[{customer_id:'1',status:'success',finished_at:'2026-10-22'}]];
 const DB={prepare(sql){assert.ok(sql.includes('?'));return{bind(...ids){assert.deepEqual(ids,['1']);return{async all(){return{results:results.shift()};}}}};}};
 const r=await worker.fetch(new Request('https://test/api/profiles?id=1',{headers:{Origin:'https://changemkl.github.io'}}),{DB,ALLOWED_ORIGIN:'https://changemkl.github.io'});
 assert.equal(r.status,200);assert.equal(r.headers.get('Access-Control-Allow-Origin'),'https://changemkl.github.io');
 const p=(await r.json()).profiles[0];assert.equal(p.signals[0].status,'pending');assert.equal(p.attributes[0].field,'痛点');assert.equal(p.lastRun.status,'success');
});
test('unknown attributes are not exposed as profile fields',()=>{
 const p=formatProfiles([{id:'1'}],[],[{customer_id:'1',field:'secret',value:'do not return'}],[]);
 assert.deepEqual(p[0].attributes,[]);
});
