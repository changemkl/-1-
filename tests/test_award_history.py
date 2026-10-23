import datetime
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path('intelligence').resolve()))
from award_history import result_row,CHINA

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

if __name__=='__main__':unittest.main()
