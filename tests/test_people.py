import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path('intelligence').resolve()))
from people import parse_people, person, collect
from collector import Page

class PeopleTests(unittest.TestCase):
    def test_commission_nav_and_biography_are_not_conflated(self):
        text='机构领导_官网 机构领导 王  桢 吴 杰 机构领导 王  桢 男，汉族，1970年生。现任上海市住房和城乡建设管理委员会主任。 机构领导 吴 杰 男，汉族。现任副主任、一级巡视员。'
        rows=parse_people('commission',text)
        self.assertEqual([r['name'] for r in rows],['王桢','吴杰'])
        self.assertEqual(rows[0]['role'],'上海市住房和城乡建设管理委员会主任')
        self.assertNotIn('1970',rows[0]['quote'])
        self.assertIsNone(rows[0]['division'])

    def test_sports_split_role_and_explicit_information_division(self):
        rows=parse_people('sports','市体育局领导及工作分工 市体育局党组副书记、副局长、直属机关党委书记 陆檩 分管：科研医务、信息化、外事。 协助分管：干部工作。 市体育局党组成员、 一级巡视员、局工会主席 宋慧 分管：群众体育、体育场馆。 返回顶部')
        self.assertEqual([r['name'] for r in rows],['陆檩','宋慧'])
        self.assertTrue(rows[0]['informationResponsibility'])
        self.assertFalse(rows[1]['informationResponsibility'])
        self.assertNotIn('宋慧',rows[0]['division'])

    def test_team_preserves_multiple_people_in_one_paragraph(self):
        rows=parse_people('team','字号：[ 大 中 小 ] 党委副书记、董事、工会主席 方思忠 财务总监 熊知平 副总经理 沈健 纪委书记 刘其泉 【打印本页】 联系我们')
        self.assertEqual([r['name'] for r in rows],['方思忠','熊知平','沈健','刘其泉'])
        self.assertTrue(all(r['division'] is None for r in rows))

    def test_basin_does_not_take_activity_names_or_dates(self):
        rows=parse_people('basin','现任领导 戴甦 简介 党组成员、副局长 戴甦，男，汉族。现任水利部太湖流域管理局党组成员、副局长。 工作分工：负责人事、水利信息化、水文方面的工作。 活动 新闻领导甲 2026-10-09')
        self.assertEqual(rows[0]['name'],'戴甦')
        self.assertTrue(rows[0]['informationResponsibility'])
        self.assertNotIn('活动',rows[0]['division'])
        self.assertFalse(person('测试','局长','不再分管信息化工作。','原文')['informationResponsibility'])
        with self.assertRaises(ValueError):parse_people('basin','会议由副局长某某出席。')

    def test_changed_layout_never_becomes_a_successful_empty_list(self):
        class Reader:
            def read(self,url):
                p=Page();p.feed('<p>请登录后查看</p>');return p
        with self.assertRaises(ValueError):
            collect({'kind':'commission','url':'https://zjw.sh.gov.cn/jgld/index.html'},Reader(),'2026-10-23')

if __name__=='__main__':unittest.main()
