"""Public award results and verified lot/supplier fields, separate from current opportunities."""
import datetime
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import urllib.parse
from collector import registry
from procurement import BASE,portal_policy,request_json
from customer_system import read_json,write_json

OUTPUT=Path('public/award-history.json')
CHINA=datetime.timezone(datetime.timedelta(hours=8))

def result_row(row,name,today):
    title=html.unescape(re.sub('<[^>]+>','',row.get('title') or '')).strip()
    buyer=(row.get('purchaseName') or '').strip()
    if not buyer or not (buyer==name or buyer.startswith(name)):return None
    if row.get('invalid')==1 or not re.search(r'中标|成交',title):return None
    if not re.search(r'结果公告|中标公告|成交公告',title):return None
    if any(word in title for word in ['更正','终止','废标','取消','撤销','作废','澄清','网上超市','电子卖场','合同公告']):return None
    if not row.get('articleId') or not row.get('parentId') or not row.get('publishDate'):return None
    try:date=datetime.datetime.fromtimestamp(float(row['publishDate'])/1000,CHINA).date()
    except (ValueError,TypeError,OverflowError):return None
    if date>today:return None
    url=BASE+'/site/detail?'+urllib.parse.urlencode({'parentId':row['parentId'],'articleId':row['articleId']})
    return {'title':title,'date':date.isoformat(),'buyer':buyer,'url':url,'source':'上海市政府采购网','dateLabel':'结果公告日期'}

def collect(name,policy,now):
    begin=now.date()-datetime.timedelta(days=1095);results=[];truncated=False
    payload={'keyword':name,'firstCode':'ZcyAnnouncement','secondCode':'ZcyAnnouncement4','districtCode':[],
             'publishDateBegin':int(datetime.datetime.combine(begin,datetime.time.min,CHINA).timestamp()*1000),
             'publishDateEnd':int(now.timestamp()*1000),'pageSize':15,'isTitleSearch':0,'order':'desc','leaf':0}
    for page in range(1,5):
        payload['pageNo']=page;data=request_json('/portal/all',policy,payload)
        rows=data.get('data',[])
        for row in rows:
            item=result_row(row,name,now.date())
            if item and item['date']>=begin.isoformat():results.append(item)
        more=len(rows)>=15 and page*15<data.get('total',0)
        if not more:break
        if page==4:truncated=True
        else:time.sleep(1)
    return results,{'from':begin.isoformat(),'to':now.date().isoformat(),'source':BASE,'truncated':truncated}

class AwardTables(HTMLParser):
    """Read explicit result-table cells, including merged package cells."""
    def __init__(self):
        super().__init__(); self.tables=[]; self.stack=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if tag=='table':self.stack.append({'rows':[], 'row':None, 'cell':None})
        if not self.stack:return
        table=self.stack[-1]
        if tag=='tr':table['row']=[]
        if tag in ('td','th') and table['row'] is not None:table['cell']={'text':[],**dict(attrs)}
        if tag=='br' and table['cell'] is not None:table['cell']['text'].append(' ')
    def handle_data(self,data):
        if self.stack and not self.skip and self.stack[-1]['cell'] is not None:self.stack[-1]['cell']['text'].append(data)
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if not self.stack:return
        table=self.stack[-1]
        if tag in ('td','th') and table['cell'] is not None:
            cell=table['cell'];cell['text']=re.sub(r'\s+',' ',''.join(cell['text'])).strip();table['row'].append(cell);table['cell']=None
        if tag=='tr' and table['row'] is not None:table['rows'].append(table['row']);table['row']=None
        if tag=='table':self.tables.append(self.stack.pop()['rows'])

def table_grid(rows):
    grid=[];pending={}
    for row in rows[:300]:
        values={col:value for col,(value,left) in pending.items()};pending={col:(value,left-1) for col,(value,left) in pending.items() if left>1};col=0
        for cell in row:
            while col in values:col+=1
            try:width=min(20,max(1,int(cell.get('colspan',1))));height=min(100,max(1,int(cell.get('rowspan',1))))
            except (ValueError,TypeError):width=height=1
            for offset in range(width):
                values[col+offset]=cell['text']
                if height>1:pending[col+offset]=(cell['text'],height-1)
            col+=width
        grid.append([values.get(i,'') for i in range(max(values,default=-1)+1)])
    return grid

