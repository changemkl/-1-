function homeRecentLogs(customers,getRows,today){
 return customers.flatMap(customer=>getRows(customer).filter(row=>/^\d{4}-\d{2}-\d{2}$/.test(row.workDate||'')&&row.workDate<=today).map(row=>({customer,row}))).sort((a,b)=>b.row.workDate.localeCompare(a.row.workDate)||String(a.row.id).localeCompare(String(b.row.id))).slice(0,5);
}
function homeUpcomingPurchases(customers,getRows){
 const seen=new Set();
 return customers.flatMap(customer=>getRows(customer).map(row=>({customer,row}))).filter(({row})=>/采购意向|招标意向|采购公告|招标公告|磋商公告|询价公告|谈判公告/.test(row.stage||'')).filter(({customer,row})=>{const key=JSON.stringify([customer[0],row.notice_url||row.url,row.name]);if(seen.has(key))return false;seen.add(key);return true;}).sort((a,b)=>(a.row.planned_purchase||a.row.deadline?.value||'9999').localeCompare(b.row.planned_purchase||b.row.deadline?.value||'9999')).slice(0,5);
}
if(typeof module!=='undefined')module.exports={homeRecentLogs,homeUpcomingPurchases};
if(typeof window!=='undefined')(()=>{
 const root=document.getElementById('business-overview');let logs=[],purchases=[];
 const decode=value=>{const node=document.createElement('textarea');node.innerHTML=value||'';return node.value;};
 const esc=syncEscape;
 let active='logs',trigger,closeTimer;
 root.innerHTML='<div class="home-entry-bar"><button type="button" data-home-open="logs" aria-haspopup="dialog">◷ 最新动态 <span>↗</span></button></div>';
 const overlay=document.createElement('div');overlay.className='org-overlay home-overview-overlay';overlay.hidden=true;
 overlay.innerHTML='<section class="org-drawer home-overview-drawer" role="dialog" aria-modal="true" aria-labelledby="home-overview-title"><header class="org-header"><div><span>最新动态</span><h2 id="home-overview-title">客户新动态</h2></div><button type="button" class="org-close" aria-label="关闭最新动态">×</button></header><div class="home-drawer-tabs" role="tablist" aria-label="动态类型"><button type="button" role="tab" id="home-tab-logs" data-home-tab="logs" aria-controls="home-drawer-panel">客户新动态</button><button type="button" role="tab" id="home-tab-purchases" data-home-tab="purchases" aria-controls="home-drawer-panel">近期采购</button></div><div class="org-content" id="home-drawer-panel" role="tabpanel"></div></section>';
 document.body.append(overlay);const panel=overlay.querySelector('#home-drawer-panel');
 function close(immediate=false){overlay.classList.remove('is-open');document.body.classList.remove('org-open');clearTimeout(closeTimer);if(immediate)overlay.hidden=true;else{closeTimer=setTimeout(()=>overlay.hidden=true,260);trigger?.focus();}}
 function open(type,source){active=type;trigger=source;clearTimeout(closeTimer);render();overlay.hidden=false;document.body.classList.add('org-open');requestAnimationFrame(()=>overlay.classList.add('is-open'));overlay.querySelector('.org-close').focus();}
 root.addEventListener('click',e=>{const button=e.target.closest('[data-home-open]');if(button)open(button.dataset.homeOpen,button);});

 function render(){
  const customers=views[0].items,today=shanghaiDate();
  logs=homeRecentLogs(customers,c=>typeof customerWorklogsFor==='function'?customerWorklogsFor(c):[],today);
  purchases=homeUpcomingPurchases(customers,c=>visibleProjectsFor(c).filter(r=>safeSource(r.notice_url||r.url)));
  const feedHTML=`<div class="home-overview-heading"><h2>近期业务动态</h2></div><div class="home-overview-grid"><section class="home-feed" aria-labelledby="home-log-title"><header><span class="home-feed-icon" aria-hidden="true">◷</span><h3 id="home-log-title">客户新动态</h3><span class="home-feed-subtitle">最近工作记录</span></header><div class="home-feed-list">${logs.length?logs.map(({customer,row},i)=>`<button type="button" class="home-feed-item" data-home-log="${i}"><span class="home-feed-meta"><strong>${esc(decode(customer[0]))}</strong><time>${esc(row.workDate)}</time></span>${row.title?`<span class="home-feed-project">${esc(row.title)}</span>`:''}<span class="home-feed-excerpt">${esc(row.content)}</span><span class="home-feed-bottom">${esc(row.actorName||row.sourceLabel||(row.sourceType==='manual'?'人工录入':row.sourceType==='dongfeng'?'东风平台':'腾讯在线表格'))}<span>查看日志 →</span></span></button>`).join(''):`<p class="home-feed-empty">${typeof customerWorklogsReady==='function'&&customerWorklogsReady()?'暂无日期明确的工作记录':'正在加载工作记录…'}</p>`}</div></section><section class="home-feed" aria-labelledby="home-purchase-title"><header><span class="home-feed-icon procurement" aria-hidden="true">▤</span><h3 id="home-purchase-title">近期采购</h3><span class="home-feed-subtitle">按采购及截止时间排序</span></header><div class="home-feed-list">${purchases.length?purchases.map(({customer,row},i)=>{const date=row.planned_purchase||row.deadline?.value||'',label=row.planned_purchase?'计划采购':row.deadline?.value?'截止':'日期未公开';return `<div class="home-purchase-row"><button type="button" class="home-feed-item" data-home-purchase="${i}"><span class="home-feed-meta"><strong>${esc(decode(customer[0]))}</strong><span class="home-purchase-date">${esc(label)}${date?' '+esc(date):''}</span></span><span class="home-feed-project">${esc(row.name||row.title||'采购公告')}</span><span class="home-feed-bottom">${esc(row.stage)}<span>查看采购 →</span></span></button><a class="home-source-link" href="${esc(safeSource(row.notice_url||row.url))}" target="_blank" rel="noopener noreferrer">公告原文 ↗</a></div>`;}).join(''):'<p class="home-feed-empty">暂无已核实的有效采购意向或招标公告</p>'}</div></section></div>`;
  const holder=document.createElement('div');holder.innerHTML=feedHTML;
  panel.replaceChildren(holder.querySelector(active==='logs'?'[aria-labelledby="home-log-title"]':'[aria-labelledby="home-purchase-title"]'));
  overlay.querySelector('h2').textContent=active==='logs'?'客户新动态':'近期采购';
  panel.setAttribute('aria-labelledby','home-tab-'+active);
  for(const tab of overlay.querySelectorAll('[data-home-tab]')){tab.setAttribute('aria-selected',String(tab.dataset.homeTab===active));tab.tabIndex=tab.dataset.homeTab===active?0:-1;}
 }
 overlay.addEventListener('click',event=>{const log=event.target.closest('[data-home-log]'),purchase=event.target.closest('[data-home-purchase]');if(log){const item=logs[Number(log.dataset.homeLog)],row=item?.row;if(!item)return;const rawId=row.projectIds?.[0]||row.projectId||'__customer__',project=customerWorklogProjectsFor(item.customer).find(p=>p.id===rawId||p.aliasIds?.includes(rawId)),id=project?.id||rawId;close(true);openCustomerDetail(item.customer,{section:'logs',projectId:id},trigger);}if(purchase){const item=purchases[Number(purchase.dataset.homePurchase)];if(item){close(true);openCustomerDetail(item.customer,{section:'procurement'},trigger);}}});
 overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('.org-close'))close();const tab=e.target.closest('[data-home-tab]');if(tab){active=tab.dataset.homeTab;render();}});
 overlay.addEventListener('keydown',e=>{
  if(e.key==='Escape'){e.preventDefault();close();return;}
  if(e.target.matches('[data-home-tab]')&&['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();active=e.key==='Home'?'logs':e.key==='End'?'purchases':active==='logs'?'purchases':'logs';render();overlay.querySelector('[aria-selected="true"]').focus();return;}
  if(e.key==='Tab'){const focusable=[...overlay.querySelectorAll('button:not([tabindex="-1"]),a')].filter(el=>el.getClientRects().length),first=focusable[0],last=focusable.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}
 });
 for(const event of ['customers-updated','public-profiles-updated','worklogs-updated','manual-records-updated'])window.addEventListener(event,render);
 render();setInterval(render,60000);
})();
