import datetime
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path('scripts').resolve()))
from worklogs import build_worklogs,work_date,CHINA

class WorklogTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.datetime(2026,10,26,10,30,tzinfo=CHINA)
        self.rows=[['集团编号','客户名称','客户标签','客户类别'],['1','客户甲','1390','政府'],['','客户乙','重要客户','企业']]
        self.config,self.initial,_=build_worklogs(self.rows,now=self.now)
    def test_baseline_is_frozen_and_only_new_columns_become_verbatim_logs(self):
        rows=[self.rows[0]+['2026-10-26工作日志','后续工作'],self.rows[1]+['拜访沟通需求\n准备方案','安排下次会议'],self.rows[2]+['','']]
        config,data,inventory=build_worklogs(rows,self.config,self.initial,self.now)
        self.assertEqual(config,self.config);self.assertEqual(len(data['entries']),2)
        log=next(r for r in data['entries'] if r['column']=='E')
        self.assertEqual(log['workDate'],'2026-10-26');self.assertEqual(log['content'],'拜访沟通需求\n准备方案');self.assertEqual(log['cell'],'E2')
        self.assertEqual(next(r for r in data['entries'] if r['column']=='F')['workDate'],None)
        self.assertEqual(len(inventory['logColumns']),2)
    def test_new_customer_and_fallback_ids_and_edited_deleted_logs(self):
        rows=[self.rows[0]+['10月26日'],self.rows[1]+['工作甲'],self.rows[2]+['工作乙']]
        _,first,_=build_worklogs(rows,self.config,now=self.now)
        self.assertEqual({r['customerId'] for r in first['entries']},{'1','name:客户乙'})
        later=self.now+datetime.timedelta(hours=1);rows[1][-1]='修改后的工作甲';rows[2][-1]=''
        _,second,_=build_worklogs(rows,self.config,first,later)
        self.assertEqual(len(second['entries']),1);new=second['entries'][0];old=next(r for r in first['entries'] if r['customerId']=='1')
        self.assertEqual(new['id'],old['id']);self.assertEqual(new['firstSeenAt'],old['firstSeenAt']);self.assertNotEqual(new['updatedAt'],old['updatedAt'])
    def test_row_insertion_and_reordered_named_columns_do_not_duplicate_logs(self):
        rows=[self.rows[0]+['2026-10-26'],self.rows[1]+['工作甲']]
        _,data,_=build_worklogs(rows,self.config,now=self.now)
        reordered=[['2026-10-26']+self.rows[0],['工作甲']+self.rows[1]]
        _,after,_=build_worklogs(reordered,self.config,data,self.now)
        self.assertEqual(len(after['entries']),1);self.assertEqual(after['entries'][0]['id'],data['entries'][0]['id'])
    def test_dates_do_not_use_today_or_pick_a_deadline_inside_body(self):
        self.assertEqual(work_date('工作日志','已沟通，下次会议2026-11-01',2026),(None,'unknown'))
        self.assertEqual(work_date('10.26工作日志','已沟通',2026),('2026-10-26','year-inferred'))
        self.assertEqual(work_date('2026-02-30','已沟通',2026),(None,'unknown'))
    def test_empty_new_column_is_not_reported_as_a_log_column(self):
        _,data,inventory=build_worklogs([self.rows[0]+[''],self.rows[1]+['']],self.config,now=self.now)
        self.assertEqual(data['entries'],[]);self.assertEqual(inventory['logColumns'],[])
    def test_duplicate_headers_keep_separate_records(self):
        _,data,_=build_worklogs([self.rows[0]+['10月26日','10月26日'],self.rows[1]+['上午沟通','下午跟进']],self.config,now=self.now)
        self.assertEqual(len(data['entries']),2);self.assertEqual(len({r['id'] for r in data['entries']}),2)

if __name__=='__main__':unittest.main()
