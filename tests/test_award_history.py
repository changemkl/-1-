import datetime
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path('intelligence').resolve()))
from award_history import result_row,CHINA,parse_award_detail

class AwardHistoryTests(unittest.TestCase):
    def row(self,**kwargs):
        return {'title':'客户甲信息化项目的中标（成交）结果公告','purchaseName':'客户甲','articleId':'a+b=','parentId':1,'publishDate':datetime.datetime(2026,10,1,tzinfo=CHINA).timestamp()*1000,**kwargs}
    def test_public_result_date_and_original_link(self):
        row=result_row(self.row(),'客户甲',datetime.date(2026,10,23))
        self.assertEqual(row['date'],'2026-10-01')
        self.assertIn('articleId=a%2Bb%3D',row['url'])
        self.assertEqual(row['dateLabel'],'结果公告日期')
    def test_buyer_must_match_and_subordinate_buyer_is_preserved(self):
        self.assertIsNone(result_row(self.row(purchaseName='其他客户'),'客户甲',datetime.date(2026,10,23)))
        self.assertIsNone(result_row(self.row(purchaseName=None),'客户甲',datetime.date(2026,10,23)))
        self.assertEqual(result_row(self.row(purchaseName='客户甲事务中心'),'客户甲',datetime.date(2026,10,23))['buyer'],'客户甲事务中心')
    def test_only_results_not_future_or_cancelled_or_shop_purchases(self):
        for title in ['信息化采购意向','信息化公开招标公告','信息化项目中标结果更正公告','信息化项目取消中标结果公告','关于打印机的网上超市采购项目成交公告','信息化合同公告']:
            self.assertIsNone(result_row(self.row(title=title),'客户甲',datetime.date(2026,10,23)),title)
        self.assertIsNone(result_row(self.row(invalid=1),'客户甲',datetime.date(2026,10,23)))
        self.assertIsNone(result_row(self.row(),'客户甲',datetime.date(2026,9,1)))

class AwardDetailsTests(unittest.TestCase):
    def test_extract_lots_and_supplier_rowspans_without_agent_or_bidder_names(self):
        body='<p>代理机构：代理公司</p><table><tr><td>序号</td><td>标项名称</td><td>中标供应商名称</td></tr><tr><td>1</td><td>网络服务</td><td rowspan="2">甲公司</td></tr><tr><td>2</td><td>安全服务</td></tr></table><table><tr><th>标项名称</th><th>供应商名称</th><th>候选排名</th></tr><tr><td>服务</td><td>乙公司</td><td>1</td></tr></table>'
        data=parse_award_detail({'projectName':'项目甲','content':body})
        self.assertEqual(data['projectName'],'项目甲')
        self.assertEqual([r['lotName'] for r in data['awards']],['网络服务','安全服务'])
        self.assertEqual([r['suppliers'] for r in data['awards']],[['甲公司'],['甲公司']])
    def test_missing_or_non_result_tables_do_not_infer_suppliers(self):
        data=parse_award_detail({'content':'<p>推荐甲公司。代理：乙公司</p><table><tr><td>标的名称</td><td>供应商地址</td></tr><tr><td>服务</td><td>上海</td></tr></table>'})
        self.assertEqual(data['awards'],[])

if __name__=='__main__':unittest.main()
