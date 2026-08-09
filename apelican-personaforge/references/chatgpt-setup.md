# ChatGPT 接入

ChatGPT 界面、套餐和工作区权限会变化。连接前查看 OpenAI 最新文档：

- https://developers.openai.com/plugins/deploy/connect-chatgpt
- https://developers.openai.com/plugins/deploy/app-review

## 公网 MCP

1. 在 ChatGPT 设置中启用 Developer mode（若当前账号/工作区提供）。
   - **验证**：当前工作区能看到创建连接入口；看不到时先核对账号、工作区管理员设置和当前官方可用性。
2. 创建新的 MCP/plugin 连接，选择 Server URL。
   - **验证**：连接类型是远程 MCP，而不是普通网页 URL 或旧 Actions 导入。
3. 填稳定 HTTPS `/mcp` URL。
   - **验证**：URL 没有空格、占位符或重复 `/mcp`；`/health` 与 `/mcp` 的行为符合预期。
4. 配置认证。公开插件使用 OAuth；私人连接优先 Bearer，旧客户端才使用兼容 query/API-Key Header。
   - **验证**：无凭证失败、正确凭证成功；公开 OAuth 还要看到登录/授权流程和正确 scope。
5. 保存连接并读取工具。
   - **验证**：工具数量与 Inspector 的 tools/list 一致，名称、描述和读写提示没有被截断成空值。
6. 用一个明确应调用的提示完成真实只读调用，再用一个不该调用的提示做反向测试。
   - **验证**：前者选择正确工具并返回真实结果，后者不会误调用；检查 JSON-RPC error 与 `result.isError`。

任一步失败都先停在该步，不要通过重复创建同名连接掩盖问题。

## OpenAI Secure MCP Tunnel

用于本机/内网私人开发。完整步骤见 [local-tunnel-deploy.md](local-tunnel-deploy.md)。Tunnel 与 Cloudflare Worker 是替代部署路径，不必同时使用。

## 网页、桌面与移动设备

先在当前支持创建连接的界面完成上述六步。其他设备是否自动出现该连接取决于账号、工作区、
客户端版本和当前产品权限，不能硬编码“手机免费可用”或固定菜单位置。

第二设备验证：登录同一目标工作区，确认连接可见、工具数量一致，并只调用一个只读工具。
若不可见，不要复制 Worker 的上游 Secret；按 [cross-device-use.md](cross-device-use.md) 检查工作区、
客户端权限和认证配置。

## 更新、禁用与删除

- 修改 Worker 后先完成生产回归，再刷新或重新连接；
- 禁用连接后验证模型不再调用其工具；
- 删除连接前记录名称与 URL，删除后验证列表中不存在；
- 这些操作不等于删除 Cloudflare Worker、上游数据或 OAuth 应用，范围必须分别确认。

## 套餐、额度与审核

套餐、额度、Developer mode 和移动端能力会变化。只引用当前官方页面和用户实际界面，
不沿用旧版文档中的固定免费额度或账号保证。公网私人连接可用也不等于公开审核通过。

## 连接失败

按顺序检查：

1. HTTPS URL 和 `/mcp` 路径；
2. 未认证为 401/403，正确认证为 200；
3. initialize 无 JSON-RPC error，有 serverInfo 与 instructions；
4. tools/list 的每个 JSON Schema 可序列化；
5. 有状态服务正确维护 session；
6. 协议版本在服务器支持范围；
7. 工具无空名称、空描述和错误 outputSchema；
8. Worker 日志无异常和凭证泄漏。

Developer mode 中能连接不代表通过公开审核。公开插件还需 OAuth 2.1、审核材料和稳定生产服务。
