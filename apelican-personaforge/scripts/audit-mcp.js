#!/usr/bin/env node
const fs = require("node:fs/promises");

const url = process.env.MCP_URL;
const token = process.env.MCP_TOKEN ?? "";
const authMode = process.env.MCP_AUTH_MODE ?? "bearer";
const expectedAuth = process.env.MCP_EXPECT_AUTH ?? "";
const invalidUrl = process.env.MCP_INVALID_URL ?? "";
const crossUserUrl = process.env.MCP_CROSS_USER_URL ?? "";
const fixturesPath = process.env.MCP_FIXTURES;
const protocolVersion = process.env.MCP_PROTOCOL_VERSION ?? "2025-06-18";
if (!url) throw new Error("Set MCP_URL to the full /mcp endpoint");
if (authMode === "capability" && !invalidUrl) throw new Error("Set MCP_INVALID_URL for capability fail-closed validation");

let nextId = 1;
function endpoint(withAuth) {
  if (!withAuth && authMode === "capability") return new URL(invalidUrl);
  const out = new URL(url);
  if (withAuth && token && authMode === "query") out.searchParams.set("token", token);
  return out;
}

function parseMcp(text) {
  const events = text.split(/\r?\n/u).filter((line) => line.startsWith("data:"));
  return JSON.parse(events.length ? events.at(-1).slice(5).trim() : text);
}

async function rpc(method, params = {}, withAuth = true, overrideUrl = "") {
  const headers = { "content-type": "application/json", accept: "application/json, text/event-stream" };
  if (withAuth && token && authMode === "bearer") headers.authorization = `Bearer ${token}`;
  const response = await fetch(overrideUrl ? new URL(overrideUrl) : endpoint(withAuth), {
    method: "POST",
    headers,
    body: JSON.stringify({ jsonrpc: "2.0", id: nextId++, method, params }),
    signal: AbortSignal.timeout(90_000),
  });
  const text = await response.text();
  return { status: response.status, value: response.ok ? parseMcp(text) : null };
}

const failures = [];
const initParams = { protocolVersion, capabilities: {}, clientInfo: { name: "personaforge-audit", version: "2" } };
const unauth = await rpc("initialize", initParams, false);
if (authMode === "capability" && ![401, 403, 404].includes(unauth.status)) failures.push(`invalid capability URL returned ${unauth.status}`);
if (token && authMode !== "capability" && ![401, 403].includes(unauth.status)) failures.push(`unauthenticated request returned ${unauth.status}`);

if (authMode === "capability" && crossUserUrl) {
  const crossUser = await rpc("initialize", initParams, true, crossUserUrl);
  if (![401, 403, 404].includes(crossUser.status)) failures.push(`cross-user capability URL returned ${crossUser.status}`);
}

if (expectedAuth === "oauth2") {
  const endpointUrl = new URL(url);
  const resourceUrl = new URL(`/.well-known/oauth-protected-resource${endpointUrl.pathname}`, endpointUrl.origin);
  const resourceResponse = await fetch(resourceUrl, { signal: AbortSignal.timeout(30_000) });
  if (!resourceResponse.ok) {
    failures.push(`OAuth protected-resource metadata failed: HTTP ${resourceResponse.status}`);
  } else {
    const resource = await resourceResponse.json();
    if (!resource.resource || !Array.isArray(resource.authorization_servers) || resource.authorization_servers.length === 0) {
      failures.push("OAuth protected-resource metadata lacks resource or authorization_servers");
    } else {
      const issuer = new URL(resource.authorization_servers[0]);
      const authMetadataResponse = await fetch(new URL("/.well-known/oauth-authorization-server", issuer), {
        signal: AbortSignal.timeout(30_000),
      });
      if (!authMetadataResponse.ok) {
        failures.push(`OAuth authorization-server metadata failed: HTTP ${authMetadataResponse.status}`);
      } else {
        const authMetadata = await authMetadataResponse.json();
        if (!authMetadata.authorization_endpoint || !authMetadata.token_endpoint) failures.push("OAuth metadata lacks authorization/token endpoint");
        if (!authMetadata.code_challenge_methods_supported?.includes("S256")) failures.push("OAuth metadata does not advertise PKCE S256");
        if (!authMetadata.client_id_metadata_document_supported && !authMetadata.registration_endpoint) {
          failures.push("OAuth metadata supports neither CIMD nor DCR");
        }
      }
    }
  }
}

const init = await rpc("initialize", initParams);
if (init.status !== 200 || init.value?.error) failures.push(`initialize failed: HTTP ${init.status} ${init.value?.error?.message ?? ""}`);
const info = init.value?.result ?? {};
if (!info.serverInfo?.name || !info.serverInfo?.version) failures.push("initialize lacks stable serverInfo name/version");
if (!info.instructions?.trim()) failures.push("initialize lacks instructions");

const listed = await rpc("tools/list");
if (listed.status !== 200 || listed.value?.error) failures.push(`tools/list failed: HTTP ${listed.status} ${listed.value?.error?.message ?? ""}`);
const tools = listed.value?.result?.tools ?? [];
for (const tool of tools) {
  for (const field of ["name", "title", "description", "inputSchema", "annotations"]) {
    if (!tool[field] || (typeof tool[field] === "string" && !tool[field].trim())) failures.push(`${tool.name ?? "<unnamed>"}: missing ${field}`);
  }
  const schemes = tool.securitySchemes ?? tool._meta?.securitySchemes;
  if (expectedAuth === "none" && Array.isArray(schemes) && schemes.length > 0) failures.push(`${tool.name}: unexpected securitySchemes for no-auth connector mode`);
  if (expectedAuth && expectedAuth !== "none" && (!Array.isArray(schemes) || !schemes.some((scheme) => scheme?.type === expectedAuth))) {
    failures.push(`${tool.name}: missing ${expectedAuth} securitySchemes`);
  }
  if (tool.outputSchema && tool.outputSchema.type !== "object") failures.push(`${tool.name}: outputSchema root must be object`);
}

const byName = new Map(tools.map((tool) => [tool.name, tool]));
for (const standard of ["search", "fetch"]) {
  if (byName.has(standard) && byName.get(standard).annotations?.readOnlyHint !== true) failures.push(`${standard}: company knowledge tool must be read-only`);
}

let called = 0;
if (fixturesPath) {
  const fixtures = JSON.parse(await fs.readFile(fixturesPath, "utf8"));
  for (const [name, args] of Object.entries(fixtures)) {
    if (!byName.has(name)) { failures.push(`fixture references unknown tool ${name}`); continue; }
    const call = await rpc("tools/call", { name, arguments: args });
    const result = call.value?.result;
    if (call.status !== 200 || call.value?.error || result?.isError) failures.push(`${name}: call failed: ${call.value?.error?.message ?? result?.content?.[0]?.text ?? `HTTP ${call.status}`}`);
    if (byName.get(name).outputSchema && !result?.structuredContent) failures.push(`${name}: outputSchema declared but structuredContent missing`);
    called++;
  }
}

console.log(JSON.stringify({ ok: failures.length === 0, server: info.serverInfo ?? null, instructions: Boolean(info.instructions), tools: tools.length, fixturesCalled: called, crossUserChecked: Boolean(crossUserUrl), failures }, null, 2));
if (failures.length) process.exitCode = 1;
