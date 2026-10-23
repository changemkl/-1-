"""Conservative extraction of attributable public facts; no sales inferences."""
import re
import unicodedata
from urllib.parse import urlsplit

VERSION = 1
IT = re.compile(r'信息化|数字化|数字孪生|人工智能|智慧(?:校园|城市|水利|工地|体育|场馆|教育|交通|园区)|智能(?:化|系统|平台|监测|建造|巡查|巡检)|数据(?:中心|治理|平台|安全|资源)|网络(?:安全|建设|改造|运维)|通信(?:服务|网络|系统|设备|保障|线路)|光缆|光纤|服务器|局域网|视频监控|无人机巢|校园网|城域网|专线|算力|政务云|云平台|软件|物联网|弱电|(?<![A-Za-z])AI\s*[+＋]|\bBIM\b|\bIT\b',re.I)
ACTION = re.compile(r'建设|采购|招标|招投标|改造|升级|平台|系统|运维|服务项目|研发|试点|部署|应用|实施')
NAME_LABEL = re.compile(r'(?:项目名称|采购项目名称)\s*[:：]\s*([^\n；;]{4,140})')
LEADER_FIELDS = ('姓名','职务','分工')


def normalize(value):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(value))).lower()


def official_url(url,source=None):
    host=(urlsplit(url).hostname or '').lower()
    if urlsplit(url).scheme!='https':return False
    if host.endswith('.gov.cn'):return True
    return bool(source and source.get('official',False) and host in source.get('hosts',[]))


def label_value(text,labels,limit=130):
    labels='|'.join(re.escape(v) for v in labels)
    match=re.search(r'(?<![\u4e00-\u9fff])(?:'+labels+r')\s*(?:[（(]([^）)\n]{1,12})[）)])?\s*[:：]\s*([^\n。；;]{1,'+str(limit)+r'})',text)
    if not match:return None
    value=match.group(2).strip()
    # Do not join a subsequent field on the same line.
    value=re.split(r'\s+(?:项目编号|预算金额|采购人|采购单位|供应商|服务期限|联系电话)\s*[:：]',value)[0].strip()
    return {'value':value,'unit':match.group(1) or '', 'quote':match.group(0)}


def stage_for(title):
    if any(w in title for w in ('终止公告','废标公告','取消采购')):return '终止或废标'
    if any(w in title for w in ('更正公告','变更公告')):return '更正公告'
    if '采购意向' in title:return '采购意向'
    if any(w in title for w in ('招标意向','招标计划')):return '招标意向'
    if any(w in title for w in ('中标','成交','结果公告')):return '中标或成交信息'
    if '合同' in title:return '合同信息'
    if '验收' in title:return '验收信息'
    if '公开招标公告' in title:return '公开招标公告'
    if '公告' in title and any(w in title for w in ('采购','招标','磋商','询价','谈判')):return '采购公告'
    if any(w in title for w in ('规划','行动计划','实施方案')):
        return '规划草案' if any(w in title for w in ('征求意见','草案')) else '规划文件涉及事项'
    return '公开建设动态'


