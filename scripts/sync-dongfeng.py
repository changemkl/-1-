"""Read authorized Dongfeng records; publish customer-scoped source work records."""
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
    return text

def normalize(value):return re.sub(r'\s+','',str(value or '')).replace('（','(').replace('）',')')

def customer_match(name,customers):
    name=normalize(name)
    exact=[c for c in customers if name in [normalize(c['name']),*[normalize(a) for a in c.get('aliases',[])]]]
    if len(exact)==1:return exact[0]
    related=[c for c in customers if any(name.startswith(normalize(p)) for p in c.get('relatedPrefixes',[])) or name in c.get('relatedNames',[])]
    return related[0] if len(related)==1 else None

ROLES={'CUSTOMER_MANAGER':'客户经理','SOLUTION_MANAGER':'解决方案经理','PRE_SALES_MANAGER':'售前经理','PRESALES_MANAGER':'售前经理','PROJECT_MANAGER':'项目经理','BUSINESS_MANAGER':'商务经理'}
SYSTEM_NAMES={'系统导入','业务流程引擎','平台调度中心','智能调度引擎','Zifang-Admin','系统','东风管理平台'}

def record_type(task):
    if task.get('businessStage')=='LEAD' or str(task.get('code','')).startswith('DF-XS-'):return '线索'
    return '商机' if task.get('taskType')=='COMMERCIAL_OPP' or task.get('businessStage') in STAGES else '项目'

def project_catalog(data,customers,previous=None):
    tasks={};parent={}
    for t in data['tasks']:
        customer=customer_match(t.get('clientName'),customers)
        if customer and t.get('id'):tasks[str(t['id'])]=(t,customer);parent[str(t['id'])]=str(t['id'])
    def root(k):
        while parent[k]!=k:parent[k]=parent[parent[k]];k=parent[k]
        return k
    def union(a,b):
        if tasks[a][1]['id']==tasks[b][1]['id']:parent[root(b)]=root(a)
    codes={t.get('code'):k for k,(t,c)in tasks.items() if t.get('code')}
    for key,(task,customer)in tasks.items():
        text='\n'.join([str(task.get('latestProgress')or''),*[str(e.get('description')or'') for e in task.get('timeline',[]) if re.search('转为商机|转化|转商机',str(e.get('title')or''))]])
        # Only explicit lead-conversion references establish project identity; names alone never merge projects.
        if re.search('转为商机|转商机|转化|生成商机|线索.*商机',text):
            for code in re.findall(r'DF-(?:XS|OPP)-[A-Za-z0-9_-]+',text):
                if code in codes:union(key,codes[code])
        details=task.get('sourceDetails')or{}
        for field in ('sourceLeadId','leadId','sourceTaskId','convertedFromId'):
            ref=details.get(field)
            if ref in tasks:union(key,ref)
    groups={}
    for key in tasks:groups.setdefault(root(key),[]).append(key)
    projects=[];by_task={}
    for keys in groups.values():
        members=[tasks[k][0] for k in keys];customer=tasks[keys[0]][1]
        commercial=[t for t in members if record_type(t)=='商机'];latest=max(commercial or members,key=lambda t:t.get('updatedAt')or'')
        old=[p for p in previous or [] if p.get('customerId')==customer['id'] and set(p.get('taskIds',[]))&set(keys)]
        identifier=old[0]['id'] if old else 'dfproject:'+hashlib.sha256((customer['id']+'|'+min(keys)).encode()).hexdigest()[:20]
        aliases=list(dict.fromkeys(a for p in old for a in [p['id'],*p.get('aliasIds',[])] if a!=identifier))
        project={'id':identifier,'aliasIds':aliases,'customerId':customer['id'],'customerName':customer['name'],'name':clean(latest.get('title')) or '未命名项目','type':'商机' if commercial else record_type(latest),'status':'已关闭' if latest.get('executionStatus')=='CLOSED' else STAGES.get(latest.get('businessStage'),clean(latest.get('businessStage')) or '待确认'),'relatedUnit':clean(latest.get('clientName')),'taskIds':keys,'codes':list(dict.fromkeys(t['code'] for t in members if t.get('code'))),'names':list(dict.fromkeys(clean(t.get('title'))for t in members if t.get('title'))),'updatedAt':latest.get('updatedAt')or''}
        projects.append(project)
        for key in keys:by_task[key]=project
    for bid in data.get('biddingRecords',[]):
        customer=customer_match(bid.get('clientName'),customers)
        if not customer:continue
        project=by_task.get(str(bid.get('taskId')))
        if not project:
            found=[p for p in projects if p['customerId']==customer['id'] and normalize(p['name'])==normalize(bid.get('projectName')) and normalize(p['relatedUnit'])==normalize(bid.get('clientName'))]
            if len(found)==1:project=found[0]
        if not project:
            project={'id':'dfbid:'+str(bid.get('id')),'customerId':customer['id'],'customerName':customer['name'],'name':clean(bid.get('projectName')) or '未命名投标项目','type':'商机','status':STAGES.get(bid.get('status'),clean(bid.get('status')) or '待确认'),'relatedUnit':clean(bid.get('clientName')),'taskIds':[],'codes':[bid.get('biddingCode')or''],'names':[clean(bid.get('projectName'))],'updatedAt':bid.get('updatedAt')or''};projects.append(project)
        by_task['bid:'+str(bid.get('id'))]=project
    known={p['id'] for p in projects}|{a for p in projects for a in p.get('aliasIds',[])}
    for old in previous or []:
        if old['id'] not in known:projects.append(old)
    return projects,by_task


