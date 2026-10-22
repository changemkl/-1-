"""Bounded, attributed public-source collection. No LLM or inferred sales facts."""
import argparse
import datetime
import hashlib
import http.client
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import uuid

from store import Store

AGENT = 'CustomerResearchBot'
MAX_BYTES = 1500000
CATEGORIES = {'采购动态': ['招标','采购公告','采购意向','中标'], '数字化动态': ['数字化','信息化','人工智能','智慧','算力'], '规划动态': ['十五五','发展规划','专项规划'], '人事动态': ['任免','任命','领导分工'], '经营动态': ['签约','中标','开工','项目','竣工','交付']}

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(s): return hashlib.sha256(s.encode()).hexdigest()

def registry(rows):
    headers = rows[0]
    name_index = next((i for i,h in enumerate(headers) if h in ['客户名称','名称','单位名称']),None)
    id_index = next((i for i,h in enumerate(headers) if h in ['集团编号','客户编号','ID']),None)
    if name_index is None: raise ValueError('Customer name column not found')
    result = {}
    for row in rows[1:]:
        name = str(row[name_index]).strip() if len(row)>name_index else ''
        if not name: continue
        identifier = str(row[id_index]).strip() if id_index is not None and len(row)>id_index else ''
        identifier = identifier or 'name:'+re.sub(r'\s+','',unicodedata.normalize('NFKC',name).lower())
        if identifier in result and result[identifier] != name: raise ValueError('Conflicting customer identifiers')
        result[identifier] = name
    if not result: raise ValueError('Empty customer registry; database not changed')
    return result

def sync_customers(store, customers):
    if not customers: raise ValueError('Empty customer registry')
    statements = []
    stamp = now()
    for identifier,name in customers.items():
        statements.append(('INSERT INTO customers(id,name,active,updated_at) VALUES(?,?,1,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,active=1,updated_at=excluded.updated_at',[identifier,name,stamp]))
    statements.append(('UPDATE customers SET active=0 WHERE updated_at<>?',[stamp]))
    store.batch(statements)

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip=0; self.title=False; self.title_parts=[]; self.parts=[]; self.links=[]; self.anchor=None; self.anchor_parts=[]; self.published=None; self.description=None; self.paragraph_parts=[]; self.paragraphs=[]; self.in_paragraph=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('script','style','noscript'): self.skip+=1
        if tag=='title':self.title=True
        if tag=='a':self.anchor=(attrs.get('href') or '').strip();self.anchor_parts=[];self.anchor_title=attrs.get('title','')
        if tag=='p':self.in_paragraph=True;self.paragraph_parts=[]
        if tag=='meta' and attrs.get('name','').lower()=='description':self.description=attrs.get('content')
        if tag=='meta' and (attrs.get('property') in ['article:published_time'] or attrs.get('name','').lower() in ['pubdate','publishdate','pubtime','date','articlepubdate','article_publishdate']):self.published=attrs.get('content')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):self.skip=max(0,self.skip-1)
        if tag=='title':self.title=False
        if tag=='a' and self.anchor:
            self.links.append((self.anchor,self.anchor_title or ''.join(self.anchor_parts).strip()));self.anchor=None
        if tag=='p' and self.in_paragraph:
            text=''.join(self.paragraph_parts).strip()
            if text:self.paragraphs.append(text)
            self.in_paragraph=False
    def handle_data(self,data):
        if self.skip:return
        text=data.strip()
        if text:self.parts.append(text)
        if self.title:self.title_parts.append(text)
        if self.anchor:self.anchor_parts.append(text)
        if self.in_paragraph:self.paragraph_parts.append(text)

class AllowedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self,hosts): self.hosts=hosts
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_url(newurl,self.hosts)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def validate_url(url,hosts):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname not in hosts or p.username or p.password or p.port not in (None,443):raise ValueError('Source URL outside approved HTTPS hosts')

def download(url,hosts):
    validate_url(url,hosts)
    request=urllib.request.Request(url,headers={'User-Agent':AGENT+'/1.0','Accept':'text/html,text/plain;q=0.9'})
    opener=urllib.request.build_opener(AllowedRedirect(hosts))
    for attempt in range(2):
        try:
            with opener.open(request,timeout=20) as response:
                if not any(t in response.headers.get('Content-Type','') for t in ['text/','application/xhtml+xml']):raise ValueError('Unsupported source content type')
                encoding=response.headers.get_content_charset() or 'utf-8'
                try:raw=response.read(MAX_BYTES+1)
                except http.client.IncompleteRead as exc:
                    # Some sites omit the final chunk marker despite a complete HTML body.
                    # Accept only a closed document; otherwise retry the transport once.
                    if b'</html>' not in exc.partial.lower():raise
                    raw=exc.partial
                if len(raw)>MAX_BYTES:raise ValueError('Source exceeds response size limit')
                meta=re.search(br'charset\s*=\s*["\']?([a-zA-Z0-9_-]+)',raw[:4096])
                if meta:encoding=meta.group(1).decode('ascii')
                try:return raw.decode(encoding)
                except (UnicodeDecodeError,LookupError):return raw.decode('gb18030',errors='replace')
        except http.client.IncompleteRead:
            if attempt:raise
            time.sleep(1)

