const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const ctx={URL,Date};vm.createContext(ctx);vm.runInContext(fs.readFileSync('public/award-history.js','utf8').split('(() => {')[0],ctx);
test('award timeline sorts publication dates, deduplicates links and rejects unsafe or invalid records',()=>{
 const row=(date,url,title='结果公告')=>({date,url,title});
 const result=ctx.sortedAwardResults([row('2026-01-01','https://example.gov.cn/old'),row('2026-10-01','https://example.gov.cn/new'),row('2026-10-01','https://example.gov.cn/new#top'),row('2027-01-01','https://example.gov.cn/future'),row('2026-02-31','https://example.gov.cn/invalid'),row('2026-01-01','javascript:alert(1)'),row('2026-01-01','https://')],'2026-10-23');
 assert.equal(result.length,2);assert.equal(result[0].date,'2026-10-01');assert.equal(result[1].date,'2026-01-01');
});
test('top three counts verified lots, deduplicates rows and preserves separate subsidiaries',()=>{
 const rows=[{url:'https://example.gov.cn/a',date:'2026-10-01',awards:[{lotNumber:'1',lotName:'网络',suppliers:['甲公司']},{lotNumber:'1',lotName:'网络',suppliers:['甲公司']},{lotNumber:'2',lotName:'安全',suppliers:['甲公司']}]},{url:'https://example.gov.cn/a#top',date:'2026-10-01',awards:[{lotNumber:'1',lotName:'网络',suppliers:['甲公司']}]},{url:'https://example.gov.cn/b',date:'2026-10-02',awards:[{lotName:'服务',suppliers:['乙公司','丙公司']}]},{url:'https://example.gov.cn/c',date:'2026-10-03',awards:[{lotName:'维护',suppliers:['甲公司分公司']}]},{url:'https://example.gov.cn/d',date:'2026-10-04',title:'未知供应商'}];
 const top=ctx.awardSupplierTop3(rows);assert.equal(top.length,3);assert.equal(top[0].name,'甲公司');assert.equal(top[0].count,2);assert.equal(top[1].name,'甲公司分公司');assert.equal(top[1].count,1);
});
test('duplicate sparse records do not erase verified award details',()=>{
 const row={url:'https://example.gov.cn/a',date:'2026-10-01',title:'结果公告',awards:[{lotName:'服务',suppliers:['甲公司']}]};
 assert.equal(ctx.sortedAwardResults([row,{url:row.url,date:row.date,title:row.title}],'2026-10-26')[0].awards[0].suppliers[0],'甲公司');
});
