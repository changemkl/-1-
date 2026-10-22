"""Publish a standalone, read-only JSON snapshot. Never writes the online sheet."""
import argparse
import datetime
import json
from pathlib import Path
import sqlite3


def publish(database, output):
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    previous = json.loads(output.read_text()) if output.exists() else {'profiles': []}
    old = {p['id']: p for p in previous.get('profiles', [])}
    profiles = []
    for customer in conn.execute('SELECT id,name FROM customers WHERE active=1 ORDER BY id'):
        identifier = customer['id']
        prior = old.get(identifier, {})
        signals = {(s['url'],s['category']):s for s in prior.get('signals', [])}
        for row in conn.execute("SELECT s.category,s.status,d.url,d.title,d.excerpt,d.published_at,d.fetched_at FROM signals s JOIN documents d ON d.id=s.document_id WHERE s.customer_id=? AND s.status!='rejected' ORDER BY d.fetched_at DESC", [identifier]):
            item = dict(row)
            item['excerpt'] = item['excerpt'].replace(item['title'], '', 2).strip()
            signals[(item['url'],item['category'])] = item
        run = conn.execute('SELECT finished_at,status,documents_found FROM crawl_runs WHERE customer_id=? ORDER BY finished_at DESC LIMIT 1', [identifier]).fetchone()
        profiles.append({'id':identifier,'name':customer['name'],'attributes':prior.get('attributes',[]),'signals':sorted(signals.values(),key=lambda x:x['fetched_at'],reverse=True)[:30], 'lastRun':dict(run) if run else prior.get('lastRun')})
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
