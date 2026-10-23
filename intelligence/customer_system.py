"""Persistent customer lifecycle and conservative official-source discovery."""
import argparse
import copy
import datetime
import ipaddress
import json
from pathlib import Path
import re
import socket
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

STATE=Path('public/customer-system.json')
ARCHIVE=Path('public/customer-archive.json')


def normalized(value):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(value))).lower()
def read_json(path,default):return json.loads(path.read_text()) if path.exists() else default

def write_json(path,data):
    if path.exists() and read_json(path,{})==data:return
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)

def catalog():return read_json(Path('intelligence/sources.json'),{'sources':[]})['sources']

def matched_source(identifier,name,definitions):
    matches=[s for s in definitions if normalized(name) in {normalized(a) for a in s.get('aliases',[])} and s.get('enabled',True)]
    return next((s for s in matches if s['customer_id']==identifier),matches[0] if matches else None)

def reconcile(rows,previous,definitions,stamp):
    from collector import registry
    active=registry(rows,allow_empty=True);old={r['id']:copy.deepcopy(r) for r in previous.get('customers',[])}
    for identifier,name in active.items():
        record=old.setdefault(identifier,{'id':identifier,'name':name,'firstSeenAt':stamp,'previousNames':[]})
        if record['name']!=name:
            record['previousNames']=list(dict.fromkeys(record.get('previousNames',[])+[record['name']]))
            record.update(name=name,nameChangedAt=stamp,sourceStatus='pending',candidates=[])
            record.pop('verifiedSource',None);record.pop('discovery',None)
        record['active']=True;record.pop('archivedAt',None)
        source=matched_source(identifier,name,definitions)
        if source:
            record.update(sourceStatus='verified',verifiedSource={**copy.deepcopy(source),'customer_id':identifier})
        elif record.get('sourceStatus')!='verified':record['sourceStatus']='pending'
    for identifier,record in old.items():
        if identifier not in active and record.get('active',True):record.update(active=False,archivedAt=stamp)
    result={'customers':list(old.values())}
    result['updatedAt']=stamp if result['customers']!=previous.get('customers',[]) else previous.get('updatedAt',stamp)
    return result

def safe_public_url(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):raise ValueError('Not a public HTTPS source')
    if '.' not in p.hostname or p.hostname.endswith(('.local','.internal')):raise ValueError('Non-public host')
    addresses=socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('Non-public network address')
    return p.hostname

def official_directory_candidates(name):
    from collector import download,Page,robot_policy,AGENT
    directories=['https://www.shanghai.gov.cn/'] if name.startswith('上海市') else ['https://www.gov.cn/home/2023-03/29/content_5748953.htm']
    aliases={normalized(name),normalized(name.removeprefix('上海')),normalized(name.removeprefix('中华人民共和国'))}
    abbreviations={'上海市教育委员会':'市教委','上海市经济和信息化委员会':'市经济信息化委','上海市卫生健康委员会':'市卫生健康委'}
    if name in abbreviations:aliases.add(normalized(abbreviations[name]))
    result=[]
    for directory in directories:
        host=urllib.parse.urlsplit(directory).hostname
        policy=robot_policy(directory,{host})
        if not policy.can_fetch(AGENT,directory):continue
        raw=download(directory,{host})
        if getattr(raw,'partial',False):continue
        page=Page();page.feed(raw)
        for href,title in page.links:
            if normalized(title) not in aliases:continue
            url=urllib.parse.urljoin(directory,href)
            if url.startswith('http://'):url='https://'+url[7:]
            if (urllib.parse.urlsplit(url).hostname or '').endswith('.gov.cn'):
                result.append({'url':url,'title':title,'status':'candidate','directory':directory})
    return result[:3]


def search_candidates(name):
    # Official government navigation is preferred over search-engine listings.
    try:
        directory=official_directory_candidates(name)
        if directory:return directory
    except Exception:pass
    # Search results are candidates, never evidence of official ownership.
    from collector import robot_policy, AGENT
    url='https://www.bing.com/search?'+urllib.parse.urlencode({'format':'rss','q':'"'+name+'" 官网'})
    hosts={'www.bing.com','cn.bing.com','bing.com'}
    policy=robot_policy(url,hosts)
    if not policy.can_fetch(AGENT,url):raise PermissionError('Search listing disallows automated reading')
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if urllib.parse.urlsplit(newurl).hostname not in hosts:raise ValueError('Search redirect outside service')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    opener=urllib.request.build_opener(Redirect())
    with opener.open(urllib.request.Request(url,headers={'User-Agent':AGENT+'/1.0'}),timeout=15) as response:
        raw=response.read(500001)
    if len(raw)>500000:raise ValueError('Search response too large')
    root=ET.fromstring(raw);results=[];seen=set()
    for item in root.findall('.//item'):
        title=item.findtext('title') or '';link=item.findtext('link') or ''
        p=urllib.parse.urlsplit(link)
        if p.scheme!='https' or not p.hostname or p.hostname in seen:continue
        if normalized(name) not in normalized(title):continue
        seen.add(p.hostname);results.append({'url':link,'title':title,'status':'candidate'})
        if len(results)==3:break
    return results

