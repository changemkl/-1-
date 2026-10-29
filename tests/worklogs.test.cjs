const{test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const c={};vm.createContext(c);vm.runInContext(fs.readFileSync('public/worklogs.js','utf8').split('(() => {')[0],c);
test('work log timeline matches current customer identity and orders real work dates before unknown dates',()=>{
 const rows=[{id:'1',customerId:'a',customerName:'客户甲',workDate:'2026-10-25',content:'旧工作'},{id:'2',customerId:'a',customerName:'客户甲',workDate:'2026-10-26',content:'新工作'},{id:'3',customerId:'a',customerName:'客户甲',workDate:null,content:'未注明日期'},{id:'4',customerId:'b',customerName:'客户乙',content:'别家工作'},{id:'5',customerId:'a',customerName:'旧客户名称',content:'改名前的记录'},{id:'6',customerId:'a',customerName:'客户甲',content:' '}];
 const logs=c.sortedCustomerWorklogs(rows,'a','客户甲');assert.equal(logs.map(r=>r.id).join(','),'2,1,3');
});
test('project log groups preserve multiple associations, conversion aliases and unassigned work',()=>{
 const context={};vm.createContext(context);vm.runInContext(fs.readFileSync('public/worklogs.js','utf8').split('(() => {')[0],context);
 const projects=[{id:'a',aliasIds:['old-lead'],name:'算力项目',type:'商机'},{id:'b',name:'视频项目',type:'线索'}];
 const rows=[{id:'one',projectIds:['old-lead'],workDate:'2026-10-28'},{id:'two',projectIds:['a','b'],workDate:'2026-10-29'},{id:'three',content:'日常交流',workDate:'2026-10-29'}];
 const groups=context.groupCustomerWorklogs(rows,projects);assert.equal(groups.length,3);assert.equal(groups.find(g=>g.id==='a').rows.length,2);assert.equal(groups.find(g=>g.id==='b').rows.length,1);assert.equal(groups.at(-1).id,'__customer__');assert.equal(groups.find(g=>g.id==='a').latest,'2026-10-29');
});
