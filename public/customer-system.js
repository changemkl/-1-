/* Customer lifecycle is separate from the source spreadsheet and collected facts. */
(() => {
  let version = '';
  const records = new Map();
  window.customerSystemState = x => records.get(customerIdentifier(x));
  window.customerSourceNeedsReview = x => {
    const r = window.customerSystemState(x);
    return Boolean(r?.nameChangedAt && r.sourceStatus !== 'verified');
  };
  window.customerStatePreview = x => {
    const r = window.customerSystemState(x);
    if (!r || r.sourceStatus === 'verified') return '';
    const label = r.nameChangedAt ? '名称已更新 · 资料来源待重新核实' : r.candidates?.length ? '已找到候选来源 · 待核实' : r.discovery?.status === 'unavailable' ? '公开资料来源待核实' : '正在查找公开资料来源';
    return `<p class="customer-source-state">${label}</p>`;
  };
  async function refresh() {
    try {
      const r = await fetch(new URL('./customer-system.json?v=' + Math.floor(Date.now()/60000),location.href),{cache:'no-store'});
      if (!r.ok) return;
      const data = await r.json();
      if (!Array.isArray(data.customers) || data.updatedAt === version) return;
      records.clear();
      for (const record of data.customers) records.set(String(record.id),record);
      version = data.updatedAt;
      if (typeof refreshProfiles === 'function') refreshProfiles();
      window.dispatchEvent(new Event('customer-sources-updated'));
    } catch { /* Keep current customer cards and their last verified records. */ }
  }
  refresh();setInterval(refresh,60000);
  window.addEventListener('customers-updated',refresh);
})();
