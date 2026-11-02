/* Per-browser read state; compare business content, never sync/check timestamps. */
function updateContent(value){
 const ignored=new Set(['updatedAt','updated_at','fetched_at','checkedAt','firstSeenAt','lastSeenAt','lastRun','lastCheck','coverage','procurementSources','finished_at','recordUpdatedDate','sourceRow','cell','column']);
 if(Array.isArray(value))return value.map(updateContent).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
 if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().filter(k=>!ignored.has(k)).map(k=>[k,updateContent(value[k])]));
 return value;
}
function trackCustomerUpdate(state,id,source,value,label=source){
 const text=JSON.stringify(updateContent(value));let a=2166136261,b=5381;for(let i=0;i<text.length;i++){a=Math.imul(a^text.charCodeAt(i),16777619);b=Math.imul(b,33)^text.charCodeAt(i);}const signature=(a>>>0).toString(16)+':'+(b>>>0).toString(16)+':'+text.length;
 const row=state[id]||(state[id]={sources:{},unread:false});
 if(Object.hasOwn(row.sources,source)&&row.sources[source]!==signature){row.unread=true;row.changes=[...new Set([...(row.changes||[]),label])];}
 row.sources[source]=signature;return row;
}
function customerUpdateParts(file,rows){
 const pick=keys=>rows.map(r=>Object.fromEntries(keys.filter(k=>r[k]!==undefined).map(k=>[k,r[k]]))).filter(r=>Object.keys(r).length);
 if(file==='organization-data')return [['主要职能',pick(['overview','basicSource'])],['组织架构',pick(['nodes','note','source','sources','name','id'])]];
 if(file==='profile-data')return [['采购意向与招标',pick(['projects'])],['领导资料',pick(['leaders'])],['组织架构',pick(['organizations'])],['公开动态',pick(['attributes','signals'])]];
 if(file==='customer-supplements')return [['历史招标结果',pick(['results'])],['合同信息',pick(['contracts'])],['采购意向与招标',pick(['projects','notices'])],['政策与建设方向',pick(['policies'])],['主要职能',pick(['overview','basicSource'])]];
 if(file==='dongfeng-worklogs')return [['工作日志',rows.filter(r=>typeof r.content==='string')],['商机进展',rows.filter(r=>typeof r.content!=='string')]];
 const labels={'tencent-data':'客户基本信息','people-data':'领导资料','customer-system':'客户来源与状态','award-history':'历史招标结果','cooperation-partners':'生态伙伴','dongfeng-worklogs':'工作日志与商机','worklogs':'工作日志','customer-scenes':'产品与场景'};
 return [[labels[file]||file,rows]];
}
if(typeof module!=='undefined')module.exports={updateContent,trackCustomerUpdate,customerUpdateParts};
if(typeof window!=='undefined')(()=>{
 const key='customer-update-read-state-v1';let state={},busy=false;
 try{state=JSON.parse(localStorage.getItem(key)||'{}');if(!state||Array.isArray(state)||typeof state!=='object')state={};}catch{state={};}
 let initialized=Object.keys(state).length>0;
 const save=()=>{try{localStorage.setItem(key,JSON.stringify(state));}catch{}};
 window.customerHasUpdate=c=>Boolean(state[customerIdentifier(c)]?.unread);
 function paint(){
  if(view===0){const expected=filtered().map(c=>encodeURIComponent(cardCustomerKey(c))),current=[...document.querySelectorAll('.customer-card')].map(c=>c.dataset.customerKey);if(expected.length!==current.length||expected.some((id,i)=>id!==current[i])){renderCards();return;}}
  document.querySelectorAll('.customer-card').forEach(card=>{
  const row=state[decodeURIComponent(card.dataset.customerKey)],unread=Boolean(row?.unread);
  card.classList.toggle('has-unread-update',unread);
  let badges=card.querySelector('.customer-update-notices');
  const labels=unread?(row.changes?.length?row.changes:['此前更新（类型未记录）']):[];
  const text=labels.map(label=>label==='新增客户'||label.startsWith('此前更新')?label:label+'更新').join('、');
  if(!unread){badges?.remove();return;}
  if(!badges){badges=document.createElement('div');badges.className='customer-update-notices';badges.setAttribute('aria-label','未读更新');card.querySelector('h3').after(badges);}
  if(badges.getAttribute('data-summary')===text)return;
  badges.setAttribute('data-summary',text);badges.replaceChildren(...labels.map(label=>{const badge=document.createElement('span');badge.className='customer-update-badge';badge.textContent=label==='新增客户'||label.startsWith('此前更新')?label:label+'更新';return badge;}));
 });}
 window.markCustomerUpdatesRead=c=>{const row=state[customerIdentifier(c)];if(row){row.unread=false;row.changes=[];save();paint();}};
 const files=['tencent-data','profile-data','customer-supplements','organization-data','people-data','customer-system','award-history','cooperation-partners','dongfeng-worklogs','worklogs','customer-scenes'];
 function rowsFor(data,file,c){
  const id=customerIdentifier(c),name=new DOMParser().parseFromString(c[0],'text/html').body.textContent;
  if(file==='tencent-data'){
   const rows=data.rows||[],header=rows.find(r=>r.includes('客户名称')||r.includes('名称'));if(!header)return [];
   const ni=header.findIndex(s=>['客户名称','名称','单位名称'].includes(s)),ii=header.findIndex(s=>['集团编号','客户编号','ID'].includes(s));
   return rows.filter(r=>r!==header&&(ii>=0?String(r[ii])===id:String(r[ni])===name)).map(r=>Object.fromEntries(header.map((h,i)=>[h,r[i]??''])));
  }
  if(file==='cooperation-partners'){
   const results=typeof awardHistoryFor==='function'?awardHistoryFor(c):[];
   const text=JSON.stringify(results);
   return (data.partners||[]).filter(p=>[p.name,...(p.aliases||[])].some(n=>n&&text.includes(n))||JSON.stringify(p.businessLinks||[]).includes(name));
  }
  const match=r=>String(r.customerId??r.id)===id&&(!(r.customerName||r.name)||(r.customerName||r.name)===name);
  return [...(data.customers||data.profiles||data.entries||[]).filter(match),...(data.projects||[]).filter(match)];
 }
 async function refresh(){if(busy||!views[0].items.length)return;busy=true;
  try{await Promise.allSettled(files.map(async file=>{const response=await fetch(new URL('./'+file+'.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(!response.ok)return;const data=await response.json();for(const c of views[0].items){const id=customerIdentifier(c),isNew=initialized&&!state[id];for(const [label,value] of customerUpdateParts(file,rowsFor(data,file,c)))trackCustomerUpdate(state,id,file+':'+label,value,label);if(isNew){state[id].unread=true;state[id].changes=['新增客户'];}}}));manual();initialized=true;save();paint();}finally{busy=false;}}
 function manual(){if(typeof manualFor!=='function')return;for(const c of views[0].items)for(const [type,label] of [['person','重要责任人'],['project','人工项目信息'],['log','工作日志']])trackCustomerUpdate(state,customerIdentifier(c),'manual:'+type,manualFor(c,type),label);save();paint();}
 new MutationObserver(paint).observe(document.getElementById('cards'),{childList:true});
 window.addEventListener('customers-updated',refresh);window.addEventListener('manual-records-updated',manual);
 window.addEventListener('storage',e=>{if(e.key===key){try{state=JSON.parse(e.newValue||'{}');paint();}catch{}}});
 refresh();setInterval(refresh,60000);
})();
