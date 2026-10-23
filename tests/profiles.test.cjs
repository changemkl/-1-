const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const context={URL,location:{href:'https://example.test/'},window:{addEventListener(){}},setInterval(){},fetch:()=>new Promise(()=>{}),Date,Intl};
vm.createContext(context);
vm.runInContext(fs.readFileSync('public/profiles.js','utf8'),context);
const clock=new Date('2026-10-22T04:00:00Z');

test('intent dates use procurement dates, retain current month without inventing a day',()=>{
 for(const date of ['2025-11','2026-04','2026-10-21',''])
  assert.equal(context.projectIsCurrent({stage:'采购意向',planned_purchase:date},clock),false,date);
 for(const date of ['2026-10','2026-10-22','2026-11','2027-01'])
  assert.equal(context.projectIsCurrent({stage:'采购意向',planned_purchase:date},clock),true,date);
});
test('open tenders require an explicit deadline that has not passed in China time',()=>{
 assert.equal(context.projectIsCurrent({stage:'公开招标公告',deadline:{value:'2026-10-23 09:00'}},clock),true);
 assert.equal(context.projectIsCurrent({stage:'公开招标公告',deadline:{value:'2026-10-22 11:59'}},clock),false);
 assert.equal(context.projectIsCurrent({stage:'公开招标公告'},clock),false);
 assert.equal(context.shanghaiDate(new Date('2026-10-21T16:00:00Z')),'2026-10-22');
});
test('public title records can have unknown dates without being called active tenders',()=>{
 const p={stage:'公开招标公告',public_title_only:true,fetched_at:'2026-10-22T03:00:00Z'};
 assert.equal(context.projectIsCurrent(p,clock),true);
 assert.equal(context.projectIsCurrent({...p,deadline:{value:'2026-10-21 09:00'}},clock),false);
 assert.equal(context.projectIsCurrent({...p,fetched_at:'2025-01-01T00:00:00Z'},clock),false);
 assert.equal(context.projectIsCurrent({...p,stage:'招标意向',planned_purchase:'2026-09'},clock),false);
 assert.equal(context.projectIsCurrent({...p,stage:'招标意向',planned_purchase:'2026-11'},clock),true);
});
