const{test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const c={URL,Date};vm.createContext(c);vm.runInContext(fs.readFileSync('public/award-history.js','utf8').split('(() => {')[0],c);vm.runInContext(fs.readFileSync('public/partners.js','utf8').split("window.addEventListener('DOMContentLoaded'")[0],c);vm.runInContext(fs.readFileSync('public/customer-trees.js','utf8').split('(() => {')[0],c);
test('customer industry tree keeps only selected customer evidence when marking global cooperation partners',()=>{
 const selected={url:'https://example.gov.cn/selected',date:'2026-10-26',buyer:'客户甲',awards:[{lotName:'客户甲建设',suppliers:['甲公司']}]};
 const global=[{name:'甲公司',type:'合作伙伴',customers:['客户乙'],evidence:[{url:'https://example.gov.cn/other',lotName:'其他客户建设',date:'2026-10-25'}],wins:1},{name:'乙公司',type:'合作伙伴',customers:['客户乙'],evidence:[],wins:0}];
 const partners=c.partnersForCustomerTree('客户甲',[selected],global);assert.equal(partners.length,1);assert.equal(partners[0].type,'合作伙伴');assert.equal(partners[0].evidence.length,1);assert.equal(partners[0].evidence[0].url,selected.url);assert.equal(partners[0].customers.join(','),'客户甲');assert.equal(c.partnersForCustomerTree('空客户',[],global).length,0);
});