def robot_policy(url,hosts):
    robots=urllib.parse.urljoin(url,'/robots.txt')
    parser=urllib.robotparser.RobotFileParser()
    try:parser.parse(download(robots,hosts).splitlines())
    except urllib.error.HTTPError as exc:
        if exc.code!=404:raise PermissionError(f'robots.txt returned HTTP {exc.code}') from None
        parser.parse([])
    return parser

def categories(title):return [label for label,words in CATEGORIES.items() if any(word in title for word in words)]

def save_document(store,customer,url,title,excerpt,published,record_categories=None):
    identifier=digest(customer+'|'+url);checksum=digest(title+'|'+excerpt);stamp=now()
    statements=[('INSERT INTO documents(id,customer_id,url,title,excerpt,published_at,fetched_at,content_hash) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,excerpt=excluded.excerpt,published_at=excluded.published_at,fetched_at=excluded.fetched_at,content_hash=excluded.content_hash',[identifier,customer,url,title,excerpt,published,stamp,checksum]),('INSERT OR IGNORE INTO document_versions(document_id,content_hash,title,excerpt,fetched_at) VALUES(?,?,?,?,?)',[identifier,checksum,title,excerpt,stamp])]
    for category in (record_categories if record_categories is not None else categories(title)):
        statements.append(('INSERT OR IGNORE INTO signals(id,customer_id,document_id,category,status,created_at) VALUES(?,?,?,?,\'pending\',?)',[digest(identifier+'|'+category),customer,identifier,category,stamp]))
    store.batch(statements)

PROFILE_WORDS = ('公司简介','集团简介','企业概况','公司概况','机构职能','主要职责','机构职责','机构概况','部门职责','Company Profile','Group Profile','Corporate Profile','About Us')
LIST_WORDS = ('公司快讯','新闻中心','新闻动态','工作动态','通知公告','最新要闻','政务公开','Company News','News Center','Press Releases','Media Center','News')

def normalize_text(text):return re.sub(r'\s+','',unicodedata.normalize('NFKC',text)).lower()

def matches_customer(page,source):
    # Required for every article, not merely the home page navigation.
    content=' '.join(page.title_parts+page.paragraphs+[p for p in page.parts if len(p)>=25])
    normalized=normalize_text(content)
    return any(normalize_text(alias) in normalized for alias in source['aliases'])

def canonical_url(url):
    p=urllib.parse.urlsplit(url.strip())
    query=urllib.parse.urlencode([(k,v) for k,v in urllib.parse.parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_')])
    return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,query,''))

def recent_url(url):
    match=re.search(r'/((?:19|20)\d{2})(0[1-9]|1[0-2])/',urllib.parse.urlsplit(url).path)
    if not match:return True
    year,month=map(int,match.groups());today=datetime.datetime.now(datetime.timezone.utc)
    return 0<=(today.year-year)*12+today.month-month<=12

def load_page(url,source,policy):
    for _ in range(3):
        validate_url(url,source['hosts'])
        if not policy.can_fetch(AGENT,url):raise PermissionError('Disallowed by robots.txt')
        text=download(url,source['hosts'])
        if any(marker in text for marker in ('__CHALLENGE_CONFIG__','__PARIS_CHALLENGE_START__')):raise PermissionError('Source requires interactive verification')
        # Some official home pages contain only a normal static location redirect.
        # This does not execute scripts or attempt a security challenge.
        redirect=re.search(r"location\.(?:replace|assign)\(['\"]([^'\"]+)['\"]\)",text) if len(text)<1000 else None
        if redirect:
            url=canonical_url(urllib.parse.urljoin(url,redirect.group(1)));continue
        page=Page();page.feed(text);return page,url
    raise ValueError('Too many static redirects')

