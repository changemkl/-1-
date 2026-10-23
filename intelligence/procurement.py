"""Read public open-tender notices; never infer a buyer from a keyword hit."""
import datetime
import gzip
import html
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
import urllib.robotparser
import uuid
from collector import Page, now, save_document
from facts import extract_facts, normalize, VERSION

BASE = 'https://www.zfcg.sh.gov.cn'

class NoRobotsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def portal_policy():
    parser=urllib.robotparser.RobotFileParser()
    try:
        opener=urllib.request.build_opener(NoRobotsRedirect())
        with opener.open(BASE+'/robots.txt',timeout=20) as response:
            body=response.read(100000).decode('utf-8')
        if '<html' in body.lower():raise ValueError('Invalid robots response')
        parser.parse(body.splitlines())
    except urllib.error.HTTPError as exc:
        # This portal redirects missing robots.txt to its home page.
        # Do not follow an HTTP downgrade or parse homepage HTML as policy.
        missing=exc.code==404 or (exc.code in (301,302,303,307,308) and exc.headers.get('Location') in (BASE+'/',BASE.replace('https:','http:')+'/'))
        if not missing:raise
        parser.parse([])
    return parser

def request_json(path, policy, payload=None):
    url = BASE + path
    if not policy.can_fetch('CustomerResearchBot',url):
        raise PermissionError('Public portal robots policy disallows this endpoint')
    headers = {'User-Agent':'CustomerResearchBot','Referer':BASE+'/site/search'}
    data = None
    if payload is not None:
        data=json.dumps(payload).encode();headers['Content-Type']='application/json'
    response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers),timeout=20)
    body=response.read(2000000)
    if body.startswith(b'\x1f\x8b'):body=gzip.decompress(body)
    result=json.loads(body)
    if result.get('success') is not True:raise ValueError('Portal did not return successful public data')
    return result['result']['data']

def tender_facts(detail, buyer, aliases):
    title=detail.get('title','')
    if '公开招标公告' not in title:return None
    page=Page();page.feed(detail.get('content',''))
    parts=page.paragraphs+page.parts
    if detail.get('projectName'):parts.append('项目名称：'+detail['projectName'])
    facts=extract_facts(title,parts,aliases)
    if not facts['projects']:return None
    text='\n'.join(page.parts)
    deadline=re.search(r'(?:提交投标文件截止时间|投标截止时间|截止时间)\s*[:：]?\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日\s*(\d{1,2})\s*[:：]\s*(\d{2})',text)
    # No deadline guessing from publication date or a different notice.
    if not deadline:return None
    y,m,d,h,minute=map(int,deadline.groups())
    expires=datetime.datetime(y,m,d,h,minute,tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
    if expires<datetime.datetime.now(datetime.timezone.utc):return None
    for project in facts['projects']:
        project['stage']='公开招标公告'
        project['buyer']={'value':buyer,'unit':'','quote':'采购人：'+buyer}
        project['deadline']={'value':expires.strftime('%Y-%m-%d %H:%M'),'unit':'','quote':deadline.group(0)}
        project['relation']='客户为公告所列采购人' if normalize(buyer)==normalize(aliases[0]) else '关联单位独立采购，不认定为客户本级直接采购'
        project['notice']='仅确认原文投标截止时间尚未到期；获取文件要求及更正、终止、结果以官方原文为准。'
    return facts

def collect_public_tenders(store, source):
    from platforms import public_listing_project
    started=now();count=0;status='failed';error=None
    try:
        policy=portal_policy();end=datetime.datetime.now(datetime.timezone.utc);seen=set();detail_checks=0;successful_queries=0;errors=[]
        payload={'keyword':source['aliases'][0],'firstCode':'ZcyAnnouncement','districtCode':[],
                 'publishDateBegin':int((end-datetime.timedelta(days=60)).timestamp()*1000),'publishDateEnd':int(end.timestamp()*1000),
                 'pageSize':15,'isTitleSearch':0,'order':'desc','leaf':0}
        for category in ('ZcyAnnouncement2','77-379845'):
            for page_no in (1,2):
                payload.update(secondCode=category,pageNo=page_no)
                try:result=request_json('/portal/all',policy,payload);successful_queries+=1
                except Exception as exc:errors.append(str(exc)[:120]);break
                rows=result.get('data',[])
                for row in rows:
                    buyer=row.get('purchaseName') or ''
                    if not buyer.startswith(source['aliases'][0]) or row.get('invalid')==1 or row.get('announcementType') not in (3001,10016):continue
                    aid=row.get('articleId')
                    if not aid or aid in seen:continue
                    seen.add(aid)
                    query=urllib.parse.urlencode({'parentId':row['parentId'],'articleId':aid});url=BASE+'/site/detail?'+query
                    title=html.unescape(re.sub('<[^>]+>','',row['title']))
                    snippet=html.unescape(re.sub('<[^>]+>','',row.get('content') or ''))
                    project=public_listing_project(title,url,source,{},'采购人：'+buyer+'\n'+snippet)
                    if not project:continue
                    if not project['planned_purchase'] and not project['deadline'] and detail_checks<4:
                        detail_checks+=1;time.sleep(1)
                        try:
                            detail=request_json('/portal/detail?'+query,policy)
                            if any(link.get('isExist') and link.get('typeName') in ('结果公告','终止公告') for link in detail.get('announcementLinkDtoList',[])):continue
                            page=Page();page.feed(detail.get('content',''))
                            project=public_listing_project(title,url,source,{},'采购人：'+buyer+'\n'+'\n'.join(page.paragraphs+page.parts))
                        except Exception:pass # The public list remains sufficient; no login handling.
                    if not project:continue
                    published=datetime.datetime.fromtimestamp(row['publishDate']/1000,datetime.timezone(datetime.timedelta(hours=8))).date().isoformat() if row.get('publishDate') else None
                    facts={'version':VERSION,'kind':'public_title','projects':[project],'leaders':[]}
                    save_document(store,source['customer_id'],url,title,project['quote'],published,['公开采购标题'],facts);count+=1
                if len(rows)<15 or page_no*15>=result.get('total',0):break
                time.sleep(1)
        if not successful_queries:raise RuntimeError('; '.join(errors) or 'Public portal unavailable')
        status='success';error='; '.join(errors) or None
    except Exception as exc:error=type(exc).__name__+': '+str(exc)[:160]
    store.query('INSERT INTO crawl_runs VALUES(?,?,?,?,?,?,?,?)',[str(uuid.uuid4()),source['customer_id'],BASE,started,now(),status,count,error])
    return {'customer_id':source['customer_id'],'source':'上海市政府采购网公开采购标题','status':status,'documents_found':count,'error':error}
