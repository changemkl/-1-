/* Published spreadsheet logs only; no Tencent or GitHub credential enters the page. */
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
  const rows=sortedCustomerWorklogs(entries,customerIdentifier(customer),name);let day;
  const timeline=rows.map(r=>{const date=r.workDate||'未注明工作日期',heading=day!==date?`<h3 class="worklog-date">${esc(date)}</h3>`:'';day=date;return `${heading}<article class="worklog-item"><p class="worklog-text">${esc(r.content)}</p><small>${esc(r.columnHeader||r.column+'列')} · 来源单元格 ${esc(r.cell)}${r.datePrecision==='year-inferred'?' · 年份按首次读取年推定':''}</small></article>`;}).join('');
  return `<p class="award-caption">${rows.length} 条工作日志 · 按工作日期倒序</p>${readFailed?'<p class="org-unconfirmed">本次日志读取未完成，保留此前记录。</p>':''}${timeline||`<p class="org-empty">${loaded?'暂无工作日志。在基础列右侧新增一列，填写该客户的工作内容后同步。':'正在读取工作日志…'}</p>`}`;
 };
 function render(){if(!selected)return;overlay.querySelector('h2').textContent=decoded(selected);overlay.querySelector('.worklog-content').innerHTML=window.customerWorklogMarkup(selected);}
 function close(){overlay.classList.remove('is-open');document.body.classList.remove('org-open');clearTimeout(closeTimer);closeTimer=setTimeout(()=>overlay.hidden=true,260);if(trigger?.isConnected)trigger.focus();}
 $('cards').addEventListener('click',e=>{const button=e.target.closest('[data-worklog-open]');if(!button)return;const id=decodeURIComponent(button.closest('.card').dataset.customerKey);selected=views[0].items.find(x=>customerIdentifier(x)===id);if(!selected)return;trigger=button;clearTimeout(closeTimer);render();overlay.hidden=false;document.body.classList.add('org-open');requestAnimationFrame(()=>overlay.classList.add('is-open'));overlay.querySelector('button').focus();});
 overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('.org-close'))close();});
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}if(e.key==='Tab'){e.preventDefault();overlay.querySelector('button').focus();}});
 window.addEventListener('customers-updated',()=>{if(!selected||overlay.hidden)return;const id=customerIdentifier(selected);selected=views[0].items.find(x=>customerIdentifier(x)===id);if(!selected){close();return;}render();});
 async function refresh(){try{const r=await fetch(new URL('./worklogs.json?v='+Date.now(),location.href),{cache:'no-store'});if(!r.ok)throw Error('Unavailable');const data=await r.json();if(!Array.isArray(data.entries))throw Error('Invalid logs');entries=data.entries;loaded=true;readFailed=false;window.dispatchEvent(new Event('worklogs-updated'));}catch{readFailed=true;}if(!overlay.hidden)render();}
 window.refreshWorklogs=refresh;window.addEventListener('refresh-public-data',refresh);refresh();setInterval(refresh,60000);
})();

