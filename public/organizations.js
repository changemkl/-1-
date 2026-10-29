/* Organization evidence is independent of the customer-name spreadsheet. */
(() => {
  const records = new Map();
  const peopleRecords = new Map();
  window.organizationInfoFor = x => {const r=records.get(customerIdentifier(x));return r?.name===decoded(x)?r:null;};
  const decoded = x => new DOMParser().parseFromString(x[0], 'text/html').body.textContent;
  window.organizationLeadersFor = x => {const r=peopleRecords.get(customerIdentifier(x));return typeof customerSourceNeedsReview==='function'&&customerSourceNeedsReview(x)||r?.customerName&&r.customerName!==decoded(x)?[]:(r?.people||[]).filter(p=>p.category==='单位领导');};
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const overlay = document.createElement('div');
  overlay.className = 'org-overlay';
  overlay.hidden = true;
  overlay.innerHTML = `<section class="org-drawer" role="dialog" aria-modal="true" aria-labelledby="org-title" tabindex="-1"><header class="org-header"><div><span>客户组织树</span><h2 id="org-title"></h2></div><button class="org-close" aria-label="关闭组织树">×</button></header><div class="org-content"></div></section>`;
  document.body.append(overlay);
  const panel = overlay.querySelector('.org-drawer');
  let trigger, closeTimer, selected;
  const tree = nodes => `<ul class="org-branches">${nodes.map(n => `<li>${n.children?.length ? `<details open><summary>${escape(n.name)}<small>${n.children.length}</small></summary>${tree(n.children)}</details>` : `<div class="org-leaf">${escape(n.name)}</div>`}</li>`).join('')}</ul>`;
  function peopleView(id, customer) {
    const record = peopleRecords.get(id), pending=typeof customerSourceNeedsReview==='function'&&customerSourceNeedsReview(customer);
    const collected=(typeof profileFor==='function'?profileFor(customer)?.leaders:[])||[];
    const raw=pending?[]:[...window.organizationLeadersFor(customer),...collected.map(p=>({...p,category:'单位领导',informationResponsibility:Boolean(p.division&&/(负责|分管)[^。]*信息化/.test(p.division)),source:{url:p.url,title:p.title,publishedAt:p.published_at},checkedAt:p.fetched_at}))];
    const unique=new Map();for(const p of raw.sort((a,b)=>(b.checkedAt||'').localeCompare(a.checkedAt||'')))if(!unique.has(p.name))unique.set(p.name,p);
    const people=[...unique.values()];
    const categories = [['单位领导', people.filter(p => p.category === '单位领导')], ['分管信息化领导', people.filter(p => p.informationResponsibility)], ['信息化部门负责人', people.filter(p => p.category === '信息化部门负责人')], ['采购项目联系人', people.filter(p => p.category === '采购项目联系人')]];
    const personView = p => `<div class="org-person"><strong>${escape(p.name)}</strong><span>${escape(p.role)}</span><button type="button" class="manual-promote" data-important-person="${encodeURIComponent(JSON.stringify({customerId:id,name:p.name,role:p.role,division:p.division,sourceUrl:p.source?.url,sourceTitle:p.source?.title}))}">设为重要责任人</button>${p.division ? `<p>${escape(p.division)}</p>` : ''}${p.source && /^https:\/\//.test(p.source.url) ? `<a title="${escape(p.source.title)} · 发布：${escape(p.source.publishedAt || '未标注')}" href="${escape(p.source.url)}" target="_blank" rel="noopener noreferrer">来源 ↗</a>` : ''}<small>核对：${escape(p.checkedAt?.slice(0,10) || '未确认')}</small></div>`;
    return `<section class="org-people"><h3>相关责任人 <small>${new Set([...people.map(p=>p.name),...(typeof manualFor==='function'?manualFor(customer,'person').map(p=>p.name):[])]).size} 人</small></h3>${record?.lastCheck?.status === 'unavailable' ? '<p class="org-unconfirmed">本次未能重新核对，以下为此前公开记录，请以原文为准。</p>' : ''}${typeof manualPeopleMarkup==='function'?manualPeopleMarkup(customer):''}${categories.map(([label, list]) => `<details class="org-person-group" ${label === '分管信息化领导' ? 'open' : ''}><summary>${label}<small>${list.length}</small></summary>${list.length ? list.map(personView).join('') : '<p class="org-unconfirmed">暂无可核实的公开资料</p>'}</details>`).join('')}</section>`;
  }
  window.customerOrganizationMarkup = customer => {
    let record = typeof customerSourceNeedsReview==='function'&&customerSourceNeedsReview(customer)?null:records.get(customerIdentifier(customer));
    if(record?.name&&record.name!==decoded(customer))record=null;
    const extracted=typeof profileFor==='function'?profileFor(customer)?.organizations:[];
    if(!record?.nodes?.length&&extracted?.length){const latest=[...extracted].sort((a,b)=>(b.fetched_at||'').localeCompare(a.fetched_at||''))[0];record={nodes:[latest],source:{url:latest.url,title:latest.title,publishedAt:latest.published_at||'未标注'},checkedAt:latest.fetched_at?.slice(0,10),note:'按官网明确列举的内设机构整理，未推断其他层级。'};}
    const sources = record?.sources || (record?.source ? [record.source] : []);
    const links = sources.filter(source => /^https:\/\//.test(source.url)).map(source => `<a class="org-source" href="${escape(source.url)}" target="_blank" rel="noopener noreferrer">${escape(source.title)} ↗<small>发布：${escape(source.publishedAt)}</small></a>`).join('');
    return `${peopleView(customerIdentifier(customer),customer)}<h3 class="org-section-title">机构设置</h3>${record?.nodes?.length ? tree(record.nodes) : '<p class="org-empty">暂无已核实的组织架构资料</p>'}<details class="org-evidence"><summary>资料来源与说明</summary><div class="org-note">${escape(record?.note || '机构层级待核实，暂不展示未经确认的部门及人员。')}</div>${links}${sources.length ? `<p class="org-checked">核对日期：${escape(record.checkedAt)}</p>` : ''}</details>`;
  };
  function render(){overlay.querySelector('#org-title').textContent=decoded(selected);overlay.querySelector('.org-content').innerHTML=window.customerOrganizationMarkup(selected);}
  function close() {
    if (overlay.hidden) return;
    overlay.classList.remove('is-open');
    document.body.classList.remove('org-open');
    clearTimeout(closeTimer);
    closeTimer = setTimeout(() => { overlay.hidden = true; }, 260);
    trigger?.focus();
  }
  function open(button) {
    const article = button.closest('.card');
    const id=decodeURIComponent(article.dataset.customerKey);
    selected = views.flatMap(v=>v.items).find(x=>customerIdentifier(x)===id);
    if (!selected) return;
    trigger = button;
    clearTimeout(closeTimer);
    render();
    overlay.hidden = false;
    document.body.classList.add('org-open');
    requestAnimationFrame(() => overlay.classList.add('is-open'));
    panel.querySelector('.org-close').focus();
  }
  document.getElementById('cards').addEventListener('click', e => {
    const button = e.target.closest('[data-org-open]');
    if (button) open(button);
  });
  overlay.addEventListener('click', e => { if (e.target === overlay || e.target.closest('.org-close')) close(); });
  overlay.addEventListener('keydown', e => {
    if (e.key === 'Escape') { e.preventDefault(); close(); }
    if (e.key === 'Tab') {
      const focusable = [...panel.querySelectorAll('button, a, summary')].filter(el => !el.closest('details:not([open])') || el.tagName === 'SUMMARY');
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  const load = async (file, map) => {
    try {
      const r = await fetch(new URL('./' + file + '?v=' + Math.floor(Date.now()/60000), location.href), {cache:'no-store'});
      if (!r.ok) throw Error('Public organization data unavailable');
      const data = await r.json();
      for (const record of data.customers || []) map.set(String(record.id), record);
      if (selected && !overlay.hidden) render();
      if (typeof refreshProfiles === 'function') refreshProfiles();
    } catch { /* Retain already loaded evidence. */ }
  };
  const updateSelected=()=>{if(!selected||overlay.hidden)return;const id=customerIdentifier(selected);const current=views.flatMap(v=>v.items).find(x=>customerIdentifier(x)===id);if(!current){close();return;}selected=current;render();};
  for(const event of ['customer-sources-updated','customers-updated','public-profiles-updated'])window.addEventListener(event,updateSelected);
  load('organization-data.json', records);
  load('people-data.json', peopleRecords);
  const refreshOrganizationData=()=>{load('organization-data.json',records);load('people-data.json',peopleRecords);};
  window.addEventListener('refresh-public-data',refreshOrganizationData);
  setInterval(refreshOrganizationData,300000);
})();