def evidence_excerpt(page,source):
    parts=list(dict.fromkeys(p.strip() for p in (page.paragraphs or page.parts) if len(p.strip())>=30))
    exact=[p for p in parts if any(normalize_text(alias) in normalize_text(p) for alias in source['aliases'])]
    body=exact+[p for p in parts if p not in exact]
    return ' '.join(body)[:900]

def collect_source(store,source):
    started=now();count=0;status='failed';error=None;errors=[]
    try:
        hosts=source['hosts'];policy=robot_policy(source['url'],hosts)
        queue=[(u,False) for u in dict.fromkeys([source['url']]+source.get('entry_urls',[]))][:3]
        visited=set();candidates={};listing_count=0;identity_found=False
        while queue:
            url,is_listing=queue.pop(0)
            if url in visited:continue
            visited.add(url)
            try:
                page,actual=load_page(url,source,policy)
                if not matches_customer(page,source):
                    errors.append('Customer identity mismatch: '+url+'; title='+''.join(page.title_parts)[:100]);continue
                identity_found=True
                for href,title in page.links:
                    link=canonical_url(urllib.parse.urljoin(actual,href))
                    try:validate_url(link,hosts)
                    except ValueError:continue
                    if not policy.can_fetch(AGENT,link):continue
                    path=urllib.parse.urlsplit(link).path
                    profile=source.get('discover_profiles') and any(w.lower() in title.lower() for w in PROFILE_WORDS)
                    if profile:
                        candidates.setdefault(link,(title,'profile'));continue
                    if not is_listing and listing_count<min(source.get('max_list_pages',2),3) and any(w.lower() in title.lower() for w in LIST_WORDS) and link not in visited:
                        queue.append((link,True));listing_count+=1
                    article=path.endswith(('.html','.htm','.shtml','.aspx')) or bool(urllib.parse.urlsplit(link).query)
                    focused=any(path.startswith(p) for p in source.get('article_prefixes',[]))
                    if article and recent_url(link) and (focused or is_listing or categories(title)) and len(title.strip())>8:
                        candidates.setdefault(link,(title,'article'))
                if source.get('kind')=='profile':candidates.setdefault(actual,(''.join(page.title_parts),'profile'))
            except Exception as exc:errors.append(type(exc).__name__+': '+str(exc)[:100])
        if not identity_found:
            raise PermissionError('; '.join(errors[:2]) or 'No matching source page could be read')
        profiles=[(u,t,k) for u,(t,k) in candidates.items() if k=='profile'][:2]
        articles=[(u,t,k) for u,(t,k) in candidates.items() if k=='article'][:min(source.get('max_articles',5),8)]
        for link,headline,kind in profiles+articles:
            time.sleep(1)
            try:
                detail,actual=load_page(link,source,policy)
                if not matches_customer(detail,source):continue
                title=''.join(detail.title_parts).strip() or headline
                excerpt=evidence_excerpt(detail,source)
                if len(excerpt)<50:continue
                record_categories=['客户概况'] if kind=='profile' else (categories(title) or ['客户动态'])
                save_document(store,source['customer_id'],actual,title,excerpt,detail.published,record_categories);count+=1
            except Exception as exc:errors.append(type(exc).__name__+': '+str(exc)[:100])
        status='success'
        if errors:error='Some pages unavailable: '+'; '.join(errors[:2])
    except (PermissionError,urllib.error.HTTPError) as exc:
        status='blocked';error=f'Source unavailable: {getattr(exc,"code",str(exc))}'[:300]
    except Exception as exc:error=type(exc).__name__+': '+str(exc)[:160]
    store.query('INSERT INTO crawl_runs(id,customer_id,source_url,started_at,finished_at,status,documents_found,error) VALUES(?,?,?,?,?,?,?,?)',[str(uuid.uuid4()),source['customer_id'],source['url'],started,now(),status,count,error])
    return {'customer_id':source['customer_id'],'status':status,'documents_found':count,'error':error}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sqlite');parser.add_argument('--customer-id');args=parser.parse_args()
    customers=registry(json.loads(Path('public/tencent-data.json').read_text())['rows'])
    store=Store(args.sqlite);store.initialize();sync_customers(store,customers)
    sources=json.loads(Path('intelligence/sources.json').read_text())['sources']
    selected=[s for s in sources if s.get('enabled') and s['customer_id'] in customers and (not args.customer_id or s['customer_id']==args.customer_id)]
    if not selected:raise RuntimeError('No enabled, approved source for the selected customers')
    results=[collect_source(store,s) for s in selected]
    print(json.dumps(results,ensure_ascii=False))
    if all(r['status']!='success' for r in results):raise RuntimeError('All selected sources failed or blocked; previous evidence retained')

if __name__=='__main__':main()
