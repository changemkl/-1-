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
import shutil
import subprocess
import tempfile
from collector import Page, load_page, robot_policy, canonical_url, validate_url, save_document, now, page_title
from facts import IT, VERSION, extract_facts, normalize

CHINA=datetime.timezone(datetime.timedelta(hours=8))
SECTIONS=('招标','采购','交易公告','公示公告')
NOTICES=('招标','采购公告','询价','磋商','采购意向')

def belongs_to_customer(buyer,source):
    return bool(buyer and (any(normalize(buyer).startswith(normalize(a)) for a in source.get('buyer_aliases',source['aliases'])) or normalize(buyer) in map(normalize,source.get('related_buyers',[]))))

def deadline_value(text,include_expired=False):
    pattern=r'(?:投标(?:文件递交)?截止(?:时间)?|提交投标文件截止时间|响应(?:文件提交)?截止(?:时间)?|报价截止(?:时间)?|递交投标文件(?:的)?截止时间)(?:[、，和][^\n\d]{1,25})?\s*[:：为]?\s*(\d{4})[年/.-]\s*(\d{1,2})[月/.-]\s*(\d{1,2})日?\s*(?:北京时间)?\s*(\d{1,2})\s*[:：时]\s*(\d{2})'
    match=re.search(pattern,text)
    if not match:return None
    try:stamp=datetime.datetime(*map(int,match.groups()),tzinfo=CHINA)
    except ValueError:return None
    if not include_expired and stamp<datetime.datetime.now(datetime.timezone.utc):return None
    return {'value':stamp.strftime('%Y-%m-%d %H:%M'),'unit':'','quote':match.group(0)}

def public_listing_project(title,url,source,spec,context=''):
    """A public title is evidence even when the detail page requires login."""
    title=' '.join(title.split())
    if not 6<=len(title)<=350 or any(w in title for w in ('中标','成交','结果公告','废标','终止','更正','澄清')):return None
    intention='采购意向' in title or '招标意向' in title or '招标计划' in title
    if not intention and (not IT.search(title) or not any(w in title for w in ('招标','采购公告','询价','磋商'))):return None
    match=re.search(r'(?:采购人|招标人|采购单位|招标单位)(?:(?:信息)?\s*[:：]?\s*(?:单位)?名\s*称)?\s*[:：]\s*([^\n；;]{2,100}?)(?=\n|\s+(?:公告|发布|预计|计划|投标|响应|报名|\d{4}[年-])|$)',context)
    buyer=match.group(1).strip() if match else None
    if buyer and not belongs_to_customer(buyer,source):return None
    associated=buyer or spec.get('dedicated_listing') or any(normalize(a) in normalize(title+' '+(context if len(context)<1500 else '')) for a in source.get('buyer_aliases',source['aliases']))
    if not associated:return None
    planned=None
    label=re.search(r'(?:预计|计划)(?:采购|招标)(?:时间|日期|月份)?\s*[:：]\s*(\d{4})[年/.-](\d{1,2})(?:[月/.-](\d{1,2})日?)?',context)
    if not label and intention:label=re.search(r'(\d{4})年\s*(\d{1,2})月',title)
    if label:
        groups=label.groups();year,month=int(groups[0]),int(groups[1]);day=int(groups[2]) if len(groups)>2 and groups[2] else None
        try:datetime.date(year,month,day or 1)
        except ValueError:return None
        planned=f'{year:04d}-{month:02d}'+(f'-{day:02d}' if day else '')
        today=datetime.datetime.now(CHINA).date().isoformat()
        if planned<(today if day else today[:7]):return None
    deadline=deadline_value(context,include_expired=True)
    if deadline and datetime.datetime.fromisoformat(deadline['value']).replace(tzinfo=CHINA)<datetime.datetime.now(datetime.timezone.utc):return None
    stage='采购意向' if '采购意向' in title else '招标意向' if intention else '公开招标公告' if '公开招标' in title else '采购公告'
    return {'name':title,'stage':stage,'public_title_only':True,'notice_url':url,'quote':'\n'.join([title]+([match.group(0)] if match else [])+([label.group(0)] if label else [])+([deadline['quote']] if deadline else [])),'buyer':{'value':buyer,'unit':'','quote':match.group(0)} if buyer else None,
            'supplier':None,'budget':None,'award_amount':None,'planned_purchase':planned,'deadline':deadline,'service_end':None,
            'relation':'公开列表所列采购人：'+buyer if buyer else '客户相关公开栏目标题；实际采购人未确认',
            'notice':'仅依据无需登录的公开标题及列表字段；未读取登录后详情。日期缺失时不确认采购有效期。'}

