"""Deterministic logs: freeze populated baseline columns, read other cells verbatim."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import unicodedata

NAME_HEADERS=('客户名称','名称','单位名称')
ID_HEADERS=('集团编号','客户编号','ID')
CHINA=datetime.timezone(datetime.timedelta(hours=8))

def column_letter(index):
    result='';index+=1
    while index:
        index,remainder=divmod(index-1,26);result=chr(65+remainder)+result
    return result

def sheet_layout(rows):
    start=next((i for i,row in enumerate(rows) if any(str(v).strip() in NAME_HEADERS for v in row)),None)
    if start is None:raise ValueError('Customer header missing; work logs unchanged')
    width=max(map(len,rows),default=0);headers=[str(v).strip() for v in rows[start]]+['']*(width-len(rows[start]));seen={};columns=[]
    for index,header in enumerate(headers):
        seen[header]=seen.get(header,0)+1
        key='header:'+header+':'+str(seen[header]) if header else 'column:'+column_letter(index)
        nonempty=sum(bool(str(row[index]).strip()) for row in rows[start+1:] if len(row)>index)
        columns.append({'key':key,'column':column_letter(index),'header':header,'nonemptyRows':nonempty})
    return start,headers,columns

def valid_date(year,month,day):
    try:return datetime.date(int(year),int(month),int(day)).isoformat()
    except (ValueError,TypeError):return None

def work_date(header,content,year):
    # Column dates take precedence. Never substitute today's date for missing dates.
    for text,anchored in ((header,False),(content,True)):
        finder=re.match if anchored else re.search
        text=re.sub(r'^\s*(?:工作日期|日期)\s*[:：]\s*','',text) if anchored else text
        match=finder(r'(?<!\d)(20\d{2})[年/.-]\s*(\d{1,2})[月/.-]\s*(\d{1,2})(?:日|(?!\d))',text)
        if match:
            date=valid_date(*match.groups());return date,'explicit' if date else 'unknown'
        match=finder(r'(?<!\d)(\d{1,2})[月/.-]\s*(\d{1,2})(?:日|(?!\d))',text)
        if match:
            date=valid_date(year,*match.groups());return date,'year-inferred' if date else 'unknown'
    return None,'unknown'

def customer_key(row,headers):
    name_index=next(i for i,h in enumerate(headers) if h in NAME_HEADERS)
    name=str(row[name_index]).strip() if len(row)>name_index else ''
    if not name:return None,None
    id_index=next((i for i,h in enumerate(headers) if h in ID_HEADERS),None)
    identifier=str(row[id_index]).strip() if id_index is not None and len(row)>id_index else ''
    return identifier or 'name:'+re.sub(r'\s+','',unicodedata.normalize('NFKC',name).lower()),name

def build_worklogs(rows,config=None,previous=None,now=None):
    now=now or datetime.datetime.now(CHINA);stamp=now.isoformat(timespec='seconds')
    start,headers,columns=sheet_layout(rows)
    if config is None:
        if not any(customer_key(row,headers)[0] for row in rows[start+1:]):raise ValueError('Cannot capture baseline without customer rows')
        config={'version':1,'capturedAt':stamp,'baseColumns':[dict(c) for c in columns if c['nonemptyRows']>0]}
    if config.get('version')!=1 or not isinstance(config.get('baseColumns'),list):raise ValueError('Invalid work-log baseline; not reset automatically')
    base={c['key'] for c in config['baseColumns']};old={r['id']:r for r in (previous or {}).get('entries',[])}
    entries=[];occurrences={}
    for row_index,row in enumerate(rows[start+1:],start+2):
        identifier,name=customer_key(row,headers)
        if not identifier:continue
        occurrences[identifier]=occurrences.get(identifier,0)+1
        for index,column in enumerate(columns):
            if column['key'] in base or len(row)<=index:continue
            content=str(row[index]).strip()
            if not content:continue
            # Customer identity is never interpreted as a log, even if moved or renamed.
            if column['header'] in NAME_HEADERS+ID_HEADERS:continue
            identifier_parts=[identifier,str(occurrences[identifier]),column['key']]
            log_id=hashlib.sha256('\0'.join(identifier_parts).encode()).hexdigest()[:24]
            prior=old.get(log_id,{})
            date,precision=work_date(column['header'],content,now.year)
            if precision=='year-inferred' and prior.get('content')==content and prior.get('workDate') and prior.get('columnHeader')==column['header']:date=prior['workDate']
            record={'id':log_id,'customerId':identifier,'customerName':name,'workDate':date,'datePrecision':precision,'content':content,'columnHeader':column['header'],'column':column['column'],'cell':column['column']+str(row_index),'sourceRow':row_index,'firstSeenAt':prior.get('firstSeenAt',stamp)}
            unchanged=all(prior.get(k)==v for k,v in record.items())
            record['updatedAt']=prior.get('updatedAt',stamp) if unchanged else stamp
            entries.append(record)
    entries.sort(key=lambda r:(r['workDate'] or '',r['updatedAt'],r['id']),reverse=True)
    inventory={'columns':columns,'baselineCapturedAt':config['capturedAt'],'logColumns':[c for c in columns if c['key'] not in base and (c['header'] or c['nonemptyRows'])]}
    return config,{'version':1,'entries':entries},inventory

def write_changed(path,data):
    path=Path(path);old=json.loads(path.read_text()) if path.exists() else None
    if old==data:return False
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temp.replace(path);return True

def sync_worklogs(rows,directory,source):
    directory=Path(directory);config_path=directory/'worklog-config.json';output=directory/'worklogs.json'
    config=json.loads(config_path.read_text()) if config_path.exists() else None
    previous=json.loads(output.read_text()) if output.exists() else None
    config,payload,inventory=build_worklogs(rows,config,previous)
    payload['source']=source
    if previous and previous.get('entries')==payload['entries'] and previous.get('source')==source:payload['updatedAt']=previous['updatedAt']
    else:payload['updatedAt']=datetime.datetime.now(CHINA).isoformat(timespec='seconds')
    write_changed(config_path,config);write_changed(output,payload);write_changed(directory/'sheet-columns.json',inventory)
    print('Spreadsheet columns:',json.dumps([{'column':c['column'],'header':c['header'],'nonemptyRows':c['nonemptyRows']} for c in inventory['columns']],ensure_ascii=False))
    print('Frozen baseline:',json.dumps([c['header'] or c['column'] for c in config['baseColumns']],ensure_ascii=False),'work logs:',len(payload['entries']))
