"""Read authorized Dongfeng records; publish customer-scoped work-log summaries only."""
import argparse
import datetime as dt
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import urllib.request

BASE='http://36.140.149.89:18080'
CHINA=dt.timezone(dt.timedelta(hours=8))
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'public/dongfeng-worklogs.json'
STATE=ROOT/'intelligence/dongfeng-worklog-state.json'
CONFIG=ROOT/'intelligence/dongfeng-customers.json'
STAGES={'LEAD':'线索','OPPORTUNITY':'商机','BIDDING':'投标中','LOST':'未中标','WON':'已中标'}

def read(path,default):
    return json.loads(path.read_text()) if path.exists() else default

def write_changed(path,data):
    if read(path,None)==data:return False
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temp.replace(path);return True

def day(value):
    if not isinstance(value,str) or not re.match(r'^\d{4}-\d{2}-\d{2}',value):return None
    try:
        if 'T' in value:
            date=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
            if date.tzinfo:date=date.astimezone(CHINA)
            return date.date().isoformat()
        return dt.date.fromisoformat(value[:10]).isoformat()
    except ValueError:return None

def clean(value):
    text=str(value or '').strip()
    # Business narrative only: omit phone numbers and credential assignments.
    text=re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)','[联系方式已省略]',text)
    text=re.sub(r'(?i)(?:密码|password|access_token|token)\s*[:：=]\s*\S+','[凭据已省略]',text)
    return text[:1800]

def normalize(value):return re.sub(r'\s+','',str(value or '')).replace('（','(').replace('）',')')

def customer_match(name,customers):
    name=normalize(name)
    exact=[c for c in customers if name in [normalize(c['name']),*[normalize(a) for a in c.get('aliases',[])]]]
    if len(exact)==1:return exact[0]
    related=[c for c in customers if any(name.startswith(normalize(p)) for p in c.get('relatedPrefixes',[])) or name in c.get('relatedNames',[])]
    return related[0] if len(related)==1 else None

def candidates(data,customers):
    rows={}
    def add(kind,source_id,customer,date,title,content,label,related=None):
        if not source_id or not customer or not date or not content:return
        key=kind+':'+str(source_id)
        rows[key]={'key':key,'customerId':customer['id'],'customerName':customer['name'],'workDate':date,'title':clean(title),'content':clean(content),'dateLabel':label,'relatedUnit':clean(related) if related and related!=customer['name'] else None}
    for task in data['tasks']:
        customer=customer_match(task.get('clientName'),customers)
        if not customer:continue
        title=clean(task.get('title'))
        for event in task.get('timeline',[]):
            if event.get('title')!='每日进展登记':continue
            date=day(event.get('workDate')) or day(event.get('timestamp'))
            body=event.get('description') or ''
            if not body.strip():continue
            # Skip generic automatically populated placeholders.
            if body.strip() in ('线索已录入，等待后续协同推进。','商机已录入，等待后续协同推进。'):continue
            add('daily',event.get('id'),customer,date,title+' · 工作进展',title+'：'+body,'东风工作日期',task.get('clientName'))
        progress=clean(task.get('latestProgress'))
        if progress and not any(s in progress for s in ['等待后续协同推进','已转为商机','已由线索转为商机']):
            stage='已关闭' if task.get('executionStatus')=='CLOSED' else STAGES.get(task.get('businessStage'),'待核实')
            content=f'{title}：{progress}（平台阶段：{stage}）'
            next_step=clean(task.get('nextStepPlan'))
            if next_step and next_step not in ('无','待客户经理维护下一步计划。'):content+=' 下一步：'+next_step
            add('progress',task.get('id'),customer,day(task.get('updatedAt')),title+' · 项目进展',content,'东风记录更新日期',task.get('clientName'))
    for visit in data['visits']:
        if visit.get('status')!='COMPLETED':continue
        customer=customer_match(visit.get('clientName'),customers)
        date=day(visit.get('actualTime')) # Never use planned visit dates as completed work dates.
        content=clean(visit.get('visitOutcome'))
        add('visit',visit.get('id'),customer,date,'客户拜访','客户拜访：'+content if content else '', '东风实际拜访日期',visit.get('clientName'))
    for log in data['workLogs']:
        content=clean(log.get('content'));title=clean(log.get('title'))
        # Require an explicit mention in the narrative; do not assign a multi-client log wholesale.
        for customer in customers:
            aliases=[customer['name'],*customer.get('aliases',[])]
            parts=[p.strip() for p in re.split(r'[\n；;]',content) if any(a in p for a in aliases)]
            if len(parts)==0 and any(a in title for a in aliases):parts=[content]
            if not parts:continue
            # A test-report reference is not work performed for that customer.
            parts=[p for p in parts if not re.search(r'(检测|测评)报告',p)]
            if parts:add('worklog',str(log.get('id'))+':'+customer['id'],customer,day(log.get('workDate')),'客户工作记录','\n'.join(parts),'东风工作日期')
    return rows