def render_public_listing(url,spec,policy):
    validate_url(url,spec['hosts'])
    if not policy.can_fetch('CustomerResearchBot',url):raise PermissionError('robots.txt disallows public page')
    browser=next((shutil.which(name) for name in ('google-chrome','chromium','chromium-browser') if shutil.which(name)),None)
    if not browser:raise PermissionError('Public page needs JavaScript; browser renderer unavailable')
    # Fresh anonymous profile; no saved credentials, login or challenge handling.
    with tempfile.TemporaryDirectory(prefix='public-procurement-browser-') as profile:
        result=subprocess.run([browser,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--user-data-dir='+profile,'--timeout=15000','--dump-dom',url],capture_output=True,timeout=25)
    if result.returncode or len(result.stdout)>2000000:raise PermissionError('Public browser page unavailable')
    page=Page();page.feed(result.stdout.decode('utf-8',errors='replace'))
    if any(w in ''.join(page.title_parts).lower() for w in ('验证码','安全验证','captcha','登录','login')):raise PermissionError('Public page requires login or verification')
    return page

def html_notice_facts(page,title,source):
    if not any(word in title for word in NOTICES) or any(word in title for word in ('中标','成交','结果公告','废标','终止','更正','澄清')):return None
    text='\n'.join(page.paragraphs+page.parts)
    match=re.search(r'(?<![\u4e00-\u9fff])(?:采购人|招标人|采购单位|招标单位)(?:(?:信息)?\s*[:：]?\s*(?:单位)?(?:名\s*称))?\s*[:：为]\s*([^\n。；;]{2,100})',text)
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
        project['relation']='客户本级采购' if normalize(buyer) in map(normalize,source['aliases']) else '官网发布的关联采购，实际采购人为'+buyer
    return facts

def yzw_notice(row,source):
    buyer=row.get('tenderCompanyName','');title=row.get('name','')
    if row.get('status') not in (1,2) or not belongs_to_customer(buyer,source) or not IT.search(title):return None
    # endTime/signUpEndDate describe registration, never substitute for tenderEndDate.
    value=row.get('tenderEndDate') or ''
    expires=None
    if value:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',value):return None
        try:expires=datetime.datetime.fromisoformat(value).replace(tzinfo=CHINA)
        except ValueError:return None
        if expires<datetime.datetime.now(datetime.timezone.utc):return None
    if not row.get('tenderCode'):return None
    query=urllib.parse.urlencode({k:row.get(k,'') for k in ('tenderId','tenderCode','source','tenantId')})
    url='https://xy.yzw.cn/sj/bid-detail?'+query
    quote=f'公告名称：{title}\n招标单位：{buyer}'+(f'\n投标截止（tenderEndDate）：{value}' if value else '')
    project={'name':title,'stage':'采购公告','public_title_only':True,'quote':quote,'buyer':{'value':buyer,'quote':'招标单位：'+buyer,'unit':''},'supplier':None,'budget':None,'award_amount':None,
             'deadline':{'value':expires.strftime('%Y-%m-%d %H:%M'),'quote':'tenderEndDate：'+value,'unit':''} if expires else None,'planned_purchase':None,'service_end':None,
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
    queue=[(u,0) for u in dict.fromkeys([spec['url']]+spec.get('entry_urls',[]))][:3]
    visited=set();entries=[];readable=False;count=0;detail_checks=0;protected=0;candidates=0
    while queue and len(visited)<5:
        url,depth=queue.pop(0)
        if url in visited:continue
        visited.add(url)
        page,actual=load_page(url,context,policy)
        if spec.get('render_public_list') and depth==0 and not any(any(w in title for w in NOTICES) for _,title in page.links):
            page=render_public_listing(actual,spec,policy)
        readable=readable or bool(page.links or page.paragraphs)
        rows={}
        for row in page.listing_rows:
            for href,title in row['links']:
                key=(href,title)
                if key not in rows or len(row['text'])<len(rows[key]):rows[key]=row['text']
        projects=[];seen=set()
        for href,title in sorted(page.links,key=lambda item:not any(w in item[1] for w in SECTIONS)):
            link=canonical_url(urllib.parse.urljoin(actual,href))
            try:validate_url(link,spec['hosts'])
            except ValueError:link=actual
            if depth<1 and len(title.strip())<=18 and not IT.search(title) and not re.search(r'\d{4}',title) and '/content/' not in link and any(w in title for w in SECTIONS) and link not in visited:
                if link not in entries:entries.append(link)
                if len(queue)<4:queue.append((link,depth+1))
            row_text=rows.get((href,title),title)
            project=public_listing_project(title,link,source,spec,row_text)
            if not project:continue
            candidates+=1
            # Optional public metadata enrichment; a protected detail never discards a public title.
            if not project['planned_purchase'] and not project['deadline'] and link!=actual and detail_checks<3 and policy.can_fetch('CustomerResearchBot',link) and not re.search(r'/(?:login|signin|sso)(?:[/?]|$)',link,re.I) and time.monotonic()+5<context['_deadline']:
                detail_checks+=1
                try:
                    detail,_=load_page(link,context,policy)
                    protected_page=any(word in ''.join(detail.title_parts).lower() for word in ('登录','login','验证码','安全验证','captcha'))
                    if not protected_page and not getattr(detail,'partial',False):
                        project=public_listing_project(title,link,source,spec,'\n'.join(detail.paragraphs+detail.parts))
                    else:protected+=1
                except Exception:protected+=1
            if not project:continue
            key=(project['notice_url'],project['name'])
            if key in seen:continue
            seen.add(key);projects.append(project)
            if len(projects)>=30:break
        if projects:
            facts={'version':VERSION,'kind':'public_listing','projects':projects,'leaders':[]}
            save_document(store,source['customer_id'],actual,page_title(page,spec['label']+'公开公告列表'),'\n'.join(p['quote'] for p in projects)[:10000],None,['公开采购标题'],facts)
            count+=len(projects)
    if not readable:raise PermissionError('Page has no readable public list; may require JavaScript or login')
    if not spec.get('is_listing') and not entries and not candidates:raise RuntimeError('No procurement section or matching notice discovered; homepage news is not procurement coverage')
    return count,{'discovered_entries':entries[:8],'pages_checked':len(visited),'public_titles_found':candidates,'optional_detail_checks':detail_checks,'protected_details_skipped':protected}


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
