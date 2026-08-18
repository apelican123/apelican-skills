#!/usr/bin/env node
const { createHash, randomBytes } = require("node:crypto");

function arg(name) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const username = arg("username");
const baseUrl = arg("base-url");
if (!username || !baseUrl) {
  throw new Error("Usage: node scripts/create-user-link.js --username <name> --base-url https://<worker-domain>");
}

const base = new URL(baseUrl);
if (base.protocol !== "https:") throw new Error("--base-url must use https://");

const normalized = username.normalize("NFKC").trim().toLowerCase();
const readable = normalized
  .normalize("NFKD")
  .replace(/[\u0300-\u036f]/gu, "")
  .replace(/[^a-z0-9]+/gu, "-")
  .replace(/^-+|-+$/gu, "")
  .slice(0, 32) || "user";
const usernameTag = createHash("sha256").update(normalized).digest("hex").slice(0, 8);
const userId = `${readable}-${usernameTag}`;
const token = randomBytes(32).toString("base64url");
const tokenHash = createHash("sha256").update(token).digest("hex");
const secretName = `MCP_USER_${userId.replace(/-/gu, "_").toUpperCase()}_TOKEN_SHA256`;
const privateUrl = new URL(`/u/${userId}/${token}/mcp`, base.origin).toString();

console.log(JSON.stringify({
  userId,
  secretName,
  secretValue: tokenHash,
  privateUrl,
  chatgptAuthentication: "无身份验证",
  warning: "privateUrl 只显示这一次；完整链接就是访问密钥，不要截图、公开、转发或写入日志。",
}, null, 2));
