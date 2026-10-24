const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
test('industry classification takes priority over company type and labels',()=>{
 const context={views:[{name:'客户组织树'},{name:'产业链树'},{name:'产品与场景树'}]};vm.createContext(context);
 vm.runInContext(fs.readFileSync('public/sync-data.js','utf8').split('async function refreshSheetData')[0],context);
 context.applySheetRows([['客户名称','客户类别','行业分类','客户标签'],['甲单位','政府','党政','集团1390'],['乙单位','企业','文旅','重点']]);
 assert.equal(context.views[0].items[0][4],'党政');assert.equal(context.views[0].items[1][4],'文旅');
 context.applySheetRows([['客户名称','客户类别','客户标签'],['甲单位','政府','集团1390']]);
 assert.equal(context.views[0].items[0][4],'政府');
});
