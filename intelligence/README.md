# 客户公开信息采集与独立画像库

## 数据边界

腾讯表格只同步客户名称；保留集团编号作为稳定关联键，不再导入表中的标签、分类、等级、地区或画像。同一集团编号改名不覆盖已有画像。若没有稳定编号，使用名称作为键，改名将被视为新客户；建议保留集团编号。删除客户只停用名单，不级联删除历史资料。

画像、标签、原文摘录、来源、发布时间、采集时间、历史版本、任务状态均存储在独立 SQLite / Cloudflare D1 数据库，不放回在线表格。库表位于 schema.sql。采集器只产生待核实动态，不自动声称“痛点、决策链、可售能力、竞争对手、下一步动作”。这些字段单独保存在 profile_attributes，只接收人工维护或审核后的结果；采集任务不覆盖它们。

## 已实现与限制

- 允许列表中的 HTTPS 公开来源、robots.txt 检查、同域链接、请求超时、单页大小限制、每来源最多 3 篇、请求间隔 1 秒。
- 基于标题的确定性分类：采购、数字化、规划、人事、经营动态。不是全网搜索，也没有调用收费 AI 接口。
- 重复文档去重，内容变更保存历史版本；访问失败写入 crawl_runs，不冒充成功无记录。
- GitHub Actions 按小时执行，或在 Actions 手动运行 Collect customer intelligence 并填写集团编号。所谓实时是手动发起后待任务完成再刷新，不保证秒级或所有网站覆盖。
- Workers 仅提供公开只读查询，爬虫在 GitHub Actions 中执行，不受免费 Workers 10ms CPU 的解析限制；需要关注 Actions 自身额度。
- 仅中建八局来源已确认可以从当前环境读取；其余 4 个候选入口返回 403，默认不启用。新客户需配置并核实 sources.json 中的公开来源。没有自动猜官网。

## 本地验证

```sh
python intelligence/collector.py --sqlite /tmp/customer-intelligence.sqlite
python3 -m unittest discover -s tests -v
node --test tests/worker.test.mjs
```

本地 SQLite 仅用于开发验证，不会自动同步到云端 D1；采集数据不提交 GitHub。SQLite 本地验证和云端部署验证分别报告。

## Cloudflare 免费方案启用步骤

1. 创建 Cloudflare 免费账号；Workers & Pages → D1 创建 customer-intelligence 数据库。
2. 从数据库控制台执行 schema.sql，或在 cloudflare 目录使用 Wrangler 执行 `wrangler d1 execute customer-intelligence --remote --file=../intelligence/schema.sql`。在 wrangler.jsonc 中填写实际 database_id。
3. 创建 Worker，部署 cloudflare/worker.mjs，并将 D1 绑定命名为 DB。设置 ALLOWED_ORIGIN 为 `https://changemkl.github.io`。可从 cloudflare 目录用 `wrangler deploy` 部署；本仓库没有自动执行部署，也没有假造 database_id。
4. 在 GitHub Actions Secrets 中添加 CLOUDFLARE_ACCOUNT_ID、CLOUDFLARE_D1_DATABASE_ID、CLOUDFLARE_API_TOKEN。Token 只授予该账号需要的 D1 编辑权限，保存到 Secrets，不发聊天、不写网页。
5. 将公开 Worker 地址填写在 public/profile-config.json 的 apiBaseUrl 中，如 `https://customer-intelligence.<你的子域>.workers.dev`。这个地址是公开配置，不是密钥。
6. 在 Actions 中手动运行 Collect customer intelligence。检查任务结果及 D1 数据，再检查公开接口 `/api/profiles?id=2100199365`。
7. 计划任务需要默认分支保留 collect-intelligence.yml；该工作流会检出 customer-workspace。网页每 5 分钟查询画像 API；修改名单后也会重新查询。

保持免费套餐，超额时停止请求，不自动订购付费方案。D1 免费额度为每天读 500 万行、写 10 万行、总存储 5GB；Workers 每天 10 万次请求（以官方账户当期规则为准）。数据库保留摘录和版本、不保存大文件；长期历史需根据实际使用增加清理策略。

目前没有配置 Cloudflare 凭据或部署线上画像 API。网页会显示“画像资料待接入”，不会用本地测试数据冒充线上数据。现有腾讯客户名单同步仍独立运行。