def extract_projects(title,paragraphs,aliases,kind):
    if kind in ('profile','leadership'):return []
    if is_standard_approval(title):return []
    text='\n'.join(paragraphs)
    named=NAME_LABEL.findall(text)
    named_it=[n for n in named if IT.search(n)]
    # A mention of AI in a science event, or an IT duty in an agency profile,
    # does not constitute a construction project.
    if not ((IT.search(title) and ACTION.search(title)) or named_it):return []
    relevant=[p for p in paragraphs if IT.search(p) and ACTION.search(p)]
    if not relevant and not named_it:return []
    stage=stage_for(title)
    name=named_it[0] if len(named_it)==1 else title
    subject_quote=next((p for p in paragraphs if name in p),None) or next(iter(relevant),title)
    record={'name':name,'stage':stage,'quote':subject_quote[:900], 'buyer':None,'supplier':None,'budget':None,'award_amount':None,'deadline':None,'service_end':None,'relation':'官网公开关联信息，采购主体未明确'}
    buyer=label_value(text,['采购人名称','采购人','采购单位','采购单位名称'])
    supplier=label_value(text,['中标供应商名称','成交供应商名称','中标供应商','成交供应商','供应商名称'])
    if buyer:
        record['buyer']=buyer
        record['relation']='客户为公告所列采购人' if any(normalize(buyer['value'])==normalize(a) for a in aliases) else '公告所列采购人另有其名，不认定为客户直接采购'
    if supplier:
        record['supplier']=supplier
        if any(normalize(supplier['value'])==normalize(a) for a in aliases):record['relation']='客户为公告所列供应商，不认定为客户采购需求'
    # Amounts and deadlines only come from labelled notice/contract fields.
    # Never reinterpret total building investment as an IT budget.
    notices=stage in ('采购意向','公开招标公告','采购公告','中标或成交信息','合同信息','验收信息','更正公告','终止或废标')
    if notices and len(named)<=1:
        record['budget']=label_value(text,['预算金额','采购预算','预算经费'])
        record['award_amount']=label_value(text,['中标金额','成交金额','合同金额'])
        record['deadline']=label_value(text,['投标截止时间','响应文件提交截止时间','提交投标文件截止时间'])
        record['service_end']=label_value(text,['服务结束日期','合同结束日期','合同到期日期'])
    record['notice']='原文事实，不代表尚有采购机会。' if stage not in ('采购意向','公开招标公告','采购公告') else '公告计划及有效期限以原文为准；不自动认定仍在招标。'
    return [record]


def is_standard_approval(title):
    return '关于批准' in title and any(word in title for word in ('标准','规范')) and '通知' in title


def extract_leaders(title,paragraphs,kind):
    if kind!='leadership':return []
    text='\n'.join(paragraphs)
    labelled=re.findall(r'(?:领导姓名|姓\s*名)\s*[:：]?\s*([\u4e00-\u9fff·]{2,12})(?=\s|[，。；;]|$)',text)
    name=None
    if len(set(labelled))==1:name=labelled[0]
    if not name and title.strip() not in ('领导分工','领导信息','领导介绍','领导简介','机构领导','单位领导','现任领导','领导班子') and re.fullmatch(r'[\u4e00-\u9fff·]{2,4}',title.strip()):name=title.strip()
    if not name:return []
    role=label_value(text,['现任职务','职务','职 务'])
    if not role:
        match=re.search(r'现任([^\n。]{2,100})',text)
        if match:role={'value':match.group(1).strip(),'unit':'','quote':match.group(0)}
    if not role or not re.search(r'局长|主任|书记|董事长|总经理|总裁|党组成员|党委委员|副董事长',role['value']):return []
    # An introduction mentioning an earlier office is not a current-office record.
    if any(w in role['value'] for w in ('曾任','原任','历任','已退休','已免职')):return []
    division=label_value(text,['工作分工','分管工作','工作职责','职责分工','分工'],500)
    name_match=re.search(re.escape(name),text)
    name_quote=text[max(0,name_match.start()-12):name_match.end()+30] if name_match else title
    return [{'name':name,'role':role['value'],'division':division['value'] if division else None,'name_quote':name_quote,'role_quote':role['quote'],'division_quote':division['quote'] if division else None,'status':'官网领导页面列示','note':'记录采集时的官网列示，不从会议出席推断任职或分工。'}]


def extract_facts(title,paragraphs,aliases,kind='article'):
    paragraphs=list(dict.fromkeys(p.strip() for p in paragraphs if p and p.strip()))
    return {'version':VERSION,'kind':kind,'projects':extract_projects(title,paragraphs,aliases,kind),'leaders':extract_leaders(title,paragraphs,kind)}