def candidates(data,customers,catalog=None):
    projects,by_task=catalog or project_catalog(data,customers)
    rows={}
    personnel={str(p.get('id')):p for p in data.get('personnel',[]) if isinstance(p,dict)}
    personnel.update({str(p.get('employeeId')):p for p in data.get('personnel',[]) if p.get('employeeId')})
    def actor(name,role='',identifier=None):
        if not name and identifier and str(identifier) in personnel:name=personnel[str(identifier)].get('name')
        name=clean(name) if isinstance(name,str) else ''
        if name in SYSTEM_NAMES or re.search(r'系统|引擎|自动',name):return '', ''
        return name,ROLES.get(role,clean(role)) if name else ''
    def add(kind,source_id,customer,date,title,content,label,related=None,name='',role='',original='',**extra):
        if not source_id or not customer or not str(content or '').strip():return
        key=kind+':'+str(source_id)+':'+customer['id']
        item={'key':key,'customerId':customer['id'],'customerName':customer['name'],'workDate':date,'title':clean(title),'content':clean(content),'dateLabel':label,'relatedUnit':clean(related) if related and related!=customer['name'] else None,'actorName':name,'actorRole':role,**extra}
        if original:item['originalContent']=clean(original)
        if kind in ('daily','event','progress','report'):
            project=by_task.get(str(task.get('id')))
            if project:item.update(projectIds=[project['id']],projectTypes={project['id']:record_type(task)})
        elif kind=='bid':
            project=by_task.get('bid:'+str(source_id))
            if project:item.update(projectIds=[project['id']],projectTypes={project['id']:'商机'})
        else:
            text=normalize(title+'\n'+content+'\n'+original)
            matches=[p for p in projects if p['customerId']==customer['id'] and (any(code and normalize(code) in text for code in p.get('codes',[])) or any(len(normalize(name))>=6 and normalize(name) in text for name in p.get('names',[p['name']])))]
            # Same-name independent projects require a code/ID; otherwise retain the customer-level log.
            matches=[p for p in matches if any(code and normalize(code) in text for code in p.get('codes',[])) or sum(normalize(q['name'])==normalize(p['name']) for q in projects if q['customerId']==customer['id'])==1]
            if matches:item.update(projectIds=[p['id'] for p in matches],projectTypes={p['id']:p['type'] for p in matches})
        # Converted opportunities can repeat the same source event; retain one event and all project names.
        if key in rows:
            item['projectNames']=list(dict.fromkeys(rows[key].get('projectNames',[rows[key]['title']])+[item['title']]))
            item['projectIds']=list(dict.fromkeys(rows[key].get('projectIds',[])+item.get('projectIds',[])))
            item['projectTypes']={**rows[key].get('projectTypes',{}),**item.get('projectTypes',{})}
        rows[key]=item
    def parts(fields):return '\n'.join(label+'：'+clean(value) for label,value in fields if value not in (None,'',[],{}))
    def mentions(text):
        return [c for c in customers if any(a in text for a in [c['name'],*c.get('aliases',[])])]
    all_customer_names=[str(c.get('fullName')or'') for c in data.get('customers',[]) if c.get('fullName')]
    def blocks(content,targets):
        """Keep continuation lines after a customer heading, stop at another known customer heading."""
        result=[];active=False
        for line in content.splitlines():
            matched=mentions(line)
            if matched:active=any(c['id'] in targets for c in matched)
            elif any(n in line for n in all_customer_names if len(n)>=3):active=False
            elif re.match(r'^\s*(?:\d+[、.．]|[一二三四五六七八九十]+[、.．])',line):active=False
            elif re.match(r'^\s*[^:：]{2,25}[:：]',line) and not re.match(r'^\s*(?:下一步|进展|需求|结果|背景|备注|工作内容)[:：]',line):active=False
            if active:result.append(line)
        return '\n'.join(result).strip()
    for task in data['tasks']:
        customer=customer_match(task.get('clientName'),customers)
        if not customer:continue
        title=clean(task.get('title')) or '未命名项目'
        for event in task.get('timeline',[]):
            event_title=event.get('title','')
            # Business actions by a person, plus migrated source-ledger progress. Skip automated configuration noise.
            human_name,human_role=actor(event.get('operatorName'),event.get('operatorRole',''),event.get('operatorEmployeeId'))
            business=event_title in ('每日进展登记','源台账进展导入','客户经理提交关闭申请','指挥部审核通过，任务正式关闭归档','商机已转投标','线索已转为商机','线索转化完成','客户经理录入商机并提交','客户经理录入线索并提交') or bool(human_name and not re.search(r'已配置|台账信息已更新|进入待研判池|自动匹配|协同待办',event_title))
            if not business:continue
            description=clean(event.get('description'))
            body=parts([('工作内容',description),('下一步',event.get('nextStepPlan') if clean(event.get('nextStepPlan')) not in description else ''),('下一步时间',event.get('nextStepDueAt') if clean(event.get('nextStepDueAt')) not in description else '')])
            if not body:body=event_title or '具体工作内容未注明'
            date=day(event.get('workDate')) or (day(event.get('timestamp')) if event_title not in ('每日进展登记','源台账进展导入') else None)
            label='东风工作日期' if day(event.get('workDate')) else '东风事件记录日期' if date else '东风日期未明确'
            participants=[]
            for person in event.get('participants',[]):
                if isinstance(person,dict) and person.get('name'):participants.append(clean(person['name'])+('（'+ROLES.get(person.get('role'),clean(person.get('role')))+'）' if person.get('role') else ''))
            add('daily' if event_title=='每日进展登记' else 'event',event.get('id'),customer,date,title+' · '+event_title,body,label,task.get('clientName'),human_name,human_role,participants=participants,recordUpdatedDate=day(event.get('timestamp')) if not date else None)
        progress=clean(task.get('latestProgress'))
        body=parts([('项目',title),('建设内容',task.get('description')),('最新进展',progress),('下一步',task.get('nextStepPlan'))])
        stage='已关闭' if task.get('executionStatus')=='CLOSED' else STAGES.get(task.get('businessStage'),clean(task.get('businessStage')) or '未注明')
        body+='\n平台阶段：'+stage
        outcomes=task.get('stageOutcomes')or{}
        body+='\n'+parts([(label,outcomes.get(key)) for key,label in [('leadOutcome','线索结果'),('biddingOutcome','投标进展'),('winLostOutcome','中失标状态'),('lostReason','失标原因')]])
        # The last editor is not assumed to be the person who performed the work.
        add('progress',task.get('id'),customer,None,title+' · 最新项目记录',body,'实际工作日期未明确',task.get('clientName'),recordUpdatedDate=day(task.get('updatedAt')),recordCreatedDate=day(task.get('createdAt')),responsibleManager=clean(task.get('customerManagerName')))
        for report_kind,report in (task.get('reports')or{}).items():
            if not isinstance(report,dict):continue
            content=parts([(k,v) for k,v in report.items() if isinstance(v,str) and k not in ('id','createdAt','updatedAt','submittedAt','author','authorName','creatorName','name','role','status','employeeId','userId')])
            if not content:continue
            name,role=actor(report.get('authorName')or report.get('creatorName'),report.get('role',''))
            add('report',str(task.get('id'))+':'+report_kind,customer,day(report.get('workDate')),title+' · 支撑报告',content,'东风工作日期' if day(report.get('workDate')) else '东风日期未明确',task.get('clientName'),name,role)
    for visit in data['visits']:
        customer=customer_match(visit.get('clientName'),customers)
        completed=visit.get('status')=='COMPLETED'
        content=parts([('拜访状态','已完成' if completed else '尚未确认完成'),('拜访目标',visit.get('visitGoal')),('拜访对象（源记录）',visit.get('targetPerson')),('客户反馈',visit.get('clientAttitude')),('客户需求',visit.get('clientDemands')),('拜访结果',visit.get('visitOutcome')),('下一步',visit.get('nextAction'))])
        name,role=actor(visit.get('responsibleManager'),'')
        date=day(visit.get('actualTime')) if completed else None
        add('visit',visit.get('id'),customer,date,'客户拜访',content,'东风实际拜访日期' if date else '实际拜访日期未明确',visit.get('clientName'),name,role,actorLabel='负责经理',plannedVisitDate=day(visit.get('plannedTime')))
    for log in data['workLogs']:
        content=clean(log.get('content'));title=clean(log.get('title'))
        direct=customer_match(log.get('clientName'),customers)
        linked=mentions(title+'\n'+content)
        if direct and all(c['id']!=direct['id'] for c in linked):linked.append(direct)
        name,role=actor(log.get('creatorName'),log.get('creatorRole',''),log.get('creatorEmployeeId'))
        for customer in linked:
            excerpt=blocks(content,{customer['id']})
            # Keep the original narrative when context cannot be separated confidently.
            if not excerpt:excerpt=content or title or '工作内容未注明'
            uncertain=not direct and not any(a in title for a in [customer['name'],*customer.get('aliases',[])])
            add('worklog',log.get('id'),customer,day(log.get('workDate')),title or '客户工作记录',excerpt,'东风工作日期' if day(log.get('workDate')) else '东风日期未明确',name=name,role=role,original=content if content!=excerpt else '',associationNote='原始日志提及该客户，具体关联待确认' if uncertain else '',durationHours=log.get('durationHours'))
    for bid in data.get('biddingRecords',[]):
        customer=customer_match(bid.get('clientName'),customers)
        content=parts([('项目',bid.get('projectName')),('投标状态',STAGES.get(bid.get('status'),bid.get('status'))),('投标阶段',bid.get('biddingStage')),('投标主体',bid.get('biddingEntity')),('投标截止时间（计划）',bid.get('bidDeadline'))])
        # A bid deadline is never presented as work performed on that day.
        add('bid',bid.get('id'),customer,None,'投标进展记录',content,'实际工作日期未明确',bid.get('clientName'),recordUpdatedDate=day(bid.get('updatedAt')))
    return rows

