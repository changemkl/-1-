import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path('intelligence').resolve()))
from collector import registry,sync_customers,save_document,collect_source,Page,validate_url
from store import Store

class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(self.temp.name+'/db.sqlite')
        self.store.initialize()
        sync_customers(self.store,{'1':'测试客户'})
    def tearDown(self):
        self.store.local.close();self.temp.cleanup()
    def test_names_are_separate_from_profiles(self):
        self.store.query('INSERT INTO profile_attributes VALUES(?,?,?,?,?)',['1','下一步动作','预约需求交流','manual','2026-10-22'])
        sync_customers(self.store,{'1':'更新名称'})
        self.assertEqual(self.store.query('SELECT name FROM customers')[0]['name'],'更新名称')
        self.assertEqual(self.store.query('SELECT value FROM profile_attributes')[0]['value'],'预约需求交流')
        sync_customers(self.store,{'2':'另一家客户'})
        self.assertEqual(self.store.query('SELECT active FROM customers WHERE id=?',['1'])[0]['active'],0)
        self.assertEqual(len(self.store.query('SELECT * FROM profile_attributes')),1)
    def test_evidence_deduplication_and_versions(self):
        args=(self.store,'1','https://example.org/news','数字化采购公告')
        save_document(*args,'原文摘录',None)
        save_document(*args,'原文摘录',None)
        self.assertEqual(len(self.store.query('SELECT * FROM documents')),1)
        self.assertEqual(len(self.store.query('SELECT * FROM document_versions')),1)
        self.assertEqual(len(self.store.query('SELECT * FROM signals')),2)
        self.assertEqual({r['status'] for r in self.store.query('SELECT status FROM signals')},{'pending'})
        save_document(*args,'更新原文',None)
        self.assertEqual(len(self.store.query('SELECT * FROM document_versions')),2)
    def test_blocked_source_is_a_failure_not_empty_success(self):
        with patch('collector.robot_policy',side_effect=PermissionError('robots blocked')):
            result=collect_source(self.store,{'customer_id':'1','url':'https://example.org/','hosts':['example.org'],'aliases':['测试客户']})
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(len(self.store.query('SELECT * FROM documents')),0)
        self.assertEqual(self.store.query('SELECT status FROM crawl_runs')[0]['status'],'blocked')
    def test_identity_and_source_validation(self):
        self.assertEqual(registry([['集团编号','客户名称','客户标签'],['1','测试客户','不要导入标签']]),{'1':'测试客户'})
        with self.assertRaises(ValueError):registry([['客户名称']])
        with self.assertRaises(ValueError):registry([['集团编号','客户名称'],['1','甲'],['1','乙']])
        for url in ['http://example.org','https://evil.example','https://example.org:8443','https://user:pass@example.org']:
            with self.assertRaises(ValueError):validate_url(url,['example.org'])
        p=Page();p.feed('<title>测试</title><script>伪造信息</script><a href="/a">采购公告</a>')
        self.assertNotIn('伪造信息',p.parts)
        self.assertEqual(p.links,[('/a','采购公告')])

if __name__=='__main__':unittest.main()
