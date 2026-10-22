const ALLOWED_FIELDS = new Set(['决策链','十五五抓手','痛点','可售能力','采购节奏','存量与竞对','下一步动作','门槛与风险','客户类别','等级','一级属地','二级属地']);
export function formatProfiles(customers, signals, attributes, runs) {
  return customers.map(c=>({id:c.id,name:c.name,attributes:attributes.filter(a=>a.customer_id===c.id&&ALLOWED_FIELDS.has(a.field)),signals:signals.filter(s=>s.customer_id===c.id),lastRun:runs.find(r=>r.customer_id===c.id)||null}));
}
export default {
  async fetch(request,env){
    const origin=request.headers.get('Origin');
    const headers={'Content-Type':'application/json; charset=utf-8','Vary':'Origin','X-Content-Type-Options':'nosniff'};
    if(origin===env.ALLOWED_ORIGIN){headers['Access-Control-Allow-Origin']=origin;}
    const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers});
    const url=new URL(request.url);
    if(request.method==='OPTIONS')return new Response(null,{status:204,headers:{...headers,'Access-Control-Allow-Methods':'GET, OPTIONS'}});
    if(request.method!=='GET')return json({error:'Method not allowed'},405);
    if(url.pathname==='/health')return json({ok:true});
    if(url.pathname!=='/api/profiles')return json({error:'Not found'},404);
    const ids=[...new Set(url.searchParams.getAll('id'))];
    if(!ids.length||ids.length>25||ids.some(id=>id.length>250))return json({error:'Supply between 1 and 25 customer identifiers'},400);
    if(!env.DB)return json({error:'Profile service not configured'},503);
    const marks=ids.map(()=>'?').join(',');
    try{
      const customers=await env.DB.prepare(`SELECT id,name FROM customers WHERE active=1 AND id IN (${marks})`).bind(...ids).all();
      const signals=await env.DB.prepare(`WITH ranked AS (SELECT s.customer_id,s.category,s.status,d.url,d.title,d.excerpt,d.published_at,d.fetched_at,ROW_NUMBER() OVER(PARTITION BY s.customer_id ORDER BY d.fetched_at DESC,s.id) AS rn FROM signals s JOIN documents d ON d.id=s.document_id WHERE s.customer_id IN (${marks}) AND s.status!='rejected') SELECT * FROM ranked WHERE rn<=10`).bind(...ids).all();
      const attributes=await env.DB.prepare(`SELECT customer_id,field,value,origin,updated_at FROM profile_attributes WHERE customer_id IN (${marks})`).bind(...ids).all();
      const runs=await env.DB.prepare(`WITH ranked AS (SELECT customer_id,finished_at,status,documents_found,ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY finished_at DESC) AS rn FROM crawl_runs WHERE customer_id IN (${marks})) SELECT * FROM ranked WHERE rn=1`).bind(...ids).all();
      headers['Cache-Control']='public, max-age=60';
      return json({profiles:formatProfiles(customers.results,signals.results,attributes.results,runs.results)});
    }catch{return json({error:'Profile query unavailable'},503);}
  }
};
