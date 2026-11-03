function homeRecentLogs(customers,getRows,today){
 return customers.flatMap(customer=>getRows(customer).filter(row=>/^\d{4}-\d{2}-\d{2}$/.test(row.workDate||'')&&row.workDate<=today).map(row=>({customer,row}))).sort((a,b)=>b.row.workDate.localeCompare(a.row.workDate)||String(a.row.id).localeCompare(String(b.row.id))).slice(0,5);
}
function homeUpcomingPurchases(customers,getRows){
 const seen=new Set();
 return customers.flatMap(customer=>getRows(customer).map(row=>({customer,row}))).filter(({row})=>/采购意向|招标意向|采购公告|招标公告|磋商公告|询价公告|谈判公告/.test(row.stage||'')).filter(({customer,row})=>{const key=JSON.stringify([customer[0],row.notice_url||row.url,row.name]);if(seen.has(key))return false;seen.add(key);return true;}).sort((a,b)=>(a.row.planned_purchase||a.row.deadline?.value||'9999').localeCompare(b.row.planned_purchase||b.row.deadline?.value||'9999')).slice(0,5);
}
function weeklyUpdateDays(events,today){
 const now=new Date(today+'T00:00:00Z'),monday=new Date(now);monday.setUTCDate(now.getUTCDate()-(now.getUTCDay()+6)%7);
 const dated=events.flatMap(e=>{
  if(!['工作日志','商机进展'].includes(e.label)||!e.items?.length)return [e];
  return e.items.map((item,i)=>{const r=item.record||{};const sourceDate=r.workDate||r.recordUpdatedDate||(r.updatedAt?new Date(r.updatedAt).toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'}):null);return {...e,id:e.id+':'+i,date:/^\d{4}-\d{2}-\d{2}$/.test(sourceDate||'')?sourceDate:e.date,recordDated:!!sourceDate,items:[item]};});
 });
 const merged=new Map();
 for(const e of dated){
  if(!['工作日志','商机进展'].includes(e.label)||!e.items?.length){merged.set(e.id,e);continue;}
  for(const item of e.items){const r=item.record||{},ids=r.projectIds?.length?r.projectIds:[r.projectId||(e.label==='商机进展'?r.id:null)||item.key];
   for(const id of ids){const key=JSON.stringify([e.date,e.customerId,id]);let group=merged.get(key);if(!group){group={...e,id:key,label:'商机进展',title:r.projectName||r.name||r.title?.split(' · ')[0]||'客户工作更新',items:[],compactProject:true};merged.set(key,group);}
    const source=r.attributionRecordId||r.sourceRecordId||r.id||item.key;
    if(!group.items.some(x=>(x.record.attributionRecordId||x.record.sourceRecordId||x.record.id||x.key)===source))group.items.push({...item,record:{...r,name:group.title,latestProgress:r.latestProgress||r.content||''}});
   }
  }
 }
 return Array.from({length:7},(_,i)=>{const d=new Date(monday);d.setUTCDate(monday.getUTCDate()+i);const date=d.toISOString().slice(0,10);return {date,weekday:['周一','周二','周三','周四','周五','周六','周日'][i],events:[...merged.values()].filter(e=>e.date===date&&e.date<=today).sort((a,b)=>b.detectedAt.localeCompare(a.detectedAt))};});
}
function changedUpdateMarkup(event,esc){
 const items=Array.isArray(event.items)?event.items:[];
 if(!items.length)return '<p class="home-feed-empty">这条旧动态未保存具体变更明细。</p>';
 const value=v=>v&&typeof v==='object'?v.value??'':v??'';
 const provenance=r=>{
  const kind=(r.sourceRecordId||'').split(':')[0];
  const method=r.recordMethod||({daily:'日志 · 每日进展登记',event:'操作记录 · '+(r.title?.split(' · ').slice(1).join(' · ')||'平台事件'),progress:'项目记录 · 最新进展',report:'项目报告',visit:'拜访记录',worklog:'工作日志',bid:'投标记录'}[kind])||(r.sourceType==='manual'?'人工录入':r.columnHeader?'腾讯表格 · '+r.columnHeader:'记录形式未明确');
  return `记录人：${r.actorName?esc(r.actorName)+(r.actorRole?'（'+esc(r.actorRole)+'）':''):'未明确'} · ${esc(method)}`;
 };
 if(event.label==='商机进展')return items.map(item=>{const r=item.record||{};return `<article class="weekly-changed-record"><strong>${esc(r.name||r.projectName||'未命名项目')}</strong><small style="display:block;margin-top:6px">${provenance(r)}</small><p class="worklog-text">${esc(r.latestProgress||'暂无进展正文')}</p></article>`;}).join('');
 const link=(url,title)=>/^https?:\/\//i.test(url||'')?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(title)} ↗</a>`:esc(title);
 const isLog=event.label==='工作日志',groups=new Map();
 for(const item of items){const r=item.record||{},name=isLog?r.projectName||r.title?.split(' · ')[0]||'客户日常工作':r.projectName||r.name||r.title||'未命名项目';const key=isLog?(r.projectIds?.join('|')||r.projectId||name):item.key;if(!groups.has(key))groups.set(key,{name,items:[]});groups.get(key).items.push(item);}
 return [...groups.values()].map(group=>`<section class="weekly-changed-project"><header><strong>${esc(group.name)}</strong><small>${group.items.length} 条变更</small></header><div class="weekly-changed-body">${group.items.map(item=>{const r=item.record||{},date=isLog?r.workDate:r.planned_purchase||value(r.deadline)||r.date||r.published_at;const heading=isLog?provenance(r):link(r.notice_url||r.url,r.title||r.name||r.projectName||group.name);const suppliers=(r.awards||[]).flatMap(a=>a.suppliers||[]);return `<article class="weekly-changed-record"><div class="weekly-change-meta"><span>${esc(item.change)}</span><time>${esc(date||(isLog?'工作日期未明确':'日期未公开'))}</time></div><p>${heading}</p>${isLog?`<p class="worklog-text">${esc(r.content||'')}</p>`:`${r.stage?`<p>${esc(r.stage)}</p>`:''}${suppliers.length?`<p>中标供应商：${esc([...new Set(suppliers)].join('、'))}</p>`:''}${r.status?`<p>${esc(r.status)}</p>`:''}${r.term?`<p>服务期限：${esc(value(r.term))}</p>`:''}`}</article>`;}).join('')}</div></section>`).join('');
}
if(typeof module!=='undefined')module.exports={homeRecentLogs,homeUpcomingPurchases,weeklyUpdateDays,changedUpdateMarkup};
if(typeof window!=='undefined')(()=>{
 const root=document.getElementById('business-overview'),esc=syncEscape;let events=[],loaded=false,failed=false,initializedAt='',trigger,closeTimer;const expanded=new Map();let manualEvents=[];try{manualEvents=JSON.parse(localStorage.getItem('customer-manual-update-journal-v1')||'[]');if(!Array.isArray(manualEvents))manualEvents=[];}catch{}
 const allEvents=()=>[...events,...manualEvents];
 root.innerHTML='<div class="home-entry-bar"><button type="button" data-home-open aria-haspopup="dialog">◷ 最新动态 <span>↗</span></button></div>';
 const overlay=document.createElement('div');overlay.className='org-overlay home-overview-overlay';overlay.hidden=true;
 overlay.innerHTML='<section class="org-drawer home-overview-drawer" role="dialog" aria-modal="true" aria-labelledby="home-overview-title"><header class="org-header"><div><span>本周更新</span><h2 id="home-overview-title">最新动态</h2></div><button type="button" class="org-close" aria-label="关闭最新动态">×</button></header><div class="org-content" id="home-drawer-panel"></div></section>';
 document.body.append(overlay);const panel=overlay.querySelector('#home-drawer-panel');
 function close(immediate=false){overlay.classList.remove('is-open');document.body.classList.remove('org-open');clearTimeout(closeTimer);if(immediate)overlay.hidden=true;else{closeTimer=setTimeout(()=>overlay.hidden=true,260);trigger?.focus();}}
 function updateMarkup(e,customer){
  if(e.compactProject){
   const rows=new Map();
   for(const item of e.items){const r=item.record,text=(r.latestProgress||r.content||'').replace(/^(?:工作内容[：:]\s*)?(?:本日进展[：:]\s*)?/,'').trim();const key=text.replace(/\s+/g,'');if(!key)continue;let row=rows.get(key);if(!row){row={text,people:new Set(),methods:new Set()};rows.set(key,row);}if(r.actorName)row.people.add(r.actorName+(r.actorRole?'（'+r.actorRole+'）':''));row.methods.add(r.recordMethod||((r.sourceRecordId||'').startsWith('daily:')?'日志 · 每日进展登记':r.title?.split(' · ').slice(1).join(' · ')||'项目记录'));}
   return `<section class="weekly-update-entry"><header><span class="home-feed-meta"><strong>${esc(e.customerName)}</strong></span><p class="home-feed-project">${esc(e.title)}</p></header><div class="weekly-log-body">${[...rows.values()].map(r=>`<article class="weekly-changed-record"><small>记录人：${esc([...r.people].join('、')||'未明确')} · ${esc([...r.methods].join('、'))}</small><p class="worklog-text">${esc(r.text)}</p></article>`).join('')||'<p class="home-feed-empty">暂无进展正文</p>'}</div></section>`;
  }
  const meta=`<span class="home-feed-meta"><strong>${esc(e.customerName)}</strong><time>${e.recordDated?'东风记录':esc(e.detectedAt.slice(11,16))}</time></span><span class="home-feed-project">${esc(e.title)}</span>`;
  if(['工作日志','商机进展','采购意向与招标','历史招标结果','合同信息'].includes(e.label))return `<section class="weekly-update-entry"><header>${meta}<span class="home-feed-bottom">${esc(e.label)}</span></header><div class="weekly-log-body">${changedUpdateMarkup(e,esc)}</div></section>`;
  return `<button type="button" class="home-feed-item" data-home-update="${esc(e.id)}">${meta}<span class="home-feed-bottom">${esc(e.label)}<span>查看详情 →</span></span></button>`;
 }
 function render(){
  const customers=new Map(views[0].items.map(c=>[customerIdentifier(c),c]));
  const valid=allEvents().filter(e=>{const c=customers.get(e.customerId);if(!c)return false;const node=document.createElement('textarea');node.innerHTML=c[0];return node.value===e.customerName;});
  const today=shanghaiDate(),days=weeklyUpdateDays(valid,today);
  panel.innerHTML=`<p class="weekly-range">${esc(days[0].date)} — ${esc(days.at(-1).date)}</p>${failed?'<p class="org-unconfirmed">更新记录暂时无法刷新，保留已加载内容。</p>':''}${!loaded&&!failed?'<p class="org-empty">正在读取本周更新…</p>':days.map(day=>`<details class="weekly-update-day" data-update-day="${day.date}" ${(expanded.has(day.date)?expanded.get(day.date):day.events.length>0)?'open':''}><summary><strong>${day.date.slice(5).replace('-','月')}日 ${day.weekday}${day.date===today?' · 今天':''}</strong><small>${day.events.length?day.events.length+' 条更新':'暂无更新'}</small></summary><div class="weekly-update-list">${day.events.length?day.events.map(e=>updateMarkup(e,customers.get(e.customerId))).join(''):'<p class="home-feed-empty">暂无更新</p>'}</div></details>`).join('')}${initializedAt?`<p class="weekly-record-start">从 ${esc(initializedAt.slice(0,10))} 起记录 · 工作日志按东风记录日期归档（北京时间）</p>`:''}`;
 }
 async function refresh(){try{const response=await fetch(new URL('./customer-updates.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(!response.ok)throw Error();const data=await response.json();if(!Array.isArray(data.events))throw Error();events=data.events;initializedAt=data.initializedAt||'';loaded=true;failed=false;}catch{failed=true;}render();}
 root.addEventListener('click',e=>{const button=e.target.closest('[data-home-open]');if(!button)return;trigger=button;clearTimeout(closeTimer);render();overlay.hidden=false;document.body.classList.add('org-open');requestAnimationFrame(()=>overlay.classList.add('is-open'));overlay.querySelector('.org-close').focus();refresh();});
 panel.addEventListener('toggle',e=>{if(e.target.matches('[data-update-day]'))expanded.set(e.target.dataset.updateDay,e.target.open);},true);
 overlay.addEventListener('click',e=>{
  if(e.target===overlay||e.target.closest('.org-close')){close();return;}
  const button=e.target.closest('[data-home-update]');if(!button)return;const event=allEvents().find(r=>r.id===button.dataset.homeUpdate),customer=views[0].items.find(c=>customerIdentifier(c)===event?.customerId);if(!customer)return;
  const label=event.label,options=label==='工作日志'||label==='商机进展'?{section:'logs'}:/采购|合同|历史招标/.test(label)?{section:'procurement',purchaseTab:label==='历史招标结果'||label==='合同信息'?'history':'current'}:{section:'trees',treeTab:label==='生态伙伴'?'industry':label==='产品与场景'?'scenes':'organization'};
  close(true);openCustomerDetail(customer,options,trigger);
 });
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();return;}if(e.key==='Tab'){const a=[...overlay.querySelectorAll('button,summary,a')].filter(el=>el.getClientRects().length),first=a[0],last=a.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
 window.addEventListener('customer-manual-update',e=>{manualEvents=[...manualEvents,e.detail].filter(r=>r.date>=new Date(Date.now()-35*86400000).toISOString().slice(0,10));try{localStorage.setItem('customer-manual-update-journal-v1',JSON.stringify(manualEvents));}catch{}render();});
 window.addEventListener('worklogs-updated',()=>{if(!overlay.hidden)render();});
 window.addEventListener('customers-updated',render);refresh();setInterval(refresh,60000);
})();
