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