def parse_award_detail(detail):
    parser=AwardTables();parser.feed(detail.get('content') or '');awards=[];seen=set()
    compact=lambda value:re.sub(r'\s+','',value).replace('（','(').replace('）',')')
    supplier_headers={'中标供应商名称','成交供应商名称','中标(成交)供应商名称'}
    lot_headers={'标项名称','标段名称','包件名称','分包名称','项目名称','包名称'}
    for table in parser.tables:
        grid=table_grid(table)
        for index,row in enumerate(grid):
            headers=[compact(v) for v in row]
            supplier=next((i for i,v in enumerate(headers) if v in supplier_headers),None)
            lot=next((i for i,v in enumerate(headers) if v in lot_headers),None)
            number=next((i for i,v in enumerate(headers) if v in ('序号','标项号','包号','包件号','标段号')),None)
            # Require the awarded-supplier and lot-name fields in the same table.
            if supplier is None or lot is None:continue
            if any('候选' in v or '投标人' in v for v in headers):continue
            for cells in grid[index+1:]:
                if max(supplier,lot)>=len(cells):continue
                name=cells[lot].strip();winner=cells[supplier].strip();lot_number=cells[number].strip() if number is not None and number<len(cells) else ''
                if not name or not winner or compact(winner) in supplier_headers or winner in ('/','无','未确定','未中标','流标','废标'):continue
                key=(lot_number,name,winner)
                if key in seen:continue
                seen.add(key);awards.append({'lotNumber':lot_number,'lotName':name,'suppliers':[winner],'quote':f'标项名称：{name}；中标供应商名称：{winner}'})
            break
    return {'projectName':(detail.get('projectName') or '').strip(),'awards':awards}

def enrich_award_records(records,policy,now,limit=12,delay=1):
    candidates=[]
    for record in records.values():
        for row in record.get('results',[]):
            check=row.get('detailCheck',{})
            if check.get('version')==1 and check.get('status')=='ok':continue
            if check.get('at','')[:10]==now.date().isoformat():continue
            candidates.append(row)
    candidates.sort(key=lambda r:(bool(r.get('detailCheck')),r.get('detailCheck',{}).get('at',''),-int(r.get('date','2000-01-01').replace('-',''))))
    checked=0
    for row in candidates[:limit]:
        stamp=now.isoformat(timespec='seconds')
        try:
            url=urllib.parse.urlsplit(row['url'])
            if url.scheme!='https' or url.netloc!=urllib.parse.urlsplit(BASE).netloc or url.path!='/site/detail':continue
            detail=request_json('/portal/detail?'+url.query,policy)
            facts=parse_award_detail(detail)
            if facts['projectName']:row['projectName']=facts['projectName']
            if facts['awards']:row['awards']=facts['awards']
            row['detailCheck']={'version':1,'at':stamp,'status':'ok' if facts['awards'] else 'unparsed'}
        except Exception as exc:row['detailCheck']={'version':1,'at':stamp,'status':'unavailable','message':str(exc)[:160]}
        checked+=1
        print('Award details',checked,row.get('date'),row['detailCheck']['status'],flush=True)
        if delay:time.sleep(delay)
    return checked

def main():
    active=registry(json.loads(Path('public/tencent-data.json').read_text())['rows'],allow_empty=True)
    prior=read_json(OUTPUT,{'customers':[]});records={r['id']:r for r in prior['customers']}
    now=datetime.datetime.now(CHINA);stamp=now.isoformat(timespec='seconds')
    policy=None;policy_error=None
    try:policy=portal_policy()
    except Exception as exc:policy_error=str(exc)
    # Keep each run bounded and rotate by the oldest check when the customer list grows.
    ordered=sorted(active.items(),key=lambda pair:records.get(pair[0],{}).get('lastCheck',{}).get('at',''))[:8]
    for identifier,name in ordered:
        record=records.get(identifier)
        if not record or record['name']!=name:record={'id':identifier,'name':name,'results':[]}
        try:
            if policy_error:raise PermissionError(policy_error)
            rows,coverage=collect(name,policy,now)
            combined={r['url']:r for r in record['results'] if r.get('date','')>=coverage['from']}
            combined.update({r['url']:{**combined.get(r['url'],{}),**r} for r in rows})
            record.update(results=sorted(combined.values(),key=lambda r:r['date'],reverse=True)[:200],coverage=coverage,lastCheck={'at':stamp,'status':'ok'})
        except Exception as exc:record['lastCheck']={'at':stamp,'status':'unavailable','message':str(exc)[:160]}
        records[identifier]=record
        print(identifier,len(record['results']),'public award results;',record['lastCheck']['status'])
    if policy is not None:enrich_award_records(records,policy,now)
    write_json(OUTPUT,{'updatedAt':stamp,'customers':list(records.values())})

if __name__=='__main__':main()
