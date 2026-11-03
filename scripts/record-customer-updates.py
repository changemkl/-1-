"""Persist business-data change discovery times across scheduled sync runs."""
import datetime,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'intelligence/customer-update-state.json'
OUTPUT=ROOT/'public/customer-updates.json'
IGNORED={'updatedAt','updated_at','fetched_at','checkedAt','firstSeenAt','lastSeenAt','lastRun','lastCheck','detailCheck','coverage','procurementSources','externalSourceChecks','finished_at','recordUpdatedDate','sourceRow','cell','column'}
def read(path,default):
 try:return json.loads(path.read_text())
 except FileNotFoundError:return default

def normalize(value):
 if isinstance(value,dict):return {k:normalize(v) for k,v in sorted(value.items()) if k not in IGNORED}
 if isinstance(value,list):return sorted([normalize(v) for v in value],key=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True))
 return value

def fingerprint(value):return hashlib.sha256(json.dumps(normalize(value),ensure_ascii=False,sort_keys=True).encode()).hexdigest()
DETAIL_LABELS={'工作日志','商机进展','采购意向与招标','历史招标结果','合同信息'}
def record_key(source,item):
 identity=item.get('id') or item.get('notice_url') or item.get('url') or item.get('sourceRecordId') or (str(item.get('projectName',item.get('name',item.get('title',''))))+'|'+str(item.get('date',item.get('workDate',''))))
 return source+':'+str(identity)
def changed_items(current,previous):
 changes=[]
 for key,item in current.items():
  if key not in previous or item['hash']!=previous[key]['hash']:
   changes.append({'key':key,'change':'新增' if key not in previous else '修改','record':json.loads(json.dumps(item['data']))})
 for key,item in previous.items():
  if key not in current:changes.append({'key':key,'change':'移除','record':json.loads(json.dumps(item['data']))})
 # Same notice can be present in the main collection and the supplements.
 unique={}
 for change in changes:
  row=change['record'];identity=row.get('notice_url') or row.get('url') or row.get('id') or change['key']
  unique[(identity,change['change'])]=change
 return list(unique.values())
