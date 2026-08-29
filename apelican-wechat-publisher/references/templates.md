# 可执行模板
GitHub 和本机包保留 `scripts/` 下的原文件。若目标平台不便上传 `.sh` / `.ps1`，可按下面代码块重建，路径与原文一致。

## `scripts/publish.sh`

```bash
#!/usr/bin/env bash
# 把 Markdown 保存到微信公众号草稿箱。不会群发或正式发表。
# Usage: ./publish.sh <markdown-file> [theme-or-css] [highlight]

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DEFAULT_THEME_OR_CSS="templates/humanities.css"
DEFAULT_HIGHLIGHT="github"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SKILL_DIR/.env"

fail() {
  echo -e "${RED}$1${NC}" >&2
  exit 1
}

check_wenyan() {
  if ! command -v wenyan >/dev/null 2>&1; then
    echo -e "${RED}未找到 wenyan 命令。${NC}"
    echo "请先安装 Node.js 18+，再执行："
    echo "  npm install -g @wenyan-md/cli"
    echo "然后重新运行本脚本。脚本不会擅自全局安装软件。"
    exit 1
  fi
}

load_credentials() {
  if [ -n "${WECHAT_APP_ID:-}" ] && [ -n "${WECHAT_APP_SECRET:-}" ]; then
    return 0
  fi
  if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}正在从技能目录 .env 读取凭据（不会打印密钥）${NC}"
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
  fi
}

check_env() {
  load_credentials
  if [ -z "${WECHAT_APP_ID:-}" ] || [ -z "${WECHAT_APP_SECRET:-}" ]; then
    echo -e "${RED}微信公众号凭证未设置。${NC}"
    echo "在技能根目录创建 .env，写入 WECHAT_APP_ID 和 WECHAT_APP_SECRET。"
    echo "逐步说明见 references/wechat-credentials.md"
    exit 1
  fi
}

resolve_style() {
  local style="$1"
  if [ -f "$style" ]; then
    echo "$style"
    return
  fi
  if [ -f "$SKILL_DIR/$style" ]; then
    echo "$SKILL_DIR/$style"
    return
  fi
  echo "$style"
}

publish() {
  local file="$1"
  local style
  style="$(resolve_style "${2:-$DEFAULT_THEME_OR_CSS}")"
  local highlight="${3:-$DEFAULT_HIGHLIGHT}"
  local -a args

  echo -e "${GREEN}准备保存到草稿箱（不会自动发表）${NC}"
  echo "  文件: $file"
  echo "  样式: $style"
  echo "  代码高亮: $highlight"
  echo

  args=(publish -f "$file" -h "$highlight")
  if [ -f "$ENV_FILE" ]; then
    args+=(--env-file "$ENV_FILE")
  fi
  case "$style" in
    *.css)
      args+=(-c "$style")
      ;;
    *)
      args+=(-t "$style")
      ;;
  esac

  wenyan "${args[@]}"

  echo
  echo -e "${GREEN}接口调用结束。请打开公众号后台草稿箱核对：${NC}"
  echo "  https://mp.weixin.qq.com/"
  echo "若结果不明确，先数草稿数量，不要立刻重试。"
}

show_help() {
  echo "Usage: $0 <markdown-file> [theme-or-css] [highlight]"
  echo
  echo "Examples:"
  echo "  $0 article.md"
  echo "  $0 article.md templates/humanities.css github"
  echo "  $0 article.md templates/tech.css solarized-light"
  echo "  $0 article.md templates/social.css github"
}

main() {
  if [ $# -eq 0 ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    show_help
    exit 0
  fi
  local file="$1"
  [ -f "$file" ] || fail "文件不存在: $file"
  check_wenyan
  check_env
  publish "$file" "${2:-}" "${3:-}"
}

main "$@"
```

## `scripts/setup.sh`

```bash
#!/usr/bin/env bash
# 从技能目录 .env 读取微信公众号环境变量，不打印密钥。
# Usage: source ./scripts/setup.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SKILL_DIR/.env"

if [ -n "${WECHAT_APP_ID:-}" ] && [ -n "${WECHAT_APP_SECRET:-}" ]; then
  echo "微信公众号环境变量已存在（未打印值）"
elif [ -f "$ENV_FILE" ]; then
  echo "正在从技能目录 .env 读取凭据（不会打印密钥）"
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
else
  echo "找不到微信公众号凭证。"
  echo "请复制 .env.example 为 .env，并按 references/wechat-credentials.md 填写。"
  return 1 2>/dev/null || exit 1
fi

if [ -z "${WECHAT_APP_ID:-}" ] || [ -z "${WECHAT_APP_SECRET:-}" ]; then
  echo "凭证读取失败，请检查 .env 是否包含 WECHAT_APP_ID 和 WECHAT_APP_SECRET。"
  return 1 2>/dev/null || exit 1
fi

export WECHAT_APP_ID
export WECHAT_APP_SECRET
echo "微信公众号环境变量已加载。"
echo "这些变量仅在当前 shell 有效，不要把 .env 发给任何人。"
```

## `scripts/publish.ps1`

```powershell
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
```

## `scripts/setup.ps1`

```powershell
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
```
