"""Collect only explicit business roles from approved official leadership pages."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from collector import Page, download, robot_policy

SOURCES = [
    {'id':'2100199365','kind':'team','url':'https://8bur.cscec.com/gywm18/gltd18/','article':'中建八局管理团队'},
    {'id':'2100172632','kind':'commission','url':'https://zjw.sh.gov.cn/jgld/index.html'},
    {'id':'2100161493','kind':'sports','url':'https://tyj.sh.gov.cn/ldcy/index.html','article':'市体育局领导及工作分工'},
    {'id':'2108019729','kind':'basin','url':'https://www.tba.gov.cn/slbthlyglj/jg/jg.html'},
]

def clean(text):
    return re.sub(r'\s+', ' ', text).strip()

def person(name, role, division, quote):
    if not re.fullmatch(r'[\u4e00-\u9fff·]{2,4}', name) or not role:
        raise ValueError('Unrecognized official leadership layout')
    return {'name':name,'role':clean(role),'division':clean(division) or None,
            'category':'单位领导','informationResponsibility':bool(re.search(r'(?:负责|分管)[^。]*信息化',division) and not re.search(r'不(?:再)?(?:负责|分管)[^。]*信息化',division)),
            'quote':clean(quote)}

def parse_people(kind, text):
    text=clean(text)
    if kind=='commission':
        records=[]
        # Split the actual biography panels, never the navigation's name list.
        for block in text.split('机构领导')[2:]:
            m=re.match(r'\s*([\u4e00-\u9fff ]{2,8})\s+(?:男|女)，',block)
            role=re.search(r'现任(.+?)[。]',block)
            if m and role:
                records.append(person(m[1].replace(' ',''),role[1],'',m[1]+' 现任'+role[1]+'。'))
        return records
    if kind=='sports':
        records=[]
        for block in text.split('市体育局党组')[1:]:
            block='党组'+block.split('返回顶部')[0].strip()
            m=re.match(r'(.+?)\s+([\u4e00-\u9fff]{2,4})\s+((?:主持|分管).+)',block)
            if not m: raise ValueError('Unrecognized sports leader block')
            records.append(person(m[2],m[1],m[3],m[0]))
        return records
    if kind=='team':
        body=text.split('字号：',1)[-1].split('【打印本页】')[0]
        pattern=r'((?:党委书记、董事长|党委副书记、总经理|党委副书记、董事、工会主席|财务总监|纪委书记|总工程师|总经济师、总法律顾问、首席合规官|副总经理(?:、总建筑师)?))\s+([\u4e00-\u9fff]{2,4})(?=\s|$)'
        return [person(m[2],m[1],'',m[0]) for m in re.finditer(pattern,body)]
    if kind=='basin':
        role=re.search(r'现任水利部太湖流域管理局(.+?)。',text)
        name=re.search(r'简介\s+.+?\s+([\u4e00-\u9fff]{2,4})，(?:男|女)',text)
        division=re.search(r'工作分工[：:]\s*(.+?)(?=\s+活动|$)',text)
        if not name or not role: raise ValueError('Unrecognized basin leader page')
        d=division[1] if division else ''
        return [person(name[1],role[1],d,name[1]+' 现任水利部太湖流域管理局'+role[1]+'。'+(' 工作分工：'+d if d else ''))]
    raise ValueError('Unknown source kind')

class Reader:
    def __init__(self):self.policies={}
    def read(self,url):
        host=urlsplit(url).hostname
        if host not in {urlsplit(s['url']).hostname for s in SOURCES}:raise ValueError('Unapproved host')
        if host not in self.policies:self.policies[host]=robot_policy(url,{host})
        if not self.policies[host].can_fetch('CustomerResearchBot',url):raise PermissionError('Robots policy prohibits reading')
        raw=download(url,{host})
        if getattr(raw,'partial',False):raise ValueError('Incomplete page')
        page=Page();page.feed(raw)
        return page

def collect(source,reader,stamp):
    url=source['url'];page=reader.read(url)
    if source.get('article'):
        links=[urljoin(url,h) for h,t in page.links if t==source['article'] and h not in ('./','#')]
        if not links:raise ValueError('Official leadership article not found')
        url=links[0];page=reader.read(url)
    pages=[(url,page)]
    if source['kind']=='basin':
        links=[urljoin(url,h) for h,t in page.links if re.fullmatch(r'[\u4e00-\u9fff]{2,4}',t) and h.endswith(('.htm','.html')) and '/jg/' not in h]
        if not links or len(links)>20:raise ValueError('Unrecognized leadership directory')
        pages=[(u,reader.read(u)) for u in dict.fromkeys(links)]
    people=[]
    for url,page in pages:
        records=parse_people(source['kind'],' '.join(page.parts))
        if not records:raise ValueError('No explicit leaders found')
        title=source.get('article') or ('太湖局官网 · 领导简介' if source['kind']=='basin' else '上海市住建委官网 · 机构领导')
        # Never take dates from unrelated news or activities below biographies.
        published=page.published
        if source['kind'] in ('team','sports'):
            date=re.search(r'\d{4}-\d{2}-\d{2}', ' '.join(page.parts).split('字号：')[0])
            published=date[0] if date else published
        for record in records:
            record.update(source={'url':url,'title':title,'publishedAt':published},checkedAt=stamp)
            people.append(record)
    if len({p['name'] for p in people})!=len(people):raise ValueError('Duplicate leader names')
    return people

def main():
    path=Path('public/people-data.json')
    data=json.loads(path.read_text()) if path.exists() else {'customers':[]}
    previous={r['id']:r for r in data['customers']};reader=Reader()
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
    for source in SOURCES:
        record=previous.setdefault(source['id'],{'id':source['id'],'people':[]})
        try:
            people=collect(source,reader,stamp)
            record.update(people=people,lastCheck={'at':stamp,'status':'ok'})
            print(source['id'],len(people),'official leaders')
        except Exception as exc:
            record['lastCheck']={'at':stamp,'status':'unavailable','message':str(exc)[:200]}
            print(source['id'],'retained previous evidence:',str(exc)[:120])
    data.update(updatedAt=stamp,customers=list(previous.values()))
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