def sync(data,customers,previous,state,initialize=False,now=None):
    now=now or dt.datetime.now(CHINA);stamp=now.isoformat(timespec='seconds')
    for key in ('tasks','visits','workLogs'):
        if not isinstance(data.get(key),list):raise ValueError('Incomplete Dongfeng response; previous logs retained')
    catalog=project_catalog(data,customers,previous.get('projects',[]))
    current=candidates(data,customers,catalog)
    hashes={k:hashlib.sha256(json.dumps({field:value for field,value in v.items() if not (k.startswith('progress:') and field in ('recordUpdatedDate','recordCreatedDate'))},sort_keys=True,ensure_ascii=False).encode()).hexdigest() for k,v in current.items()}
    # Replace generated synchronization summaries; retain all previously collected source records.
    entries={r['sourceRecordId']:r for r in previous.get('entries',[]) if r.get('sourceRecordId') and not r.get('isInitialSummary')}
    if not initialize:
        for key,record in current.items():
            prior=entries.get(key,{})
            if prior and hashes[key]==state.get('hashes',{}).get(key):continue
            identifier='dongfeng:'+hashlib.sha256(key.encode()).hexdigest()[:24]
            entry={**{k:v for k,v in record.items() if k not in ('key','dateLabel')},'id':identifier,'datePrecision':'explicit' if record['workDate'] else 'unknown','sourceType':'dongfeng','sourceLabel':'东风平台 · '+record['dateLabel'],'sourceRecordId':key,'sourceUrl':BASE+'/dongfeng?workspace=DONGFENG','firstSeenAt':prior.get('firstSeenAt',stamp),'updatedAt':stamp}
            entries[key]=entry
        # Superseded v1 entries are replaced by the corresponding explicit source record.
        for key in list(entries):
            if key not in current and key+':'+entries[key]['customerId'] in current:del entries[key]
    ordered=sorted(entries.values(),key=lambda r:(r.get('workDate')or'',r['id']),reverse=True)
    output={**previous,'version':3,'source':'东风平台','projects':catalog[0],'entries':ordered,'coverage':{'sourceRecords':len(current),'byType':{kind:sum(k.startswith(kind+':') for k in current) for kind in ('daily','event','progress','visit','worklog','report','bid')},'unknownDates':sum(not r.get('workDate')for r in ordered)}}
    if ordered!=previous.get('entries',[]):output['updatedAt']=stamp
    next_state={'version':2,'initializedAt':state.get('initializedAt',stamp),'hashes':{**state.get('hashes',{}),**hashes}}
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
