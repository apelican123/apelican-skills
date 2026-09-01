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
