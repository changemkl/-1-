const{test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const c={URL,Date};vm.createContext(c);vm.runInContext(fs.readFileSync('public/award-history.js','utf8').split('(() => {')[0],c);vm.runInContext(fs.readFileSync('public/partners.js','utf8').split("window.addEventListener('DOMContentLoaded'")[0],c);
test('potential partners deduplicate awarded lots, retain customer evidence and exclude our company',()=>{
 const row={url:'https://example.gov.cn/a',date:'2026-10-01',buyer:'客户甲直属单位',awards:[{lotNumber:'1',lotName:'网络',suppliers:['甲公司','中移动系统集成有限公司']},{lotNumber:'2',lotName:'安全',suppliers:['甲公司']}]};
 const partners=c.aggregatePartnerSuppliers([{name:'客户甲',results:[row,row]},{name:'客户乙',results:[row]}]);assert.equal(partners.length,1);assert.equal(partners[0].name,'甲公司');assert.equal(partners[0].wins,2);assert.equal(partners[0].customers.length,2);assert.equal(partners[0].evidence[0].buyer,'客户甲直属单位');
});
test('existing partners replace potential entries without losing award evidence',()=>{
 const potential=[{name:'甲公司',type:'潜在合作伙伴',evidence:[{lotName:'网络'}],customers:['客户甲'],wins:1}];
 const partners=c.mergeCooperationPartners(potential,[{name:'甲公司',notes:'已合作',capabilities:'网络安全'},{name:'乙公司',notes:'线下合作'}]);assert.equal(partners.length,2);assert.equal(partners[0].type,'合作伙伴');assert.equal(partners[0].wins,1);assert.equal(partners[0].evidence.length,1);assert.equal(partners[1].wins,0);assert.equal(potential[0].type,'潜在合作伙伴');
});
test('platform aliases promote supplier records without duplicating wins and local edits retain import status',()=>{
 const potential=[{name:'浙江大华技术股份有限公司',type:'潜在合作伙伴',evidence:[{url:'https://example.gov.cn/a',lotNumber:'1',lotName:'视频',date:'2026-01-01'}],customers:['客户甲'],wins:1}];
 const imported=c.mergeCooperationPartners(potential,[{name:'浙江大华技术股份有限公司',aliases:['大华'],source:'东风平台',relationship:'有合作记录',capabilities:'视频'}]);
 const edited=c.mergeCooperationPartners(imported,[{name:'大华',notes:'本地备注'}]);assert.equal(edited.length,1);assert.equal(edited[0].type,'合作伙伴');assert.equal(edited[0].relationship,'有合作记录');assert.equal(edited[0].source,'东风平台');assert.equal(edited[0].wins,1);
});
test('telecom and unicom competitors are excluded from crawled, saved and alias partner entries',()=>{
 const rows=[{url:'https://example.gov.cn/a',date:'2026-10-26',awards:[{lotName:'服务',suppliers:['中国电信股份有限公司上海分公司','中电信数智科技有限公司','中国联合网络通信有限公司上海市分公司','中国联通有限公司','甲公司']}]}];
 const potential=c.aggregatePartnerSuppliers([{name:'客户甲',results:rows}]);assert.equal(potential.length,1);assert.equal(potential[0].name,'甲公司');
 assert(!potential.some(p=>/电信|联通/.test(p.name)));
 const merged=c.mergeCooperationPartners([{name:'电信公司'},{name:'甲公司'}],[{name:'乙公司',aliases:['联 通公司']},{name:'中电信数智公司'},{name:'丙公司'}]);assert.equal(merged.map(p=>p.name).join(','),'甲公司,丙公司');
 assert.equal(c.awardSupplierTop3(rows).length,3); // Original historical results and competitor statistics stay intact.
});
