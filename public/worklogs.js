/* Published customer logs from Tencent and Dongfeng; credentials stay on the server. */
function sortedCustomerWorklogs(entries,id,name){
 const unique=new Map();
 for(const r of entries){if(r.customerId!==id||r.customerName!==name||typeof r.id!=='string'||typeof r.content!=='string'||!r.content.trim())continue;unique.set(r.id,r);}
 return [...unique.values()].sort((a,b)=>(b.workDate||'').localeCompare(a.workDate||'')||(b.updatedAt||'').localeCompare(a.updatedAt||'')||a.id.localeCompare(b.id));
}
(() => {
 let entries=[],loaded=false,readFailed=false,selected=null,trigger,closeTimer;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const decoded=x=>new DOMParser().parseFromString(x[0],'text/html').body.textContent;
 const overlay=document.createElement('div');overlay.className='org-overlay worklog-overlay';overlay.hidden=true;
 overlay.innerHTML='<section class="org-drawer" role="dialog" aria-modal="true" aria-labelledby="worklog-title"><header class="org-header"><div><span>工作日志</span><h2 id="worklog-title"></h2></div><button class="org-close" aria-label="关闭工作日志">×</button></header><div class="org-content worklog-content"></div></section>';
 document.body.append(overlay);
 window.customerWorklogMarkup=customer=>{const name=decoded(customer);
  const rows=sortedCustomerWorklogs([...entries,...(typeof manualWorklogsFor==='function'?manualWorklogsFor(customer):[])],customerIdentifier(customer),name);let day;
  const timeline=rows.map(r=>{const date=r.workDate||'日期未明确',heading=day!==date?`<h3 class="worklog-date">${esc(date)}</h3>`:'';day=date;const actor=r.sourceType==='dongfeng'?`<div class="worklog-actor"><strong>${esc(r.actorName||'人员未明确')}</strong><span>${esc(r.actorName?(r.actorRole||r.actorLabel||'岗位未注明'):'东风原始记录')}</span></div>`:'';return `${heading}<article class="worklog-item">${actor}${r.title?`<p class="worklog-project">${esc(r.title)}</p>`:''}${r.relatedUnit?`<small>关联单位：${esc(r.relatedUnit)}</small>`:''}${r.associationNote?`<small class="worklog-association">${esc(r.associationNote)}</small>`:''}<p class="worklog-text">${esc(r.content)}</p>${r.durationHours!=null?`<small>记录用时：${esc(r.durationHours)} 小时</small>`:''}${r.participants?.length?`<small>参与人员：${esc(r.participants.join('、'))}</small>`:''}${r.responsibleManager?`<small>负责经理：${esc(r.responsibleManager)}（不据此认定为填报人）</small>`:''}${r.recordUpdatedDate?`<small>记录更新日期：${esc(r.recordUpdatedDate)}（实际工作日期未明确）</small>`:''}${r.plannedVisitDate&&!r.workDate?`<small>计划拜访日期：${esc(r.plannedVisitDate)}（未确认完成）</small>`:''}${r.originalContent?`<details class="worklog-original"><summary>原始填报全文</summary><p class="worklog-text">${esc(r.originalContent)}</p></details>`:''}<small>${r.sourceType==='manual'?`人工录入 · ${typeof manualButtons==='function'?manualButtons({...r,id:r.manualId}):''}`:r.sourceType==='dongfeng'?`${esc(r.sourceLabel||'东风平台')}${/^http:\/\/36\.140\.149\.89:18080\/dongfeng(?:\?|$)/.test(r.sourceUrl||'')?` · <a href="${esc(r.sourceUrl)}" target="_blank" rel="noopener noreferrer">来源 ↗</a>`:''}`:`${esc(r.columnHeader||r.column+'列')} · 来源单元格 ${esc(r.cell)}${r.datePrecision==='year-inferred'?' · 年份按首次读取年推定':''}`}</small></article>`;}).join('');
  return `<p class="award-caption">${rows.length} 条工作日志 · 按工作日期倒序</p>${readFailed?'<p class="org-unconfirmed">本次日志读取未完成，保留此前记录。</p>':''}${timeline||`<p class="org-empty">${loaded?'暂无工作日志。在基础列右侧新增一列，填写该客户的工作内容后同步。':'正在读取工作日志…'}</p>`}`;
 };
 function render(){if(!selected)return;overlay.querySelector('h2').textContent=decoded(selected);overlay.querySelector('.worklog-content').innerHTML=window.customerWorklogMarkup(selected);}
 function close(){overlay.classList.remove('is-open');document.body.classList.remove('org-open');clearTimeout(closeTimer);closeTimer=setTimeout(()=>overlay.hidden=true,260);if(trigger?.isConnected)trigger.focus();}
 $('cards').addEventListener('click',e=>{const button=e.target.closest('[data-worklog-open]');if(!button)return;const id=decodeURIComponent(button.closest('.card').dataset.customerKey);selected=views[0].items.find(x=>customerIdentifier(x)===id);if(!selected)return;trigger=button;clearTimeout(closeTimer);render();overlay.hidden=false;document.body.classList.add('org-open');requestAnimationFrame(()=>overlay.classList.add('is-open'));overlay.querySelector('button').focus();});
 overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('.org-close'))close();});
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}if(e.key==='Tab'){e.preventDefault();overlay.querySelector('button').focus();}});
 window.addEventListener('customers-updated',()=>{if(!selected||overlay.hidden)return;const id=customerIdentifier(selected);selected=views[0].items.find(x=>customerIdentifier(x)===id);if(!selected){close();return;}render();});
 async function refresh(){
  const results=await Promise.allSettled(['worklogs.json','dongfeng-worklogs.json'].map(async file=>{const r=await fetch(new URL('./'+file+'?v='+Date.now(),location.href),{cache:'no-store'});if(!r.ok)throw Error('Unavailable');const data=await r.json();if(!Array.isArray(data.entries))throw Error('Invalid logs');return data.entries;}));
  const previous=[entries.filter(r=>r.sourceType!=='dongfeng'),entries.filter(r=>r.sourceType==='dongfeng')];
  entries=results.flatMap((result,i)=>result.status==='fulfilled'?result.value:previous[i]);loaded=loaded||results.some(r=>r.status==='fulfilled');readFailed=results.some(r=>r.status==='rejected');
  window.dispatchEvent(new Event('worklogs-updated'));if(!overlay.hidden)render();
 }

 window.refreshWorklogs=refresh;window.addEventListener('refresh-public-data',refresh);refresh();setInterval(refresh,60000);
})();
