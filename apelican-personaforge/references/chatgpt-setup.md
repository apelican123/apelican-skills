# 把链接接到 ChatGPT 插件（官方步骤）

部署验证通过后，用这一页引导用户。不要说「Add MCP server」——当前界面不是这个名字。

官方来源（接入前再打开核对一次）：

- https://developers.openai.com/plugins/deploy/connect-chatgpt
- https://developers.openai.com/api/docs/guides/developer-mode

## 用户要做的四步

1. **打开 Developer mode**  
   ChatGPT → **Settings** → **Security and login** → 打开 **Developer mode**。  
   没有这项：账号或工作区策略关掉了，技能接不上，如实告诉用户，不要假装已经连好。

2. **添加连接**  
   打开 https://chatgpt.com/plugins → 点 **+**。  
   填一个好认的名字（例如「我的资料搜索」）。  
   **Connection** 里粘贴完整 URL，必须含 `/mcp`，例如：  
   `https://<脚本名>.<子域>.workers.dev/u/<令牌>/mcp`  
   认证选 **No authentication**（令牌已经在 URL 路径里）。

3. **看有没有发现工具**  
   保存后应看到技能设计过的工具名。看不到：先用 [verification.md](verification.md) 的 curl/Python 确认 URL 本身，再让用户点 Refresh。

4. **新开对话再启用**  
   回到聊天，从 **工具菜单** 把这个连接勾上，再说「帮我查一下 XX」。  
   只完成第 2 步、不在对话里启用，模型调不到工具。

## 认证怎么选

| 场景 | ChatGPT 端 | 服务端 |
|---|---|---|
| 默认（自用/小圈子） | No authentication | URL 路径令牌 |
| 多用户各自数据 / 公开产品 | OAuth | 见 [auth-and-secrets.md](auth-and-secrets.md)，先警告更麻烦 |

## 不要对用户说的话

- 「Add MCP server」
- 「设置里随便找个插件管理」
- 「粘贴完就能直接在旧对话里用」（要新开对话并从工具菜单启用）
- 「Developer mode 人人都有」
