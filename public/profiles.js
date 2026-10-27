const customerProfiles=new Map();
const customerSupplements=new Map();
function supplementFor(x){if(typeof customerSourceNeedsReview==='function'&&customerSourceNeedsReview(x))return null;const r=customerSupplements.get(customerIdentifier(x));const decoded=new DOMParser().parseFromString(x[0],'text/html').body.textContent;return r?.name===decoded?r:null;}
let profilesBusy=false,profilesQueued=false,profileConnection='unconfigured';
function customerIdentifier(x){const number=(x[9]||[]).find(([k])=>['集团编号','客户编号','ID'].includes(k))?.[1];const decoded=document.createElement('textarea');decoded.innerHTML=number||x[0];return number?decoded.value:'name:'+decoded.value.normalize('NFKC').toLowerCase().replace(/\s+/g,'');}
function safeSource(url){try{const u=new URL(url);return u.protocol==='https:'?u.href:null;}catch{return null;}}
function profileFor(x){if(typeof customerSourceNeedsReview==='function'&&customerSourceNeedsReview(x))return null;const p=customerProfiles.get(customerIdentifier(x));if(p?.name){const name=document.createElement('textarea');name.innerHTML=x[0];if(p.name!==name.value)return null;}return p;}
function sourceLink(p){const url=safeSource(p.url);return url?`<a class="original-source" href="${syncEscape(url)}" target="_blank" rel="noopener noreferrer">原文 · ${syncEscape(new URL(url).hostname)} ↗</a>`:'';}
function sourceTime(p){return `${p.published_at?'发布：'+syncEscape(p.published_at)+' · ':'发布日期未确认 · '}采集：${syncEscape(new Date(p.fetched_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}))}`;}
function shanghaiDate(now=new Date()){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);}
function publicTitleIsRecent(p,now){const checked=new Date(p.fetched_at||'');return Number.isFinite(checked.getTime())&&now-checked<=30*86400000&&now>=checked;}
function projectIsCurrent(p,now=new Date()){
 const today=shanghaiDate(now);
 if(p.stage==='中标或成交信息')return false;
 if(p.stage==='采购意向'||p.stage==='招标意向'){
  const date=p.planned_purchase||'';
  if(/^\d{4}-\d{2}-\d{2}$/.test(date))return date>=today;
  if(/^\d{4}-\d{2}$/.test(date))return date>=today.slice(0,7);
  const years=[...(p.name||'').matchAll(/(?:20\d{2})年/g)].map(m=>Number(m[0].slice(0,4)));
  if(years.length&&Math.max(...years)<Number(today.slice(0,4)))return false;
  return p.public_title_only===true&&publicTitleIsRecent(p,now);
 }
 if(/采购公告|招标公告|磋商公告|询价公告|谈判公告/.test(p.stage||'')){
  const value=p.deadline?.value||'';
  if(!value)return p.public_title_only===true&&publicTitleIsRecent(p,now);
  if(!/^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$/.test(value))return false;
  const normalized=value.length===10?value+'T23:59:59':value.replace(' ','T');
  return new Date(normalized+'+08:00').getTime()>=now.getTime();
 }
 return true;
}
function visibleProjectsFor(x,now=new Date()){return(profileFor(x)?.projects||[]).filter(p=>projectIsCurrent(p,now));}
async function refreshProfiles(){
 if(profilesBusy){profilesQueued=true;return;}profilesBusy=true;
 try{
  const config=await(await fetch(new URL('./profile-config.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'})).json();
  const all=views.filter((v,i)=>i!==1).flatMap(v=>v.items),ids=[...new Set(all.map(customerIdentifier))];let incoming=[];
  if(!config.apiBaseUrl){const r=await fetch(new URL('./profile-data.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(!r.ok)throw Error('Information unavailable');const data=await r.json();if(!Array.isArray(data.profiles))throw Error('Invalid profiles');incoming=data.profiles;}
  else{const base=new URL(config.apiBaseUrl);if(base.protocol!=='https:')return;for(let i=0;i<ids.length;i+=25){const url=new URL('/api/profiles',base);for(const id of ids.slice(i,i+25))url.searchParams.append('id',id);const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('Unavailable');incoming.push(...(await r.json()).profiles);}}
  try{const response=await fetch(new URL('./customer-supplements.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(response.ok){const data=await response.json();if(Array.isArray(data.customers)){customerSupplements.clear();for(const item of data.customers)customerSupplements.set(String(item.id),item);}}}catch{}
  profileConnection='connected';
  for(const p of incoming)customerProfiles.set(p.id,p);
  for(const x of all){const p=profileFor(x);x[6]=[...new Set(visibleProjectsFor(x).map(r=>syncEscape(r.stage)))];if(profileLeaderCountFor(x))x[6].push('官网领导信息');x[3]='待核实';x[2]=syncEscape(basicInfoFor(x)?.address||'');}
  for(const v of views.filter((v,i)=>i!==1))v.groups=[...new Set(v.items.map(x=>x[4]))];renderShell();window.dispatchEvent(new Event('public-profiles-updated'));
 }catch{document.getElementById('sync-status').textContent='公开资料暂时无法刷新，现有资料已保留';}
 finally{profilesBusy=false;if(profilesQueued){profilesQueued=false;refreshProfiles();}}
}
function profileProjectCountFor(x){return visibleProjectsFor(x).length;}
function profileLeaderCountFor(x){const all=[...(profileFor(x)?.leaders||[]),...(typeof organizationLeadersFor==='function'?organizationLeadersFor(x):[])];return new Set(all.map(p=>p.name)).size;}
function basicInfoFor(x){return typeof organizationInfoFor==='function'?organizationInfoFor(x):null;}
function historyCountFor(x){return typeof awardHistoryCountFor==='function'?awardHistoryCountFor(x):0;}
function organizationCountFor(x){return (basicInfoFor(x)?.nodes?.length||profileFor(x)?.organizations?.length||0);}
function profileCountFor(x){return profileProjectCountFor(x)+profileLeaderCountFor(x)+historyCountFor(x)+organizationCountFor(x)+(basicInfoFor(x)?.overview?1:0);}
function customerCoverageFor(x){
 const fields=[['主要职能',Boolean(basicInfoFor(x)?.overview)],['组织架构',organizationCountFor(x)>0],['领导资料',profileLeaderCountFor(x)>0],['采购意向与招标',profileProjectCountFor(x)>0],['历史招标结果',historyCountFor(x)>0]];
 return {count:fields.filter(([,present])=>present).length,total:fields.length,missing:fields.filter(([,present])=>!present).map(([label])=>label)};
}
function customerCoveragePreview(x){const c=customerCoverageFor(x);return `<span class="coverage-badge ${c.count===c.total?'coverage-full':''}" title="${syncEscape(c.missing.length?'待补充：'+c.missing.join('、'):'已覆盖五类资料，范围与时效以原文为准')}" aria-label="资料覆盖${c.count}/${c.total}类${c.missing.length?'，待补充：'+syncEscape(c.missing.join('、')):''}">资料覆盖 ${c.count}/${c.total}</span>`;}
function profilePreview(x){
 const basics=basicInfoFor(x);const overview=basics?.overview?`<div class="customer-overview"><p>${syncEscape(basics.overview)}</p>${safeSource((basics.basicSource||basics.source)?.url)?`<a href="${syncEscape(safeSource((basics.basicSource||basics.source).url))}" target="_blank" rel="noopener noreferrer">资料来源 ↗</a>`:''}</div>`:'';
 return overview||'<p class="information-empty">主要职能待补充</p>';
}

function profileSearchFor(x){const p=profileFor(x);return[...visibleProjectsFor(x).map(r=>r.name+' '+r.quote+' '+(r.buyer?.value||'')),...[...(p?.leaders||[]),...(typeof organizationLeadersFor==='function'?organizationLeadersFor(x):[])].map(r=>r.name+' '+r.role+' '+(r.division||''))].join(' ')+' '+(basicInfoFor(x)?.overview||'')+' '+JSON.stringify(basicInfoFor(x)?.nodes||[]);}
window.addEventListener('customers-updated',refreshProfiles);setInterval(refreshProfiles,300000);refreshProfiles();

function profileSourcesFor(x){
 const sources=profileFor(x)?.procurementSources||[];
 const root=typeof customerSystemState==='function'?customerSystemState(x)?.verifiedSource:null;
 const website=!profileCountFor(x)&&root?.dedicated&&safeSource(root.url)?`<a class="customer-website" href="${syncEscape(safeSource(root.url))}" target="_blank" rel="noopener noreferrer">单位官网 ↗</a>`:'';
 if(!sources.length)return website;
 const labels={success:'已检查公开范围',blocked:'暂不可自动读取',failed:'检查未完成',not_checked:'待检查'};
 return `<div class="procurement-source-links"><span>采购来源</span>${sources.filter(s=>safeSource(s.url)).map(s=>`<a href="${syncEscape(safeSource(s.url))}" target="_blank" rel="noopener noreferrer" data-source-status="${syncEscape(s.status||'not_checked')}" title="${syncEscape(labels[s.status]||'待检查')}">${syncEscape(s.label)} ↗${s.status==='blocked'?' · 暂不可读':''}</a>`).join('')}</div>`+website;
}

function customerProcurementMarkup(customer){
  const rows=visibleProjectsFor(customer).filter(r=>safeSource(r.notice_url||r.url)).sort((a,b)=>(a.planned_purchase||a.deadline?.value||'9999').localeCompare(b.planned_purchase||b.deadline?.value||'9999'));
 const policies=(supplementFor(customer)?.policies||[]).filter(p=>safeSource(p.url));
 const policyMarkup=policies.length?`<section class="customer-tree-section"><h3>政策与建设方向</h3><p class="award-caption">规划方向，尚未确认具体采购安排</p>${policies.map(p=>`<div class="card-project-row"><div class="card-project-date"><span>发布日期</span><time>${syncEscape(p.date)}</time></div><a href="${syncEscape(safeSource(p.url))}" target="_blank" rel="noopener noreferrer">${syncEscape(p.title)} ↗</a><p class="customer-tree-caption">${syncEscape(p.summary)}</p></div>`).join('')}</section>`:'';
 return `<p class="award-caption">${rows.length} 条公开信息 · 按采购及截止日期排序</p>`+(rows.length?rows.map(r=>`<div class="card-project-row"><div class="card-project-date"><span>${syncEscape(r.stage)} · ${r.planned_purchase?'计划采购':r.deadline?.value?'截止时间':'采购日期'}</span><time>${syncEscape(r.planned_purchase||r.deadline?.value||'未公开')}</time></div><a href="${syncEscape(safeSource(r.notice_url||r.url))}" target="_blank" rel="noopener noreferrer">${syncEscape(r.name)} ↗</a></div>`).join(''):'<p class="org-empty">暂无已核实的有效采购意向或招标公告</p>')+policyMarkup;
 }

window.addEventListener('DOMContentLoaded',() => {
 const overlay=document.createElement('div');overlay.className='org-overlay procurement-overlay';overlay.hidden=true;
 overlay.innerHTML='<section class="org-drawer" role="dialog" aria-modal="true" aria-labelledby="procurement-title"><header class="org-header"><div><span>采购意向与公开招标</span><h2 id="procurement-title"></h2></div><button class="org-close" aria-label="关闭采购意向">×</button></header><div class="org-content procurement-content"></div></section>';
 document.body.append(overlay);let selected,trigger,timer;
 function render(){const name=document.createElement('textarea');name.innerHTML=selected[0];overlay.querySelector('h2').textContent=name.value;overlay.querySelector('.procurement-content').innerHTML=customerProcurementMarkup(selected);}
 function close(){overlay.classList.remove('is-open');document.body.classList.remove('org-open');clearTimeout(timer);timer=setTimeout(()=>overlay.hidden=true,260);if(trigger?.isConnected)trigger.focus();}
 document.getElementById('cards').addEventListener('click',e=>{const button=e.target.closest('[data-procurement-open]');if(!button)return;const id=decodeURIComponent(button.closest('.card').dataset.customerKey);selected=views.flatMap(v=>v.items).find(x=>customerIdentifier(x)===id);if(!selected)return;trigger=button;clearTimeout(timer);render();overlay.hidden=false;document.body.classList.add('org-open');requestAnimationFrame(()=>overlay.classList.add('is-open'));overlay.querySelector('button').focus();});
 overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('.org-close'))close();});
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}if(e.key==='Tab'){const a=[...overlay.querySelectorAll('button,a')],first=a[0],last=a.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
 for(const event of ['customers-updated','public-profiles-updated'])window.addEventListener(event,()=>{if(!selected||overlay.hidden)return;const id=customerIdentifier(selected),current=views.flatMap(v=>v.items).find(x=>customerIdentifier(x)===id);if(!current){close();return;}selected=current;render();});
});
