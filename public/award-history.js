function sortedAwardResults(rows,today){
 const unique=new Map();
 for(const row of rows){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(row.date||'')||row.date>today)continue;
  const date=new Date(row.date+'T00:00:00Z');if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==row.date||!/^https:\/\//.test(row.url||''))continue;
  let url;try{url=new URL(row.url);}catch{continue;}if(url.username||url.password)continue;
  unique.set(url.href.split('#')[0],row);
 }
 return [...unique.values()].sort((a,b)=>b.date.localeCompare(a.date)||a.title.localeCompare(b.title));
}
(() => {
 const records=new Map();let selected,trigger,timer;
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
  const timeline=rows.map(row=>{const y=row.date.slice(0,4);const heading=y!==year?`<h3 class="award-year">${y}</h3>`:'';year=y;return `${heading}<div class="award-item"><time datetime="${esc(row.date)}">${esc(row.date)}</time><a href="${esc(row.url)}" target="_blank" rel="noopener noreferrer">${esc(row.title)} <span aria-hidden="true">↗</span></a>${row.buyer!==name?`<small>采购单位：${esc(row.buyer)}</small>`:''}</div>`;}).join('');
  const coverage=record?.coverage;
  overlay.querySelector('.award-content').innerHTML=`<p class="award-caption">${rows.length} 条公开结果 · 按结果公告日期倒序</p>${record?.lastCheck?.status==='unavailable'?'<p class="org-unconfirmed">本次读取未完成，保留此前已核实记录。</p>':''}${timeline||'<p class="org-empty">暂无已核实的公开招标结果</p>'}<div class="award-footnote">${coverage?`查询范围：${esc(coverage.from)} 至 ${esc(coverage.to)}<br>来源：上海市政府采购网${coverage.truncated?' · 分页范围内已核实记录':''}`:'历史结果正在补充，仅展示能核实到的公开记录。'}<br>未接入或无法读取的其他渠道不代表没有历史采购。</div>`;
 }
 function close(){overlay.classList.remove('is-open');document.body.classList.remove('org-open');clearTimeout(timer);timer=setTimeout(()=>overlay.hidden=true,260);if(trigger?.isConnected)trigger.focus();}
 document.getElementById('cards').addEventListener('click',e=>{const button=e.target.closest('[data-award-open]');if(!button)return;selected=filtered()[Number(button.closest('.card').dataset.customerIndex)];if(!selected)return;trigger=button;clearTimeout(timer);render();overlay.hidden=false;document.body.classList.add('org-open');requestAnimationFrame(()=>overlay.classList.add('is-open'));overlay.querySelector('.org-close').focus();});
 overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('.org-close'))close();});
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}if(e.key==='Tab'){const items=[...overlay.querySelectorAll('button,a')],first=items[0],last=items.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
 const update=()=>{if(!selected||overlay.hidden)return;const id=customerIdentifier(selected),current=views.flatMap(v=>v.items).find(x=>customerIdentifier(x)===id);if(!current){close();return;}selected=current;render();};
 for(const event of ['customers-updated','public-profiles-updated'])window.addEventListener(event,update);
 async function refresh(){try{const r=await fetch(new URL('./award-history.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(!r.ok)return;const data=await r.json();for(const record of data.customers||[])records.set(String(record.id),record);update();}catch{}}
 refresh();setInterval(refresh,300000);
})();
