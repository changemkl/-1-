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
 def test_only_changed_records_are_archived_not_entire_customer(self):
  now=datetime.datetime(2026,11,3,9,tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
  def entry(content):return {'hash':m.fingerprint(content),'data':content}
  original={'log-a':entry({'id':'a','content':' unchanged'}),'log-b':entry({'id':'b','content':'old'})}
  changed={'log-a':original['log-a'],'log-b':entry({'id':'b','content':'new'}),'log-c':entry({'id':'c','content':'added'})}
  old={'x':{'name':'甲','parts':{'工作日志':'old'},'records':{'工作日志':original}}}
  current={'x':{'name':'甲','parts':{'工作日志':'new'},'records':{'工作日志':changed}}}
  state,j=m.record(current,old,[],now)
  self.assertEqual([i['key'] for i in j['events'][0]['items']],['log-b','log-c'])
  self.assertEqual([i['change'] for i in j['events'][0]['items']],['修改','新增'])
  self.assertEqual(j['events'][0]['items'][0]['record']['content'],'new')
  changed['log-b']['data']['content']='later'
  # Serialized journal preserves the event version, not a live customer lookup.
  self.assertEqual(j['events'][0]['items'][0]['record']['content'],'new')
 def test_procurement_removal_and_metadata_changes(self):
  a={'id':'a','title':'项目甲','url':'https://example.gov.cn/a','fetched_at':'old'}
  b={**a,'fetched_at':'new'}
  self.assertEqual(m.changed_items({'a':{'hash':m.fingerprint(b),'data':b}},{'a':{'hash':m.fingerprint(a),'data':a}}),[])
  removed=m.changed_items({}, {'a':{'hash':m.fingerprint(a),'data':a}})
  self.assertEqual(removed[0]['change'],'移除')
if __name__=='__main__':unittest.main()
