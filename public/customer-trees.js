function partnersForCustomerTree(name,results,cooperators){
 const suppliers=aggregatePartnerSuppliers([{name,results}]);
 const names=new Set(suppliers.map(p=>partnerNameKey(p.name)));
 const matched=cooperators.filter(p=>[p.name,...(p.aliases||[])].some(n=>names.has(partnerNameKey(n))));
 return mergeCooperationPartners(suppliers,matched).sort((a,b)=>Number(b.type==='合作伙伴')-Number(a.type==='合作伙伴')||b.wins-a.wins||a.name.localeCompare(b.name,'zh-CN'));
}
(() => {
 const esc=syncEscape,decode=x=>new DOMParser().parseFromString(x[0],'text/html').body.textContent;
 let selected=null,tab='organization',section='trees',purchaseTab='current',trigger,timer,scenes=[];
 const tabs=[['organization','客户组织树'],['industry','产业链树'],['scenes','产品与场景树']];
 const overlay=document.createElement('div');overlay.className='org-overlay customer-trees-overlay';overlay.hidden=true;
 overlay.innerHTML='<section class="org-drawer customer-trees-drawer" role="dialog" aria-modal="true" aria-labelledby="customer-trees-title"><header class="org-header"><div><span>客户详情</span><h2 id="customer-trees-title"></h2></div><button class="org-close" aria-label="关闭客户详情">×</button></header><div class="customer-detail-summary"></div><div class="customer-detail-nav" role="tablist" aria-label="客户内容"></div><div class="customer-tree-tabs" role="tablist" aria-label="客户三棵树"></div><div id="customer-tree-panel" class="org-content customer-tree-content" role="tabpanel"></div></section>';
 document.body.append(overlay);const panel=overlay.querySelector('[role="tabpanel"]'),tablist=overlay.querySelector('.customer-tree-tabs'),mainNav=overlay.querySelector('.customer-detail-nav');
 function industry(){
  const partners=partnersForCustomerTree(decode(selected),typeof awardHistoryFor==='function'?awardHistoryFor(selected):[],views[1].items.filter(x=>x.partner?.type==='合作伙伴').map(x=>x.partner));
  const groups=['合作伙伴','潜在合作伙伴'];
  return `<p class="customer-tree-caption">关联依据：该客户及下属单位的公开中标结果。</p>${groups.map(type=>{const rows=partners.filter(p=>p.type===type);return `<section class="customer-tree-section"><h3>${type}<small>${rows.length}</small></h3>${rows.length?`<ul class="org-branches">${rows.map(p=>`<li><details class="customer-partner-node"><summary>${esc(p.name)}<small>${p.wins} 次</small></summary>${type==='合作伙伴'?'<p class="customer-tree-caption">我司合作伙伴 · 有该客户中标记录</p>':''}${p.evidence.map(e=>`<a href="${esc(safeSource(e.url))}" target="_blank" rel="noopener noreferrer"><span>${esc(e.lotName)} ↗</span><small>${esc(e.date)} · ${esc(e.buyer||e.customerName)}</small></a>`).join('')}</details></li>`).join('')}</ul>`:'<p class="org-empty">暂无已核实的关联'+type+'</p>'}</section>`;}).join('')}`;
 }
 function scenario(){return '';}

 const sections=[['trees','三棵树'],['logs','工作日志'],['procurement','采购信息']],purchases=[['current','采购意向与招标'],['history','历史招标结果']];
 function render(){if(!selected)return;overlay.querySelector('h2').textContent=decode(selected);
  const number=(selected[9]||[]).find(([label])=>['集团编号','客户编号','ID'].includes(label))?.[1];
  overlay.querySelector('.customer-detail-summary').innerHTML=`${selected[10]?.length?`<div class="customer-labels">${selected[10].map(t=>`<span>${t}</span>`).join('')}</div>`:''}${number?`<p class="customer-detail-meta">客户编号 ${number}</p>`:''}${selected[2]?`<p class="customer-detail-meta">${selected[2]}</p>`:''}${profilePreview(selected)}`;
  mainNav.innerHTML=sections.map(([key,label])=>`<button type="button" role="tab" id="customer-section-${key}" aria-selected="${section===key}" aria-controls="customer-tree-panel" tabindex="${section===key?0:-1}" data-customer-section="${key}">${label}</button>`).join('');
  tablist.hidden=section==='logs';const choices=section==='trees'?tabs:purchases,active=section==='trees'?tab:purchaseTab;
  tablist.innerHTML=section==='logs'?'':choices.map(([key,label])=>`<button type="button" role="tab" id="customer-subtab-${key}" aria-selected="${active===key}" aria-controls="customer-tree-panel" tabindex="${active===key?0:-1}" ${section==='trees'?'data-tree-tab':'data-purchase-tab'}="${key}">${label}</button>`).join('');
  tablist.setAttribute('aria-label',section==='trees'?'客户三棵树':'客户采购信息');panel.setAttribute('aria-labelledby',section==='logs'?'customer-section-logs':'customer-subtab-'+active);
  panel.className='org-content customer-tree-content'+(section==='logs'?' worklog-content':section==='procurement'&&purchaseTab==='history'?' award-content':'');
  panel.innerHTML=section==='logs'?customerWorklogMarkup(selected):section==='procurement'?(purchaseTab==='history'?customerAwardMarkup(selected):customerProcurementMarkup(selected)):tab==='organization'?customerOrganizationMarkup(selected):tab==='industry'?industry():scenario();if(section==='procurement'&&purchaseTab==='current')panel.innerHTML+=profileSourcesFor(selected);
 }

 function close(){overlay.classList.remove('is-open');document.body.classList.remove('org-open');clearTimeout(timer);timer=setTimeout(()=>overlay.hidden=true,260);if(trigger?.isConnected)trigger.focus();else [...document.querySelectorAll('.customer-card')].find(el=>el.dataset.customerKey===encodeURIComponent(customerIdentifier(selected)))?.focus();}
 function open(article,button){const id=decodeURIComponent(article.dataset.customerKey);selected=views[0].items.find(x=>customerIdentifier(x)===id);if(!selected)return;trigger=button||article;section='trees';tab='organization';purchaseTab='current';clearTimeout(timer);render();overlay.hidden=false;document.body.classList.add('org-open');requestAnimationFrame(()=>overlay.classList.add('is-open'));overlay.querySelector('.org-close').focus();}
 $('cards').addEventListener('click',e=>{const article=e.target.closest('.customer-card');if(!article)return;const button=e.target.closest('[data-customer-trees]');if(!button&&e.target.closest('button,a,input,textarea,select,summary,details,label'))return;if(!button&&window.getSelection()?.toString())return;open(article,button);});
 $('cards').addEventListener('keydown',e=>{const article=e.target.closest('.customer-card');if(article&&e.target===article&&['Enter',' '].includes(e.key)){e.preventDefault();open(article);}});
 function scrollTop(){overlay.querySelector('.org-drawer').scrollTop=0;}
 mainNav.addEventListener('click',e=>{const button=e.target.closest('[data-customer-section]');if(!button)return;section=button.dataset.customerSection;render();scrollTop();mainNav.querySelector('[aria-selected="true"]').focus();});
 mainNav.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const i=sections.findIndex(([key])=>key===section);const next=e.key==='Home'?0:e.key==='End'?sections.length-1:(i+(e.key==='ArrowRight'?1:-1)+sections.length)%sections.length;section=sections[next][0];render();scrollTop();mainNav.querySelector('[aria-selected="true"]').focus();});
 tablist.addEventListener('click',e=>{const button=e.target.closest('[data-tree-tab],[data-purchase-tab]');if(!button)return;if(section==='trees')tab=button.dataset.treeTab;else purchaseTab=button.dataset.purchaseTab;render();scrollTop();tablist.querySelector('[aria-selected="true"]').focus();});
 tablist.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const choices=section==='trees'?tabs:purchases,current=section==='trees'?tab:purchaseTab;let i=choices.findIndex(([key])=>key===current);i=e.key==='Home'?0:e.key==='End'?choices.length-1:(i+(e.key==='ArrowRight'?1:-1)+choices.length)%choices.length;if(section==='trees')tab=choices[i][0];else purchaseTab=choices[i][0];render();scrollTop();tablist.querySelector('[aria-selected="true"]').focus();});
 overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('.org-close'))close();});
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}if(e.key==='Tab'){const a=[...overlay.querySelectorAll('button:not([tabindex="-1"]),a,summary')].filter(el=>!el.closest('details:not([open])')||el.tagName==='SUMMARY'),first=a[0],last=a.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
 function update(){if(!selected||overlay.hidden)return;const id=customerIdentifier(selected);selected=views[0].items.find(x=>customerIdentifier(x)===id);if(!selected){close();return;}render();}
 for(const event of ['customers-updated','public-profiles-updated','award-history-updated','partners-updated','customer-sources-updated','worklogs-updated'])window.addEventListener(event,update);
 async function refreshScenes(){try{const r=await fetch(new URL('./customer-scenes.json?v='+Date.now(),location.href),{cache:'no-store'});if(!r.ok)return;const data=await r.json();if(Array.isArray(data.customers)){scenes=data.customers;update();}}catch{}}
 window.addEventListener('refresh-public-data',refreshScenes);refreshScenes();setInterval(refreshScenes,300000);
})();
