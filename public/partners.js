/* Supplier evidence is public. Manually added partners are local to this browser. */
const PARTNER_STORAGE_KEY='changemkl/-1-/cooperation-partners-v1';
const partnerNameKey=name=>String(name||'').normalize('NFKC').replace(/\s+/g,'').toLowerCase();
function isCompetitorPartner(record){const names=typeof record==='string'?[record]:[record.name,...(record.aliases||[])];return names.some(name=>/电信|联通|中国联合网络通信|中国联合通信/.test(partnerNameKey(name)));}
function aggregatePartnerSuppliers(customers){
 const partners=new Map(),own=new Set(['中移动系统集成有限公司','中移系统集成有限公司'].map(partnerNameKey));
 for(const customer of customers)for(const row of customer.results)for(const lot of verifiedAwardLots(row))for(const name of lot.suppliers){
  const key=partnerNameKey(name);if(!key||own.has(key)||isCompetitorPartner(name))continue;
  let partner=partners.get(key);if(!partner){partner={name,type:'潜在合作伙伴',capabilities:'',notes:'',evidence:[],customers:new Set(),seen:new Set()};partners.set(key,partner);}
  partner.customers.add(customer.name);
  const win=[row.url.split('#')[0],lot.lotNumber||'',lot.lotName].join('|');if(partner.seen.has(win))continue;partner.seen.add(win);
  partner.evidence.push({customerName:customer.name,buyer:row.buyer,lotName:lot.lotName,lotNumber:lot.lotNumber||'',url:row.url,date:row.date});
 }
 return [...partners.values()].map(p=>({name:p.name,type:p.type,capabilities:'',notes:'',customers:[...p.customers],evidence:p.evidence.sort((a,b)=>b.date.localeCompare(a.date)),wins:p.evidence.length}));
}
function mergeCooperationPartners(potential,saved){
 const partners=new Map(potential.filter(p=>!isCompetitorPartner(p)).map(p=>[partnerNameKey(p.name),p]));
 for(const record of saved){
  if(isCompetitorPartner(record))continue;
  const names=new Set([record.name,...(record.aliases||[])].map(partnerNameKey));
  const matches=[...partners.values()].filter(p=>[p.name,...(p.aliases||[])].some(n=>names.has(partnerNameKey(n))));
  const evidence=new Map();for(const p of matches)for(const e of p.evidence||[])evidence.set([e.url,e.lotNumber||'',e.lotName].join('|'),e);
  const prior=matches.find(p=>p.type==='合作伙伴')||matches[0]||{};
  for(const p of matches)partners.delete(partnerNameKey(p.name));
  partners.set(partnerNameKey(record.name),{...prior,...record,type:'合作伙伴',evidence:[...evidence.values()].sort((a,b)=>b.date.localeCompare(a.date)),wins:evidence.size,customers:[...new Set(matches.flatMap(p=>p.customers||[]))],aliases:[...new Set([...matches.flatMap(p=>[p.name,...(p.aliases||[])]),...(record.aliases||[])])].filter(n=>partnerNameKey(n)!==partnerNameKey(record.name))});
 }
 return [...partners.values()];
}
let platformPartners=[],cooperationPartners=[],partnerStorageError='',partnerSaveBusy=false;
function readCooperationPartners(){
 partnerStorageError='';
 try{const raw=localStorage.getItem(PARTNER_STORAGE_KEY);if(raw===null)return [];const data=JSON.parse(raw);if(!Array.isArray(data))throw Error();const unique=new Map();for(const p of data){if(typeof p?.name!=='string'||!p.name.trim()||p.name.length>160)throw Error();unique.set(partnerNameKey(p.name),{name:p.name.trim(),capabilities:typeof p.capabilities==='string'?p.capabilities.slice(0,200):'',notes:typeof p.notes==='string'?p.notes.slice(0,1000):'',addedAt:typeof p.addedAt==='string'?p.addedAt:''});}return [...unique.values()];}
 catch{partnerStorageError='当前浏览器无法读取已保存的合作伙伴，请检查浏览器存储设置。';return [];}
}
function rebuildPartners(){
 const customers=views[0].items.map(x=>{const name=document.createElement('textarea');name.innerHTML=x[0];return {name:name.value,results:typeof awardHistoryFor==='function'?awardHistoryFor(x):[]};});
 const partners=mergeCooperationPartners(mergeCooperationPartners(aggregatePartnerSuppliers(customers),platformPartners),cooperationPartners);
 views[1].items=partners.map(p=>{const item=[syncEscape(p.name),syncEscape(p.name),'','待核实',p.type,syncEscape(p.notes),p.capabilities?[syncEscape(p.capabilities)]:[],p.wins,false,[...p.customers.map(name=>['关联客户',syncEscape(name)]),...(p.aliases||[]).map(name=>['平台名称',syncEscape(name)]),['合作状态',syncEscape(p.relationship||'')],...[...(p.businessLinks||[]),...(p.cooperationOutcomes||[])].map(r=>['关联业务',syncEscape(r.title)])],[]];item.partner=p;return item;});
 views[1].groups=['潜在合作伙伴','合作伙伴'];views[1].chanceKnown=false;renderShell();window.dispatchEvent(new Event('partners-updated'));
}
function partnerStatPairs(){const items=views[1].items.map(x=>x.partner);return [['伙伴总数',items.length],['潜在合作伙伴',items.filter(p=>p.type==='潜在合作伙伴').length],['合作伙伴',items.filter(p=>p.type==='合作伙伴').length],['关联客户',new Set(items.flatMap(p=>p.customers)).size]];}
function partnerBusinessView(p){
 const links=p.businessLinks||[],outcomes=p.cooperationOutcomes||[];
 const list=rows=>rows.map(r=>`<div class="partner-business-row"><span class="partner-business-type">${syncEscape(r.type)}</span><div><strong>${syncEscape(r.title)}</strong>${r.relationship||r.note?`<small>${syncEscape(r.relationship||r.note)}</small>`:''}</div></div>`).join('');
 return `<section class="partner-businesses"><h4>关联商机 / 线索</h4>${links.length?list(links):'<p class="information-empty">暂无已核实的关联商机或线索</p>'}${outcomes.length?`<h4>历史合作记录</h4>${list(outcomes)}`:''}</section>`;
}
function partnerCard(x){
 const p=x.partner,key=encodeURIComponent(partnerNameKey(p.name)),cooperating=p.type==='合作伙伴';
 const publicEvidence=`<p class="partner-counts">${p.wins} 次已核实中标 · ${p.customers.length} 家关联客户</p>${p.customers.length?`<div class="customer-labels">${p.customers.map(n=>`<span>${syncEscape(n)}</span>`).join('')}</div>`:''}${p.evidence.length?`<details class="partner-evidence"><summary>查看中标来源 <small>${p.evidence.length}</small></summary>${p.evidence.map(e=>`<a href="${syncEscape(safeSource(e.url))}" target="_blank" rel="noopener noreferrer"><time>${syncEscape(e.date)}</time><span>${syncEscape(e.lotName)} ↗</span><small>${syncEscape(e.buyer||e.customerName)}</small></a>`).join('')}</details>`:''}`;
 const customNote=p.notes&&!/^平台登记|^线索\/商机记录中/.test(p.notes)?p.notes:'';
 return `<article class="card partner-card"><div class="card-body"><div class="card-top"><span class="category">${p.type}</span><button class="org-entry" data-partner-edit="${key}">${cooperating?'编辑':'添加为合作伙伴'} ↗</button></div><h3>${syncEscape(p.name)}</h3>${p.relationship?`<div class="customer-labels partner-status"><span>${syncEscape(p.relationship)}</span>${/全称待核实/.test(p.notes||'')?'<span>全称待核实</span>':''}</div>`:''}${cooperating?partnerBusinessView(p):p.capabilities?`<p class="summary">合作方向：${syncEscape(p.capabilities)}</p>`:''}${customNote?`<p class="summary">${syncEscape(customNote)}</p>`:''}${!cooperating?publicEvidence:''}${p.source?`<p class="information-empty">来源：${syncEscape(p.source)}</p>`:''}</div></article>`;
}
function validPartnerBusinessRows(rows,historical){
 if(!Array.isArray(rows))return [];
 return rows.filter(r=>r&&typeof r.title==='string'&&r.title.trim()&&r.title.length<=300&&(historical?['项目','客户单位','成果描述']:['线索','商机']).includes(r.type)).map(r=>({title:r.title.trim(),type:r.type,relationship:typeof r.relationship==='string'?r.relationship.slice(0,100):'',note:typeof r.note==='string'?r.note.slice(0,150):''}));
}
async function refreshPlatformPartners(){
 try{
  const r=await fetch(new URL('./cooperation-partners.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(!r.ok)return;const data=await r.json();if(!Array.isArray(data.partners))return;
  const incoming=data.partners.map(p=>{if(typeof p.name!=='string'||!p.name.trim()||p.name.length>160)throw Error('Invalid partner');return {name:p.name.trim(),aliases:(Array.isArray(p.aliases)?p.aliases:[]).filter(a=>typeof a==='string'&&a.length<=160),capabilities:typeof p.capabilities==='string'?p.capabilities.slice(0,200):'',notes:typeof p.notes==='string'?p.notes.slice(0,1000):'',relationship:['有合作记录','合作意向'].includes(p.relationship)?p.relationship:'待核实',source:'东风平台',businessLinks:validPartnerBusinessRows(p.businessLinks,false),cooperationOutcomes:validPartnerBusinessRows(p.cooperationOutcomes,true)};});
  platformPartners=incoming;rebuildPartners();
 }catch{}
}
window.addEventListener('DOMContentLoaded',()=>{
 cooperationPartners=readCooperationPartners();
 const overlay=document.createElement('div');overlay.className='org-overlay partner-overlay';overlay.hidden=true;
 overlay.innerHTML='<section class="org-drawer" role="dialog" aria-modal="true" aria-labelledby="partner-form-title"><header class="org-header"><div><span>产业链树 · 合作伙伴</span><h2 id="partner-form-title">添加合作伙伴</h2></div><button type="button" class="org-close" aria-label="关闭合作伙伴窗口">×</button></header><div class="org-content"><form id="partner-form"><label>合作伙伴名称 <span>*</span><input name="name" required maxlength="160" autocomplete="organization"></label><label>合作方向<input name="capabilities" maxlength="200" placeholder="如：网络安全、软件开发、设备供应"></label><label>合作过的商机 / 线索（或备注）<textarea name="notes" maxlength="1000" rows="4"></textarea></label><p class="partner-storage-note">保存到当前浏览器，刷新后保留，暂不跨设备共享。</p><p class="partner-form-error" role="alert"></p><div class="partner-form-actions"><button type="submit" class="partner-save">保存合作伙伴</button><button type="button" class="partner-cancel">取消</button><button type="button" class="partner-delete" hidden>移除合作伙伴</button></div></form></div></section>';
 document.body.append(overlay);const form=overlay.querySelector('form'),error=overlay.querySelector('.partner-form-error');let editing=null,trigger,timer;
 function close(){overlay.classList.remove('is-open');document.body.classList.remove('org-open');clearTimeout(timer);timer=setTimeout(()=>overlay.hidden=true,260);if(trigger?.isConnected)trigger.focus();else $('add-partner').focus();}
 function open(p,button){form.reset();editing=p?.type==='合作伙伴'?partnerNameKey(p.name):null;trigger=button;error.textContent=partnerStorageError;form.elements.name.value=p?.name||'';form.elements.capabilities.value=p?.capabilities||'';form.elements.notes.value=p?.notes||'';overlay.querySelector('h2').textContent=editing?'编辑合作伙伴':'添加合作伙伴';overlay.querySelector('.partner-delete').hidden=!editing||Boolean(p?.source);overlay.querySelector('.partner-storage-note').textContent=p?.source?'平台导入名单由系统保存；编辑内容仅保存到当前浏览器。':'保存到当前浏览器，刷新后保留，暂不跨设备共享。';clearTimeout(timer);overlay.hidden=false;document.body.classList.add('org-open');requestAnimationFrame(()=>overlay.classList.add('is-open'));form.elements.name.focus();}
 function save(next){if(partnerStorageError){error.textContent=partnerStorageError;return false;}try{localStorage.setItem(PARTNER_STORAGE_KEY,JSON.stringify(next));cooperationPartners=next;rebuildPartners();return true;}catch{error.textContent='保存失败：当前浏览器存储不可用或空间不足。';return false;}}
 $('add-partner').onclick=e=>open(null,e.currentTarget);
 $('cards').addEventListener('click',e=>{const button=e.target.closest('[data-partner-edit]');if(!button)return;const key=decodeURIComponent(button.dataset.partnerEdit),p=views[1].items.find(x=>partnerNameKey(x.partner.name)===key)?.partner;if(p)open(p,button);});
 form.addEventListener('submit',e=>{e.preventDefault();if(partnerSaveBusy)return;const name=form.elements.name.value.trim(),key=partnerNameKey(name);if(!key){error.textContent='请填写合作伙伴名称。';return;}if(isCompetitorPartner(name)){error.textContent='电信、联通属于竞争对手，不加入合作伙伴。';return;}if(['中移动系统集成有限公司','中移系统集成有限公司'].map(partnerNameKey).includes(key)){error.textContent='这是我方公司，请添加合作单位。';return;}if(views[1].items.some(x=>x.partner.type==='合作伙伴'&&[x.partner.name,...(x.partner.aliases||[])].some(n=>partnerNameKey(n)===key)&&partnerNameKey(x.partner.name)!==editing)){error.textContent='该合作伙伴已添加，请在对应卡片中编辑。';return;}const previous=cooperationPartners.find(p=>partnerNameKey(p.name)===editing);const record={name,capabilities:form.elements.capabilities.value.trim(),notes:form.elements.notes.value.trim(),addedAt:previous?.addedAt||new Date().toISOString()};partnerSaveBusy=true;try{if(save([...cooperationPartners.filter(p=>partnerNameKey(p.name)!==editing),record])){if(group==='潜在合作伙伴')group='合作伙伴';query='';$('search').value='';renderShell();close();}}finally{partnerSaveBusy=false;}});
 overlay.querySelector('.partner-delete').onclick=()=>{if(save(cooperationPartners.filter(p=>partnerNameKey(p.name)!==editing)))close();};
 overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('.org-close,.partner-cancel'))close();});
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}if(e.key==='Tab'){const a=[...overlay.querySelectorAll('button:not([hidden]),input,textarea')],first=a[0],last=a.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
 window.addEventListener('storage',e=>{if(e.key===PARTNER_STORAGE_KEY||e.key===null){cooperationPartners=readCooperationPartners();rebuildPartners();}});
 for(const event of ['customers-updated','award-history-updated'])window.addEventListener(event,rebuildPartners);
 rebuildPartners();refreshPlatformPartners();setInterval(refreshPlatformPartners,300000);
});
