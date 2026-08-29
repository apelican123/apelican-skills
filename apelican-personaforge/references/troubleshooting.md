# 故障排查

铸造模式的报错绝大多数发生在这几层，按层定位。

## Cloudflare 准备阶段

| 现象 | 原因 | 处理 |
|---|---|---|
| 查询 subdomain 返回 `success: false` | 从未启用 workers.dev 子域 | 回到 dashboard 的 Workers & Pages 首启子域后再试 |
| API Token 无权限（上传返回 9109 之类错误） | Token 权限不是 Workers Scripts: Edit，或绑错了账号 | 重新创建 Token，只勾 Workers Scripts Edit；确认 Account 是同一 ID |
| 上传返回 `script exceeds size limit` | Worker 代码过大或意外打包了依赖 | 本技能模板是零依赖单文件（几 KB）；出现此错说明模板被改大，检查是否误加 npm 产物 |
| 上传返回 `syntax error` | worker.js 有语法错误 | 对照 [templates.md](templates.md) 模板逐行检查；重点看 `REST_TOOLS` 的引号与逗号 |

## 部署后传输层（curl 能到、协议不对）

| 现象 | 原因 | 处理 |
|---|---|---|
| 错误令牌返回 401（符合预期）但正确令牌也 401 | `LINK_TOKEN` Secret 没写、写错、或路径拼写不一致 | `GET .../secrets` 确认存在；确认 URL 中 `/u/<令牌>/mcp` 与 Secret 完全一致（令牌无多余空格/换行） |
| initialize 返回 `method not supported` | POST body 的 `jsonrpc` 或 `method` 字段名拼错 | 按 [verification.md](verification.md) 的请求体原样核对 |
| 返回 415 content-type | 请求头没带 `Content-Type: application/json` | ChatGPT 端偶发，检查自定义客户端；浏览器/curl 手动加头 |
| 返回 405 | 用了 GET（除健康检查外只接受 POST） | 改用 POST |

## 上游连通层（协议对、调用失败）

| 现象 | 原因 | 处理 |
|---|---|---|
| tools/call 返回上游 401/403 | `UPSTREAM_KEY` 未写、写错、或上游要求别的头 | 确认 Secret 写入；模板默认加 `Authorization: Bearer`，上游若是 `X-API-Key` 风格需在 `REST_TOOLS` 的 `headers` 或 MCP 的 `authHeader` 里显式配置 |
| tools/list 只返回 REST 工具、上游 MCP 工具缺失 | MCP 上游不可达或 tools/list 失败 | 先单独 curl 上游 MCP 确认存活；模板对该错误保持静默，属故障隔离设计 |
| 上游返回超大响应 | 结果被截断到 8000 字符 | 属设计行为；若业务需要更多，应让上游支持分页并做成 `page` 参数 |
| ChatGPT 能发现工具但调用一直失败 | 上游 CORS/网络/认证三选一 | 用 verification.md 的 curl 直连复现；curl 通而 ChatGPT 不通时查上游是否限流同 IP |

## ChatGPT 接入层

| 现象 | 原因 | 处理 |
|---|---|---|
| 添加 MCP 时「验证失败」「无法连接」 | 链接末尾多了/少了路径；或令牌 Secret 没生效 | 把链接完整粘贴（含 `/u/<令牌>/mcp`），重新检查 Secret |
| 添加后看不到工具 | ChatGPT 端缓存 | 断开重连；仍不行用 curl 直连 tools/list 确认 URL 本身正常 |
| 端上要求选认证方式 | 正常 | 默认路径选 **No authentication**（令牌在 URL 里）；如 ChatGPT 界面提供填写 Bearer 的入口，两种填法都可用 |
| OAuth 选型下验证失败 | OAuth 集成复杂且 ChatGPT 端常见失败 | 按 auth-and-secrets.md 降级到默认令牌路径先上线 |

## 链接轮换与作废

- 重生成一个 32 字节随机令牌 → `PUT .../secrets` 覆盖 `LINK_TOKEN` → 旧链接立即失效，交付新链接；
- 若怀疑上游密钥泄露，除覆盖 Secret 外，建议同时在上游后台轮换；
- Cloudflare API Token 用完即删（My Profile → API Tokens）。

## 找不到原因时

按 [official-sources.md](official-sources.md) 核对官方最新 API 形态（端点、字段名可能已变），不要把历史经验当当前规则。