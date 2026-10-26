function sortedAwardResults(rows,today){
 const unique=new Map();
 for(const row of rows){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(row.date||'')||row.date>today)continue;
  const date=new Date(row.date+'T00:00:00Z');if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==row.date||!/^https:\/\//.test(row.url||''))continue;
  let url;try{url=new URL(row.url);}catch{continue;}if(url.username||url.password)continue;
  const key=url.href.split('#')[0],previous=unique.get(key);unique.set(key,previous?.awards?.length&&!row.awards?.length?{...row,...previous}:row);
 }
 return [...unique.values()].sort((a,b)=>b.date.localeCompare(a.date)||a.title.localeCompare(b.title));
}
function verifiedAwardLots(row){
 const lots=new Map();
 for(const lot of Array.isArray(row.awards)?row.awards:[]){
  if(typeof lot.lotName!=='string'||!lot.lotName.trim())continue;
  const suppliers=[...new Set((Array.isArray(lot.suppliers)?lot.suppliers:[]).filter(n=>typeof n==='string'&&n.trim()).map(n=>n.trim()))];
  if(!suppliers.length)continue;
  const key=String(lot.lotNumber||'')+'|'+lot.lotName.trim();
  const old=lots.get(key);lots.set(key,{...lot,lotName:lot.lotName.trim(),suppliers:[...new Set([...(old?.suppliers||[]),...suppliers])]});
 }
 return [...lots.values()];
}
function awardSupplierTop3(rows){
 const suppliers=new Map(),seen=new Set();
 const normalize=name=>name.normalize('NFKC').replace(/\s+/g,'');
 for(const row of rows)for(const lot of verifiedAwardLots(row))for(const name of lot.suppliers){
  const key=normalize(name),win=[row.url.split('#')[0],lot.lotNumber||'',lot.lotName,key].join('|');if(seen.has(win))continue;seen.add(win);
  const old=suppliers.get(key)||{name,count:0,latest:''};old.count++;old.latest=old.latest>row.date?old.latest:row.date;suppliers.set(key,old);
 }
 return [...suppliers.values()].sort((a,b)=>b.count-a.count||b.latest.localeCompare(a.latest)||a.name.localeCompare(b.name,'zh-CN')).slice(0,3);
}
(() => {
 const records=new Map();let selected,trigger,timer;
 window.awardHistoryCountFor=x=>{const r=records.get(customerIdentifier(x));const name=new DOMParser().parseFromString(x[0],'text/html').body.textContent;return r?.name===name?sortedAwardResults(r.results||[],shanghaiDate()).length:0;};
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const overlay=document.createElement('div');overlay.className='org-overlay award-overlay';overlay.hidden=true;
 overlay.innerHTML='<section class="org-drawer" role="dialog" aria-modal="true" aria-labelledby="award-title"><header class="org-header"><div><span>历史招标结果</span><h2 id="award-title"></h2></div><button class="org-close" aria-label="关闭历史招标结果">×</button></header><div class="org-content award-content"></div></section>';
 document.body.append(overlay);
 function render(){
  const name=new DOMParser().parseFromString(selected[0],'text/html').body.textContent;
  overlay.querySelector('#award-title').textContent=name;
  const saved=records.get(customerIdentifier(selected));const record=saved?.name===name?saved:null;
  const projects=(typeof profileFor==='function'?profileFor(selected)?.projects:[])||[];
  const extra=projects.filter(p=>p.stage==='中标或成交信息'&&p.buyer?.value?.startsWith(name)).map(p=>({title:p.title||p.name,date:(p.published_at||'').slice(0,10),buyer:p.buyer.value,url:p.notice_url||p.url}));
  const rows=sortedAwardResults([...(record?.results||[]),...extra],shanghaiDate());let year='';
  const top=awardSupplierTop3(rows),verified=rows.filter(row=>verifiedAwardLots(row).length).length;
  const competitors=`<section class="award-competitors" aria-label="竞争对手 TOP3"><h3>竞争对手 <span>TOP3</span></h3>${top.length?`<ol>${top.map(s=>`<li><span>${esc(s.name)}</span><b>${s.count} 次</b></li>`).join('')}</ol>`:'<p class="org-unconfirmed">暂无已核实的中标供应商</p>'}<small>按已核实标项计次 · ${verified}/${rows.length} 条公告已核实供应商</small></section>`;
  const timeline=rows.map(row=>{const y=row.date.slice(0,4);const heading=y!==year?`<h3 class="award-year">${y}</h3>`:'';year=y;
   const lots=verifiedAwardLots(row),items=lots.length?lots:[{lotName:row.projectName||'标项名称待核实',suppliers:[]}];
   return `${heading}<div class="award-item"><time datetime="${esc(row.date)}">${esc(row.date)}</time>${items.map(lot=>`<a class="award-lot" href="${esc(row.url)}" title="${esc(row.title)}" target="_blank" rel="noopener noreferrer"><strong>${esc(lot.lotName)} <span aria-hidden="true">↗</span></strong><span class="award-supplier">${lot.suppliers.length?'中标供应商：'+esc(lot.suppliers.join('、')):'中标供应商待核实'}</span></a>`).join('')}${row.buyer!==name?`<small>采购单位：${esc(row.buyer)}</small>`:''}</div>`;}).join('');
  const coverage=record?.coverage;
  overlay.querySelector('.award-content').innerHTML=`${competitors}<p class="award-caption">${rows.length} 条公开结果 · 按结果公告日期倒序</p>${record?.lastCheck?.status==='unavailable'?'<p class="org-unconfirmed">本次读取未完成，保留此前已核实记录。</p>':''}${timeline||'<p class="org-empty">暂无已核实的公开招标结果</p>'}<div class="award-footnote">${coverage?`查询范围：${esc(coverage.from)} 至 ${esc(coverage.to)}<br>来源：上海市政府采购网${coverage.truncated?' · 分页范围内已核实记录':''}`:'历史结果正在补充，仅展示能核实到的公开记录。'}<br>未接入或无法读取的其他渠道不代表没有历史采购。</div>`;
 }
 function close(){overlay.classList.remove('is-open');document.body.classList.remove('org-open');clearTimeout(timer);timer=setTimeout(()=>overlay.hidden=true,260);if(trigger?.isConnected)trigger.focus();}
 document.getElementById('cards').addEventListener('click',e=>{const button=e.target.closest('[data-award-open]');if(!button)return;const id=decodeURIComponent(button.closest('.card').dataset.customerKey);selected=views.flatMap(v=>v.items).find(x=>customerIdentifier(x)===id);if(!selected)return;trigger=button;clearTimeout(timer);render();overlay.hidden=false;document.body.classList.add('org-open');requestAnimationFrame(()=>overlay.classList.add('is-open'));overlay.querySelector('.org-close').focus();});
 overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('.org-close'))close();});
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}if(e.key==='Tab'){const items=[...overlay.querySelectorAll('button,a')],first=items[0],last=items.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
 const update=()=>{if(!selected||overlay.hidden)return;const id=customerIdentifier(selected),current=views.flatMap(v=>v.items).find(x=>customerIdentifier(x)===id);if(!current){close();return;}selected=current;render();};
 for(const event of ['customers-updated','public-profiles-updated'])window.addEventListener(event,update);
 async function refresh(){try{const r=await fetch(new URL('./award-history.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(!r.ok)return;const data=await r.json();for(const record of data.customers||[])records.set(String(record.id),record);update();if(typeof refreshProfiles==='function')refreshProfiles();}catch{}}
 window.addEventListener('refresh-public-data',refresh);refresh();setInterval(refresh,300000);
})();
