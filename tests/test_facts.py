import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path('intelligence').resolve()))
from facts import extract_facts, official_url

class FactTests(unittest.TestCase):
    def facts(self,title,body,kind='article'):
        return extract_facts(title,body.split('\n'),['客户甲'],kind)

    def test_generic_news_and_civil_investment_are_not_it_projects(self):
        for title,body in [('学校建设开工','总投资：9.97亿元'),('科普活动举行','介绍人工智能系统应用')]:
            self.assertEqual(self.facts(title,body)['projects'],[])

    def test_notice_preserves_budget_and_buyer_evidence(self):
        p=self.facts('信息化系统采购公告','项目名称：信息化系统建设\n采购人：客户甲\n预算金额（万元）：100\n总投资：9亿元')['projects'][0]
        self.assertEqual(p['budget']['value'],'100')
        self.assertEqual(p['budget']['unit'],'万元')
        self.assertEqual(p['stage'],'采购公告')
        self.assertEqual(p['relation'],'客户为公告所列采购人')

    def test_supplier_does_not_become_customer_demand(self):
        p=self.facts('信息化系统中标公告','项目名称：信息化系统建设\n采购人：其他单位\n中标供应商：客户甲\n成交金额：200万元')['projects'][0]
        self.assertIn('供应商',p['relation'])
        self.assertIsNone(p['budget'])
        self.assertEqual(p['award_amount']['value'],'200万元')

    def test_multiple_projects_have_no_merged_budget(self):
        p=self.facts('信息化采购意向','项目名称：信息化系统建设\n预算金额：100万元\n项目名称：智慧校园建设\n预算金额：300万元')['projects'][0]
        self.assertIsNone(p['budget'])

    def test_investigation_is_not_tender_or_leader_evidence(self):
        f=self.facts('调研AI+建设工程招投标项目','局长张三调研人工智能系统建设')
        self.assertEqual(f['projects'][0]['stage'],'公开建设动态')
        self.assertIsNone(f['projects'][0]['budget'])
        self.assertEqual(f['leaders'],[])

    def test_leadership_requires_explicit_role_and_division(self):
        p=self.facts('张三','姓名：张三\n职务：局长\n工作分工：负责信息化建设','leadership')['leaders'][0]
        self.assertEqual(p['division'],'负责信息化建设')
        self.assertIn('职务：局长',p['role_quote'])
        self.assertEqual(self.facts('张三','姓名：张三\n原职务：局长','leadership')['leaders'],[])
        p=self.facts('张三','职务：局长','leadership')['leaders'][0]
        self.assertIsNone(p['division'])

    def test_sources_must_be_official_https(self):
        self.assertTrue(official_url('https://unit.gov.cn/a'))
        self.assertFalse(official_url('https://unit.gov.cn.evil.test/a'))
        self.assertFalse(official_url('http://unit.gov.cn/a'))

if __name__=='__main__':unittest.main()
