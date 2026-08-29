# 历史踩坑

## 把 ChatGPT 步骤写成「Add MCP server」

官方当前是：Settings → Security and login → Developer mode → https://chatgpt.com/plugins 点 + → 对话里从工具菜单启用。写错按钮名，小白接不上。

## metadata 里写 `workers_dev: true`

Multipart metadata 官方字段没有这个键。必须 `POST /accounts/{id}/workers/scripts/{name}/subdomain` `{"enabled": true}`，否则上传成功但没有公开 URL。

## 模块 MIME 用 `application/javascript`

ES module Worker 要 `application/javascript+module`，否则常见 `main_module name is not present`。

## PowerShell 的 `metadata=<file>`

`<` 会被当成重定向。铸造用 Python urllib 组 multipart，不要把 curl 丢给 Windows 小白。

## GET `/mcp` 返回 200 文本

规范：不提供 SSE 就返回 **405**。返回 `MCP endpoint ready` 会让 ChatGPT 探测失败。curl 自检仍可能绿。

## 通知返回 JSON-RPC 200

`notifications/initialized` 必须 **202 空 body**。

## initialize 写死 `2025-03-26`

客户端常发 `2025-06-18`。应回显双方都支持的版本。

## Secret 存哈希、URL 放明文

比较对不上，正确链接 401。LINK_TOKEN 两端用同一段 `token_hex(32)`。

## 默认推 OAuth

自用场景成本高于收益。默认 noauth + 路径令牌。

## 让用户装 wrangler

公开用户装不了开发环境。用 Cloudflare REST + Python。

## 模板留着 `api.example.com`

AI 忘了改配置区，用户连上后一查就失败。生成前必须换成用户真实接口。

## 纯网页 ChatGPT 跑铸造

没有终端就调不了 Cloudflare API。技能必须先说明运行前提。

## 把连接成功写成全部通过

ChatGPT 发现工具 ≠ 真实调用成功。分层记。

## 忘记首启账号级 workers.dev 子域

`GET /workers/subdomain` 失败时停下来让用户去控制台启用，不要继续上传。
