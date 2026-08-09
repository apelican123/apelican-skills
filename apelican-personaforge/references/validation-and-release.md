# 验证与发布门槛

## 部署前

| 步骤 | 操作 | 通过证据 | 失败时 |
|---|---|---|---|
| 1 | 检查 Node/npm/Wrangler 版本 | 三条命令状态码 0，版本满足当前依赖 | 更新环境并重开终端 |
| 2 | `npm install`、`npm ls --depth=0` | 无 unmet dependency | 核对官方版本，不默认绕过 peer dependency |
| 3 | 类型或语法检查 | `tsc --noEmit` 状态码 0 | 修代码，不关闭 strict 掩盖错误 |
| 4 | Wrangler dry-run | 状态码 0、入口/绑定符合预期、未生产部署 | 修配置，不进入部署 |
| 5 | 扫描占位符、凭证、私人路径 | 生产路径无命中 | 替换/脱敏后重扫 |
| 6 | 保存生产基线 | 当前 version ID、URL、工具数、auth/init/list/call 结果齐全 | 无基线时先只读盘点 |

安装验证通过后，实际项目应记录 `npm ls --depth=0` 的解析版本并保留 lockfile；公开技能模板
可以使用 `latest` 提醒生成者核对当前官方版本，但生产部署不能在未回归时漂移依赖。

## 协议验证

依次验证：

- 无认证和错误认证返回 401/403；
- initialize 返回稳定 serverInfo 和非空 instructions；
- notifications/initialized 正常；
- tools/list 无 JSON-RPC error；
- 每个工具都有 name/title/description/inputSchema/annotations；
- 声明 outputSchema 的工具实际返回 structuredContent；
- ping 正常；
- 每个只读工具至少调用一次正常输入；
- 关键工具另测空值、越界、上游 4xx/5xx 与超时；
- 检查 JSON-RPC error 和 result.isError，不能只看 HTTP 200。

写工具不加入自动 fixture。用 dry-run、用户确认、实际执行、读回四步验证。

## 生产发布

1. 单个 Worker 部署，不把多个服务绑成一次变更。
   - **验证**：部署输出只含目标 Worker；记录新 version ID。
2. 等待边缘传播。
   - **验证**：`deployments status` 出现新版本，`/health` 命中目标服务。
3. 对生产 URL 重跑 auth/init/initialized/ping/list/call。
   - **验证**：与部署前基线对照；工具缺失、重命名或 schema 变化必须解释。
4. 查看脱敏后的日志。
   - **验证**：无 Authorization、cookie、token、私人正文或内部 URL。
5. 做模型选择回归。
   - **验证**：一个应调用提示选对工具，一个不应调用提示不误选。
6. 在第二设备或第二客户端做只读回归（目标要求多设备时）。
   - **验证**：工具数量和只读结果关键字段一致。
7. 失败只回滚该 Worker。
   - **验证**：旧 version 恢复后再次通过 auth/init/list/call；其他 Worker 版本未变化。

## 公开插件额外要求

- OAuth 2.1、PKCE、scope 与重定向 URI验证；
- 工具级 securitySchemes；
- 隐私政策、支持链接、品牌资料；
- 可复现的审核账号/步骤；
- 生产 URL 长期可访问，不依赖本机 Tunnel；
- 提交前重新核对 OpenAI 最新 app review 清单。

报告时把“私人可用”和“公开审核准备完成”分开，不能混称。

## 发布技能包

1. 运行技能结构校验。
2. 验证包内仅包含必要 Markdown，无 README、Secret、缓存、日志或真实部署配置。
3. 检查所有相对链接和外部官方链接。
4. 对照 [compatibility-and-regression.md](compatibility-and-regression.md) 完成回归矩阵。
5. 创建版本化 ZIP，计算 SHA-256。
6. 解压到临时目录，重新验证根目录层级、文件清单、逐文件哈希和技能结构。

只有解压后复验也通过，才把 ZIP 标记为发布候选。
