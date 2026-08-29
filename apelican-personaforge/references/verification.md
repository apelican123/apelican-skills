# 部署后验证（4.0.1）

`MCP_URL` = `https://<脚本名>.<subdomain>.workers.dev/u/<令牌>/mcp`

用 Python 测，避免 PowerShell 转义把请求测废。

```python
import json, os, urllib.request, urllib.error

URL = os.environ["MCP_URL"]

def call(method, body=None, http="POST"):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(URL if method != "bad" else URL.replace("/u/", "/u/wrong"), data=data, headers=headers, method=http)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

st, raw = call("GET", http="GET")
assert st == 405, f"GET should 405, got {st} {raw[:80]}"

st, raw = call("bad", {"jsonrpc":"2.0","id":1,"method":"ping"})
assert st == 401, f"bad token should 401, got {st}"

st, raw = call("init", {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}})
assert st == 200 and b"2025-06-18" in raw and b"serverInfo" in raw, raw[:400]

st, raw = call("note", {"jsonrpc":"2.0","method":"notifications/initialized"})
assert st == 202, f"notification should 202, got {st} {raw[:80]}"

st, raw = call("list", {"jsonrpc":"2.0","id":2,"method":"tools/list"})
assert st == 200 and b'"tools"' in raw, raw[:400]
print("ok", json.loads(raw).get("result", {}).get("tools"))
```

通过标准：

- [ ] 错误令牌 401
- [ ] GET 405
- [ ] initialize 回显客户端 protocolVersion 且有 serverInfo
- [ ] notifications/initialized 为 202 空 body
- [ ] tools/list 与设计一致，没有 `api.example.com` 残留工具（除非用户接口本来就是这个）
- [ ] 用户同意时，一次只读 tools/call 成功

全部通过才把 URL 和 [chatgpt-setup.md](chatgpt-setup.md) 交给用户。curl 200 不算 ChatGPT 已接好。
