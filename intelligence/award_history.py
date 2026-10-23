"""Public award-result titles, separate from current procurement opportunities."""
import datetime
import html
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
            combined.update({r['url']:r for r in rows})
            record.update(results=sorted(combined.values(),key=lambda r:r['date'],reverse=True)[:200],coverage=coverage,lastCheck={'at':stamp,'status':'ok'})
        except Exception as exc:record['lastCheck']={'at':stamp,'status':'unavailable','message':str(exc)[:160]}
        records[identifier]=record
        print(identifier,len(record['results']),'public award results;',record['lastCheck']['status'])
    write_json(OUTPUT,{'updatedAt':stamp,'customers':list(records.values())})

if __name__=='__main__':main()
