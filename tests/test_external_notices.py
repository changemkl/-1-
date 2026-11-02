import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'intelligence'))
from external_notices import parse_notice
class ExternalNoticeTests(unittest.TestCase):
 def parse(self,text,title='客户网络设备中标公告',name='公安部第三研究所'):
  return parse_notice(text,title,'https://www.ccgp.gov.cn/a',{'name':name},'2026-11-02')
 def test_masked_amount_not_reconstructed(self):
  r=self.parse('2026年10月27日 采购单位\n公安部第三研究所\n二、项目名称：网络设备\n供应商名称：甲公司\n中标（成交）金额：\n***\n元\n')
  self.assertNotIn('amountYuan',r['record']['awards'][0])
 def test_explicit_amount_units(self):
  r=self.parse('2026年10月27日 采购单位\n公安部第三研究所\n二、项目名称：网络设备\n供应商名称：甲公司\n中标（成交）金额：\n3967000\n.00元\n')
  self.assertEqual(r['record']['awards'][0]['amountYuan'],3967000)
 def test_wrong_buyer_rejected(self):
  self.assertIsNone(self.parse('2026年10月27日 采购单位\n上海市杨浦区城市运行管理中心\n',name='上海市城市运行管理中心'))
 def test_joint_buyer_is_explicit(self):
  self.assertIsNotNone(self.parse('2026年10月27日 采购单位\n上海外国语大学、中国建筑第八工程局有限公司\n二、项目名称：弱电工程\n供应商名称：甲公司\n',name='中国建筑第八工程局有限公司'))
 def test_expired_tender_and_corrections_excluded(self):
  body='2026年10月27日 采购单位\n公安部第三研究所\n截止时间：2026年10月30日09点00分'
  self.assertIsNone(self.parse(body,title='网络设备公开招标公告'))
  self.assertIsNone(self.parse(body,title='网络设备中标结果更正公告'))
 def test_live_tender_and_no_date_guess(self):
  body='2026年10月27日 采购单位\n公安部第三研究所\n截止时间：2026年11月12日09点00分'
  r=self.parse(body,title='网络设备竞争性磋商公告');self.assertEqual(r['record']['deadline']['value'],'2026-11-12 09:00')
  self.assertIsNone(self.parse(body.split('截止时间')[0],title='网络设备竞争性磋商公告'))
if __name__=='__main__':unittest.main()
