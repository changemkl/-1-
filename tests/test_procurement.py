import sys
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path('intelligence').resolve()))
from procurement import tender_facts,collect_public_tenders
from collector import sync_customers
from store import Store

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

    def test_public_portal_title_is_saved_if_detail_requires_login(self):
        row={'purchaseName':'客户甲','announcementType':3001,'articleId':'notice1','parentId':1,'title':'信息化系统公开招标公告','content':'公开列表摘要'}
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory+'/db.sqlite');store.initialize();sync_customers(store,{'1':'客户甲'})
            responses=[{'data':[row],'total':1},PermissionError('Login required'),{'data':[],'total':0}]
            with patch('procurement.portal_policy'),patch('procurement.request_json',side_effect=responses),patch('procurement.time.sleep'):
                result=collect_public_tenders(store,{'customer_id':'1','aliases':['客户甲']})
            self.assertEqual(result['documents_found'],1)
            import json
            p=json.loads(store.query('SELECT payload FROM document_facts')[0]['payload'])['projects'][0]
            self.assertEqual(p['name'],'信息化系统公开招标公告')
            self.assertTrue(p['public_title_only'])
            self.assertIsNone(p['deadline'])
            store.local.close()

if __name__=='__main__':unittest.main()
