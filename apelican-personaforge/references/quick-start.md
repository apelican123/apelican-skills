# 快速开始（0 到链接的最短路径）

这条路径预计 10 分钟内走完。你在对话里把它当指令念给 AI 即可。

## 你（用户）要做的事

1. 打开 https://dash.cloudflare.com 注册或登录；首次用 Workers 的话，进入 Workers & Pages 按提示启用 `workers.dev` 子域；
2. My Profile → API Tokens → Create Token → 自定义：权限只勾 `Workers Scripts` → `Edit`，复制 Token；
3. 复制 Account ID（dashboard 首页右侧）；
4. 准备上游接口信息：地址 + 密钥（或 MCP 地址 + 密钥）。

## 然后对 AI 说

```text
帮我把这个 API 铸造成 ChatGPT 插件：
- 功能：<一句话说明要做什么>
- 接口：<地址>
- 密钥：<密钥>
- 我的 Cloudflare Account ID：<ID>
- 我的 Cloudflare API Token：<Token>
- 只有只读查询，自用
```

或者更简单：

```text
铸一个 ChatGPT 插件，接我这两个 MCP：<MCP1 地址+密钥>、<MCP2 地址+密钥>，自用。Cloudflare 的 Token 和 Account ID 我已经准备好了：<粘贴>
```

## AI 会完成的步骤（你不需要懂）

1. 自动设计工具面（把接口整理成 ChatGPT 好选的工具）；
2. 生成零依赖 Worker 代码；
3. 查询你的 workers.dev 子域 → 上传脚本 → 写入密钥（上游 Key、路径令牌）；
4. 拼出链接 `https://<脚本名>.<你的用户名>.workers.dev/u/<令牌>/mcp`；
5. 验证：错误令牌 401、initialize、tools/list、一次只读调用（征得你同意后）；
6. 交付链接 + ChatGPT 配置步骤。

## 你在 ChatGPT 里做的事

1. 打开 ChatGPT → 设置或插件管理 → Add MCP server；
2. 粘贴链接（整条，含 `/u/` 那段）；
3. 认证选 **No authentication**；
4. 回到对话，用自然语言试试：「帮我查一下 XX」。

## 如果卡住

- 部署报错 → 把报错原文发给 AI，对照 [troubleshooting.md](troubleshooting.md)；
- ChatGPT 连接不上 → 先用 [verification.md](verification.md) 的 curl 命令确认链接本身正常；
- 链接泄露或想作废 → 让 AI 重新生成令牌，旧链接立即失效。