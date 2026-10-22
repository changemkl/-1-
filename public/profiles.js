const customerProfiles=new Map();
let profilesBusy=false,profilesQueued=false,profileConnection='unconfigured';
function customerIdentifier(x){const number=(x[9]||[]).find(([k])=>['集团编号','客户编号','ID'].includes(k))?.[1];const decoded=document.createElement('textarea');decoded.innerHTML=number||x[0];return number?decoded.value:'name:'+decoded.value.normalize('NFKC').toLowerCase().replace(/\s+/g,'');}
function safeSource(url){try{const u=new URL(url);return u.protocol==='https:'?u.href:null;}catch{return null;}}
function profileFor(x){return customerProfiles.get(customerIdentifier(x));}
function sourceLink(p){const url=safeSource(p.url);return url?`<a class="original-source" href="${syncEscape(url)}" target="_blank" rel="noopener noreferrer">原文 · ${syncEscape(new URL(url).hostname)} ↗</a>`:'';}
function sourceTime(p){return `${p.published_at?'发布：'+syncEscape(p.published_at)+' · ':'发布日期未确认 · '}采集：${syncEscape(new Date(p.fetched_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}))}`;}
function projectHTML(p){const url=safeSource(p.url);if(!url)return '';const fields=[['采购人',p.buyer],['中标/成交供应商',p.supplier],['公告预算',p.budget],['中标/合同金额',p.award_amount],['提交截止',p.deadline],['明确的服务结束日期',p.service_end],['计划采购月份',p.planned_purchase?{quote:p.planned_purchase}:null]].filter(([,v])=>v?.quote);return `<article class="evidence project-evidence"><span class="evidence-kind">${syncEscape(p.stage)}</span><h5>${syncEscape(p.name)}</h5><p class="project-relation">${syncEscape(p.relation)}</p>${fields.length?`<dl>${fields.map(([label,v])=>`<dt>${label}</dt><dd>${syncEscape(v.quote)}</dd>`).join('')}</dl>`:''}${p.budget_scope?`<p class="budget-scope">${syncEscape(p.budget_scope)}</p>`:''}${!p.budget?'<span class="unconfirmed-field">预算未确认</span>':''}<blockquote>${syncEscape(p.quote)}</blockquote><p class="fact-notice">${syncEscape(p.notice)}</p>${sourceLink(p)}<small>${sourceTime(p)}</small></article>`;}
function leaderHTML(p){if(!safeSource(p.url))return '';return `<article class="evidence leader-evidence"><h5>${syncEscape(p.name)} <span>${syncEscape(p.role)}</span></h5><p class="leader-status">${syncEscape(p.status)}</p><dl><dt>分工</dt><dd>${syncEscape(p.division||'未确认，不推断信息化分管职责')}</dd></dl><blockquote>${syncEscape(p.role_quote)}${p.division_quote?'\n'+syncEscape(p.division_quote):''}</blockquote>${sourceLink(p)}<small>${sourceTime(p)}</small></article>`;}
function extraProfile(x){const p=profileFor(x);const projects=p?.projects||[],leaders=p?.leaders||[];return `<section class="fact-section"><h4>项目与采购 <span>${projects.length}</span></h4>${projects.map(projectHTML).join('')||'<p class="profile-empty">暂未取得可核验的项目与采购资料；不代表没有建设需求。</p>'}</section><section class="fact-section"><h4>领导及正式分工 <span>${leaders.length}</span></h4>${leaders.map(leaderHTML).join('')||'<p class="profile-empty">暂未取得可核验的领导页面或分工信息，不从会议报道推断现任。</p>'}</section>${p?.lastRun?`<p class="collection-status">来源检查：${syncEscape(new Date(p.lastRun.finished_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}))} · ${p.lastRun.status==='success'?'已完成':p.lastRun.status==='blocked'?'暂不可访问':'未完成'}</p>`:''}`;}
async function refreshProfiles(){
 if(profilesBusy){profilesQueued=true;return;}profilesBusy=true;
 try{
  const config=await(await fetch(new URL('./profile-config.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'})).json();
  const all=views.flatMap(v=>v.items),ids=[...new Set(all.map(customerIdentifier))];let incoming=[];
  if(!config.apiBaseUrl){const r=await fetch(new URL('./profile-data.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(!r.ok)throw Error('Information unavailable');const data=await r.json();if(!Array.isArray(data.profiles))throw Error('Invalid profiles');incoming=data.profiles;}
  else{const base=new URL(config.apiBaseUrl);if(base.protocol!=='https:')return;for(let i=0;i<ids.length;i+=25){const url=new URL('/api/profiles',base);for(const id of ids.slice(i,i+25))url.searchParams.append('id',id);const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('Unavailable');incoming.push(...(await r.json()).profiles);}}
  profileConnection='connected';
  for(const p of incoming)customerProfiles.set(p.id,p);
  for(const x of all){const p=profileFor(x);x[6]=[...new Set((p?.projects||[]).map(r=>syncEscape(r.stage)))];if(p?.leaders?.length)x[6].push('官网领导信息');x[4]=p?.projects?.length?'有项目资料':p?.leaders?.length?'仅领导资料':'待补充资料';x[3]='待核实';x[2]='';}
  for(const v of views)v.groups=[...new Set(v.items.map(x=>x[4]))];renderShell();
 }catch{document.getElementById('sync-status').textContent='公开资料暂时无法刷新，现有资料已保留';}
 finally{profilesBusy=false;if(profilesQueued){profilesQueued=false;refreshProfiles();}}
}
function profileProjectCountFor(x){return(profileFor(x)?.projects||[]).length;}
function profileLeaderCountFor(x){return(profileFor(x)?.leaders||[]).length;}
function profileCountFor(x){return profileProjectCountFor(x)+profileLeaderCountFor(x);}
function profilePreview(x){const p=profileFor(x),projects=p?.projects||[],leaders=p?.leaders||[];if(!projects.length&&!leaders.length)return '<p class="information-empty">项目与领导资料待补充，不用普通新闻替代。</p>';return `<div class="public-preview"><span class="preview-label">项目与采购 ${projects.length} · 领导资料 ${leaders.length}</span>${projects.slice(0,2).map(r=>{const url=safeSource(r.url);return url?`<a href="${syncEscape(url)}" target="_blank" rel="noopener noreferrer"><span class="project-stage">${syncEscape(r.stage)}</span>${syncEscape(r.name)} ↗</a>`:'';}).join('')}${leaders.slice(0,2).map(r=>`<p class="leader-preview">${syncEscape(r.name)} · ${syncEscape(r.role)}<small>官网列示</small></p>`).join('')}</div>`;}
function profileSearchFor(x){const p=profileFor(x);return[...(p?.projects||[]).map(r=>r.name+' '+r.quote+' '+(r.buyer?.value||'')),...(p?.leaders||[]).map(r=>r.name+' '+r.role+' '+(r.division||''))].join(' ');}
window.addEventListener('customers-updated',refreshProfiles);setInterval(refreshProfiles,300000);refreshProfiles();

function renderProcurementOverview(items){
 const section=document.getElementById('procurement-overview');if(!section)return;
 const notices=items.flatMap(x=>(profileFor(x)?.projects||[]).filter(p=>p.featured&&safeSource(p.url)).map(p=>({...p,customer:x[0]}))).filter(p=>(p.customer+' '+p.name+' '+p.quote+' '+(p.buyer?.value||'')).toLowerCase().includes(query.toLowerCase())).sort((a,b)=>(b.planned_purchase||b.deadline?.value||'').localeCompare(a.planned_purchase||a.deadline?.value||''));
 section.hidden=view!==0||!notices.length;
 section.innerHTML=`<div class="procurement-heading"><h2>采购意向与公告 <span>${notices.length}</span></h2></div><div class="procurement-list">${notices.map(p=>`<article class="procurement-row"><div class="procurement-date"><time>${syncEscape(p.planned_purchase||p.deadline?.value||'待确认')}</time><span>${p.planned_purchase?'计划采购月份':p.deadline?'响应截止时间':'采购日期'}</span></div><a class="procurement-title" href="${syncEscape(safeSource(p.url))}" target="_blank" rel="noopener noreferrer" title="${syncEscape(p.buyer?.value||'')}">${syncEscape(p.name)} <span aria-hidden="true">↗</span></a></article>`).join('')}</div>`;
}
