const customerProfiles=new Map();
let profilesBusy=false, profilesQueued=false, profileConnection='unconfigured';
function customerIdentifier(x){const number=(x[9]||[]).find(([k])=>['集团编号','客户编号','ID'].includes(k))?.[1];const decoded=document.createElement('textarea');decoded.innerHTML=number||x[0];const value=decoded.value;return number?value:'name:'+value.normalize('NFKC').toLowerCase().replace(/\s+/g,'');}
function safeSource(url){try{const u=new URL(url);return u.protocol==='https:'?u.href:null;}catch{return null;}}
function extraProfile(x){
 const p=customerProfiles.get(customerIdentifier(x));
 if(!p)return `<div class="profile-empty">${profileConnection==='unconfigured'?'画像资料待接入':'尚未采集公开动态'}</div>`;
 const attrs=(p.attributes||[]).map(a=>`<dt>${syncEscape(a.field)}</dt><dd>${syncEscape(a.value)}</dd>`).join('');
 const signals=(p.signals||[]).map(s=>{const url=safeSource(s.url);if(!url)return '';return `<article class="evidence"><span class="evidence-kind">${syncEscape(s.category)} · ${s.status==='verified'?'已核实':'待核实'}</span><a href="${syncEscape(url)}" target="_blank" rel="noopener noreferrer">${syncEscape(s.title)} ↗</a><p>${syncEscape(s.excerpt)}</p><small>${s.published_at?'发布日期：'+syncEscape(s.published_at)+' · ':''}采集：${syncEscape(new Date(s.fetched_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}))}</small></article>`;}).join('');
 return `${attrs?`<dl class="business-attributes">${attrs}</dl>`:''}<h4>公开动态</h4>${signals||'<div class="profile-empty">暂无公开动态</div>'}${p.lastRun?`<p class="collection-status">最近采集：${syncEscape(new Date(p.lastRun.finished_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}))} · ${p.lastRun.status==='success'?'已完成':p.lastRun.status==='blocked'?'来源暂不可访问':'未完成'}</p>`:''}`;
}
async function refreshProfiles(){
 if(profilesBusy){profilesQueued=true;return;}profilesBusy=true;
 try{
  const config=await (await fetch(new URL('./profile-config.json?v='+Math.floor(Date.now()/60000),location.href),{cache:'no-store'})).json();
  if(!config.apiBaseUrl)return;
  document.getElementById('profile-toolbar').hidden=false;
  const base=new URL(config.apiBaseUrl);if(base.protocol!=='https:')return;
  const all=views.flatMap(v=>v.items);const ids=[...new Set(all.map(customerIdentifier))];const incoming=[];
  for(let i=0;i<ids.length;i+=25){const url=new URL('/api/profiles',base);for(const id of ids.slice(i,i+25))url.searchParams.append('id',id);const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('Profile service unavailable');const data=await r.json();if(!Array.isArray(data.profiles))throw Error('Invalid profiles');incoming.push(...data.profiles);}
  profileConnection='connected';
  document.getElementById('profile-status').textContent='';
  for(const p of incoming)customerProfiles.set(p.id,p);
  for(const x of all){const p=customerProfiles.get(customerIdentifier(x));x[6]=[...new Set((p?.signals||[]).map(s=>syncEscape(s.category)+(s.status==='verified'?'':' · 待核实')))];const attributes=new Map((p?.attributes||[]).map(a=>[a.field,a.value]));x[4]=syncEscape(attributes.get('客户类别')||'未分类');const level=attributes.get('等级');x[3]=['A','B','C'].includes(level)?level:'待核实';x[2]=syncEscape([attributes.get('一级属地'),attributes.get('二级属地')].filter(Boolean).join(' / '));}
  for(const v of views)v.groups=[...new Set(v.items.map(x=>x[4]))];
  renderShell();
 }catch{document.getElementById('profile-status').textContent='画像资料暂不可刷新';}
 finally{profilesBusy=false;if(profilesQueued){profilesQueued=false;refreshProfiles();}}
}
window.addEventListener('customers-updated',refreshProfiles);
setInterval(refreshProfiles,300000);
refreshProfiles();
