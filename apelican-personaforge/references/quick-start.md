# 快速开始（小白：注册 Cloudflare → 拿到 ChatGPT 链接）

你只做 Cloudflare 账号这件事。部署和生成链接由 AI 完成。

## 先确认

跟你说话的 AI 必须能写文件、能访问互联网（Hermes / Codex / Claude Code / Cursor）。把这个技能丢进纯网页 ChatGPT，它没法替你部署。

## 你做的事

1. 打开 https://dash.cloudflare.com 注册或登录。
2. 进入 Workers，按提示启用 `workers.dev` 子域（第一次必须做）。
3. 头像 → My Profile → API Tokens → Create Token → Custom：
   - `Account` → `Workers Scripts` → `Edit`
4. 复制 API Token 和 Account ID。
5. 准备要接的接口：API 或 MCP 的地址和密钥。

然后对 AI 说：

```text
帮我铸成 ChatGPT 插件：
- 功能：<一句话>
- 接口：<地址>
- 密钥：<密钥>
- Cloudflare Account ID：<ID>
- Cloudflare API Token：<Token>
- 只读，自用
```

## AI 做的事（你不用懂）

生成 Worker → 上传到你的 Cloudflare → 写入密钥 → **打开这个 Worker 的 workers.dev** → 验证协议 → 给你一条：

`https://<脚本名>.<子域>.workers.dev/u/<令牌>/mcp`

## 你把链接接到 ChatGPT

1. ChatGPT → Settings → Security and login → 打开 **Developer mode**
2. 打开 https://chatgpt.com/plugins → 点 **+**
3. 粘贴完整链接（含 `/mcp`），认证选 **No authentication**
4. 新开对话，从工具菜单启用这个连接，再说「帮我查一下 XX」

详细点按点见 [chatgpt-setup.md](chatgpt-setup.md)。

## 卡住了

- 部署报错：把报错原文发回 AI，对照 [troubleshooting.md](troubleshooting.md)
- ChatGPT 连不上：先按 [verification.md](verification.md) 测 URL
- 链接泄露：让 AI 重写令牌，旧链接立刻失效
