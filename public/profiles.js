const customerProfiles=new Map();
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
  const all=views.flatMap(v=>v.items),ids=[...new Set(all.map(customerIdentifier))];let incoming=[];
  if(!config.apiBaseUrl){const r=await fetch(new URL('./profile-data.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(!r.ok)throw Error('Information unavailable');const data=await r.json();if(!Array.isArray(data.profiles))throw Error('Invalid profiles');incoming=data.profiles;}
  else{const base=new URL(config.apiBaseUrl);if(base.protocol!=='https:')return;for(let i=0;i<ids.length;i+=25){const url=new URL('/api/profiles',base);for(const id of ids.slice(i,i+25))url.searchParams.append('id',id);const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('Unavailable');incoming.push(...(await r.json()).profiles);}}
  profileConnection='connected';
  for(const p of incoming)customerProfiles.set(p.id,p);
  for(const x of all){const p=profileFor(x);x[6]=[...new Set(visibleProjectsFor(x).map(r=>syncEscape(r.stage)))];if(profileLeaderCountFor(x))x[6].push('官网领导信息');x[4]=visibleProjectsFor(x).length?'有项目资料':profileLeaderCountFor(x)?'有领导资料':historyCountFor(x)?'有历史资料':organizationCountFor(x)?'有机构资料':basicInfoFor(x)?.overview?'有基础资料':'待补充资料';x[3]='待核实';x[2]=syncEscape(basicInfoFor(x)?.address||'');}
  for(const v of views)v.groups=[...new Set(v.items.map(x=>x[4]))];renderShell();window.dispatchEvent(new Event('public-profiles-updated'));
 }catch{document.getElementById('sync-status').textContent='公开资料暂时无法刷新，现有资料已保留';}
 finally{profilesBusy=false;if(profilesQueued){profilesQueued=false;refreshProfiles();}}
}
function profileProjectCountFor(x){return visibleProjectsFor(x).length;}
function profileLeaderCountFor(x){const all=[...(profileFor(x)?.leaders||[]),...(typeof organizationLeadersFor==='function'?organizationLeadersFor(x):[])];return new Set(all.map(p=>p.name)).size;}
function basicInfoFor(x){return typeof organizationInfoFor==='function'?organizationInfoFor(x):null;}
function historyCountFor(x){return typeof awardHistoryCountFor==='function'?awardHistoryCountFor(x):0;}
function organizationCountFor(x){return (basicInfoFor(x)?.nodes?.length||profileFor(x)?.organizations?.length||0);}
function profileCountFor(x){return profileProjectCountFor(x)+profileLeaderCountFor(x)+historyCountFor(x)+organizationCountFor(x)+(basicInfoFor(x)?.overview?1:0);}
function profilePreview(x){
 const basics=basicInfoFor(x);const overview=basics?.overview?`<div class="customer-overview"><p>${syncEscape(basics.overview)}</p>${safeSource((basics.basicSource||basics.source)?.url)?`<a href="${syncEscape(safeSource((basics.basicSource||basics.source).url))}" target="_blank" rel="noopener noreferrer">资料来源 ↗</a>`:''}</div>`:'';
 const p=profileFor(x),projects=visibleProjectsFor(x).sort((a,b)=>(b.planned_purchase||b.deadline?.value||'').localeCompare(a.planned_purchase||a.deadline?.value||'')),leaders=p?.leaders||[];
 if(!projects.length&&!leaders.length){
  const details=[];if(profileLeaderCountFor(x))details.push(profileLeaderCountFor(x)+' 位领导');if(organizationCountFor(x))details.push('机构设置');if(historyCountFor(x))details.push(historyCountFor(x)+' 条历史结果');
  if(details.length)return overview+`<p class="information-empty">${details.join(' · ')}</p>`;
  if(overview)return overview;
  if(typeof customerStatePreview==='function'&&customerStatePreview(x))return '';
  return '<p class="information-empty">暂无已核实的公开资料</p>';
 }
 return overview+`<div class="card-project-list">${projects.filter(r=>safeSource(r.notice_url||r.url)).map(r=>`<div class="card-project-row" data-featured="${Boolean(r.featured)}"><a href="${syncEscape(safeSource(r.notice_url||r.url))}" target="_blank" rel="noopener noreferrer" title="${syncEscape(r.buyer?.value||'')}">${syncEscape(r.name)} <span aria-hidden="true">↗</span></a><div class="card-project-date"><span>${r.planned_purchase?(r.stage==='招标意向'?'招标意向 · 计划招标':'采购意向 · 计划采购'):r.deadline?(r.stage==='公开招标公告'?'公开招标 · 投标截止':'采购公告 · 截止时间'):r.public_title_only?'公开标题 · 有效期待确认':'发布日期'}</span><time>${syncEscape(r.planned_purchase||r.deadline?.value||(r.public_title_only?'采购日期未公开':r.published_at||'未确认'))}</time></div></div>`).join('')}${leaders.map(r=>`<p class="leader-preview">${syncEscape(r.name)} · ${syncEscape(r.role)}</p>`).join('')}</div>`;
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
