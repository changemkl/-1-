/* Organization evidence is independent of the customer-name spreadsheet. */
(() => {
  const records = new Map();
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const overlay = document.createElement('div');
  overlay.className = 'org-overlay';
  overlay.hidden = true;
  overlay.innerHTML = `<section class="org-drawer" role="dialog" aria-modal="true" aria-labelledby="org-title" tabindex="-1"><header class="org-header"><div><span>客户组织树</span><h2 id="org-title"></h2></div><button class="org-close" aria-label="关闭组织树">×</button></header><div class="org-content"></div></section>`;
  document.body.append(overlay);
  const panel = overlay.querySelector('.org-drawer');
  let trigger, closeTimer, selected;
  const tree = nodes => `<ul class="org-branches">${nodes.map(n => `<li>${n.children?.length ? `<details open><summary>${escape(n.name)}<small>${n.children.length}</small></summary>${tree(n.children)}</details>` : `<div class="org-leaf">${escape(n.name)}</div>`}</li>`).join('')}</ul>`;
  function render() {
    const record = records.get(customerIdentifier(selected));
    overlay.querySelector('#org-title').textContent = new DOMParser().parseFromString(selected[0], 'text/html').body.textContent;
    const sources = record?.sources || (record?.source ? [record.source] : []);
    const links = sources.filter(source => /^https:\/\//.test(source.url)).map(source => `<a class="org-source" href="${escape(source.url)}" target="_blank" rel="noopener noreferrer">${escape(source.title)} ↗<small>发布：${escape(source.publishedAt)}</small></a>`).join('');
    overlay.querySelector('.org-content').innerHTML = `<div class="org-root">${escape(overlay.querySelector('#org-title').textContent)}</div>${record?.nodes?.length ? tree(record.nodes) : '<p class="org-empty">暂无已核实的组织架构资料</p>'}<div class="org-note">${escape(record?.note || '机构层级待核实，暂不展示未经确认的部门及人员。')}</div>${links}${sources.length ? `<p class="org-checked">核对日期：${escape(record.checkedAt)}</p>` : ''}`;
  }
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
    selected = filtered()[Number(article.dataset.customerIndex)];
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
  fetch('./organization-data.json', {cache:'no-store'}).then(r => { if (!r.ok) throw Error('organization data'); return r.json(); }).then(data => {
    for (const record of data.customers || []) records.set(String(record.id), record);
    if (selected && !overlay.hidden) render();
  }).catch(() => {});
})();
