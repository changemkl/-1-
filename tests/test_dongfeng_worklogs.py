import datetime as dt
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('dongfeng',Path(__file__).resolve().parents[1]/'scripts/sync-dongfeng.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class WorklogTests(unittest.TestCase):
    def setUp(self):
        self.customers=[{'id':'a','name':'公安部第三研究所','aliases':['公安三所']},{'id':'b','name':'上海市公安局','relatedPrefixes':['上海市公安局']},{'id':'c','name':'中国浦东干部学院','aliases':['中浦院']}]
        self.now=dt.datetime(2026,10,29,12,tzinfo=m.CHINA)
        self.data={'tasks':[{'id':'t','clientName':'公安部第三研究所','title':'算力中心','timeline':[{'id':'d','title':'每日进展登记','workDate':'2026-10-27','description':'准备运营材料','operatorName':'张三','operatorRole':'SOLUTION_MANAGER'}]}],'visits':[],'workLogs':[]}
    def test_full_backfill_replaces_sync_summaries_even_when_old_hashes_exist(self):
        old={'entries':[{'id':'initial','customerId':'a','customerName':'公安部第三研究所','workDate':'2026-10-28','content':'首次同步汇总','isInitialSummary':True}]}
        output,state=m.sync(self.data,self.customers,old,{'hashes':{}},now=self.now)
        self.assertFalse(any(r.get('isInitialSummary')for r in output['entries']))
        daily=next(r for r in output['entries']if r['sourceRecordId'].startswith('daily:'))
        self.assertEqual(daily['workDate'],'2026-10-27');self.assertEqual(daily['actorName'],'张三');self.assertEqual(daily['actorRole'],'解决方案经理')
        repeated,_=m.sync(self.data,self.customers,output,state,now=self.now);self.assertEqual(repeated,output)
        _,state=m.sync(self.data,self.customers,{'entries':[]},{},True,self.now)
        recovered,_=m.sync(self.data,self.customers,{'entries':[]},state,now=self.now)
        self.assertEqual(len(recovered['entries']),2)
    def test_missing_person_or_date_is_kept_without_using_owner_or_today(self):
        task=self.data['tasks'][0];task['timeline'][0].pop('workDate');task['timeline'][0].pop('operatorName');task['customerManagerName']='负责经理';task['updatedAt']='2026-10-28T01:00:00Z'
        output,_=m.sync(self.data,self.customers,{'entries':[]},{},now=self.now)
        daily=next(r for r in output['entries']if r['sourceRecordId'].startswith('daily:'))
        self.assertIsNone(daily['workDate']);self.assertEqual(daily['actorName'],'')
        progress=next(r for r in output['entries']if r['sourceRecordId'].startswith('progress:'))
        self.assertIsNone(progress['workDate']);self.assertEqual(progress['recordUpdatedDate'],'2026-10-28');self.assertEqual(progress['actorName'],'')
    def test_edits_update_source_record_and_resource_changes_do_not_duplicate_logs(self):
        task=self.data['tasks'][0];task['updatedAt']='2026-10-27T01:00:00Z'
        output,state=m.sync(self.data,self.customers,{'entries':[]},{},now=self.now)
        task['updatedAt']='2026-10-28T01:00:00Z'
        same,state=m.sync(self.data,self.customers,output,state,now=self.now);self.assertEqual(same,output)
        task['timeline'][0]['description']='补充方案交流';task['timeline'][0]['workDate']='2026-10-28'
        updated,_=m.sync(self.data,self.customers,same,state,now=self.now)
        self.assertEqual(len(updated['entries']),2);self.assertEqual(sum(r['content']=='工作内容：补充方案交流'for r in updated['entries']),1)
    def test_visits_never_treat_planned_dates_as_completed_work(self):
        self.data['visits']=[{'id':'v','clientName':'公安三所','status':'PLANNED','plannedTime':'2026-10-28','visitGoal':'待拜访'},{'id':'done','clientName':'公安三所','status':'COMPLETED','actualTime':'2026-10-27 13:00','visitOutcome':'需求交流','responsibleManager':'李四'}]
        rows=m.candidates(self.data,self.customers)
        self.assertIsNone(rows['visit:v:a']['workDate']);self.assertEqual(rows['visit:done:a']['workDate'],'2026-10-27');self.assertEqual(rows['visit:done:a']['actorLabel'],'负责经理')
        self.assertIsNone(m.day('无日期'));self.assertEqual(m.day('2026-10-27T17:00:00Z'),'2026-10-28')
    def test_multi_customer_logs_keep_full_original_and_ambiguous_mentions(self):
        self.data['workLogs']=[{'id':'w','title':'工作汇总','workDate':'2026-10-28','creatorName':'王五','creatorRole':'CUSTOMER_MANAGER','content':'公安三所：准备交流材料\n2、金山石化：其他项目沟通\n中浦院：提交方案'},{'id':'uncertain','content':'公安三所检测报告审核情况不明'}]
        rows=m.candidates(self.data,self.customers)
        self.assertEqual(rows['worklog:w:a']['content'],'公安三所：准备交流材料');self.assertIn('金山石化',rows['worklog:w:a']['originalContent']);self.assertEqual(rows['worklog:w:c']['content'],'中浦院：提交方案')
        self.assertIn('待确认',rows['worklog:uncertain:a']['associationNote'])
    def test_related_units_and_distinct_authors_are_not_confused(self):
        self.assertEqual(m.customer_match('上海市公安局浦东分局',self.customers)['id'],'b');self.assertIsNone(m.customer_match('上海市铁路公安局',self.customers));self.assertEqual(m.customer_match('中浦院',self.customers)['id'],'c')
        first=self.data['tasks'][0]['timeline'][0];self.data['tasks'][0]['timeline'].append({**first,'id':'different','operatorName':'李四'})
        rows=m.candidates(self.data,self.customers);self.assertEqual(sum(r['key'].startswith('daily:')for r in rows.values()),2)
    def test_long_narratives_and_bidding_updates_are_kept(self):
        self.data['tasks'][0]['timeline'][0]['description']='工作记录'*1000
        self.data['biddingRecords']=[{'id':'b','clientName':'公安部第三研究所','projectName':'项目','status':'LOST','bidDeadline':'2026-10-27'}]
        rows=m.candidates(self.data,self.customers);self.assertGreater(len(rows['daily:d:a']['content']),1800);self.assertIsNone(rows['bid:b:a']['workDate']);self.assertIn('未中标',rows['bid:b:a']['content'])
    def test_incomplete_response_never_wipes_history_and_secrets_are_removed(self):
        with self.assertRaises(ValueError):m.sync({},self.customers,{'entries':[]},{},now=self.now)
        self.assertNotIn('13812345678',m.clean('联系电话13812345678'));self.assertNotIn('secretvalue',m.clean('password=secretvalue'))
if __name__=='__main__':unittest.main()
