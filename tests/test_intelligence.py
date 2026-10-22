import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path('intelligence').resolve()))
from collector import registry,sync_customers,save_document,collect_source,Page,validate_url,page_title,matches_customer,canonical_url,SourceHTML
from store import Store

class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(self.temp.name+'/db.sqlite')
        self.store.initialize()
        sync_customers(self.store,{'1':'测试客户'})
    def tearDown(self):
        self.store.local.close();self.temp.cleanup()
    def test_names_are_separate_from_profiles(self):
        self.store.query('INSERT INTO profile_attributes VALUES(?,?,?,?,?)',['1','下一步动作','预约需求交流','manual','2026-10-22'])
        sync_customers(self.store,{'1':'更新名称'})
        self.assertEqual(self.store.query('SELECT name FROM customers')[0]['name'],'更新名称')
        self.assertEqual(self.store.query('SELECT value FROM profile_attributes')[0]['value'],'预约需求交流')
        sync_customers(self.store,{'2':'另一家客户'})
        self.assertEqual(self.store.query('SELECT active FROM customers WHERE id=?',['1'])[0]['active'],0)
        self.assertEqual(len(self.store.query('SELECT * FROM profile_attributes')),1)
    def test_evidence_deduplication_and_versions(self):
        args=(self.store,'1','https://example.org/news','数字化采购公告')
        save_document(*args,'原文摘录',None)
        save_document(*args,'原文摘录',None)
        self.assertEqual(len(self.store.query('SELECT * FROM documents')),1)
        self.assertEqual(len(self.store.query('SELECT * FROM document_versions')),1)
        self.assertEqual(len(self.store.query('SELECT * FROM signals')),2)
        self.assertEqual({r['status'] for r in self.store.query('SELECT status FROM signals')},{'pending'})
        save_document(*args,'更新原文',None)
        self.assertEqual(len(self.store.query('SELECT * FROM document_versions')),2)
    def test_blocked_source_is_a_failure_not_empty_success(self):
        with patch('collector.robot_policy',side_effect=PermissionError('robots blocked')):
            result=collect_source(self.store,{'customer_id':'1','url':'https://example.org/','hosts':['example.org'],'aliases':['测试客户']})
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(len(self.store.query('SELECT * FROM documents')),0)
        self.assertEqual(self.store.query('SELECT status FROM crawl_runs')[0]['status'],'blocked')
    def test_article_metadata_beats_generic_site_title(self):
        page=Page();page.feed('<title>信息详情</title><meta name="ArticleTitle" content="客户甲数字化采购公告"><meta name="PubDate" content="2026-10-22"><h1>客户甲数字化采购公告</h1><p>客户甲发布数字化采购公告，内容必须来自正文。</p>')
        self.assertEqual(page_title(page),'客户甲数字化采购公告')
        self.assertEqual(page.published,'2026-10-22')
        self.assertTrue(matches_customer(page,{'aliases':['客户甲']}))
        # A navigation-only alias, without a matching article title or paragraph, is rejected.
        unrelated=Page();unrelated.feed('<title>其他客户消息</title><nav>客户甲</nav><p>这段正文只描述另一家公司开展的业务，不涉及当前目标单位。</p>')
        self.assertFalse(matches_customer(unrelated,{'aliases':['客户甲']}))
        self.assertEqual(canonical_url('https://example.org/a?utm_source=x&id=1#top'),'https://example.org/a?id=1')

    def test_section_discovery_and_customer_overview(self):
        source={'customer_id':'1','url':'https://example.org/','hosts':['example.org'],'aliases':['测试客户'],'discover_profiles':True,'max_list_pages':1}
        pages={
          'https://example.org/':'<title>测试客户</title><a href="/about/">公司简介</a><a href="/news/">新闻中心</a>',
          'https://example.org/news/':'<title>测试客户新闻</title><a href="/article.html">测试客户数字化采购公告</a><a href="/other.html">另一家公司的项目公告</a>',
          'https://example.org/about/':'<title>测试客户公司简介</title><p>测试客户是一家公开登记的企业。其主营业务及组织职责由该官网公开介绍，本段只是用于验证采集器识别机构概况和保存原文证据。</p>',
          'https://example.org/article.html':'<title>信息详情</title><meta name="ArticleTitle" content="测试客户数字化采购公告"><p>测试客户公开发布数字化采购公告，本段业务资料明确与测试客户有关，来源链接和采集时间应当一起保留，且不自动推断客户痛点。</p>',
          'https://example.org/other.html':'<title>另一家公司公告</title><p>另一家公司与目标客户无关，不能仅因同一页面栏目出现就关联到当前客户。正文没有任何目标名称，不应写入该客户的公开动态。</p>'}
        policy=type('Policy',(),{'can_fetch':lambda *args:True})()
        with patch('collector.robot_policy',return_value=policy),patch('collector.download',side_effect=lambda u,h:pages[u]),patch('collector.time.sleep'):
            result=collect_source(self.store,source)
        self.assertEqual(result['documents_found'],2)
        categories={r['category'] for r in self.store.query('SELECT category FROM signals')}
        self.assertIn('客户概况',categories);self.assertIn('数字化动态',categories)
        self.assertEqual(len(self.store.query('SELECT * FROM documents')),2)

    def test_partial_listing_is_discovery_only(self):
        source={'customer_id':'1','url':'https://example.org/','hosts':['example.org'],'aliases':['测试客户']}
        listing=SourceHTML('<title>测试客户</title><a href="/partial.html">测试客户数字化项目公告</a><a href="/complete.html">测试客户采购公告</a>');listing.partial=True
        partial=SourceHTML('<title>测试客户数字化项目公告</title><p>测试客户的这篇文章在传输中断后只收到一部分，不能作为完整证据存储，即使已经包含足够多的字符和目标名称也应跳过。</p>');partial.partial=True
        complete='<title>测试客户采购公告</title><p>测试客户发布了一篇已完整读取的采购公告，应被保存并在页面显示来源，同时不能因为上一条响应中断就放弃整个来源的其他正常文章。</p>'
        pages={'https://example.org/':listing,'https://example.org/partial.html':partial,'https://example.org/complete.html':complete}
        policy=type('Policy',(),{'can_fetch':lambda *args:True})()
        with patch('collector.robot_policy',return_value=policy),patch('collector.download',side_effect=lambda u,h:pages[u]),patch('collector.time.sleep'):
            result=collect_source(self.store,source)
        self.assertEqual(result['documents_found'],1)
        self.assertEqual(self.store.query('SELECT url FROM documents')[0]['url'],'https://example.org/complete.html')

    def test_identity_and_source_validation(self):
        self.assertEqual(registry([['集团编号','客户名称','客户标签'],['1','测试客户','不要导入标签']]),{'1':'测试客户'})
        with self.assertRaises(ValueError):registry([['客户名称']])
        with self.assertRaises(ValueError):registry([['集团编号','客户名称'],['1','甲'],['1','乙']])
        for url in ['http://example.org','https://evil.example','https://example.org:8443','https://user:pass@example.org']:
            with self.assertRaises(ValueError):validate_url(url,['example.org'])
        p=Page();p.feed('<title>测试</title><script>伪造信息</script><a href="/a">采购公告</a>')
        self.assertNotIn('伪造信息',p.parts)
        self.assertEqual(p.links,[('/a','采购公告')])

if __name__=='__main__':unittest.main()
