const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const ctx={URL,Date};vm.createContext(ctx);vm.runInContext(fs.readFileSync('public/award-history.js','utf8').split('(() => {')[0],ctx);
test('award timeline sorts publication dates, deduplicates links and rejects unsafe or invalid records',()=>{
 const row=(date,url,title='结果公告')=>({date,url,title});
 const result=ctx.sortedAwardResults([row('2026-01-01','https://example.gov.cn/old'),row('2026-10-01','https://example.gov.cn/new'),row('2026-10-01','https://example.gov.cn/new#top'),row('2027-01-01','https://example.gov.cn/future'),row('2026-02-31','https://example.gov.cn/invalid'),row('2026-01-01','javascript:alert(1)'),row('2026-01-01','https://')],'2026-10-23');
 assert.equal(result.length,2);assert.equal(result[0].date,'2026-10-01');assert.equal(result[1].date,'2026-01-01');
});
