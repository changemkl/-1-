import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path('intelligence').resolve()))
from procurement import tender_facts

class ProcurementTests(unittest.TestCase):
    def detail(self,date='2099年11月25日 09:30'):
        return {'title':'信息化系统公开招标公告','projectName':'信息化系统建设','content':f'<p>项目名称：信息化系统建设</p><p>投标截止时间：{date}</p>'}

    def test_only_explicit_unexpired_public_tenders_are_imported(self):
        facts=tender_facts(self.detail(),'客户甲',['客户甲'])
        self.assertEqual(facts['projects'][0]['stage'],'公开招标公告')
        self.assertEqual(facts['projects'][0]['deadline']['value'],'2099-11-25 09:30')
        self.assertIsNone(tender_facts(self.detail('2025年01月01日 10:00'),'客户甲',['客户甲']))
        self.assertIsNone(tender_facts({**self.detail(),'content':'<p>项目名称：信息化系统建设</p>'},'客户甲',['客户甲']))
        self.assertIsNone(tender_facts({**self.detail(),'title':'信息化系统竞争性磋商公告'},'客户甲',['客户甲']))

    def test_subordinate_buyer_is_not_presented_as_parent_buyer(self):
        p=tender_facts(self.detail(),'客户甲信息中心',['客户甲'])['projects'][0]
        self.assertEqual(p['buyer']['value'],'客户甲信息中心')
        self.assertIn('不认定为客户本级直接采购',p['relation'])

if __name__=='__main__':unittest.main()