def verify_government_home(name,candidate,reader=None):
    """Only exact agency homepages on gov.cn qualify; articles/corporate sites stay pending."""
    from collector import Page,download,robot_policy,AGENT
    url=candidate['url'];p=urllib.parse.urlsplit(url)
    if not (p.hostname or '').endswith('.gov.cn'):return None
    if p.query or not re.fullmatch(r'/(?:[a-zA-Z_-]+/)?(?:index\.(?:html?|shtml))?',p.path or '/'):return None
    host=safe_public_url(url)
    if reader is None:
        policy=robot_policy(url,{host})
        if not policy.can_fetch(AGENT,url):raise PermissionError('Agency homepage disallows reading')
        raw=download(url,{host})
    else:raw=reader(url)
    if getattr(raw,'partial',False):raise ValueError('Incomplete official homepage')
    page=Page();page.feed(raw);title=normalized(' '.join(page.title_parts));body=' '.join(page.parts)
    exact=normalized(name)
    if not re.fullmatch(re.escape(exact)+r'(?:[|_·—-]?(?:官网|官方网站|门户网站|政府网站|首页))*',title):return None
    if not any(word in body for word in ['政府网站标识码','机构职能','政府信息公开']):return None
    return {'url':url,'hosts':[host],'enabled':True,'aliases':[name],'article_prefixes':[],
            'max_articles':4,'max_list_pages':3,'time_budget':45,'discover_profiles':True,
            'discover_leaders':True,'official':True,'dedicated':True,'government_procurement':True,
            'procurement_sources':[],'verification':'gov.cn exact-name agency homepage','verified_by':candidate.get('directory',url)}

def discover(state,stamp,search=search_candidates,verify=verify_government_home,limit=3):
    changed=False;attempted=0
    for record in state['customers']:
        if not record['active'] or record['sourceStatus']=='verified':continue
        last=record.get('discovery',{}).get('at')
        if last and datetime.datetime.fromisoformat(stamp)-datetime.datetime.fromisoformat(last)<datetime.timedelta(days=1):continue
        if attempted>=limit:break
        attempted+=1
        try:
            candidates=search(record['name']);record['candidates']=candidates
            for candidate in candidates:
                try:source=verify(record['name'],candidate)
                except Exception:continue
                if source:
                    record.update(sourceStatus='verified',verifiedSource={**source,'customer_id':record['id']});break
            record['discovery']={'at':stamp,'status':'checked'}
        except Exception as exc:record['discovery']={'at':stamp,'status':'unavailable','message':str(exc)[:140]}
        changed=True
    if changed:state['updatedAt']=stamp
    return state

def effective_sources(customers,definitions=None,state=None):
    definitions=catalog() if definitions is None else definitions
    state=read_json(STATE,{'customers':[]}) if state is None else state
    entries={r['id']:r for r in state['customers']};result=[]
    for identifier,name in customers.items():
        source=matched_source(identifier,name,definitions)
        record=entries.get(identifier,{})
        if not source and record.get('active') and record.get('name')==name and record.get('sourceStatus')=='verified':source=record.get('verifiedSource')
        if source:result.append({**copy.deepcopy(source),'customer_id':identifier})
    return result

def archive_removed(state,stamp):
    archived=read_json(ARCHIVE,{'customers':[]});entries={r['id']:r for r in archived['customers']}
    snapshots={key:{str(r['id']):r for r in read_json(Path(path),{field:[]}).get(field,[])} for key,path,field in [
        ('profile','public/profile-data.json','profiles'),('organization','public/organization-data.json','customers'),('people','public/people-data.json','customers')]}
    for record in state['customers']:
        if not record['active'] and (record['id'] not in entries or record.get('archivedAt')!=entries[record['id']].get('archivedAt')):
            entries[record['id']]={**copy.deepcopy(record),**{key:copy.deepcopy(values.get(record['id'])) for key,values in snapshots.items()}}
        elif record['active'] and record['id'] in entries:entries[record['id']].setdefault('restoredAt',stamp)
    updated={'customers':list(entries.values())};write_json(ARCHIVE,updated)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--discover',action='store_true');args=parser.parse_args()
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    rows=read_json(Path('public/tencent-data.json'),{})['rows']
    state=reconcile(rows,read_json(STATE,{'customers':[]}),catalog(),stamp)
    if args.discover:discover(state,stamp)
    archive_removed(state,stamp);write_json(STATE,state)
    print('Customer system:',sum(r['active'] for r in state['customers']),'active;',sum(r['active'] and r['sourceStatus']=='pending' for r in state['customers']),'sources pending')

if __name__=='__main__':main()
