/* Per-browser read state; compare business content, never sync/check timestamps. */
function updateContent(value){
 const ignored=new Set(['updatedAt','updated_at','fetched_at','checkedAt','firstSeenAt','lastSeenAt','lastRun','lastCheck','coverage','procurementSources','finished_at','recordUpdatedDate','sourceRow','cell','column']);
 if(Array.isArray(value))return value.map(updateContent).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
 if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().filter(k=>!ignored.has(k)).map(k=>[k,updateContent(value[k])]));
 return value;
}
function trackCustomerUpdate(state,id,source,value){
 const text=JSON.stringify(updateContent(value));let a=2166136261,b=5381;for(let i=0;i<text.length;i++){a=Math.imul(a^text.charCodeAt(i),16777619);b=Math.imul(b,33)^text.charCodeAt(i);}const signature=(a>>>0).toString(16)+':'+(b>>>0).toString(16)+':'+text.length;
 const row=state[id]||(state[id]={sources:{},unread:false});
 if(Object.hasOwn(row.sources,source)&&row.sources[source]!==signature)row.unread=true;
 row.sources[source]=signature;return row;
}
if(typeof module!=='undefined')module.exports={updateContent,trackCustomerUpdate};
if(typeof window!=='undefined')(()=>{
 const key='customer-update-read-state-v1';let state={},busy=false;
 try{state=JSON.parse(localStorage.getItem(key)||'{}');if(!state||Array.isArray(state)||typeof state!=='object')state={};}catch{state={};}
 let initialized=Object.keys(state).length>0;
 const save=()=>{try{localStorage.setItem(key,JSON.stringify(state));}catch{}};
 window.customerHasUpdate=c=>Boolean(state[customerIdentifier(c)]?.unread);
 function paint(){document.querySelectorAll('.customer-card').forEach(card=>{const unread=Boolean(state[decodeURIComponent(card.dataset.customerKey)]?.unread);card.classList.toggle('has-unread-update',unread);let badge=card.querySelector('.customer-update-badge');if(unread&&!badge){badge=document.createElement('span');badge.className='customer-update-badge';badge.textContent='有更新';card.querySelector('.card-top').append(badge);}if(!unread)badge?.remove();});}
 window.markCustomerUpdatesRead=c=>{const row=state[customerIdentifier(c)];if(row){row.unread=false;save();paint();}};
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
  try{await Promise.allSettled(files.map(async file=>{const response=await fetch(new URL('./'+file+'.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(!response.ok)return;const data=await response.json();for(const c of views[0].items){const id=customerIdentifier(c),isNew=initialized&&!state[id];const row=trackCustomerUpdate(state,id,file,rowsFor(data,file,c));if(isNew)row.unread=true;}}));manual();initialized=true;save();paint();}finally{busy=false;}}
 function manual(){if(typeof manualFor!=='function')return;for(const c of views[0].items)trackCustomerUpdate(state,customerIdentifier(c),'manual',['person','project','log'].flatMap(type=>manualFor(c,type)));save();paint();}
 new MutationObserver(paint).observe(document.getElementById('cards'),{childList:true});
 window.addEventListener('customers-updated',refresh);window.addEventListener('manual-records-updated',manual);
 window.addEventListener('storage',e=>{if(e.key===key){try{state=JSON.parse(e.newValue||'{}');paint();}catch{}}});
 refresh();setInterval(refresh,60000);
})();
