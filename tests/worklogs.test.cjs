const{test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const c={};vm.createContext(c);vm.runInContext(fs.readFileSync('public/worklogs.js','utf8').split('(() => {')[0],c);
test('work log timeline matches current customer identity and orders real work dates before unknown dates',()=>{
 const rows=[{id:'1',customerId:'a',customerName:'客户甲',workDate:'2026-10-25',content:'旧工作'},{id:'2',customerId:'a',customerName:'客户甲',workDate:'2026-10-26',content:'新工作'},{id:'3',customerId:'a',customerName:'客户甲',workDate:null,content:'未注明日期'},{id:'4',customerId:'b',customerName:'客户乙',content:'别家工作'},{id:'5',customerId:'a',customerName:'旧客户名称',content:'改名前的记录'},{id:'6',customerId:'a',customerName:'客户甲',content:' '}];
 const logs=c.sortedCustomerWorklogs(rows,'a','客户甲');assert.equal(logs.map(r=>r.id).join(','),'2,1,3');
});
