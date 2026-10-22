"""Bounded, attributed public-source collection. No LLM or inferred sales facts."""
import argparse
import datetime
import hashlib
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
        super().__init__(); self.skip=0; self.title=False; self.title_parts=[]; self.parts=[]; self.links=[]; self.anchor=None; self.anchor_parts=[]; self.published=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('script','style','noscript'): self.skip+=1
        if tag=='title':self.title=True
        if tag=='a':self.anchor=(attrs.get('href') or '').strip();self.anchor_parts=[]
        if tag=='meta' and (attrs.get('property') in ['article:published_time'] or attrs.get('name','').lower() in ['pubdate','publishdate','pubtime','date']):self.published=attrs.get('content')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):self.skip=max(0,self.skip-1)
        if tag=='title':self.title=False
        if tag=='a' and self.anchor:
            self.links.append((self.anchor,''.join(self.anchor_parts).strip()));self.anchor=None
    def handle_data(self,data):
        if self.skip:return
        text=data.strip()
        if text:self.parts.append(text)
        if self.title:self.title_parts.append(text)
        if self.anchor:self.anchor_parts.append(text)

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
    with opener.open(request,timeout=20) as response:
        if not any(t in response.headers.get('Content-Type','') for t in ['text/','application/xhtml+xml']):raise ValueError('Unsupported source content type')
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('Source exceeds response size limit')
        encoding=response.headers.get_content_charset() or 'utf-8'
        try:return raw.decode(encoding)
        except UnicodeDecodeError:return raw.decode('gb18030',errors='replace')

def robot_policy(url,hosts):
    robots=urllib.parse.urljoin(url,'/robots.txt')
    parser=urllib.robotparser.RobotFileParser()
    try:parser.parse(download(robots,hosts).splitlines())
    except urllib.error.HTTPError as exc:
        if exc.code!=404:raise PermissionError('Source robots policy unavailable or blocked') from None
        parser.parse([])
    return parser

def categories(title):return [label for label,words in CATEGORIES.items() if any(word in title for word in words)]

def save_document(store,customer,url,title,excerpt,published):
    identifier=digest(customer+'|'+url);checksum=digest(title+'|'+excerpt);stamp=now()
    statements=[('INSERT INTO documents(id,customer_id,url,title,excerpt,published_at,fetched_at,content_hash) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,excerpt=excluded.excerpt,published_at=excluded.published_at,fetched_at=excluded.fetched_at,content_hash=excluded.content_hash',[identifier,customer,url,title,excerpt,published,stamp,checksum]),('INSERT OR IGNORE INTO document_versions(document_id,content_hash,title,excerpt,fetched_at) VALUES(?,?,?,?,?)',[identifier,checksum,title,excerpt,stamp])]
    for category in categories(title):
        statements.append(('INSERT OR IGNORE INTO signals(id,customer_id,document_id,category,status,created_at) VALUES(?,?,?,?,\'pending\',?)',[digest(identifier+'|'+category),customer,identifier,category,stamp]))
    store.batch(statements)

def collect_source(store,source):
    started=now();count=0;status='failed';error=None
    try:
        hosts=source['hosts'];url=source['url'];policy=robot_policy(url,hosts)
        if not policy.can_fetch(AGENT,url):raise PermissionError('Disallowed by source robots policy')
        page=Page();page.feed(download(url,hosts))
        text=' '.join(page.parts)
        if not any(alias in text for alias in source['aliases']):raise ValueError('Source customer identity not confirmed')
        candidates=[]
        for href,title in page.links:
            link=urllib.parse.urljoin(url,href).split('#')[0]
            try:validate_url(link,hosts)
            except ValueError:continue
            path=urllib.parse.urlsplit(link).path
            date_match=re.search(r'/((?:19|20)\d{2})(0[1-9]|1[0-2])/',path)
            if date_match:
                year,month=map(int,date_match.groups())
                age=(datetime.datetime.now().year-year)*12+datetime.datetime.now().month-month
                if age<0 or age>12:continue
            prefixes=source.get('article_prefixes',[])
            article=any(path.startswith(prefix) for prefix in prefixes) if prefixes else bool(categories(title))
            if article and path.endswith(('.html','.htm','.shtml')) and policy.can_fetch(AGENT,link) and link not in [p[0] for p in candidates]:candidates.append((link,title))
        # Small batches protect free quotas and target sites. No bypass of 403 or login.
        for link,headline in candidates[:3]:
            time.sleep(1)
            detail=Page();detail.feed(download(link,hosts))
            title=''.join(detail.title_parts).strip() or headline
            if not categories(title):continue
            relevant=[p for p in detail.parts if any(word in p for words in CATEGORIES.values() for word in words)]
            excerpt=' '.join(relevant)[:700]
            if not excerpt:continue
            save_document(store,source['customer_id'],link,title,excerpt,detail.published);count+=1
        status='success'
    except (PermissionError,urllib.error.HTTPError) as exc:
        status='blocked';error=f'Source unavailable: {getattr(exc,"code",type(exc).__name__)}'
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
