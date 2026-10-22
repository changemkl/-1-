import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path('intelligence').resolve()))
from store import Store
from collector import sync_customers,save_document
from publish import publish

class PublishTests(unittest.TestCase):
    def test_export_and_preserve_evidence_on_failed_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            database=directory+'/db.sqlite';output=Path(directory)/'data.json'
            store=Store(database);store.initialize();sync_customers(store,{'1':'客户甲'})
            save_document(store,'1','https://example.org/a','项目交付','项目公开原文',None)
            publish(database,output)
            data=json.loads(output.read_text());self.assertEqual(len(data['profiles'][0]['signals']),1)
            store.query('DELETE FROM signals');store.query('DELETE FROM document_versions');store.query('DELETE FROM documents')
            store.query('INSERT INTO crawl_runs VALUES(?,?,?,?,?,?,?,?)',['run','1','https://example.org','2026-10-22','2026-10-22','blocked',0,'403'])
            publish(database,output)
            data=json.loads(output.read_text());self.assertEqual(len(data['profiles'][0]['signals']),1)
            self.assertEqual(data['profiles'][0]['lastRun']['status'],'blocked')
            self.assertNotIn('CLOUDFLARE',output.read_text())
            store.local.close()

if __name__=='__main__':unittest.main()
