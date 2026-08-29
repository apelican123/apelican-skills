# Cloudflare 部署手册（全自动铸造）

目标：不依赖本机安装 wrangler / Node.js，只通过 Cloudflare Workers API 完成「上传脚本 → 写入 Secret → 启用 workers.dev → 组装链接」。

> 注意：本手册给出的 API 形态以 2026-08 为准。实施前务必对照 [official-sources.md](official-sources.md) 中 Cloudflare 开发者文档的最新示例核对端点、请求体字段名，官方契约优先。

## 一、准备 Cloudflare（用户手动，2 分钟）

这些步骤必须由用户本人完成，技能负责引导：

1. 打开 https://dash.cloudflare.com 注册或登录；
2. 首次使用 Workers：进入 Workers & Pages → 按提示启用一个 `workers.dev` 子域（形如 `<你的用户名>.workers.dev`）。没有这一步，后续部署无法生成公开 URL；
3. 创建 API Token：右上角 My Profile → API Tokens → Create Token → 选 Custom token：
   - Permissions：`Workers Scripts` → `Edit`（只给这一个权限，不要给 Account 全部权限）；
   - Account Resources：选择要使用的账号；
4. 复制两样东西给技能：
   - **Account ID**：dashboard 首页右侧可复制；
   - **API Token**：创建时只显示一次，复制后妥善保存。

安全提示：该 Token 只用于本次部署，交付链接后建议在 Cloudflare 后台删除（My Profile → API Tokens → Delete）。技能不会保存、不会回显你的 Token。

## 二、启动命令（bash / PowerShell）

把 Token 放进环境变量，避免出现在终端历史里：

```bash
# bash（macOS / Linux）
export CF_API_TOKEN="<你的-api-token>"
export CF_ACCOUNT_ID="<你的-account-id>"
```

```powershell
# PowerShell（Windows）
$env:CF_API_TOKEN = "<你的-api-token>"
$env:CF_ACCOUNT_ID = "<你的-account-id>"
```

## 三、查询 workers.dev 子域

`<你的脚本名>` 用工作流第 4 步生成的脚本名替换（小写字母、数字、连字符，不要下划线）。

```bash
# bash
curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/workers/subdomain" \
  -H "Authorization: Bearer $CF_API_TOKEN"
```

```powershell
# PowerShell
curl.exe -s -X GET "https://api.cloudflare.com/client/v4/accounts/$env:CF_ACCOUNT_ID/workers/subdomain" -H "Authorization: Bearer $env:CF_API_TOKEN"
```

响应示例（`success: true` 时）：

```json
{ "success": true, "result": { "subdomain": "<你的用户名>" } }
```

- 若 `success: false` 或提示 subdomain 不存在：用户尚未首启 workers.dev，回去完成「准备 Cloudflare」第 2 步；
- 记录 `subdomain` 值，最终 URL 为 `https://<脚本名>.<subdomain>.workers.dev`。

## 四、上传 Worker 脚本

在存放 `worker.js` 与 `metadata.json` 的目录执行。

`metadata.json` 内容（`main_module` 必须与脚本文件名一致）：

```json
{
  "main_module": "worker.js",
  "workers_dev": true,
  "compatibility_date": "2026-08-01"
}
```

上传：

```bash
# bash
curl -s -X PUT "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/workers/scripts/<你的脚本名>" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -F "metadata=<metadata.json>;type=application/json" \
  -F "worker.js=@worker.js;type=application/javascript"
```

```powershell
# PowerShell
curl.exe -s -X PUT "https://api.cloudflare.com/client/v4/accounts/$env:CF_ACCOUNT_ID/workers/scripts/<你的脚本名>" -H "Authorization: Bearer $env:CF_API_TOKEN" -F "metadata=<metadata.json>;type=application/json" -F "worker.js=@worker.js;type=application/javascript"
```

- 返回 `success: true` 即上传成功；`errors` 字段会给出具体失败原因（权限不足、语法错误、模块名不符等），对照 [troubleshooting.md](troubleshooting.md)；
- 脚本名要全局唯一（官方不保证，但跨账号也可能冲突，撞名时换一个再传）。

## 五、写入 Secret

每个密钥一条记录，名称和值按 [templates.md](templates.md) 的约定：`UPSTREAM_KEY`（上游 API Key）、`LINK_TOKEN`（路径令牌哈希）等。

```bash
# bash：写入一个名为 UPSTREAM_KEY 的 Secret
curl -s -X PUT "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/workers/scripts/<你的脚本名>/secrets" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "UPSTREAM_KEY", "text": "<上游密钥值>", "type": "secret_text"}'
```

```powershell
# PowerShell
curl.exe -s -X PUT "https://api.cloudflare.com/client/v4/accounts/$env:CF_ACCOUNT_ID/workers/scripts/<你的脚本名>/secrets" -H "Authorization: Bearer $env:CF_API_TOKEN" -H "Content-Type: application/json" -d '{"name": "UPSTREAM_KEY", "text": "<上游密钥值>", "type": "secret_text"}'
```

要点：

- 密钥值只出现在请求体 JSON 中，不出现在 URL、命令参数、shell 历史或日志；
- 每个需要的密钥（上游 Key、路径令牌、可能的下游 MCP Token）都要单独写一次；
- 写入后可通过 `GET .../secrets` 确认存在，但响应不回传明文值。

## 六、组装与交付链接

```text
https://<脚本名>.<subdomain>.workers.dev/u/<路径令牌>/mcp
```

- `<路径令牌>` 是技能生成的 256-bit 随机值（至少 32 字节），ChatGPT 端选 No authentication 时也随 URL 路径携带，服务端据此校验；
- 该 URL 即凭据：只放进对话/剪贴板，不写入源码、Git、日志、截图或审计输出；
- 需要作废时：重新生成令牌并覆盖 `LINK_TOKEN` Secret，旧链接立即失效。

## 七、环境变量表（部署阶段用）

| 变量 | 用途 | 获取方式 |
|---|---|---|
| `CF_API_TOKEN` | 调用 Cloudflare Workers API 的认证 | Cloudflare dashboard → My Profile → API Tokens（仅 Workers Scripts: Edit） |
| `CF_ACCOUNT_ID` | 指定部署到哪个账号 | Cloudflare dashboard 首页右侧 |
| `UPSTREAM_KEY` | 上游 API Key / Bearer | 用户上游服务后台 |
| `LINK_TOKEN` | 路径令牌（技能生成） | 技能生成，写入 Worker Secret 并拼进 URL |

以上变量在部署结束后都不应保留在终端环境或任何文件中；`UPSTREAM_KEY`、`LINK_TOKEN` 的正式存储位置是 Cloudflare Worker Secret。