/* Shared published business data; never use collection timestamps as work dates. */
(function(root){
 function today(now=new Date()){const p=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);return ['year','month','day'].map(k=>p.find(x=>x.type===k).value).join('-');}
 function validDate(s){if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(s))return false;const d=new Date(s+'T00:00:00Z');return Number.isFinite(+d)&&d.toISOString().slice(0,10)===s;}
 function customers(rows){const h=rows.findIndex(r=>r.includes('客户名称'));if(h<0)throw Error('客户列表格式不正确');const cols=rows[h],at=(r,k)=>String(r[cols.indexOf(k)]||'').trim();return rows.slice(h+1).filter(r=>at(r,'客户名称')).map(r=>{const name=at(r,'客户名称');return {id:at(r,'集团编号')||'name:'+name.normalize('NFKC').toLowerCase().replace(/\s+/g,''),name,tags:at(r,'客户标签'),category:({'中国建筑第八工程局有限公司':'国企','水利部太湖流域管理局':'政府'})[name]||at(r,'客户类别')||'未分类'};});}
 function dated(entries,customer,cutoff=today()){
 const unique=new Map();
 for(const r of entries){if(r.customerId!==customer.id||r.customerName!==customer.name||!validDate(r.workDate)||r.workDate>cutoff||typeof r.content!=='string'||!r.content.trim())continue;
 if(/重复.*(?:关闭|关单)|(?:关闭|关单).*重复/.test((r.title||'')+' '+r.content))continue;
 const key=[r.workDate,(r.projectIds||[r.projectId]).filter(Boolean).sort().join(','),r.content.trim(),r.actorName||''].join('|');if(!unique.has(key))unique.set(key,r);}
 const list=[...unique.values()].sort((a,b)=>b.workDate.localeCompare(a.workDate)||String(a.id||'').localeCompare(String(b.id||'')));
 return list;
 }
 function latest(entries,customer,cutoff=today()){const list=dated(entries,customer,cutoff);return list.filter(r=>r.workDate===list[0]?.workDate);}
 function monthStart(cutoff=today()){
 const [y,m,d]=cutoff.split('-').map(Number),last=new Date(Date.UTC(y,m-1,0)).getUTCDate();
 return new Date(Date.UTC(y,m-2,Math.min(d,last))).toISOString().slice(0,10);
 }
 function recentGroups(entries,projects,customer,cutoff=today()){
 const start=monthStart(cutoff),groups=new Map(),aliases=new Map(),known=new Map();
 for(const p of projects.filter(p=>p.customerId===customer.id&&p.customerName===customer.name)){known.set(p.id,p);for(const id of [p.id,...(p.aliasIds||[])])aliases.set(id,p.id);}
 for(const r of dated(entries,customer,cutoff).filter(r=>r.workDate>=start)){
 const ids=[...new Set((r.projectIds||[r.projectId]).filter(Boolean).map(id=>aliases.get(id)||id))];
 for(const id of ids.length?ids:['__customer__']){
 const p=known.get(id),ref=r.projectRefs?.[id];
 if(!groups.has(id))groups.set(id,{id,name:p?.name||ref?.name||r.projectName||(id==='__customer__'?'客户日常工作／待关联商机':r.title?.split(' · ')[0]||'商机名称待补充'),type:p?.type||r.projectTypes?.[id]||r.projectType||'',status:p?.status||'',rows:[]});
 const g=groups.get(id);if(!g.rows.some(x=>x.workDate===r.workDate&&x.content.trim()===r.content.trim()&&(x.actorName||'')===(r.actorName||'')))g.rows.push(r);
 }
 }
 return [...groups.values()].sort((a,b)=>Number(a.id==='__customer__')-Number(b.id==='__customer__')||b.rows[0].workDate.localeCompare(a.rows[0].workDate)||a.name.localeCompare(b.name,'zh-CN'));
 }
 const api={today,validDate,customers,latest,monthStart,recentGroups};if(typeof module!=='undefined')module.exports=api;else root.MobileData=api;
})(typeof window==='undefined'?globalThis:window);
