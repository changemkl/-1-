"""Refresh reviewed public notices. Never read masked fields or authenticated data."""
import argparse,datetime,json,re,time,urllib.request
from pathlib import Path
from collector import Page
CHINA=datetime.timezone(datetime.timedelta(hours=8))
MANIFEST=Path('intelligence/external-notices.json')

def parse_notice(text,title,url,customer,today=None):
    today=today or datetime.datetime.now(CHINA).date().isoformat()
    name=customer['name'];compact=lambda s:re.sub(r'\s+','',s).replace('（','(').replace('）',')')
    buyer=re.search(r'采购单位\s*\n([^\n]+)',text)
    if not buyer:buyer=re.search(r'(?:采购人|采购单位)信息\s*\n名\s*称\s*[:：]\s*([^\n]+)',text)
    if not buyer:return None
    buyer=buyer[1].strip();bn=compact(buyer);cn=compact(name)
    if not (bn==cn or bn==cn+'(本级)' or (name=='上海市消防救援总队' and bn.startswith(cn)) or cn in [compact(n) for n in re.split('[、，,]',buyer)]):return None
    title=title.split('_')[0].strip()
    if not title or any(w in title for w in ['更正','终止','废标','取消','撤销']):return None
    date=re.search(r'(20\d{2})[年-](\d{1,2})[月-](\d{1,2})(?:日|\s)',text)
    if not date:return None
    try:published=datetime.date(*map(int,date.groups())).isoformat()
    except ValueError:return None
    if published>today:return None
    pname=re.search(r'二、项目名称\s*[:：]\s*([^\n]+)',text)
    project_name=pname[1].strip() if pname else title
    if any(w in title for w in ['中标公告','成交公告','结果公告']):
        names=list(dict.fromkeys(re.findall(r'供应商名称\s*[:：]\s*([^\n]+)',text)))
        row={'title':title,'projectName':project_name,'date':published,'buyer':buyer,'url':url,'source':'中国政府采购网' if 'www.ccgp.gov.cn/' in url else '政府采购信息网·易找标（公开转载）','dateLabel':'结果公告日期'}
        if len(names)==1 and '*' not in names[0]:
            lot={'lotName':project_name,'suppliers':names,'quote':'项目名称：'+project_name+'；中标供应商：'+names[0]}
            money=re.search(r'中标[（(]成交[）)]金额\s*[:：]\s*([\d,，.\s]+)\s*[（(]?(万元|元)',text)
            if money:
                try:lot['amountYuan']=round(float(re.sub(r'[,，\s]','',money[1]))*(10000 if money[2]=='万元' else 1),2)
                except ValueError:pass
            row['awards']=[lot]
        return {'kind':'award','record':row}
    if not any(w in title for w in ['招标公告','磋商公告','询价公告','谈判公告']):return None
    expiry=re.search(r'(?:提交投标文件截止时间|截止时间)\s*[:：]\s*(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\s*(\d{1,2})[点时:：]\s*(\d{1,2})',text)
    if not expiry:return None
    try:deadline=datetime.datetime(*map(int,expiry.groups()),tzinfo=CHINA)
    except ValueError:return None
    if deadline.date().isoformat()<today:return None
    stage='竞争性磋商公告' if '磋商' in title else '公开招标公告' if '公开招标' in title else '采购公告'
    project={'name':project_name,'stage':stage,'notice_url':url,'quote':title+'\n采购人：'+buyer+'\n'+expiry[0], 'buyer':{'value':buyer,'unit':'','quote':'采购人：'+buyer},'deadline':{'value':deadline.strftime('%Y-%m-%d %H:%M'),'unit':'','quote':expiry[0]},'planned_purchase':None}
    return {'kind':'project','record':project,'published_at':published,'title':title}

def refresh(evidence=None,limit=4):
    manifest=json.loads(MANIFEST.read_text())['notices'];hist_path=Path('public/award-history.json');profile_path=Path('public/profile-data.json')
    hist=json.loads(hist_path.read_text());profiles=json.loads(profile_path.read_text());history={r['id']:r for r in hist['customers']};by_id={r['id']:r for r in profiles['profiles']}
    stamp=datetime.datetime.now(CHINA).isoformat(timespec='seconds');provided={r['url']:r for r in evidence or []};counts={'award':0,'project':0,'skipped':0}
    def checked(spec):return history.get(spec['customerId'],{}).get('externalSourceChecks',{}).get(spec['url'],{}).get('at','')
    selected=manifest if evidence is not None else sorted(manifest,key=checked)[:limit]
    for spec in selected:
        identifier=spec['customerId'];customer={'name':spec['customerName']};h=history.setdefault(identifier,{'id':identifier,'name':customer['name'],'results':[]})
        if h['name']!=customer['name'] or by_id.get(identifier,{}).get('name')!=customer['name']:continue
        try:
            cached=provided.get(spec.get('mirrorUrl'))
            if evidence is not None and not cached:continue
            if cached:
                text=cached.get('originalText') if spec['url'].startswith('https://www.ccgp.gov.cn/') else cached.get('text');title=cached['title']
                if not text:continue
            else:
                raw=urllib.request.urlopen(urllib.request.Request(spec['url'],headers={'User-Agent':'CustomerResearchBot/1.0'}),timeout=15).read(2000000).decode('utf-8',errors='replace');page=Page();page.feed(raw);text='\n'.join(page.parts);title=''.join(page.title_parts)
                time.sleep(.5)
            parsed=parse_notice(text,title,spec['url'],customer)
            h.setdefault('externalSourceChecks',{})[spec['url']]={'at':stamp,'status':'ok' if parsed else 'unconfirmed'}
            if not parsed:counts['skipped']+=1;continue
            record=parsed['record'];record['mirror_url']=spec.get('mirrorUrl');counts[parsed['kind']]+=1
            if parsed['kind']=='award':
                rows={r['url']:r for r in h['results']};rows[spec['url']]=record;h['results']=sorted(rows.values(),key=lambda r:r['date'],reverse=True)
            else:
                p=by_id[identifier];facts={'version':1,'kind':'procurement','projects':[record],'leaders':[],'organizations':[]}
                signal={'url':spec['url'],'title':parsed['title'],'published_at':parsed['published_at'],'fetched_at':stamp,'source_host':'www.ccgp.gov.cn','category':'项目与采购公开信息','status':'verified','excerpt':record['quote'],'facts':facts}
                p['signals']=[s for s in p.get('signals',[]) if s['url']!=spec['url']]+[signal]
                p['projects']=[r for r in p.get('projects',[]) if (r.get('notice_url') or r.get('url'))!=spec['url']]+[{**record,**{k:signal[k] for k in ['url','title','published_at','fetched_at','source_host']}}]
        except Exception as exc:h.setdefault('externalSourceChecks',{})[spec['url']]={'at':stamp,'status':'unavailable','message':str(exc)[:150]}
    hist['customers']=list(history.values());hist['updatedAt']=stamp;profiles['updatedAt']=stamp
    hist_path.write_text(json.dumps(hist,ensure_ascii=False,indent=2)+'\n');profile_path.write_text(json.dumps(profiles,ensure_ascii=False,indent=2)+'\n')
    print('Reviewed external notices:',json.dumps(counts))
    return counts

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence');parser.add_argument('--limit',type=int,default=4);args=parser.parse_args()
    refresh(json.loads(Path(args.evidence).read_text()) if args.evidence else None,args.limit)
