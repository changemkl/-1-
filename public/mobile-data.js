/* Shared published business data; never use collection timestamps as work dates. */
(function(root){
 function today(now=new Date()){const p=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);return ['year','month','day'].map(k=>p.find(x=>x.type===k).value).join('-');}
 function validDate(s){if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(s))return false;const d=new Date(s+'T00:00:00Z');return Number.isFinite(+d)&&d.toISOString().slice(0,10)===s;}
 function customers(rows){const h=rows.findIndex(r=>r.includes('客户名称'));if(h<0)throw Error('客户列表格式不正确');const cols=rows[h],at=(r,k)=>String(r[cols.indexOf(k)]||'').trim();return rows.slice(h+1).filter(r=>at(r,'客户名称')).map(r=>{const name=at(r,'客户名称');return {id:at(r,'集团编号')||'name:'+name.normalize('NFKC').toLowerCase().replace(/\s+/g,''),name,tags:at(r,'客户标签'),category:({'中国建筑第八工程局有限公司':'国企','水利部太湖流域管理局':'政府'})[name]||at(r,'客户类别')||'未分类'};});}
 function latest(entries,customer,cutoff=today()){
 const unique=new Map();
 for(const r of entries){if(r.customerId!==customer.id||r.customerName!==customer.name||!validDate(r.workDate)||r.workDate>cutoff||typeof r.content!=='string'||!r.content.trim())continue;
 if(/重复.*(?:关闭|关单)|(?:关闭|关单).*重复/.test((r.title||'')+' '+r.content))continue;
 const key=[r.workDate,(r.projectIds||[r.projectId]).filter(Boolean).sort().join(','),r.content.trim(),r.actorName||''].join('|');if(!unique.has(key))unique.set(key,r);}
 const list=[...unique.values()].sort((a,b)=>b.workDate.localeCompare(a.workDate)||String(a.id||'').localeCompare(String(b.id||'')));
 return list.filter(r=>r.workDate===list[0]?.workDate);
 }
 const api={today,validDate,customers,latest};if(typeof module!=='undefined')module.exports=api;else root.MobileData=api;
})(typeof window==='undefined'?globalThis:window);
