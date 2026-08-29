# 把 Markdown 保存到微信公众号草稿箱。不会群发或正式发表。
# Usage: .\scripts\publish.ps1 <markdown-file> [theme-or-css] [highlight]

param(
  [Parameter(Position = 0)]
  [string]$MarkdownFile,
  [Parameter(Position = 1)]
  [string]$ThemeOrCss = "templates/humanities.css",
  [Parameter(Position = 2)]
  [string]$Highlight = "github"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $SkillDir ".env"

function Show-Help {
  Write-Host "Usage: .\scripts\publish.ps1 <markdown-file> [theme-or-css] [highlight]"
  Write-Host ""
  Write-Host "Examples:"
  Write-Host "  .\scripts\publish.ps1 article.md"
  Write-Host "  .\scripts\publish.ps1 article.md templates/humanities.css github"
  Write-Host "  .\scripts\publish.ps1 article.md templates/tech.css solarized-light"
}

if (-not $MarkdownFile -or $MarkdownFile -in @("-h", "--help")) {
  Show-Help
  exit 0
}

if (-not (Get-Command wenyan -ErrorAction SilentlyContinue)) {
  Write-Host "未找到 wenyan 命令。"
  Write-Host "请先安装 Node.js 18+，再执行："
  Write-Host "  npm install -g @wenyan-md/cli"
  Write-Host "脚本不会擅自全局安装软件。"
  exit 1
}

if (-not (Test-Path -LiteralPath $MarkdownFile)) {
  Write-Host "文件不存在: $MarkdownFile"
  exit 1
}

if (-not $env:WECHAT_APP_ID -or -not $env:WECHAT_APP_SECRET) {
  if (Test-Path -LiteralPath $EnvFile) {
    Write-Host "正在从技能目录 .env 读取凭据（不会打印密钥）"
    Get-Content -LiteralPath $EnvFile | ForEach-Object {
      if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
      $name, $value = $_.Split("=", 2)
      if ($name -and $value -and -not [Environment]::GetEnvironmentVariable($name.Trim())) {
        Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim()
      }
    }
  }
}

if (-not $env:WECHAT_APP_ID -or -not $env:WECHAT_APP_SECRET) {
  Write-Host "微信公众号凭证未设置。"
  Write-Host "在技能根目录创建 .env，写入 WECHAT_APP_ID 和 WECHAT_APP_SECRET。"
  Write-Host "逐步说明见 references/wechat-credentials.md"
  exit 1
}

$style = $ThemeOrCss
if (Test-Path -LiteralPath $style) {
  $style = (Resolve-Path -LiteralPath $style).Path
} elseif (Test-Path -LiteralPath (Join-Path $SkillDir $style)) {
  $style = (Resolve-Path -LiteralPath (Join-Path $SkillDir $style)).Path
}

Write-Host "准备保存到草稿箱（不会自动发表）"
Write-Host "  文件: $MarkdownFile"
Write-Host "  样式: $style"
Write-Host "  代码高亮: $Highlight"

$argsList = @("publish", "-f", $MarkdownFile, "-h", $Highlight)
if (Test-Path -LiteralPath $EnvFile) {
  $argsList += @("--env-file", $EnvFile)
}
if ($style -like "*.css") {
  $argsList += @("-c", $style)
} else {
  $argsList += @("-t", $style)
}

& wenyan @argsList
if ($LASTEXITCODE -ne 0) {
  Write-Host "保存失败。先看 references/troubleshooting.md，不要立刻重试造成重复草稿。"
  exit $LASTEXITCODE
}

Write-Host "接口调用结束。请打开公众号后台草稿箱核对："
Write-Host "  https://mp.weixin.qq.com/"
