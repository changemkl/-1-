独立同步接口，不使用东风平台。服务器需要能通过 HTTPS 访问 api.github.com，用户浏览器只访问网页和此接口。

部署前准备：一个可部署 Node.js 或 Docker 的独立主机、一个用于接口的 HTTPS 域名，以及仓库专用 GitHub fine-grained token（只授予 changemkl/-1- 的 Actions: Read and write）。腾讯凭据继续保存在 GitHub Secrets，接口不需要腾讯密码。

1. 将此目录放到服务器，复制 `.env.example` 为 `.env`。
2. 填入仓库 token，设置至少 12 字符的随机同步口令和至少 32 字符的会话签名密钥；签名密钥可用 `openssl rand -hex 32` 生成。`.env` 不提交 Git。
3. 在此目录执行 `docker compose up -d --build`，用 HTTPS 反向代理将接口域名转到 `127.0.0.1:8788`。容器卷保留最近 24 小时任务；单实例运行。
4. 确认接口 `/health` 返回 `{"ok":true}`，然后将 `public/sync-config.json` 中的 `apiBaseUrl` 改为实际 HTTPS 接口根地址并发布网页。

配置为空时，网站保留原入口，不会假装独立后台已部署。配置正确后，原“读取工作日志”“同步在线表格”按钮直接提交后台任务，不打开 GitHub；首次需要输入独立同步口令，浏览器只暂存一小时授权令牌。口令与 GitHub、腾讯密码无关。

接口限定两类固定任务，不允许客户端选择其他仓库、分支或 workflow。每次任务携带随机 request_id，按同一编号查询 GitHub 任务，避免把其他人的运行误认成此次同步。部署服务端并配置 GitHub token 后，才能验证真实服务器至 GitHub 的网络连通性；目前代码准备好不代表已上线该接口。

人工录入共享保存复用本服务的访问码和会话认证。新增的 SQLite 数据库位于 `DATA_DIR/manual.sqlite`（Docker 下为 `/data/manual.sqlite`），重启后仍保留；备份时连同 SQLite 的 WAL 文件一致备份，或停止服务后复制数据库。重新构建 Docker 镜像会包含 `manual-store.mjs`。接口：认证后 `GET /api/manual-records`、`POST /api/manual-records`、`DELETE /api/manual-records/:id`，编辑/删除必须带当前 revision，冲突返回409；单条记录客户编号、名称及类型不可改。访问码为团队共享写入权限，当前没有逐人账号与权限区分。

部署后把 `public/manual-config.json` 的 `apiBaseUrl` 配成该服务 HTTPS 地址，页面“录入信息”中输入访问码连接。当前默认地址为空：人工资料只存在当前浏览器的 localStorage，与自动同步完全分开，不能视作跨设备共享。配置共享服务后不自动上传此前本机资料，避免未确认的内部记录外传。人工人员、项目与日志不会由腾讯、东风或公开网页采集任务覆盖。共享数据库内容仅通过认证接口读取，不写入公开 GitHub JSON。

人工工作日志支持可选的 `projectId`、`projectName`、`projectType` 字段。页面只提供关联项目选择，类型由已选项目自动带入；不选项目的日志保留在客户日常工作／待关联记录。
