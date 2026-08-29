# Cloudflare 部署手册（4.0.1）

目标：用户只提供 Account ID + API Token。**由 AI 用 Python 调 Cloudflare API** 完成上传、写 Secret、打开 workers.dev。不要把一串 curl 丢给小白自己跑。

基线：2026-08-29。实施前对照 [official-sources.md](official-sources.md)。官方字段名优先。

## 一、用户手动（只这一段）

1. 打开 https://dash.cloudflare.com 注册或登录。
2. 进入 **Workers**（有的账号仍显示 Workers & Pages / Compute）。首次使用必须启用 `workers.dev` 子域，形如 `<你的用户名>.workers.dev`。没有子域，后面没有公开 URL。
3. 右上角头像 → **My Profile** → **API Tokens** → **Create Token** → Custom token：
   - Permissions：`Account` → `Workers Scripts` → **Edit**
   - 这就是 API 文档里的 `Workers Scripts Write`
   - Account Resources：选当前账号
   - 不要用 Global API Key
4. 复制：
   - **API Token**（只显示一次）
   - **Account ID**（Workers 概览页右侧，或 Overview）

交给 AI 后即可。用完建议删除该 Token。

## 二、AI 执行（Python，跨 Windows / macOS / Linux）

不要用 `curl -F metadata=<file>`：PowerShell 会把 `<` 当成重定向。模块 Worker 的脚本 part 必须是 `application/javascript+module`。

把下面脚本写到临时文件后运行。用环境变量传 Token，不要打印 Token。

```python
# deploy_worker.py  — 由铸造流程写入临时目录后执行
import json, os, secrets, sys, urllib.request, urllib.error
from pathlib import Path

ACCOUNT = os.environ["CF_ACCOUNT_ID"].strip()
TOKEN = os.environ["CF_API_TOKEN"].strip()
NAME = os.environ.get("CF_SCRIPT_NAME", "personaforge-mcp").strip()
UPSTREAM = os.environ.get("UPSTREAM_KEY", "").strip()
LINK = os.environ.get("LINK_TOKEN") or secrets.token_hex(32)
WORKER = Path(os.environ["WORKER_JS"]).read_bytes()

API = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/workers"

def call(method, path, data=None, content_type="application/json"):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    body = None
    if data is not None and content_type == "application/json":
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    elif data is not None:
        body = data
        headers["Content-Type"] = content_type
    req = urllib.request.Request(API + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")
        raise SystemExit(f"HTTP {e.code} {path}: {err[:2000]}")

# 1. 账号级 workers.dev 子域
sub = call("GET", "/subdomain")
if not sub.get("success"):
    raise SystemExit("尚未启用 workers.dev 子域。请让用户在 Cloudflare Workers 控制台先启用一次。")
subdomain = (sub.get("result") or {}).get("subdomain")
if not subdomain:
    raise SystemExit("API 未返回 subdomain。请让用户完成 workers.dev 首启。")

# 2. 上传 ES module Worker
boundary = "----pf" + secrets.token_hex(8)
metadata = json.dumps({
    "main_module": "worker.js",
    "compatibility_date": "2026-08-01",
})
parts = []
def add(name, payload, filename=None, ctype="application/json"):
    head = [f"--{boundary}", f'Content-Disposition: form-data; name="{name}"' + (f'; filename="{filename}"' if filename else ""), f"Content-Type: {ctype}", "", ""]
    parts.append("\r\n".join(head[:-1]).encode() + b"\r\n" + payload + b"\r\n")
add("metadata", metadata.encode(), ctype="application/json")
add("worker.js", WORKER, filename="worker.js", ctype="application/javascript+module")
parts.append(f"--{boundary}--\r\n".encode())
body = b"".join(parts)
up = call("PUT", f"/scripts/{NAME}", data=body, content_type=f"multipart/form-data; boundary={boundary}")
if not up.get("success"):
    raise SystemExit(f"上传失败: {up}")

# 3. Secret：LINK_TOKEN 与 URL 用同一段明文
sec1 = call("PUT", f"/scripts/{NAME}/secrets", {"name": "LINK_TOKEN", "text": LINK, "type": "secret_text"})
if not sec1.get("success"):
    raise SystemExit(f"写入 LINK_TOKEN 失败: {sec1}")
if UPSTREAM:
    sec2 = call("PUT", f"/scripts/{NAME}/secrets", {"name": "UPSTREAM_KEY", "text": UPSTREAM, "type": "secret_text"})
    if not sec2.get("success"):
        raise SystemExit(f"写入 UPSTREAM_KEY 失败: {sec2}")

# 4. 打开这个 Worker 的 workers.dev（metadata.workers_dev 无效，必须调这个接口）
en = call("POST", f"/scripts/{NAME}/subdomain", {"enabled": True})
if not en.get("success"):
    raise SystemExit(f"打开 workers.dev 失败: {en}")

url = f"https://{NAME}.{subdomain}.workers.dev/u/{LINK}/mcp"
# 只把 URL 打到 stdout；不要打印 Token
print(json.dumps({"ok": True, "script": NAME, "subdomain": subdomain, "url": url}, ensure_ascii=False))
```

环境变量：

| 变量 | 谁填 | 说明 |
|---|---|---|
| `CF_API_TOKEN` | 用户 | Workers Scripts Edit / Write |
| `CF_ACCOUNT_ID` | 用户 | 控制台 Account ID |
| `CF_SCRIPT_NAME` | AI | 小写字母、数字、连字符，不要下划线 |
| `WORKER_JS` | AI | 生成的 worker.js 绝对路径 |
| `LINK_TOKEN` | AI | 可省略，脚本会生成 `token_hex(32)` |
| `UPSTREAM_KEY` | 用户经 AI | 上游密钥；没有就不写 |

运行后读 stdout 的 `url`。不要把 `CF_API_TOKEN` 写进对话。

## 三、组装规则

```text
https://<脚本名>.<账号subdomain>.workers.dev/u/<LINK_TOKEN明文>/mcp
```

- `LINK_TOKEN` 存进 Secret 的值 = URL 路径里的值，不要哈希
- 作废：重新生成 hex，覆盖 Secret，旧链接立即 401

## 四、官方端点备查

- 账号子域：`GET /accounts/{id}/workers/subdomain`
- 上传：`PUT /accounts/{id}/workers/scripts/{name}` multipart，`main_module` 必填
- Secret：`PUT /accounts/{id}/workers/scripts/{name}/secrets`
- **打开公开 URL**：`POST /accounts/{id}/workers/scripts/{name}/subdomain` `{"enabled": true}`
