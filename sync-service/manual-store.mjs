import {DatabaseSync} from 'node:sqlite';
import crypto from 'node:crypto';
const fields={person:{name:200,department:200,role:200,businessRole:200,topic:200,notes:600,infoSource:200,learnedDate:10,sourceUrl:1000,sourceTitle:200},project:{title:200,description:600,progress:600,nextAction:600,infoSource:200},log:{workDate:10,content:1800,infoSource:200,projectId:250,projectName:200,projectType:20}};
const required={person:['name'],project:['title','description'],log:['workDate','content']};
const fail=(message,status=400)=>{throw Object.assign(Error(message),{status});};
function date(value){if(!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;const stamp=new Date(value+'T00:00:00Z');return Number.isFinite(stamp.getTime())&&stamp.toISOString().slice(0,10)===value;}
export function createManualStore(file){
 const db=new DatabaseSync(file);db.exec('PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS manual_records (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)');
 return {
  list:()=>db.prepare('SELECT payload FROM manual_records ORDER BY id').all().map(r=>JSON.parse(r.payload)),
  save(input){
   if(!input||typeof input!=='object'||!Object.hasOwn(fields,input.type))fail('Invalid record type');
   if(typeof input.customerId!=='string'||!input.customerId.trim()||input.customerId.length>250||typeof input.customerName!=='string'||!input.customerName.trim()||input.customerName.length>250)fail('Invalid customer identity');
   const record={id:input.id||crypto.randomUUID(),type:input.type,customerId:input.customerId,customerName:input.customerName};
   if(typeof record.id!=='string'||!/^[a-zA-Z0-9-]{1,100}$/.test(record.id))fail('Invalid record identifier');
   for(const[key,max]of Object.entries(fields[input.type])){if(input[key]!=null&&typeof input[key]!=='string')fail('Invalid field');const value=(input[key]||'').trim();if(value.length>max)fail('Field too long');record[key]=value;}
   if(record.sourceUrl){try{if(new URL(record.sourceUrl).protocol!=='https:')fail('Invalid source URL');}catch{fail('Invalid source URL');}}
   for(const key of required[input.type])if(!record[key])fail('Missing required field');
   for(const key of ['workDate','learnedDate'])if(record[key]&&!date(record[key]))fail('Invalid date');
   const old=db.prepare('SELECT revision,payload FROM manual_records WHERE id=?').get(record.id);
   if(old){const prior=JSON.parse(old.payload);if(prior.customerId!==record.customerId||prior.customerName!==record.customerName||prior.type!==record.type)fail('Customer identity cannot be changed',409);if(input.revision!==old.revision)fail('Record changed; reload and retry',409);record.createdAt=prior.createdAt;}else{if(input.revision)fail('Record no longer exists',409);if(db.prepare('SELECT count(*) AS n FROM manual_records').get().n>=10000)fail('Record limit reached',409);record.createdAt=new Date().toISOString();}
   record.updatedAt=new Date().toISOString();record.revision=(old?.revision||0)+1;record.position=Number.isFinite(input.position)?input.position:Date.now();
   if(old){const result=db.prepare('UPDATE manual_records SET revision=?,payload=? WHERE id=? AND revision=?').run(record.revision,JSON.stringify(record),record.id,old.revision);if(result.changes!==1)fail('Record changed; reload and retry',409);}else{try{db.prepare('INSERT INTO manual_records VALUES(?,?,?)').run(record.id,record.revision,JSON.stringify(record));}catch{fail('Record already exists',409);}}
   return record;
  },
  remove(id,revision){const r=db.prepare('DELETE FROM manual_records WHERE id=? AND revision=?').run(id,revision);if(r.changes!==1)fail('Record changed or deleted; reload and retry',409);},
  close:()=>db.close()
 };
}
