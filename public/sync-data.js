/* Public data only. API tokens never enter the browser. */
const syncEscape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let syncVersion = '', syncBusy = false;
function applySheetRows(rows) {
  const aliases = ['名称','客户名称','单位名称','企业名称','客户','单位','场景名称','伙伴名称'];
  const headerIndex = rows.findIndex(row => row.some(c => aliases.includes(String(c).trim())));
  // Keep the current customer list if the header cannot be recognized.
  if (headerIndex < 0) return false;
  const headers = rows[headerIndex].map(x => String(x).trim());
  const column = names => headers.findIndex(h => names.includes(h));
  const nameCol = column(aliases), treeCol = column(['所属树','树类型','视图']);
  const groupCol = ['行业分类','客户分类','分类','客户行业','所属行业','行业','所属板块','板块','客户类别'].map(h=>headers.indexOf(h)).find(i=>i>=0) ?? -1;
  const gradeCol = column(['等级','客户等级','重要程度']);
  const descCol = column(['描述','备注','客户描述','业务需求','需求']);
  const fullCol = column(['全称','单位全称','客户全称']);
  const addressCol = column(['地址','服务对象','地区']);
  const regionCols = [column(['一级属地']), column(['二级属地'])].filter(i=>i>=0);
  const customerTagsCol = column(['客户标签']);
  const skillsCol = column(['能力','产品能力','标签','关键词','客户标签']);
  const chanceCol = column(['关联机会','机会数','关联机会数']);
  const profileCol = column(['已画像','画像状态','已完善画像']);
  const buckets = [[],[],[]];
  for (const row of rows.slice(headerIndex+1)) {
    if (!String(row[nameCol] ?? '').trim()) continue;
    const tree = treeCol < 0 ? '客户组织树' : String(row[treeCol] || '客户组织树').trim();
    const index = views.findIndex(v => v.name === tree);
    if (index < 0) throw new Error('存在未识别的所属树，请使用客户组织树、产业链树或产品与场景树');
    const text = col => col < 0 ? '' : String(row[col] ?? '').trim();
    const level = text(gradeCol).toUpperCase().match(/^[ABC]/)?.[0] || '待核实';
    const raw = [text(nameCol),text(fullCol)||text(nameCol),text(addressCol)||regionCols.map(i=>text(i)).filter(Boolean).join(' / '),level,text(groupCol)||'未分类',text(descCol),text(skillsCol).split(/[、,，;；]/).filter(Boolean),Math.max(0,Number(text(chanceCol))||0),['是','已画像','已完善','true','1'].includes(text(profileCol))];
    const item=raw.map((x,i) => i===6?x.map(syncEscape):typeof x==='string'?syncEscape(x):x);
    item.push(headers.map((label,col)=>[syncEscape(label),syncEscape(row[col]||'')]).filter(([label])=>label));
    item.push([...new Set(text(customerTagsCol).split(/[、,，;；\n]+/).map(t=>t.trim()).filter(Boolean))].map(syncEscape));
    buckets[index].push(item);
  }
  for (let i=0;i<3;i++) {
    // A tree selector makes every bucket authoritative, including empty trees.
    const live = treeCol >= 0 || i===0;
    views[i].live=true;
    views[i].chanceKnown=chanceCol>=0;
    if(i===1&&typeof rebuildPartners==='function')continue;
    views[i].items=buckets[i];
    views[i].groups=[...new Set(buckets[i].map(x=>x[4]))];
  }
  return true;
}
async function refreshSheetData(force=false) {
  if(syncBusy)return;
  syncBusy=true;
  try {
    const dataUrl=new URL('./tencent-data.json',location.href);
    dataUrl.searchParams.set('v',String(force?Date.now():Math.floor(Date.now()/60000)));
    const response=await fetch(dataUrl,{cache:'no-store'});
    if(response.status===404){$('sync-status').textContent='客户资料暂未更新';return;}
    if(!response.ok)throw new Error('获取数据失败');
    const data=await response.json();
    if(!Array.isArray(data.rows)||!data.rows.every(r=>Array.isArray(r)&&r.every(c=>typeof c==='string'))||!Number.isFinite(Date.parse(data.updatedAt)))throw new Error('数据格式不正确');
    if(syncVersion===data.updatedAt)return;
    applySheetRows(data.rows);
    const time=new Date(data.updatedAt).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'});
    $('sync-status').textContent=`资料更新：${time}`;
    group='全部板块';grade='全部等级';renderShell();syncVersion=data.updatedAt;window.dispatchEvent(new Event('customers-updated'));
  } catch(error) {
    $('sync-status').textContent=syncVersion?'暂时无法刷新，当前资料已保留':'客户资料加载失败，请稍后重试';
  } finally {syncBusy=false;}
}
refreshSheetData();setInterval(refreshSheetData,60000);