def snapshot(root=ROOT):
 import sys
 sys.path.insert(0,str(root/'intelligence'))
 from collector import registry
 customers=registry(read(root/'public/tencent-data.json',{})['rows'],allow_empty=True)
 result={id:{'name':name,'parts':{},'records':{}} for id,name in customers.items()}
 specs={'profile-data':{'采购意向与招标':['projects'],'领导资料':['leaders'],'组织架构':['organizations'],'公开动态':['attributes']},'organization-data':{'主要职能':['overview','basicSource'],'组织架构':['nodes','note','source','sources']},'people-data':{'领导资料':['people']},'award-history':{'历史招标结果':['results']},'customer-supplements':{'历史招标结果':['results'],'合同信息':['contracts'],'采购意向与招标':['projects','notices'],'政策与建设方向':['policies']},'dongfeng-worklogs':{'工作日志':['entries'],'商机进展':['projects']},'worklogs':{'工作日志':['entries']},'customer-scenes':{'产品与场景':['scenes']}}
 for file,parts in specs.items():
  data=read(root/f'public/{file}.json',{})
  for id,c in result.items():
   def match(r):return str(r.get('customerId',r.get('id','')))==id and (not r.get('customerName') or r['customerName']==c['name']) and (not (r.get('name') and 'customerId' not in r) or r['name']==c['name'])
   rows=[r for r in data.get('customers',data.get('profiles',[])) if match(r)]
   for label,keys in parts.items():
    value=[r for k in keys if k in ('entries','projects') and k in data for r in data[k] if match(r)] if file in ('dongfeng-worklogs','worklogs') else [{k:r[k] for k in keys if k in r} for r in rows]
    c['parts'].setdefault(label,{})[file]=value
    if label in DETAIL_LABELS:
     records=value if file in ('dongfeng-worklogs','worklogs') else [item for row in rows for key in keys for item in row.get(key,[]) if isinstance(item,dict)]
     for item in records:
      if label=='商机进展':
       progress=next((entry for entry in data.get('entries',[]) if str(entry.get('sourceRecordId','')).startswith('progress:') and item.get('id') in entry.get('projectIds',[])),None)
       if progress:
        content=progress.get('content','')
        match_progress=re.search(r'最新进展[：:]\s*(.*?)(?=\n(?:下一步|平台阶段|线索结果|中失标状态)[：:]|$)',content,re.S)
        if match_progress:item={**item,'latestProgress':match_progress.group(1).strip(),'actorName':progress.get('actorName',''),'actorRole':progress.get('actorRole',''),'recordMethod':str(progress.get('projectTypes',{}).get(item.get('id'),item.get('type','项目')))+'记录 · 最新进展','sourceRecordId':progress.get('sourceRecordId',''),'sourceUrl':progress.get('sourceUrl','')}
      key=record_key(file,item)
      c['records'].setdefault(label,{})[key]={'hash':fingerprint(item),'data':item}
     if label=='商机进展':c['parts'][label][file]=[v['data'] for v in c['records'].get(label,{}).values()]

 for id,c in result.items():
  names=set()
  for file in ('award-history','customer-supplements'):
   for r in read(root/f'public/{file}.json',{}).get('customers',[]):
    if r.get('id')==id:
     for notice in r.get('results',[]):
      for lot in notice.get('awards',[]):names.update(lot.get('suppliers',[]))
  c['parts']['生态伙伴']={'partners':[p for p in read(root/'public/cooperation-partners.json',{}).get('partners',[]) if any(n in names for n in [p.get('name'),*p.get('aliases',[])]) or c['name'] in json.dumps(p.get('businessLinks',[]),ensure_ascii=False)]}
 rows=read(root/'public/tencent-data.json',{}).get('rows',[])
 if rows:
  headers=rows[0];ni=next((i for i,h in enumerate(headers) if h in ('客户名称','名称')),None);ii=next((i for i,h in enumerate(headers) if h in ('集团编号','客户编号','ID')),None)
  for row in rows[1:]:
   if ni is None or ni>=len(row):continue
   name=str(row[ni]).strip();id=str(row[ii]).strip() if ii is not None and ii<len(row) and row[ii] else 'name:'+re.sub(r'\s+','',name).lower()
   if id in result:result[id]['parts']['客户基本信息']={'sheet':dict(zip(headers,row))}
 return {id:{'name':c['name'],'parts':{k:fingerprint(v) for k,v in c['parts'].items()},'records':c['records']} for id,c in result.items()}

def record(current,previous,events,now):
 stamp=now.isoformat(timespec='seconds');day=now.date().isoformat();cutoff=(now.date()-datetime.timedelta(days=35)).isoformat();events=[e for e in events if e.get('date','')>=cutoff]
 for id,c in current.items():
  old=previous.get(id)
  labels=['新增客户'] if previous and not old else [label for label,value in c['parts'].items() if old and label in old['parts'] and old['parts'][label]!=value]
  for label in labels:
   event_id=hashlib.sha256((id+label+stamp+c['parts'].get(label,'')).encode()).hexdigest()[:24]
   event={'id':event_id,'customerId':id,'customerName':c['name'],'label':label,'title':label if label=='新增客户' else label+'更新','detectedAt':stamp,'date':day}
   if label in DETAIL_LABELS:
    if old and 'records' in old:
     event['items']=changed_items(c.get('records',{}).get(label,{}),old['records'].get(label,{}))
     if not event['items']:continue
    else:event['items']=[] # Old category-only state cannot establish individual changes.
   events.append(event)
 return {'customers':json.loads(json.dumps(current)),'updatedAt':stamp},{'version':1,'initializedAt':None,'events':events}

def main():
 now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)));old=read(STATE,{});journal=read(OUTPUT,{});state,out=record(snapshot(),old.get('customers',{}),journal.get('events',[]),now);out['initializedAt']=journal.get('initializedAt') or now.isoformat(timespec='seconds')
 STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('Customer update journal:',len(out['events']),'retained events')
if __name__=='__main__':main()
