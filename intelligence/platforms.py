"""Customer-specific public procurement sources, with independent failure records."""
import datetime
import gzip
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collector import Page, load_page, robot_policy, canonical_url, validate_url, save_document, now, page_title
from facts import IT, VERSION, extract_facts, normalize

CHINA=datetime.timezone(datetime.timedelta(hours=8))
SECTIONS=('招标','采购','交易公告','公示公告')
NOTICES=('招标','采购公告','询价','磋商','采购意向')

def belongs_to_customer(buyer,source):
    return bool(buyer and any(normalize(buyer).startswith(normalize(a)) for a in source.get('buyer_aliases',source['aliases'])))

def deadline_value(text):
    pattern=r'(?:投标(?:文件递交)?截止(?:时间)?|提交投标文件截止时间|响应(?:文件提交)?截止(?:时间)?|报价截止(?:时间)?|递交投标文件(?:的)?截止时间)\s*[:：为]?\s*(\d{4})[年/.-]\s*(\d{1,2})[月/.-]\s*(\d{1,2})日?\s*(?:北京时间)?\s*(\d{1,2})\s*[:：时]\s*(\d{2})'
    match=re.search(pattern,text)
    if not match:return None
    try:stamp=datetime.datetime(*map(int,match.groups()),tzinfo=CHINA)
    except ValueError:return None
    if stamp<datetime.datetime.now(datetime.timezone.utc):return None
    return {'value':stamp.strftime('%Y-%m-%d %H:%M'),'unit':'','quote':match.group(0)}

def html_notice_facts(page,title,source):
    if not any(word in title for word in NOTICES) or any(word in title for word in ('中标','成交','结果公告','废标','终止','更正','澄清')):return None
    text='\n'.join(page.paragraphs+page.parts)
    match=re.search(r'(?<![\u4e00-\u9fff])(?:采购人|招标人|采购单位|招标单位)(?:(?:信息)?\s*[:：]?\s*(?:名\s*称))?\s*[:：为]\s*([^\n。；;]{2,100})',text)
    if not match:return None
    buyer=match.group(1).strip()
    if not belongs_to_customer(buyer,source):return None
    facts=extract_facts(title,page.paragraphs+page.parts,source['aliases'])
    if not facts['projects'] or any(p['stage'] not in ('采购意向','公开招标公告','采购公告') for p in facts['projects']):return None
    deadline=deadline_value(text)
    if '采购意向' not in title and not deadline:return None
    planned=None
    if '采购意向' in title:
        m=re.search(r'(?:预计采购时间|计划采购时间)\s*[:：]\s*(\d{4})[年/.-](\d{1,2})',text)
        if not m:return None
        if not 1<=int(m[2])<=12:return None
        planned=f'{m[1]}-{int(m[2]):02d}'
        if planned<datetime.datetime.now(CHINA).strftime('%Y-%m'):return None
    for project in facts['projects']:
        project['buyer']={'value':buyer,'unit':'','quote':match.group(0)}
        project['deadline']=deadline
        project['planned_purchase']=planned
        project['relation']='客户本级采购' if normalize(buyer) in map(normalize,source['aliases']) else '关联单位独立采购，实际采购人以原文为准'
    return facts

def yzw_notice(row,source):
    buyer=row.get('tenderCompanyName','');title=row.get('name','')
    if row.get('status') not in (1,2) or not belongs_to_customer(buyer,source) or not IT.search(title):return None
    # endTime/signUpEndDate describe registration, never substitute for tenderEndDate.
    value=row.get('tenderEndDate') or ''
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',value):return None
    try:expires=datetime.datetime.fromisoformat(value).replace(tzinfo=CHINA)
    except ValueError:return None
    if expires<datetime.datetime.now(datetime.timezone.utc):return None
    if not row.get('tenderCode'):return None
    query=urllib.parse.urlencode({k:row.get(k,'') for k in ('tenderId','tenderCode','source','tenantId')})
    url='https://xy.yzw.cn/sj/bid-detail?'+query
    quote=f'公告名称：{title}\n招标单位：{buyer}\n投标截止（tenderEndDate）：{value}'
    project={'name':title,'stage':'采购公告','quote':quote,'buyer':{'value':buyer,'quote':'招标单位：'+buyer,'unit':''},'supplier':None,'budget':None,'award_amount':None,
             'deadline':{'value':expires.strftime('%Y-%m-%d %H:%M'),'quote':'tenderEndDate：'+value,'unit':''},'planned_purchase':None,'service_end':None,
             'relation':'平台所列客户或关联单位采购，实际采购人为'+buyer,'notice':'公开列表记录；未把竞价采购标成公开招标，采购方式及后续更正以原文为准。'}
    return url,title,quote,row.get('publishDate'),{'version':VERSION,'kind':'procurement','projects':[project],'leaders':[]}

