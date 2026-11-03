import importlib.util,datetime,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('journal',Path(__file__).resolve().parents[1]/'scripts/record-customer-updates.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class JournalTests(unittest.TestCase):
 def test_baseline_no_fake_history_and_real_changes_retain_after_read(self):
  now=datetime.datetime(2026,11,3,9,tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
  first={'a':{'name':'甲','parts':{'工作日志':'1'}}};state,j=m.record(first,{},[],now);self.assertEqual(j['events'],[])
  new={'a':{'name':'甲','parts':{'工作日志':'2'}}};state,j=m.record(new,state['customers'],j['events'],now);self.assertEqual(j['events'][0]['date'],'2026-11-03');self.assertEqual(j['events'][0]['label'],'工作日志')
  state,j=m.record(new,state['customers'],j['events'],now);self.assertEqual(len(j['events']),1)
  new['b']={'name':'乙','parts':{'工作日志':'1'}};state,j=m.record(new,state['customers'],j['events'],now);self.assertEqual(j['events'][-1]['label'],'新增客户')
 def test_metadata_and_array_reordering_do_not_create_changes(self):
  self.assertEqual(m.fingerprint({'updatedAt':'old','rows':[{'name':'乙'},{'name':'甲'}]}),m.fingerprint({'updatedAt':'new','rows':[{'name':'甲'},{'name':'乙'}]}))
if __name__=='__main__':unittest.main()
