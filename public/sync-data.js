/* Public data only. API tokens never enter the browser. */
const syncEscape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let syncVersion = '', syncBusy = false;
const demoItems = views.map(v => v.items);
const demoGroups = views.map(v => v.groups);
function applySheetRows(rows) {
  const aliases = ['名称','客户名称','单位名称','企业名称','客户','单位','场景名称','伙伴名称'];
  const headerIndex = rows.findIndex(row => row.some(c => aliases.includes(String(c).trim())));
  // Unrecognized layouts still display losslessly in the source table.
  if (headerIndex < 0) return false;
  const headers = rows[headerIndex].map(x => String(x).trim());
  const column = names => headers.findIndex(h => names.includes(h));
  const nameCol = column(aliases), treeCol = column(['所属树','树类型','视图']);
  const groupCol = column(['板块','所属板块','分类','行业','客户类别']);
  const gradeCol = column(['等级','客户等级','重要程度']);
  const descCol = column(['描述','备注','客户描述','业务需求','需求']);
  const fullCol = column(['全称','单位全称','客户全称']);
  const addressCol = column(['地址','服务对象','地区']);
  const regionCols = [column(['一级属地']), column(['二级属地'])].filter(i=>i>=0);
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
    buckets[index].push(item);
  }
  for (let i=0;i<3;i++) {
    // A tree selector makes every bucket authoritative, including empty trees.
    const live = treeCol >= 0 || i===0;
    views[i].live=live;
    views[i].chanceKnown=chanceCol>=0;
    views[i].items=live?buckets[i]:demoItems[i];
    views[i].groups=live?[...new Set(buckets[i].map(x=>x[4]))]:demoGroups[i];
  }
  return true;
}
async function refreshSheetData() {
  if(syncBusy)return;
  syncBusy=true;
  try {
    const response=await fetch(new URL('./tencent-data.json',location.href),{cache:'no-store'});
    if(response.status===404){$('sync-status').textContent='等待首次同步：请运行 GitHub Actions 同步任务';return;}
    if(!response.ok)throw new Error('获取数据失败');
    const data=await response.json();
    if(!Array.isArray(data.rows)||!data.rows.every(r=>Array.isArray(r)&&r.every(c=>typeof c==='string'))||!Number.isFinite(Date.parse(data.updatedAt)))throw new Error('数据格式不正确');
    if(syncVersion===data.updatedAt)return;
    const mapped=applySheetRows(data.rows);
    const wrapper=document.createElement('div');wrapper.className='source-table-scroll';
    const table=document.createElement('table');table.className='source-table';
    const body=document.createElement('tbody');
    const columns=Math.max(0,...data.rows.map(r=>r.length));
    for(const row of data.rows){const tr=document.createElement('tr');for(let i=0;i<columns;i++){const td=document.createElement('td');td.textContent=row[i]||'';tr.appendChild(td);}body.appendChild(tr);}
    table.appendChild(body);wrapper.appendChild(table);$('sheet-table').replaceChildren(wrapper);
    const time=new Date(data.updatedAt).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'});
    $('sync-status').textContent=`最近数据变更：${time}（北京时间） · ${data.rows.length} 行`;
    document.querySelector('.sync-hint').textContent=mapped?'已连接腾讯表格；已识别的数据同步到对应树视图。没有对应数据源的树继续标注为示例。':'已连接腾讯表格，以下按原表展示。要生成三棵树卡片，请添加“名称”表头；可选添加“所属树、板块、等级、描述、能力、关联机会”等字段。下方卡片仍为示例。';
    document.querySelector('.dates').textContent='腾讯表格已连接 · '+(mapped?'卡片按表头映射':'原表展示');
    document.querySelector('footer span').textContent='腾讯表格数据公开同步；未接入的树视图继续使用示例数据。';group='全部板块';grade='全部等级';renderShell();syncVersion=data.updatedAt;
  } catch(error) {
    $('sync-status').textContent='本次检查失败，保留现有数据；请查看 GitHub Actions 同步记录';
  } finally {syncBusy=false;}
}
$('refresh-data').onclick=refreshSheetData;
refreshSheetData();setInterval(refreshSheetData,60000);