def collect_yzw(store,source,spec):
    policy=robot_policy(spec['api_url'],spec['hosts'])
    if not policy.can_fetch('CustomerResearchBot',spec['api_url']):raise PermissionError('robots.txt disallows public list')
    request=urllib.request.Request(spec['api_url'],headers={'User-Agent':'CustomerResearchBot/1.0','Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=20) as response:
        validate_url(response.geturl(),spec['hosts']);body=response.read(2000000)
    if body.startswith(b'\x1f\x8b'):body=gzip.decompress(body)
    payload=json.loads(body)
    if payload.get('success') is not True or not isinstance(payload.get('data'),list):raise PermissionError('Public list unavailable; no login or challenge bypass attempted')
    count=0
    for row in payload['data'][:50]:
        notice=yzw_notice(row,source)
        if not notice:continue
        url,title,quote,published,facts=notice
        save_document(store,source['customer_id'],url,title,quote,published,['企业采购公告'],facts);count+=1
    return count,{'coverage':'云筑集采门户公开推荐列表，非全量搜索','items_checked':len(payload['data'])}

def collect_html(store,source,spec):
    policy=robot_policy(spec['url'],spec['hosts'])
    context={**spec,'_deadline':time.monotonic()+spec.get('time_budget',45)}
    queue=[(u,0) for u in dict.fromkeys([spec['url']]+spec.get('entry_urls',[]))][:3];visited=set();articles={};entries=[];readable=False;count=0
    while queue and len(visited)<5:
        url,depth=queue.pop(0)
        if url in visited:continue
        visited.add(url)
        page,actual=load_page(url,context,policy)
        readable=readable or bool(page.links or page.paragraphs)
        for href,title in sorted(page.links,key=lambda item:not any(w in item[1] for w in SECTIONS)):
            link=canonical_url(urllib.parse.urljoin(actual,href))
            try:validate_url(link,spec['hosts'])
            except ValueError:continue
            if not policy.can_fetch('CustomerResearchBot',link):continue
            if depth<1 and len(title.strip())<=18 and '/content/' not in link and any(w in title for w in SECTIONS) and link not in visited:
                if link not in entries:entries.append(link)
                if len(queue)<4:queue.append((link,depth+1))
            if len(title)>7 and any(w in title for w in NOTICES) and IT.search(title):articles.setdefault(link,title)
    for url,title in list(articles.items())[:6]:
        if time.monotonic()>context['_deadline']:break
        time.sleep(1)
        page,actual=load_page(url,context,policy)
        if getattr(page,'partial',False):continue
        title=page_title(page,title)
        facts=html_notice_facts(page,title,source)
        if not facts:continue
        save_document(store,source['customer_id'],actual,title,'\n'.join(page.paragraphs+page.parts)[:5000],page.published,['单位平台采购公告'],facts);count+=1
    if not readable:raise PermissionError('Page has no readable public list; may require JavaScript or login')
    if not spec.get('is_listing') and not entries and not articles:raise RuntimeError('No procurement section or matching notice discovered; homepage news is not procurement coverage')
    return count,{'discovered_entries':entries[:8],'pages_checked':len(visited),'candidate_notices':len(articles)}

def collect_customer_platforms(store,source):
    results=[]
    for spec in source.get('procurement_sources',[]):
        started=now();count=0;status='failed';error=None;diagnostics={}
        try:
            count,diagnostics=(collect_yzw if spec['kind']=='yzw' else collect_html)(store,source,spec)
            status='success'
        except (PermissionError,urllib.error.HTTPError) as exc:status='blocked';error=str(exc)[:180]
        except Exception as exc:error=type(exc).__name__+': '+str(exc)[:160]
        store.query('INSERT INTO crawl_runs VALUES(?,?,?,?,?,?,?,?)',[str(uuid.uuid4()),source['customer_id'],spec['url'],started,now(),status,count,error])
        results.append({'customer_id':source['customer_id'],'source':spec['label'],'url':spec['url'],'status':status,'documents_found':count,'error':error,**diagnostics})
    return results
