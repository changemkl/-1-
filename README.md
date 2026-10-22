# 战客一组· 三棵树经营工作台

面向客户经理的客户组织树、产业链树、产品与场景树工作台。展示腾讯文档同步的业务资料，不展示示例客户或口号。网页展示无需密钥；后台同步凭据通过 GitHub Secrets 提供。

使用 Node.js 18 或以上版本，在仓库目录运行 `npm run dev`，默认端口为 3000，可通过 `PORT` 调整。无需安装 npm 依赖。运行 `npm run check` 检查 JavaScript 语法。

开发模式会检测 HTML、CSS 和 JavaScript 文件变化，并在约一秒内自动刷新打开的页面。云端使用平台的 3000 端口预览入口访问；本机运行时访问 localhost:3000。`npm start` 启动不含自动刷新的普通服务。

采用蓝色数据总览、横向导航和客户卡片布局，支持三视图切换、板块和等级组合筛选、实时搜索、画像展开及筛选结果 JSON 导出。统计值根据已接入的业务资料计算；无数据栏目显示为空。页面使用系统字体，不需要访问外部字体服务。

## 腾讯文档自动同步

官方接口：`/openapi/drive/v2/util/converter` 转换链接 ID；`/openapi/spreadsheet/v3/files/{fileId}/{sheetId}/{range}` 读取内容。数据源固定为用户提供的公开表格 `DTEhRanNnS3dJV2hm`，子表 `BB08J2`，按子表实际尺寸读取，最多 6000 行、200 列（超过时任务失败并保留旧文件）。首次调用需要文档 ID 转换权限，读取需要 `scope.sheet.readonly` 或对应读写权限。

在 GitHub Actions Secrets 中保存 `TENCENT_DOCS_CLIENT_ID`、`TENCENT_DOCS_ACCESS_TOKEN`、`TENCENT_DOCS_OPEN_ID`。不把凭据保存进代码、JSON 或日志。Token 到期后更新 Secret；当前没有配置自动续期。

建议 Settings → Pages → Source 选择 **GitHub Actions**；首次部署已在当前设置下验证成功。工作流 `Sync Tencent spreadsheet` 每小时第 17 分钟运行（GitHub 可能延迟），也可以在 Actions 中手动 Run workflow。计划任务读取默认分支的工作流，所以默认分支也需要保留此工作流文件；任务固定检出并更新 `customer-workspace`。成功读取后提交公开数据 `public/tencent-data.json`，并使用 Pages 官方部署步骤发布根入口和 `public` 子目录，避免机器人提交不触发 Pages 构建的问题。没有数据变化时不重复提交，但仍部署最新页面。首次同步必须成功后才能看到真实数据。

网页每分钟检查已经发布的 JSON；这不会消耗腾讯 API 额度。腾讯 API 调用由工作流产生，每次需要多页时调用数会增加；不要将 20000 次试用额度理解为每月重置。失败时保留上一次成功数据，并在 Actions 中显示失败，页面显示的是最近数据变更时间，不声称后台最近检查成功。

原表内容通过文本方式展示，不识别的表头也可查看。若表头包含“名称／客户名称／单位名称／企业名称／客户／单位／场景名称／伙伴名称”，自动生成卡片；可选列为“所属树、全称、地址、板块、等级、描述、能力、关联机会、已画像”。本表的“客户类别”用作板块，“客户标签”用作标签，“一级属地 / 二级属地”用作区域，展开画像保留全部原始列。所属树应填写三个栏目全称，不填写此列则默认作为客户组织树。无数据源的栏目显示为空；未提供的统计不虚构，未填写等级显示待核实。表格数据将作为公开 JSON 发布，请只维护允许公开的内容。

验证：`npm run check`；`python3 -m unittest discover -s tests -v`。这些验证不等于真实 API 和线上部署成功，需要查看首次 Actions 结果。
