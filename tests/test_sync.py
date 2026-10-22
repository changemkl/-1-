import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('sync', 'scripts/sync-tencent.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

class SyncTests(unittest.TestCase):
    def test_cell_types(self):
        self.assertEqual(sync.cell_text({'cellValue': {'number': 0}}), '0')
        self.assertEqual(sync.cell_text({'cellValue': {'text': '<script>bad</script>'}}), '<script>bad</script>')
        self.assertEqual(sync.cell_text({'cellValue': {'location': {'name': '上海'}}}), '上海')
        self.assertEqual(sync.cell_text({}), '')

    def test_success_cache_and_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'data.json'
            page = {'gridData': {'rows': [{'values': [{'cellValue': {'text': '名称'}}]}, {'values': [{'cellValue': {'text': '测试客户'}}]}]}}
            blank = {'gridData': {'rows': []}}
            secrets = {k: 'secret-placeholder' for k in ['TENCENT_DOCS_CLIENT_ID','TENCENT_DOCS_ACCESS_TOKEN','TENCENT_DOCS_OPEN_ID']}
            with patch.object(sync, 'OUTPUT', output), patch.dict(os.environ, secrets), patch.object(sync, 'request_api', side_effect=[{'fileID': 'test-id'}, page, blank]) as api:
                sync.main()
                self.assertEqual(api.call_count, 3)
                original = output.read_text()
                self.assertNotIn('secret-placeholder', original)
                self.assertEqual(json.loads(original)['rows'][1], ['测试客户'])
            with patch.object(sync, 'OUTPUT', output), patch.dict(os.environ, secrets), patch.object(sync, 'request_api', side_effect=[page, blank]) as api:
                sync.main()
                self.assertEqual(api.call_count, 2)
                self.assertEqual(output.read_text(), original)
            for bad in [{'gridData': {}}, {'gridData': {'rows': []}}]:
                with patch.object(sync, 'OUTPUT', output), patch.dict(os.environ, secrets), patch.object(sync, 'request_api', return_value=bad):
                    with self.assertRaises(RuntimeError): sync.main()
                    self.assertEqual(output.read_text(), original)

    def test_missing_secrets(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'Missing GitHub Secrets'): sync.main()

if __name__ == '__main__': unittest.main()
