独立同步接口，不使用东风平台。服务器需要能通过 HTTPS 访问 api.github.com，用户浏览器只访问网页和此接口。

部署前准备：一个可部署 Node.js 或 Docker 的独立主机、一个用于接口的 HTTPS 域名，以及仓库专用 GitHub fine-grained token（只授予 changemkl/-1- 的 Actions: Read and write）。腾讯凭据继续保存在 GitHub Secrets，接口不需要腾讯密码。

1. 将此目录放到服务器，复制 `.env.example` 为 `.env`。
2. 填入仓库 token，设置至少 12 字符的随机同步口令和至少 32 字符的会话签名密钥；签名密钥可用 `openssl rand -hex 32` 生成。`.env` 不提交 Git。
3. 在此目录执行 `docker compose up -d --build`，用 HTTPS 反向代理将接口域名转到 `127.0.0.1:8788`。容器卷保留最近 24 小时任务；单实例运行。
4. 确认接口 `/health` 返回 `{"ok":true}`，然后将 `public/sync-config.json` 中的 `apiBaseUrl` 改为实际 HTTPS 接口根地址并发布网页。

配置为空时，网站保留原入口，不会假装独立后台已部署。配置正确后，原“读取工作日志”“同步在线表格”按钮直接提交后台任务，不打开 GitHub；首次需要输入独立同步口令，浏览器只暂存一小时授权令牌。口令与 GitHub、腾讯密码无关。

接口限定两类固定任务，不允许客户端选择其他仓库、分支或 workflow。每次任务携带随机 request_id，按同一编号查询 GitHub 任务，避免把其他人的运行误认成此次同步。部署服务端并配置 GitHub token 后，才能验证真实服务器至 GitHub 的网络连通性；目前代码准备好不代表已上线该接口。
