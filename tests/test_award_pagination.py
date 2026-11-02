import sys,unittest,datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'intelligence'))
from award_history import collect
class PaginationTests(unittest.TestCase):
 def test_deeper_customer_search_finds_business_award_after_office_supplies(self):
  now=datetime.datetime(2026,11,2,tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
  def response(path,policy,payload):
   page=payload['pageNo'];item={'title':'交易平台升级的中标结果公告' if page==5 else '关于扫把的网上超市采购项目成交公告','purchaseName':'上海市房地产交易中心','publishDate':int(now.timestamp()*1000),'articleId':str(page),'parentId':137027}
   return {'data':[item]*15,'total':75}
  with patch('award_history.request_json',side_effect=response),patch('award_history.time.sleep'):
   rows,coverage=collect('上海市房地产交易中心',None,now);self.assertEqual(len(rows),0);self.assertTrue(coverage['truncated'])
   rows,coverage=collect('上海市房地产交易中心',None,now,page_limit=8);self.assertTrue(rows);self.assertFalse(coverage['truncated']);self.assertTrue(all('网上超市' not in r['title'] for r in rows))
if __name__=='__main__':unittest.main()
