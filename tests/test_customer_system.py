import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path('intelligence').resolve()))
import customer_system as system
from facts import extract_organizations

STAMP='2026-10-23T00:00:00+00:00'
LATER='2026-10-24T00:00:00+00:00'
SOURCE={'customer_id':'seed','enabled':True,'aliases':['客户甲','客户甲简称'],'url':'https://agency.gov.cn/','hosts':['agency.gov.cn'],'official':True}

class CustomerSystemTests(unittest.TestCase):
    def reconcile(self,rows,old=None):return system.reconcile([['客户编号','客户名称']]+rows,old or {'customers':[]},[SOURCE],STAMP)
    def test_added_customer_inherits_verified_source_by_exact_alias(self):
        state=self.reconcile([['new','客户甲简称'],['other','客户乙']])
        self.assertEqual(state['customers'][0]['verifiedSource']['customer_id'],'new')
        self.assertEqual(state['customers'][1]['sourceStatus'],'pending')
        self.assertEqual(len(system.effective_sources({'new':'客户甲简称','other':'客户乙'},[SOURCE],state)),1)
        self.assertEqual(self.reconcile([['new','客户甲简称'],['other','客户乙']],state),state)
    def test_rename_rechecks_source_and_deletion_is_reversible(self):
        state=self.reconcile([['new','客户甲'],['other','客户乙']])
        state=self.reconcile([['new','客户丙']],state)
        renamed=state['customers'][0]
        self.assertEqual(renamed['previousNames'],['客户甲'])
        self.assertEqual(renamed['sourceStatus'],'pending')
        self.assertNotIn('verifiedSource',renamed)
        self.assertFalse(state['customers'][1]['active'])
        restored=self.reconcile([['new','客户丙'],['other','客户乙']],state)
        self.assertTrue(restored['customers'][1]['active'])
        self.assertEqual(restored['customers'][1]['firstSeenAt'],STAMP)
    def test_removing_the_last_customer_archives_it_without_destroying_identity(self):
        before=self.reconcile([['x','客户甲']])
        after=self.reconcile([],before)
        self.assertFalse(after['customers'][0]['active'])
        self.assertEqual(after['customers'][0]['id'],'x')

    def test_ambiguous_results_remain_pending_and_retry_is_bounded(self):
        state=self.reconcile([['x','客户乙']])
        search=lambda name:[{'url':'https://example.com/','title':name}]
        system.discover(state,STAMP,search,lambda *args:None)
        self.assertEqual(state['customers'][0]['sourceStatus'],'pending')
        with patch.object(system,'search_candidates',side_effect=AssertionError('should not search')):
            system.discover(state,STAMP,lambda _:self.fail('same-day retry'),lambda *a:None)
        old=copy.deepcopy(state)
        system.discover(state,LATER,lambda _:(_ for _ in ()).throw(PermissionError('blocked')))
        self.assertEqual(state['customers'][0]['candidates'],old['customers'][0]['candidates'])
        self.assertEqual(state['customers'][0]['discovery']['status'],'unavailable')
    def test_automatic_approval_requires_exact_agency_homepage(self):
        html='<title>客户乙官方网站</title><p>政府信息公开 机构职能</p>'
        with patch.object(system,'safe_public_url',return_value='agency.gov.cn'):
            self.assertIsNotNone(system.verify_government_home('客户乙',{'url':'https://agency.gov.cn/'},lambda _:html))
            for url,title in [('https://agency.gov.cn/news/123.html','客户乙官方网站'),('https://example.com/','客户乙官方网站'),('https://agency.gov.cn/','关于客户乙的新闻')]:
                self.assertIsNone(system.verify_government_home('客户乙',{'url':url},lambda _:'<title>'+title+'</title><p>政府信息公开</p>'))
    def test_private_and_credential_urls_are_rejected(self):
        for url in ['http://agency.gov.cn/','https://user:pass@example.com/','https://localhost/','https://127.0.0.1/','https://169.254.169.254/']:
            with self.assertRaises(ValueError):system.safe_public_url(url)
    def test_archive_preserves_profile_without_rewriting_on_every_sync(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'archive.json'
            state={'customers':[{'id':'x','active':False,'archivedAt':STAMP,'name':'客户乙'}]}
            def read(path_,default):
                if path_==path:return json.loads(path.read_text()) if path.exists() else default
                if str(path_)=='public/profile-data.json':return {'profiles':[{'id':'x','projects':[{'name':'历史项目'}]}]}
                return default
            with patch.object(system,'ARCHIVE',path),patch.object(system,'read_json',side_effect=read):
                system.archive_removed(state,STAMP)
                saved=path.read_text();system.archive_removed(state,LATER)
                self.assertEqual(path.read_text(),saved)
                self.assertEqual(json.loads(saved)['customers'][0]['profile']['projects'][0]['name'],'历史项目')
    def test_only_explicit_department_enumerations_are_extracted(self):
        nodes=extract_organizations(['二、内设机构','（一）办公室。负责机关运转。','（二）信息化处。负责信息化工作。'],'profile')
        self.assertEqual([n['name'] for n in nodes[0]['children']],['办公室','信息化处'])
        self.assertEqual(extract_organizations(['会议邀请办公室、信息化处参会。'],'article'),[])
        self.assertEqual(extract_organizations(['主要职责：（一）负责信息化建设。'],'profile'),[])

if __name__=='__main__':unittest.main()