(() => {
 const overlay=document.createElement('div');overlay.className='org-overlay sheet-task-overlay';overlay.hidden=true;
 overlay.innerHTML='<section class="org-drawer" role="dialog" aria-modal="true" aria-labelledby="sheet-task-title"><header class="org-header"><div><span>腾讯在线表格</span><h2 id="sheet-task-title"></h2></div><button class="org-close" aria-label="关闭同步任务">×</button></header><div class="org-content"><p class="sheet-task-help">点击下方链接进入 GitHub，使用有仓库运行权限的 GitHub 账号登录后点击 Run workflow，再点击绿色运行按钮。本页会检查任务结果并载入已发布数据。</p><a class="sheet-task-link" target="_blank" rel="noopener noreferrer">打开 GitHub 同步任务 ↗</a><p class="sheet-task-state" role="status"></p><button class="sheet-task-reload" type="button">读取已发布结果</button><p class="sheet-task-baseline"></p><p class="sheet-task-help">基础列右侧新增的列用于日志，每行关联该行客户。列名可填写工作日期；无法确定日期的日志会明确标注。新增客户行请使用“同步在线表格”。</p></div></section>';
 document.body.append(overlay);let trigger,startedAt=0,file='',timer,closeTimer,generation=0,runId=null;
 const status=overlay.querySelector('.sheet-task-state');
 async function reload(){await Promise.all([refreshSheetData(true),refreshWorklogs()]);if(typeof refreshProfiles==='function')await refreshProfiles();}
 async function poll(token){
  if(token!==generation||overlay.hidden)return;
  try{const response=await fetch(`https://api.github.com/repos/changemkl/-1-/actions/workflows/${file}/runs?event=workflow_dispatch&per_page=5`,{headers:{Accept:'application/vnd.github+json'},cache:'no-store'});if(!response.ok)throw Error('Cannot read task state');const data=await response.json();
   if(token!==generation||overlay.hidden)return;
   const run=data.workflow_runs?.find(r=>(runId===null?Date.parse(r.created_at)>=startedAt-3000:r.id===runId));
   if(!run){status.textContent='等待你在 GitHub 点击 Run workflow；尚未检测到新任务。';return;}
   runId=run.id;
   if(run.status!=='completed'){status.textContent=run.status==='in_progress'?'后台正在读取表格并发布结果…':'同步任务正在排队…';return;}
   clearInterval(timer);
   if(run.conclusion==='success'){status.textContent='同步任务成功，正在载入已发布结果…';await reload();if(token!==generation||overlay.hidden)return;status.textContent=file==='read-worklogs.yml'?'工作日志同步完成。可在客户卡片中查看时间轴。':'客户表格同步完成。客户公开资料由后台继续补充。';}
   else status.textContent='同步任务未成功，现有数据已保留。请在 GitHub 查看任务记录后重试。';
  }catch{if(token===generation)status.textContent='暂时无法读取 GitHub 任务状态。你可在任务完成后点击“读取已发布结果”。';}
 }
 async function baseline(token){try{const response=await fetch(new URL('./worklog-config.json?v='+Date.now(),location.href),{cache:'no-store'});if(!response.ok)return;const data=await response.json();if(token===generation)overlay.querySelector('.sheet-task-baseline').textContent='已固定的基础列：'+data.baseColumns.map(c=>c.header||c.column+'列（未命名）').join('、')+'。';}catch{}}
 function open(kind,button){generation++;const token=generation;file=kind==='logs'?'read-worklogs.yml':'sync-tencent.yml';startedAt=Date.now();runId=null;trigger=button;clearInterval(timer);clearTimeout(closeTimer);overlay.querySelector('h2').textContent=kind==='logs'?'读取工作日志':'同步在线表格';overlay.querySelector('.sheet-task-link').href=`https://github.com/changemkl/-1-/actions/workflows/${file}`;overlay.querySelector('.sheet-task-baseline').textContent='';status.textContent='请进入 GitHub 运行同步任务。当前未向腾讯表格发起读取。';overlay.hidden=false;document.body.classList.add('org-open');requestAnimationFrame(()=>overlay.classList.add('is-open'));overlay.querySelector('button').focus();baseline(token);timer=setInterval(()=>poll(token),30000);}
 function close(){generation++;clearInterval(timer);overlay.classList.remove('is-open');document.body.classList.remove('org-open');closeTimer=setTimeout(()=>overlay.hidden=true,260);if(trigger?.isConnected)trigger.focus();}
 $('read-worklogs').onclick=e=>open('logs',e.currentTarget);$('sync-online-sheet').onclick=e=>open('customers',e.currentTarget);
 overlay.querySelector('.sheet-task-reload').onclick=async e=>{const button=e.currentTarget;button.disabled=true;try{await reload();status.textContent='已读取目前发布的数据；后台任务是否完成请以 GitHub 记录为准。';}finally{button.disabled=false;}};
 overlay.querySelector('.sheet-task-link').addEventListener('click',()=>{status.textContent='在 GitHub 点击 Run workflow 后返回本页，即可查看同步结果。';});
 overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('.org-close'))close();});
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}if(e.key==='Tab'){const a=[...overlay.querySelectorAll('button:not(:disabled),a')],first=a[0],last=a.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
 window.addEventListener('focus',()=>{if(!overlay.hidden)poll(generation);});
})();
