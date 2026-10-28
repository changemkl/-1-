import datetime as dt
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('dongfeng',Path(__file__).resolve().parents[1]/'scripts/sync-dongfeng.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class WorklogTests(unittest.TestCase):
    def setUp(self):
        self.customers=[{'id':'a','name':'公安部第三研究所','aliases':['公安三所']},{'id':'b','name':'上海市公安局','relatedPrefixes':['上海市公安局']},{'id':'c','name':'中国浦东干部学院','aliases':['中浦院']}]
        self.now=dt.datetime(2026,10,28,12,tzinfo=m.CHINA)
        self.data={'tasks':[{'id':'t','clientName':'公安部第三研究所','title':'算力中心','timeline':[{'id':'d','title':'每日进展登记','workDate':'2026-10-27','description':'准备运营材料'}]}],'visits':[],'workLogs':[]}
    def test_baseline_then_new_events_keep_source_date_and_stay_idempotent(self):
        old={'entries':[{'id':'initial','customerId':'a','customerName':'公安部第三研究所','workDate':'2026-10-28','content':'首次同步汇总'}]}
        initial,state=m.sync(self.data,self.customers,old,{},True,self.now)
        same,state=m.sync(self.data,self.customers,initial,state,now=self.now)
        self.assertEqual(same,initial)
        self.data['tasks'][0]['timeline'].append({'id':'new','title':'每日进展登记','workDate':'2026-10-28','description':'完成方案交流'})
        newer,state=m.sync(self.data,self.customers,same,state,now=self.now)
        self.assertEqual(len(newer['entries']),2)
        self.assertEqual(next(r for r in newer['entries']if r['id']!='initial')['workDate'],'2026-10-28')
        repeated,_=m.sync(self.data,self.customers,newer,state,now=self.now)
        self.assertEqual(repeated,newer)
    def test_resource_only_timestamp_changes_do_not_create_new_progress(self):
        task=self.data['tasks'][0];task['latestProgress']='准备方案';task['updatedAt']='2026-10-27T01:00:00Z'
        initial,state=m.sync(self.data,self.customers,{'entries':[]},{},True,self.now)
        task['updatedAt']='2026-10-28T01:00:00Z'
        same,_=m.sync(self.data,self.customers,initial,state,now=self.now)
        self.assertEqual(same['entries'],[])
    def test_only_completed_visits_and_explicit_dates(self):
        self.data['visits']=[{'id':'v','clientName':'公安三所','status':'PLANNED','plannedTime':'2026-10-28','visitOutcome':'待拜访'},{'id':'done','clientName':'公安三所','status':'COMPLETED','actualTime':'2026-10-27 13:00','visitOutcome':'需求交流'}]
        rows=m.candidates(self.data,self.customers)
        self.assertNotIn('visit:v',rows);self.assertEqual(rows['visit:done']['workDate'],'2026-10-27')
        self.assertIsNone(m.day('无日期'));self.assertEqual(m.day('2026-10-27T17:00:00Z'),'2026-10-28')
    def test_related_units_and_ambiguous_railway_unit_are_separate(self):
        self.assertEqual(m.customer_match('上海市公安局浦东分局',self.customers)['id'],'b')
        self.assertIsNone(m.customer_match('上海市铁路公安局',self.customers))
        self.assertEqual(m.customer_match('中浦院',self.customers)['id'],'c')
    def test_multi_customer_narrative_is_split_and_testing_references_excluded(self):
        self.data['workLogs']=[{'id':'w','title':'工作汇总','workDate':'2026-10-28','content':'公安三所：准备交流材料\n中浦院：提交方案\n其他客户：内部协调'},{'id':'bad','workDate':'2026-10-28','content':'公安三所检测报告不满足要求'}]
        rows=m.candidates(self.data,self.customers)
        self.assertEqual(rows['worklog:w:a']['content'],'公安三所：准备交流材料')
        self.assertEqual(rows['worklog:w:c']['content'],'中浦院：提交方案')
        self.assertNotIn('worklog:bad:a',rows)
    def test_incomplete_response_and_missing_baseline_never_wipe_history(self):
        with self.assertRaises(ValueError):m.sync({},self.customers,{'entries':[]},{},now=self.now)
        with self.assertRaises(ValueError):m.sync(self.data,self.customers,{'entries':[]},{},now=self.now)
    def test_sensitive_contact_and_credentials_are_removed(self):
        self.assertNotIn('13812345678',m.clean('联系电话13812345678'))
        self.assertNotIn('secretvalue',m.clean('password=secretvalue'))

if __name__=='__main__':unittest.main()
