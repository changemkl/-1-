import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path('intelligence').resolve()))
from store import Store
from collector import sync_customers,save_document
from publish import publish,deduplicate_signals,merge_public_projects

class PublishTests(unittest.TestCase):
    def test_public_titles_do_not_replace_verified_dates_or_duplicate_notices(self):
        detailed={'name':'明确项目','url':'https://unit.gov.cn/notice','planned_purchase':'2025-11'}
        title={'name':'公开标题','url':'https://unit.gov.cn/list','notice_url':detailed['url'],'public_title_only':True}
        result=merge_public_projects([title,detailed])
        self.assertEqual(result,[detailed])
        second={**title,'notice_url':'https://unit.gov.cn/other'}
        self.assertEqual(len(merge_public_projects([second,dict(second)])),1)

    def test_identical_monthly_intent_titles_on_different_notices_are_retained(self):
        base={'category':'公开采购标题','title':'单位2099年11月采购意向','excerpt':'相同的列表摘要','fetched_at':'2026-10-23','url':'https://unit.gov.cn/a','facts':{'projects':[{'public_title_only':True}]}}
        self.assertEqual(len(deduplicate_signals([base,{**base,'url':'https://unit.gov.cn/b'}])),2)

    def test_verified_notices_survive_repeated_automatic_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            database=directory+'/db.sqlite';output=Path(directory)/'data.json'
            store=Store(database);store.initialize()
            sync_customers(store,{'2100161493':'上海市体育局','2100172632':'上海市住房和城乡建设管理委员会'})
            for _ in range(2):
                publish(database,output)
                data=json.loads(output.read_text())
                projects=[p for c in data['profiles'] for p in c['projects']]
                self.assertEqual(len(projects),6)
                self.assertEqual(len({p['url'] for p in projects}),6)
                exam=next(p for p in projects if p['name']=='线下计算机考试技术服务费')
                self.assertIn('人才开发评价中心',exam['buyer']['value'])
                self.assertIn('不认定为委机关直接采购',exam['relation'])
                self.assertEqual(exam['planned_purchase'],'2027-01')
            store.local.close()

    def test_url_deduplication_does_not_merge_different_generic_titles(self):
        base={'category':'客户动态','title':'工作通知','excerpt':'不同内容一','fetched_at':'2026-10-22','url':'https://example.org/a'}
        duplicate={**base,'category':'数字化动态'}
        different={**base,'url':'https://example.org/b','excerpt':'不同内容二'}
        self.assertEqual(len(deduplicate_signals([base,duplicate,different])),2)

    def test_export_and_preserve_evidence_on_failed_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            database=directory+'/db.sqlite';output=Path(directory)/'data.json'
            store=Store(database);store.initialize();sync_customers(store,{'1':'客户甲'})
            save_document(store,'1','https://unit.gov.cn/a','信息化系统采购公告','项目名称：信息化系统建设\n预算金额：100万元',None)
            publish(database,output)
            data=json.loads(output.read_text());self.assertEqual(len(data['profiles'][0]['signals']),1)
            store.query('DELETE FROM document_facts');store.query('DELETE FROM signals');store.query('DELETE FROM document_versions');store.query('DELETE FROM documents')
            store.query('INSERT INTO crawl_runs VALUES(?,?,?,?,?,?,?,?)',['run','1','https://example.org','2026-10-22','2026-10-22','blocked',0,'403'])
            publish(database,output)
            data=json.loads(output.read_text());self.assertEqual(len(data['profiles'][0]['signals']),1)
            self.assertEqual(data['profiles'][0]['lastRun']['status'],'blocked')
            self.assertNotIn('CLOUDFLARE',output.read_text())
            store.local.close()

if __name__=='__main__':unittest.main()
