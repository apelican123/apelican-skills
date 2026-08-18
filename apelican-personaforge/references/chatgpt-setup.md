# ChatGPT 接入说明

ChatGPT 页面名称、账号权限和工作区策略会变化。执行时先查看 OpenAI 当前“Connect and test your plugin”文档；实际页面与旧截图不同，以当前页面为准。

## 默认：专属能力链接

这是私人自用的最短路径。ChatGPT 端不保存 API Key，Cloudflare 根据完整 URL 校验用户标识和随机 Token。

1. 在 ChatGPT 打开 **Settings → Security and login → Developer mode**。Developer mode 是否可见取决于账号和工作区策略。
2. 打开当前的 ChatGPT Plugins 页面，选择加号新增连接。
3. 填写普通人能看懂的名称和一句用途。
4. 选择公网 MCP URL，并粘贴完整专属链接：

   ```text
   https://<你的-worker-域名>/u/<用户名标识>/<随机Token>/mcp
   ```

5. 如果当前表单显示认证方式，选择 **无身份验证**。不要在 OpenAI/ChatGPT 端再填 API Key、Token、Bearer 或 OAuth Client Secret。
6. 创建后核对工具数量、工具描述和读写提示；先做一个真实只读调用。

这里的“无身份验证”只描述 ChatGPT 端没有单独的认证字段。Worker 仍在 Cloudflare 端验证 URL；固定 `/mcp` 不得因此匿名开放。

必须同时提示：**完整链接就是访问密钥；任何拿到它的人都可能使用对应能力。** 不要截图、公开、转发或写入日志。泄露时立即撤销该用户的 Secret 并生成新链接。

## 一人一链接和多人隔离

- 每位用户使用不同的 `userId`、随机 Token、摘要 Secret 和完整 URL。
- 用户名只做标签并附加哈希，不是密码；Token 必须独立随机生成。
- 共用 Worker 时，A 的 Token 放入 B 的路径必须返回 401/403/404。
- 如果上游数据按用户隔离，还要使用每人的上游身份/scope；入口链接不同不等于底层数据已经隔离。
- 大量用户或复杂权限改用 OAuth 2.1。

## OAuth 连接

多人产品、独立账号/scope 或公开发布使用 OAuth 2.1：

- MCP 服务器每次请求验证 access token；
- 提供 protected-resource metadata 和授权服务器 metadata；
- 支持当前 OpenAI 客户端可发现的 CIMD、DCR 或预定义客户端方式，并使用 PKCE；
- scope 与每个工具真实权限一致；
- 上游 API Key 仍只放服务器端，不填入 ChatGPT。

公开发布还需要稳定公网 HTTPS 端点、审核材料和 OpenAI plugin submission/review。私人 Developer mode 中能连接，不代表已经通过公开审核。

## OpenAI Secure MCP Tunnel

用于本机或内网的私人开发连接。按 [local-tunnel-deploy.md](local-tunnel-deploy.md) 安装、初始化和验证。Tunnel 不是 Cloudflare Tunnel，也不是公开生产端点。

## 连接失败时先分层

按顺序判断：

1. ChatGPT 是否允许 Developer mode，当前页面入口是否存在；
2. URL 是否完整、HTTPS、以 `/mcp` 结束且没有被换行截断；
3. 错用户名、错 Token、缺 Secret 是否按预期被 Cloudflare 拒绝；
4. 正确链接能否在 MCP Inspector 完成 `initialize`、`tools/list` 和只读调用；
5. 工具 schema、annotations 和认证元数据是否可序列化且与真实行为一致；
6. OAuth 401 challenge、protected-resource metadata、PKCE 和客户端注册是否可发现；
7. Tunnel 的 workspace 关联和 client 状态是否正常。

不要一上来删除连接重建。先证明错误位于 ChatGPT 页面、Cloudflare 链接校验、MCP 协议还是上游服务中的哪一层。

官方入口：

- https://developers.openai.com/plugins/deploy/connect-chatgpt
- https://developers.openai.com/plugins/build/auth
- https://developers.openai.com/plugins/deploy/app-review
