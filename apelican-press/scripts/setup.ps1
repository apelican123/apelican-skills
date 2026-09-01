# 从技能目录 .env 读取微信公众号环境变量，不打印密钥。
# Usage: .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $SkillDir ".env"

if ($env:WECHAT_APP_ID -and $env:WECHAT_APP_SECRET) {
  Write-Host "微信公众号环境变量已存在（未打印值）"
  return
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
  Write-Host "找不到微信公众号凭证。"
  Write-Host "请复制 .env.example 为 .env，并按 references/wechat-credentials.md 填写。"
  exit 1
}

Write-Host "正在从技能目录 .env 读取凭据（不会打印密钥）"
Get-Content -LiteralPath $EnvFile | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
  $name, $value = $_.Split("=", 2)
  if ($name -and $value) {
    Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim()
  }
}

if (-not $env:WECHAT_APP_ID -or -not $env:WECHAT_APP_SECRET) {
  Write-Host "凭证读取失败，请检查 .env 是否包含 WECHAT_APP_ID 和 WECHAT_APP_SECRET。"
  exit 1
}

Write-Host "微信公众号环境变量已加载。"
Write-Host "这些变量仅在当前 PowerShell 会话有效，不要把 .env 发给任何人。"
