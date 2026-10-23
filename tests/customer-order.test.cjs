const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('node:vm');
test('customers with verified information precede empty customers regardless of grade',()=>{
 const c={document:{getElementById(){}},profileCountFor:x=>({history:54,leaders:8,empty:0}[x[0]])};vm.createContext(c);
 vm.runInContext(fs.readFileSync('public/app.js','utf8').split("$('search').oninput")[0],c);
 vm.runInContext("views[0].items=[['empty','','','A','待补充资料','',[],0],['leaders','','','C','有领导资料','',[],0],['history','','','B','有历史资料','',[],0]]",c);
 assert.equal(vm.runInContext('filtered().map(x=>x[0]).join(",")',c),'history,leaders,empty');
});
