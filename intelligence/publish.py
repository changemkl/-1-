"""Publish a standalone, read-only JSON snapshot. Never writes the online sheet."""
import argparse
import datetime
import json
import re
import unicodedata
import urllib.parse
from pathlib import Path
import sqlite3
from facts import extract_facts,official_url,VERSION,is_standard_approval


def deduplicate_signals(items):
    by_url = {}
    def quality(item):
        projects=(item.get('facts') or {}).get('projects',[])
        return (2 if any(not p.get('public_title_only') for p in projects) else 1 if projects else 0,item['fetched_at'])
    for item in sorted(items,key=quality,reverse=True):
        if item['category']=='客户概况' and '信息列表' in item['title']:continue
        url=item['url'].split('#')[0]
        by_url.setdefault(url,dict(item))
    unique=[];seen=set()
    for item in by_url.values():
        title=re.sub(r'\s+','',unicodedata.normalize('NFKC',item['title'])).lower()
        excerpt=re.sub(r'\s+','',item['excerpt'])[:120]
        title_only=any(p.get('public_title_only') for p in (item.get('facts') or {}).get('projects',[]))
        key=(title,excerpt,item['url'] if title_only else '')
        if key in seen:continue
        seen.add(key)
        item['source_host']=urllib.parse.urlsplit(item['url']).hostname
        unique.append(item)
    return unique


def merge_public_projects(projects):
    known={}
    for project in projects:
        key=project.get('notice_url') or project['url']
        for field in ('planned_purchase','deadline'):
            value=project.get(field)
            if value:
                identifier=value.get('value') if isinstance(value,dict) else value
                known.setdefault((key,field),{})[identifier]=value
    detailed={p['url'] for p in projects if not p.get('public_title_only')}
    unique={}
    for project in sorted(projects,key=lambda p:bool(p.get('public_title_only'))):
        project=dict(project);url=project.get('notice_url') or project['url']
        if project.get('public_title_only'):
            if url in detailed:continue
            for field in ('planned_purchase','deadline'):
                values=known.get((url,field),{})
                if not project.get(field) and len(values)==1:project[field]=next(iter(values.values()))
        unique.setdefault((url,project['name']),project)
    return list(unique.values())


def publish(database, output):
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    previous = json.loads(output.read_text()) if output.exists() else {'profiles': []}
    old = {p['id']: p for p in previous.get('profiles', [])}
    verified = json.loads(Path('intelligence/verified-procurement.json').read_text()).get('records', [])
    profiles = []
    for customer in conn.execute('SELECT id,name FROM customers WHERE active=1 ORDER BY id'):
        identifier = customer['id']
        prior = old.get(identifier, {})
        signals = {(s['url'],s['category']):s for s in prior.get('signals', [])}
        for record in verified:
            if record['customer_id'] == identifier:
                item = {k:v for k,v in record.items() if k != 'customer_id'}
                signals = {key:value for key,value in signals.items() if value['url'] != item['url']}
                signals[(item['url'],item['category'])] = item
        definitions=json.loads(Path('intelligence/sources.json').read_text())['sources']
        source=next((s for s in definitions if s['customer_id']==identifier),None)
        for row in conn.execute("SELECT s.category,s.status,d.url,d.title,d.excerpt,d.published_at,d.fetched_at,f.payload AS facts_json FROM signals s JOIN documents d ON d.id=s.document_id LEFT JOIN document_facts f ON f.document_id=d.id WHERE s.customer_id=? AND s.status!='rejected' ORDER BY d.fetched_at DESC", [identifier]):
            item = dict(row)
            item['facts']=json.loads(item.pop('facts_json')) if item.get('facts_json') else None
            item.pop('facts_json',None)
            item['excerpt'] = item['excerpt'].replace(item['title'], '', 2).strip()
            signals[(item['url'],item['category'])] = item
        run = conn.execute('SELECT finished_at,status,documents_found,source_url FROM crawl_runs WHERE customer_id=? ORDER BY finished_at DESC LIMIT 1', [identifier]).fetchone()
        latest_run=max([r for r in [dict(run) if run else None,prior.get('lastRun')] if r],key=lambda r:r.get('finished_at',''),default=None)
        filtered=[];projects=[];leaders=[]
        for item in deduplicate_signals(signals.values()):
            if is_standard_approval(item['title']):continue
            if not official_url(item['url'],source):continue
            facts=item.get('facts')
            if not facts or facts.get('version')!=VERSION:
                # Older snippets are sufficient for conservative IT-dynamic filtering,
                # but never for confirming a current leader from a meeting report.
                kind='profile' if item['category']=='客户概况' else 'article'
                facts=extract_facts(item['title'],[item['excerpt']],source.get('aliases',[customer['name']]) if source else [customer['name']],kind)
            if not facts['projects'] and not facts['leaders']:continue
            item['facts']=facts
            item['category']='领导及分工' if facts['leaders'] else '项目与采购公开信息'
            filtered.append(item)
            provenance={k:item[k] for k in ['url','title','published_at','fetched_at','source_host']}
            projects.extend({**p,**provenance} for p in facts['projects'])
            leaders.extend({**p,**provenance} for p in facts['leaders'])
        unique_leaders={}
        projects=merge_public_projects(projects)
        for leader in sorted(leaders,key=lambda p:p['fetched_at'],reverse=True):
            unique_leaders.setdefault((leader['name'],leader['role']),leader)
        source_specs=list((source or {}).get('procurement_sources',[]))
        if source and source.get('government_procurement',True):
            source_specs.insert(0,{'label':'上海市政府采购网','url':'https://www.zfcg.sh.gov.cn'})
        prior_checks={s['url']:s for s in prior.get('procurementSources',[])}
        checks=[]
        for spec in source_specs:
            check=conn.execute('SELECT finished_at,status,documents_found FROM crawl_runs WHERE customer_id=? AND source_url=? ORDER BY finished_at DESC LIMIT 1',[identifier,spec['url']]).fetchone()
            latest_check=max([r for r in [dict(check) if check else None,prior_checks.get(spec['url'])] if r],key=lambda r:r.get('finished_at',''),default={'status':'not_checked'})
            checks.append({**latest_check,'label':spec['label'],'url':spec['url']})
        profiles.append({'id':identifier,'name':customer['name'],'attributes':[], 'signals':filtered[:30],'projects':projects[:30],'leaders':list(unique_leaders.values())[:20], 'procurementSources':checks,'lastRun':latest_run})

    if not profiles:
        raise RuntimeError('No active customers; previous snapshot retained')
    payload = {'updatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'profiles':profiles}
    output.parent.mkdir(parents=True,exist_ok=True)
    temp = output.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    temp.replace(output)
    conn.close()
    print(f'Published {len(profiles)} customers and {sum(len(p["signals"]) for p in profiles)} source signals')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--sqlite',required=True);parser.add_argument('--output',default='public/profile-data.json');args=parser.parse_args()
    publish(args.sqlite,Path(args.output))
