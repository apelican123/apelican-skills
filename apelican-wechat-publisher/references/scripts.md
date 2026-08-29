# 可复制脚本

小红书技能上传页截图点名支持 `.md` `.txt` `.html` `.css` `.js` `.py` `.json` `.xml`。`.sh` 和 `.ps1` 没有点名，1.3 公开包不附带这两类文件，避免上传页识别不了。

功能不变：还是调用 `wenyan publish` 进草稿箱，不群发。把下面代码复制到本机自行保存即可。

本地 `.env` 放在技能根目录，键名：

```text
WECHAT_APP_ID=your_wechat_app_id
WECHAT_APP_SECRET=your_wechat_app_secret
```

不要把真实密钥写进这个技能包。

## 最短命令

```bash
wenyan publish -f article.md -c templates/humanities.css -h github --no-mac-style --env-file .env
```

```powershell
wenyan publish -f article.md -c templates/humanities.css -h github --no-mac-style --env-file .env
```

## bash 完整脚本

原路径 `scripts/publish.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail
DEFAULT_THEME_OR_CSS="templates/humanities.css"
DEFAULT_HIGHLIGHT="github"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SKILL_DIR/.env"

fail() { echo "$1" >&2; exit 1; }

if ! command -v wenyan >/dev/null 2>&1; then
  echo "未找到 wenyan。先安装 Node.js 18+，再执行 npm install -g @wenyan-md/cli"
  exit 1
fi

if [ -z "${WECHAT_APP_ID:-}" ] || [ -z "${WECHAT_APP_SECRET:-}" ]; then
  if [ -f "$ENV_FILE" ]; then
    set -a
    . "$ENV_FILE"
    set +a
  fi
fi

if [ -z "${WECHAT_APP_ID:-}" ] || [ -z "${WECHAT_APP_SECRET:-}" ]; then
  echo "请在技能根目录创建 .env，写入 WECHAT_APP_ID 和 WECHAT_APP_SECRET。"
  exit 1
fi

file="$1"
style="${2:-$DEFAULT_THEME_OR_CSS}"
highlight="${3:-$DEFAULT_HIGHLIGHT}"
[ -f "$file" ] || fail "文件不存在: $file"
[ -f "$style" ] || { [ -f "$SKILL_DIR/$style" ] && style="$SKILL_DIR/$style"; }

args=(publish -f "$file" -h "$highlight" --no-mac-style)
[ -f "$ENV_FILE" ] && args+=(--env-file "$ENV_FILE")
case "$style" in
  *.css) args+=(-c "$style") ;;
  *) args+=(-t "$style") ;;
esac
wenyan "${args[@]}"
echo "接口调用结束。打开 https://mp.weixin.qq.com/ 核对草稿箱。不要立刻重试。"
```

## PowerShell 完整脚本

原路径 `scripts/publish.ps1`：

```powershell
param(
  [Parameter(Position = 0)][string]$MarkdownFile,
  [Parameter(Position = 1)][string]$ThemeOrCss = "templates/humanities.css",
  [Parameter(Position = 2)][string]$Highlight = "github"
)
$ErrorActionPreference = "Stop"
$SkillDir = Split-Path -Parent $PSScriptRoot
if (-not $PSScriptRoot) { $SkillDir = Get-Location }
$EnvFile = Join-Path $SkillDir ".env"

if (-not (Get-Command wenyan -ErrorAction SilentlyContinue)) {
  Write-Host "未找到 wenyan。先安装 Node.js 18+，再执行 npm install -g @wenyan-md/cli"
  exit 1
}
if (-not (Test-Path -LiteralPath $MarkdownFile)) {
  Write-Host "文件不存在: $MarkdownFile"
  exit 1
}
if (-not $env:WECHAT_APP_ID -or -not $env:WECHAT_APP_SECRET) {
  if (Test-Path -LiteralPath $EnvFile) {
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
  Write-Host "请在技能根目录创建 .env，写入 WECHAT_APP_ID 和 WECHAT_APP_SECRET。"
  exit 1
}
$style = $ThemeOrCss
if (Test-Path -LiteralPath (Join-Path $SkillDir $style)) {
  $style = (Join-Path $SkillDir $style)
}
$argsList = @("publish", "-f", $MarkdownFile, "-h", $Highlight, "--no-mac-style")
if (Test-Path -LiteralPath $EnvFile) { $argsList += @("--env-file", $EnvFile) }
if ($style -like "*.css") { $argsList += @("-c", $style) } else { $argsList += @("-t", $style) }
& wenyan @argsList
Write-Host "接口调用结束。打开 https://mp.weixin.qq.com/ 核对草稿箱。"
```
