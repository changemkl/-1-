const customerProfiles=new Map();
let profilesBusy=false, profilesQueued=false, profileConnection='unconfigured';
function customerIdentifier(x){const number=(x[9]||[]).find(([k])=>['集团编号','客户编号','ID'].includes(k))?.[1];const decoded=document.createElement('textarea');decoded.innerHTML=number||x[0];const value=decoded.value;return number?value:'name:'+value.normalize('NFKC').toLowerCase().replace(/\s+/g,'');}
function safeSource(url){try{const u=new URL(url);return u.protocol==='https:'?u.href:null;}catch{return null;}}
function extraProfile(x){
 const p=customerProfiles.get(customerIdentifier(x));
 if(!p)return `<div class="profile-empty">${profileConnection==='unconfigured'?'公开资料加载中':'尚未采集到相关公开信息'}</div>`;
 const attrs=(p.attributes||[]).map(a=>`<dt>${syncEscape(a.field)}</dt><dd>${syncEscape(a.value)}</dd>`).join('');
 const signals=(p.signals||[]).map(s=>{const url=safeSource(s.url);if(!url)return '';return `<article class="evidence"><span class="evidence-kind">${syncEscape(s.category)} · ${syncEscape(s.source_host||new URL(url).hostname)}</span><a href="${syncEscape(url)}" target="_blank" rel="noopener noreferrer">${syncEscape(s.title)} ↗</a><p>${syncEscape(s.excerpt)}</p><small>${s.published_at?'发布日期：'+syncEscape(s.published_at)+' · ':''}采集：${syncEscape(new Date(s.fetched_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}))}</small></article>`;}).join('');
 return `${attrs?`<dl class="business-attributes">${attrs}</dl>`:''}<h4>公开动态</h4>${signals||`<div class="profile-empty">${p.lastRun?'暂未发现相关公开动态':'尚未采集到相关公开信息'}</div>`}${p.lastRun?`<p class="collection-status">最近采集：${syncEscape(new Date(p.lastRun.finished_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}))} · ${p.lastRun.status==='success'?'已完成':p.lastRun.status==='blocked'?'来源暂不可访问':'未完成'}</p>`:''}`;
}
async function refreshProfiles(){
 if(profilesBusy){profilesQueued=true;return;}profilesBusy=true;
 try{
  const config=await (await fetch(new URL('./profile-config.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'})).json();
  const all=views.flatMap(v=>v.items);const ids=[...new Set(all.map(customerIdentifier))];let incoming=[];
  if(!config.apiBaseUrl){
    const r=await fetch(new URL('./profile-data.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'});if(!r.ok)throw Error('Information unavailable');
    const data=await r.json();if(!Array.isArray(data.profiles))throw Error('Invalid information');incoming=data.profiles;
  }else{
  const base=new URL(config.apiBaseUrl);if(base.protocol!=='https:')return;
  for(let i=0;i<ids.length;i+=25){const url=new URL('/api/profiles',base);for(const id of ids.slice(i,i+25))url.searchParams.append('id',id);const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('Profile service unavailable');const data=await r.json();if(!Array.isArray(data.profiles))throw Error('Invalid profiles');incoming.push(...data.profiles);}
  }
  profileConnection='connected';
  
  for(const p of incoming)customerProfiles.set(p.id,p);
  for(const x of all){const p=customerProfiles.get(customerIdentifier(x));x[6]=[...new Set((p?.signals||[]).map(s=>syncEscape(s.category)))];const attributes=new Map((p?.attributes||[]).map(a=>[a.field,a.value]));x[4]=syncEscape(attributes.get('客户类别')||((p?.signals||[]).length?'有公开动态':'暂无公开动态'));const level=attributes.get('等级');x[3]=['A','B','C'].includes(level)?level:'待核实';x[2]=syncEscape([attributes.get('一级属地'),attributes.get('二级属地')].filter(Boolean).join(' / '));}
  for(const v of views)v.groups=[...new Set(v.items.map(x=>x[4]))];
  renderShell();
 }catch{document.getElementById('sync-status').textContent='公开信息暂时无法刷新，现有资料已保留';}
 finally{profilesBusy=false;if(profilesQueued){profilesQueued=false;refreshProfiles();}}
}
window.addEventListener('customers-updated',refreshProfiles);
setInterval(refreshProfiles,300000);
refreshProfiles();

function profileCountFor(x){return (customerProfiles.get(customerIdentifier(x))?.signals||[]).length;}
function profilePreview(x){const p=customerProfiles.get(customerIdentifier(x));const signals=p?.signals||[];if(!signals.length)return `<p class="information-empty">${p?.lastRun?.status==='blocked'?'来源暂不可访问，待后续更新':'暂未收录公开动态'}</p>`;return `<div class="public-preview"><span class="preview-label">最新公开动态</span>${signals.slice(0,2).map(s=>{const url=safeSource(s.url);return url?`<a href="${syncEscape(url)}" target="_blank" rel="noopener noreferrer">${syncEscape(s.title)} ↗</a>`:'';}).join('')}</div>`;}

function profileSearchFor(x){return (customerProfiles.get(customerIdentifier(x))?.signals||[]).map(s=>s.title+' '+s.excerpt).join(' ');}
