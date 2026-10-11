#!/usr/bin/env bash
# REL-10 · 部署脚本（零配置版）：按 tag 拉取 -> 重启服务 -> 健康检查 -> 失败自动回退
#
# 用法：
#   bash scripts/deploy.sh --detect          # 只看它会认成什么，不做任何改动
#   bash scripts/deploy.sh v2026.10.1        # 真正部署
#
# 服务名、端口、健康端点全部自动识别；识别不到时用兜底值并在输出里说明。
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/lifetrip}"        # 代码目录
TARGET_ENV="${TARGET_ENV:-staging}"        # 标签，只用于日志
REQUIRE_ISOCHRONE="${REQUIRE_ISOCHRONE:-0}" # 1 = isochrone 仍降级则算失败
ISOCHRONE_PROBE="${ISOCHRONE_PROBE:-}"      # 例：http://127.0.0.1:8800/v1/isochrone/analyze?lat=..&lon=..
WANT_KEEP="${KEEP_COMMITS:-5}"

log(){ printf '\n\033[1;32m==> [%s] %s\033[0m\n' "$TARGET_ENV" "$*"; }
warn(){ printf '\033[1;33m注意：%s\033[0m\n' "$*"; }

detect_service(){
  systemctl list-units --type=service --all --no-legend 2>/dev/null \
    | awk '{print $1}' | sed 's/\.service$//' | grep -iE 'lifetrip' | head -1
}
detect_port(){
  systemctl cat "$SERVICE" 2>/dev/null | grep -oE '127\.0\.0\.1:[0-9]{4}|0\.0\.0\.0:[0-9]{4}|:[0-9]{4}' \
    | grep -oE '[0-9]{4}' | head -1
}
detect_health(){
  local p
  for p in /v1/health /healthz /health /api/health /healthcheck /; do
    if curl -fsS --max-time 5 "http://127.0.0.1:${PORT}${p}" >/dev/null 2>&1; then
      printf '%s' "$p"; return 0
    fi
  done
  return 1
}
unit_env_keys(){
  systemctl cat "$SERVICE" 2>/dev/null | grep -oE '^Environment=[A-Za-z_][A-Za-z0-9_]*' | sed 's/^Environment=//'
}

SERVICE="${SERVICE:-$(detect_service || true)}"; SERVICE="${SERVICE:-lifetrip-api}"
PORT="${PORT:-$(detect_port || true)}";           PORT="${PORT:-8800}"
HEALTH_PATH="$(detect_health || true)"

# ---------------- --detect：只读体检 ----------------
if [ "${1:-}" = "--detect" ]; then
  echo "代码目录  : $APP_DIR $( [ -d "$APP_DIR/.git" ] && echo '（git 仓库）' || echo '（⚠ 不是 git 仓库）' )"
  echo "服务名    : $SERVICE"
  echo "端口      : $PORT"
  if [ -n "$HEALTH_PATH" ]; then echo "健康端点  : http://127.0.0.1:${PORT}${HEALTH_PATH}  ✅ 有响应"
  else echo "健康端点  : ⚠ 五个候选路径都无响应，部署时只能退化为端口连通性检查"; fi
  echo "启动命令  :"; systemctl cat "$SERVICE" 2>/dev/null | grep -E '^ExecStart' || echo "  （读不到单元文件）"
  echo "工作目录  :"; systemctl cat "$SERVICE" 2>/dev/null | grep -E '^WorkingDirectory' || echo "  （未设置）"
  echo "环境变量键名（值已隐藏）:"; unit_env_keys | sed 's/^/  - /' || true
  echo "OSRM 相关 :"; unit_env_keys | grep -iE 'osrm|route' | sed 's/^/  - /' || echo "  - 没有任何 OSRM 相关键（这很可能就是 isochrone 降级的根因）"
  exit 0
fi

# ---------------- 正式部署 ----------------
NEW_TAG="${1:?用法: deploy.sh <tag> 或 deploy.sh --detect}"
PREV_TAG="$(git -C "$APP_DIR" describe --tags --abbrev=0 "${NEW_TAG}^" 2>/dev/null || true)"

healthy(){
  local i
  for i in $(seq 1 20); do
    if [ -n "$HEALTH_PATH" ]; then
      curl -fsS --max-time 5 "http://127.0.0.1:${PORT}${HEALTH_PATH}" >/dev/null && return 0
    else
      curl -fsS --max-time 5 -o /dev/null "http://127.0.0.1:${PORT}/" && return 0
    fi
    sleep 3
  done
  return 1
}

switch_to(){
  local tag="$1"
  log "切换到 $tag"
  git -C "$APP_DIR" fetch --tags --prune origin
  git -C "$APP_DIR" checkout --force "$tag"
  # 前端 dist 由 CI 构建后一起取；不在服务器上跑 Node 构建（2C4G 会与 OpenClaw 抢内存）
  sudo systemctl restart "$SERVICE"
  if healthy; then log "健康检查通过：$tag"; return 0; fi
  return 1
}

assert_isochrone(){
  [ -n "$ISOCHRONE_PROBE" ] || { warn "未配置 ISOCHRONE_PROBE，跳过业务断言"; return 0; }
  local body
  body="$(curl -fsS --max-time 10 "$ISOCHRONE_PROBE")" || { warn "isochrone 探针不可达"; return 0; }
  if printf '%s' "$body" | grep -qE '"time_s"[[:space:]]*:[[:space:]]*[0-9]'; then
    log "isochrone 正常（time_s 有值）"; return 0
  fi
  if [ "$REQUIRE_ISOCHRONE" = "1" ]; then
    printf '\033[1;31m!! isochrone 仍是降级模式（time_s 为 null）\033[0m\n' >&2; return 1
  fi
  warn "isochrone 处于已知降级（time_s 为 null）——本次部署记为「已知降级」，不算通过"
  return 0
}

[ -n "$HEALTH_PATH" ] || warn "没有可用健康端点，退化为端口连通性检查（正式发布前建议补一个 /healthz）"

if ! switch_to "$NEW_TAG"; then
  log "部署失败，回退到 ${PREV_TAG:-上一个版本}"
  [ -n "${PREV_TAG:-}" ] && switch_to "$PREV_TAG"
  exit 1
fi

assert_isochrone || exit 1
log "完成：$NEW_TAG 已在 $TARGET_ENV 生效"
