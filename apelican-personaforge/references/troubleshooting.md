# 故障排查

## Cloudflare 准备

| 现象 | 原因 | 处理 |
|---|---|---|
| GET `/workers/subdomain` 失败 | 未启用账号级 workers.dev | 控制台 Workers 里首启子域 |
| 上传 9109 / 无权限 | Token 不是 Workers Scripts Edit/Write，或绑错账号 | 重建 Token，只勾这一项 |
| `main_module name is not present` | MIME 不是 `application/javascript+module`，或 part 名 ≠ metadata.main_module | 用 cloudflare-deploy.md 的 Python 上传 |
| 上传成功但打开 URL 404 | 没调用脚本级 subdomain enable | `POST .../scripts/{name}/subdomain {"enabled":true}` |
| PowerShell 报重定向 / 文件找不到 | 用了 `metadata=<file>` | 改用 Python，不要 curl `-F <` |

## 协议层（URL 已能打开）

| 现象 | 原因 | 处理 |
|---|---|---|
| 正确 URL 也 401 | LINK_TOKEN Secret 和路径不是同一段明文，或有换行 | 重写 Secret，确认无空格 |
| ChatGPT 添加失败，curl initialize 却成功 | GET 返回了 200 文本，或 notification 不是 202 | 确认模板是 4.0.1：GET 405、通知 202 |
| initialize 后客户端断开 | 写死了旧 protocolVersion | 回显 2025-03-26 或 2025-06-18 |
| tools/list 只有示例 search_documents | 没改 REST_TOOLS | 换成用户真实接口再部署 |

## ChatGPT 接入

| 现象 | 原因 | 处理 |
|---|---|---|
| 找不到 Add MCP server | 界面不是这个名字 | 按 chatgpt-setup.md：Developer mode → chatgpt.com/plugins → + |
| 没有 Developer mode | 账号/工作区策略关闭 | 如实告知，不能假装接好 |
| 添加成功但对话里不调工具 | 没在新对话的工具菜单启用 | 新开对话再勾选 |
| 要求选认证 | 正常 | 默认 No authentication |

## 轮换

重生成 `token_hex(32)` → 覆盖 `LINK_TOKEN` → 旧链接 401。上游密钥泄露则同时在上游后台轮换。Cloudflare Token 用完即删。