def sync(data,customers,previous,state,initialize=False,now=None):
    now=now or dt.datetime.now(CHINA);stamp=now.isoformat(timespec='seconds')
    for key in ('tasks','visits','workLogs'):
        if not isinstance(data.get(key),list):raise ValueError('Incomplete Dongfeng response; previous logs retained')
    current=candidates(data,customers)
    # Resource assignment can change updatedAt without a new business progress entry.
    hashes={k:hashlib.sha256(json.dumps({field:value for field,value in v.items() if not (k.startswith('progress:') and field=='workDate')},sort_keys=True,ensure_ascii=False).encode()).hexdigest() for k,v in current.items()}
    if not state and not initialize:raise ValueError('Missing baseline; initialize explicitly to avoid importing old records as new work')
    entries={r['id']:r for r in previous.get('entries',[])}
    if not initialize:
        for key,record in current.items():
            if hashes[key]==state.get('hashes',{}).get(key):continue
            identifier='dongfeng:'+hashlib.sha256((key+'|'+record['workDate']).encode()).hexdigest()[:24]
            content=record['content']
            if record.get('relatedUnit'):content='关联单位：'+record['relatedUnit']+'\n'+content
            prior=entries.get(identifier,{})
            entry={'id':identifier,'customerId':record['customerId'],'customerName':record['customerName'],'workDate':record['workDate'],'datePrecision':'explicit','content':content,'sourceType':'dongfeng','sourceLabel':'东风平台 · '+record['dateLabel'],'sourceRecordId':key,'sourceUrl':BASE+'/dongfeng?workspace=DONGFENG','firstSeenAt':prior.get('firstSeenAt',stamp),'updatedAt':stamp}
            # Daily entries may be copied into a converted opportunity; display one same-client/day/content.
            duplicate=next((r for r in entries.values() if r['customerId']==entry['customerId'] and r['workDate']==entry['workDate'] and r['content']==entry['content']),None)
            if not duplicate:entries[identifier]=entry
            elif duplicate['id']==identifier:entries[identifier]=entry
    ordered=sorted(entries.values(),key=lambda r:(r['workDate'],r['id']),reverse=True)
    output={**previous,'version':1,'source':'东风平台','entries':ordered}
    if ordered!=previous.get('entries',[]):output['updatedAt']=stamp
    next_state={'version':1,'initializedAt':state.get('initializedAt',stamp),'hashes':{**state.get('hashes',{}),**hashes}}
    return output,next_state

def fetch_platform(account,password):
    jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    opener.add_handler(NoRedirect())
    def request(path,payload=None):
        headers={'Accept':'application/json','Referer':BASE+'/dongfeng?workspace=DONGFENG'}
        if payload is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        with opener.open(req,timeout=45) as response:body=json.load(response)
        return body
    auth=request('/api/v1/auth/login',{'account':account,'password':password})
    if not isinstance(auth.get('data',{}).get('user'),dict):raise RuntimeError('Dongfeng login failed; check repository credentials')
    data=request('/api/v1/dongfeng/bootstrap').get('data',{})
    if not isinstance(data,dict):raise RuntimeError('Invalid Dongfeng response')
    return data

def main():
    p=argparse.ArgumentParser();p.add_argument('--initialize',action='store_true');args=p.parse_args()
    account=os.environ.get('DONGFENG_ACCOUNT');password=os.environ.get('DONGFENG_PASSWORD')
    if not account or not password:raise RuntimeError('Missing DONGFENG_ACCOUNT or DONGFENG_PASSWORD repository secrets')
    data=fetch_platform(account,password)
    customers=read(CONFIG,{'customers':[]})['customers'];sheet=read(ROOT/'public/tencent-data.json',{})['rows']
    name_col=next(i for i,h in enumerate(sheet[0]) if h in ('客户名称','名称','单位名称'))
    active={row[name_col].strip() for row in sheet[1:] if len(row)>name_col}
    customers=[c for c in customers if c['name'] in active]
    output,state=sync(data,customers,read(OUTPUT,{'entries':[]}),read(STATE,{}),args.initialize)
    write_changed(OUTPUT,output);write_changed(STATE,state)
    print('Dongfeng logs:',len(output['entries']),'matched customers:',len({r['customerId']for r in output['entries']}))

if __name__=='__main__':
    try:main()
    except Exception as error:
        # Never print response bodies, session cookies, account details or raw business records.
        raise SystemExit('Dongfeng sync failed: '+type(error).__name__+'; existing logs retained. Check connectivity and repository secrets.')
