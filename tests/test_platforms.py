import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path('intelligence').resolve()))
from collector import Page,sync_customers
from store import Store
from platforms import yzw_notice,html_notice_facts,collect_customer_platforms,public_listing_project,collect_html

SOURCE={'customer_id':'1','aliases':['中国建筑第八工程局有限公司','中建八局'],'buyer_aliases':['中国建筑第八工程局','中建八局']}

class PlatformTests(unittest.TestCase):
    def row(self,**changes):
        return {'name':'中建八局信息化系统采购','tenderCompanyName':'中建八局第一建设有限公司','tenderCode':'public-test','status':1,'tenderEndDate':'2099-10-30 10:00:00',**changes}

    def test_registration_deadline_is_never_a_tender_deadline(self):
        notice=yzw_notice(self.row(tenderEndDate=None,endTime='2099-10-30 10:00:00'),SOURCE)
        self.assertIsNone(notice[4]['projects'][0]['deadline'])
        self.assertTrue(notice[4]['projects'][0]['public_title_only'])
        self.assertIsNone(yzw_notice(self.row(tenderEndDate='2025-01-01 10:00:00'),SOURCE))

    def test_keyword_hit_does_not_establish_customer_buyer_or_it_project(self):
        self.assertIsNone(yzw_notice(self.row(tenderCompanyName='中建三局'),SOURCE))
        self.assertIsNone(yzw_notice(self.row(name='中建八局砂石材料采购'),SOURCE))

    def test_public_platform_list_does_not_imply_open_tender_method_or_budget(self):
        _,_,_,_,facts=yzw_notice(self.row(amount=1000000,bidMethod='BIDDING_PRICE_PURCHASE'),SOURCE)
        project=facts['projects'][0]
        self.assertEqual(project['stage'],'采购公告')
        self.assertIsNone(project['budget'])
        self.assertEqual(project['deadline']['value'],'2099-10-30 10:00')
        self.assertEqual(project['buyer']['value'],'中建八局第一建设有限公司')

    def test_html_notice_requires_buyer_and_a_future_actual_deadline(self):
        page=Page();page.feed('<p>采购人：中建八局第一建设有限公司</p><p>信息化系统建设项目采购</p><p>投标截止时间：2099-10-30 10:00</p>')
        facts=html_notice_facts(page,'信息化系统公开招标公告',SOURCE)
        self.assertEqual(facts['projects'][0]['deadline']['value'],'2099-10-30 10:00')
        unrelated=Page();unrelated.feed('<p>采购人：中建三局</p><p>信息化系统建设项目采购</p><p>投标截止时间：2099-10-30 10:00</p>')
        self.assertIsNone(html_notice_facts(page,'信息化系统招标终止公告',SOURCE))
        self.assertIsNone(html_notice_facts(unrelated,'中建八局项目的信息化公开招标公告',SOURCE))

    def test_a_blocked_platform_does_not_prevent_checking_another_source(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory+'/db.sqlite');store.initialize();sync_customers(store,{'1':'客户'})
            specs=[{'label':str(i),'url':f'https://example.gov.cn/{i}','kind':'html'} for i in (1,2)]
            with patch('platforms.collect_html',side_effect=[PermissionError('Access unavailable'),(0,{'pages_checked':1})]):
                results=collect_customer_platforms(store,{**SOURCE,'procurement_sources':specs})
            self.assertEqual([r['status'] for r in results],['blocked','success'])
            self.assertEqual(len(store.query('SELECT * FROM crawl_runs')),2)
            store.local.close()

    def test_official_related_buyer_and_deadline_on_next_line(self):
        source={**SOURCE,'related_buyers':['太湖流域水文水资源监测中心(太湖流域水环境监测中心)']}
        page=Page();page.feed('<p>项目名称：无人机巢智能巡查项目</p><p>1.采购人信息</p><p>单位名称：太湖流域水文水资源监测中心(太湖流域水环境监测中心)</p><p>四、提交投标文件截止时间、开标时间和地点</p><p>2099-10-30 14:00（北京时间）</p>')
        facts=html_notice_facts(page,'无人机巢智能巡查项目采购公告',source)
        self.assertEqual(facts['projects'][0]['deadline']['value'],'2099-10-30 14:00')
        self.assertEqual(facts['projects'][0]['buyer']['value'],source['related_buyers'][0])
        self.assertIn('官网发布的关联采购',facts['projects'][0]['relation'])

    def test_public_intent_title_does_not_require_body_or_invent_dates(self):
        p=public_listing_project('中建八局信息化系统招标意向','https://platform.gov.cn/a',SOURCE,{},'报名截止时间：2099-10-30 10:00')
        self.assertEqual(p['stage'],'招标意向')
        self.assertIsNone(p['deadline'])
        self.assertIsNone(p['planned_purchase'])
        self.assertIsNone(p['buyer'])
        self.assertTrue(p['public_title_only'])
        self.assertIsNone(public_listing_project('中建八局2025年11月采购意向','https://platform.gov.cn/a',SOURCE,{}))
        self.assertIsNone(public_listing_project('中建三局信息化系统招标意向','https://platform.gov.cn/a',SOURCE,{}))

    def test_public_title_survives_protected_detail(self):
        page=Page();page.feed('<ul><li><a href="/notice/1">中建八局信息化系统公开招标公告</a><span>采购人：中建八局第一建设有限公司</span></li></ul>')
        spec={'url':'https://platform.gov.cn/notices/','hosts':['platform.gov.cn'],'kind':'html','label':'公开列表','is_listing':True}
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory+'/db.sqlite');store.initialize();sync_customers(store,{'1':'客户'})
            with patch('platforms.robot_policy') as robot,patch('platforms.load_page',side_effect=[(page,spec['url']),PermissionError('Detail requires login')]) as load:
                robot.return_value.can_fetch.return_value=True
                count,diagnostics=collect_html(store,SOURCE,spec)
            self.assertEqual(count,1)
            self.assertEqual(load.call_count,2)
            self.assertEqual(diagnostics['protected_details_skipped'],1)
            import json
            facts=json.loads(store.query('SELECT payload FROM document_facts')[0]['payload'])
            self.assertEqual(facts['projects'][0]['name'],'中建八局信息化系统公开招标公告')
            self.assertIsNone(facts['projects'][0]['deadline'])
            self.assertEqual(store.query('SELECT url FROM documents')[0]['url'],spec['url'])
            store.local.close()

if __name__=='__main__':unittest.main()
