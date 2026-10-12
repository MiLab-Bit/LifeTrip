#!/usr/bin/env bash
# REL-10 · 部署脚本：按 tag/ref 拉取 -> 重启服务 -> 健康检查 -> 失败自动回退
#
# 用法：
#   bash scripts/deploy.sh --detect        # 只读体检：认成什么服务 / 端口 / 健康端点，不做任何改动
#   bash scripts/deploy.sh <tag|ref>       # 真正部署
#
# 可用环境变量（全部可选）：
#   APP_DIR           代码目录，默认 /opt/lifetrip
#   SERVICE           systemd 服务名；不设则自动识别（识别结果必须真的指向 APP_DIR）
#   PORT              服务端口；不设则从单元文件里读
#   HEALTH_PATH       健康端点路径；不设则按候选列表探测
#   TARGET_ENV        仅用于日志，默认 staging
#   ISOCHRONE_PROBE   isochrone 业务断言探针 URL
#   REQUIRE_ISOCHRONE 1 = isochrone 仍降级则算失败（默认 0，只记「已知降级」）
#   POST_DEPLOY_CMD   部署后置校验命令；非 0 视为部署失败并触发回退
#   ROLLBACK_TO       指定回退目标（默认取目标 ref 之前最近的 tag）
#   FORCE_SERVICE=1   允许 SERVICE 与 APP_DIR 不一致（默认不允许，见下方护栏）
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/lifetrip}"
TARGET_ENV="${TARGET_ENV:-staging}"
WANT_KEEP="${KEEP_COMMITS:-5}"

log(){ printf '\n\033[1;32m==> [%s] %s\033[0m\n' "$TARGET_ENV" "$*"; }
# 提示一律走 stderr：这些函数会在命令替换 $( ) 里被调用，
# 任何多余的 stdout 输出都会污染它们的返回值（踩过一次）。
warn(){ printf '\033[1;33m注意：%s\033[0m\n' "$*" >&2; }
die(){ printf '\033[1;31m错误：%s\033[0m\n' "$*" >&2; exit 1; }

# ---------------- 服务识别 ----------------
# 关键护栏：服务必须「真的」指向 APP_DIR。
# 反例：/opt/lifetrip 是 /opt/lifetrip-staging 的子串，用名字模糊匹配会把
# staging 部署打到生产服务 lifetrip-api 上。

unit_matches_dir(){
  local name="$1" wd ex
  wd="$(systemctl show -p WorkingDirectory --value "$name" 2>/dev/null || true)"
  [ "$wd" = "$APP_DIR" ] && return 0
  ex="$(systemctl show -p ExecStart --value "$name" 2>/dev/null || true)"
  case "$ex" in *"path=${APP_DIR}/"*) return 0 ;; esac
  systemctl cat "$name" 2>/dev/null \
    | grep -qE "(WorkingDirectory|--chdir)=${APP_DIR}([[:space:]]|\$)" && return 0
  return 1
}

all_services(){
  systemctl list-units --type=service --all --no-legend 2>/dev/null \
    | awk '{print $1}' | sed 's/\.service$//'
}

detect_service(){
  local name matches
  matches=""
  for name in $(all_services); do
    if unit_matches_dir "$name"; then matches="$matches $name"; fi
  done
  matches="$(printf '%s' "$matches" | tr ' ' '\n' | sed '/^$/d')"
  [ -z "$matches" ] && return 1
  # 同一目录可能有多个单元（api / worker）。部署面对的是 HTTP 服务，优先 api。
  if [ "$(printf '%s\n' "$matches" | wc -l)" -gt 1 ]; then
    warn "同一目录下有多个单元：$(printf '%s ' $matches)"
    warn "本次选 API 类单元；若不对，用 SERVICE=<名> 显式指定。"
  fi
  printf '%s\n' "$matches" | grep -iE '(^|-)api$|api[-.]' | head -1 && return 0
  printf '%s\n' "$matches" | grep -iE 'web|staging|app' | head -1 && return 0
  printf '%s\n' "$matches" | head -1
}

port_from_unit(){
  # 只看 ExecStart 行：单元里别的行也可能有端口（例如 Environment=LIFETRIP_OSRM_URL=http://127.0.0.1:5000
  # 会让朴素的全文匹配读出 5000，把健康探测打到错误的端口上——踩过一次）。
  local port
  port="$(systemctl cat "$1" 2>/dev/null | grep -E '^ExecStart' \
    | grep -oE -- '--port[[:space:]]+[0-9]{4}' | grep -oE '[0-9]{4}' | head -1)"
  [ -n "$port" ] && { printf '%s' "$port"; return 0; }
  port="$(systemctl cat "$1" 2>/dev/null | grep -E '^ExecStart' \
    | grep -oE '(127\.0\.0\.1|0\.0\.0\.0):[0-9]{4}' | grep -oE '[0-9]{4}' | head -1)"
  [ -n "$port" ] && { printf '%s' "$port"; return 0; }
  return 1
}

detect_health(){
  local p
  # 候选顺序：先用本套件自带的端点，再退到常见约定。
  for p in ${HEALTH_PATH:-/v1/health /healthz /health /api/health /healthcheck /}; do
    if curl -fsS --max-time 5 "http://127.0.0.1:${PORT}${p}" >/dev/null 2>&1; then
      printf '%s' "$p"; return 0
    fi
  done
  return 1
}

unit_env_keys(){
  systemctl cat "$1" 2>/dev/null | grep -oE '^Environment=[A-Za-z_][A-Za-z0-9_]*' | sed 's/^Environment=//'
}

[ -d "$APP_DIR" ] || die "APP_DIR 不存在：$APP_DIR"
APP_DIR="$(cd "$APP_DIR" && pwd -P)"

if [ -n "${SERVICE:-}" ]; then
  if ! unit_matches_dir "$SERVICE"; then
    if [ "${FORCE_SERVICE:-0}" = "1" ]; then
      warn "SERVICE=$SERVICE 并不指向 APP_DIR=$APP_DIR，但 FORCE_SERVICE=1，继续。"
    else
      die "SERVICE=$SERVICE 的单元文件并不指向 APP_DIR=$APP_DIR。
     这通常意味着你会把部署打到另一个环境（例如用 /opt/lifetrip 的代码去重启 lifetrip-staging）。
     确认要用就加 FORCE_SERVICE=1。"
    fi
  fi
else
  SERVICE="$(detect_service || true)"
fi
SERVICE="${SERVICE:-}"
if [ -n "$SERVICE" ]; then
  PORT="${PORT:-$(port_from_unit "$SERVICE" || true)}"
  if [ -z "${HEALTH_PATH:-}" ]; then HEALTH_PATH="$(detect_health || true)"; fi
fi
PORT="${PORT:-8800}"

# ---------------- --detect：只读体检 ----------------
if [ "${1:-}" = "--detect" ]; then
  echo "代码目录  : $APP_DIR $( [ -d "$APP_DIR/.git" ] && echo '（git 仓库）' || echo '（⚠ 不是 git 仓库）' )"
  if [ -n "$SERVICE" ]; then
    echo "服务名    : $SERVICE  $( unit_matches_dir "$SERVICE" && echo '（单元确实指向本目录 ✅）' || echo '（单元未指向本目录 ⚠）' )"
  else
    echo "服务名    : ⚠ 识别不到指向本目录的 systemd 单元（静态站点/未注册服务就是这种情形）"
  fi
  echo "端口      : ${PORT:-未识别}"
  if [ -n "${HEALTH_PATH:-}" ]; then
    echo "健康端点  : http://127.0.0.1:${PORT}${HEALTH_PATH}  ✅ 有响应"
  else
    echo "健康端点  : ⚠ 候选路径都无响应，部署时只能退化为端口连通性检查"
  fi
  echo "当前版本  : $(git -C "$APP_DIR" describe --tags --always 2>/dev/null || echo '（不是 git 仓库）')  HEAD=$(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || echo '-')"
  if [ -n "$SERVICE" ]; then
    echo "启动命令  :"; systemctl cat "$SERVICE" 2>/dev/null | grep -E '^ExecStart' || echo "  （读不到单元文件）"
    echo "工作目录  :"; systemctl cat "$SERVICE" 2>/dev/null | grep -E '^WorkingDirectory' || echo "  （未设置）"
    echo "环境变量键名（值已隐藏）:"; unit_env_keys "$SERVICE" | sed 's/^/  - /' || true
    echo "OSRM 相关 :"; unit_env_keys "$SERVICE" | grep -iE 'osrm|route' | sed 's/^/  - /' || echo "  - 没有任何 OSRM 相关键（isochrone 很可能降级）"
  fi
  echo "结论      : $( [ -n "$SERVICE" ] && echo '可部署（deploy.sh <tag|ref>）' || echo '本目录没有可部署服务，deploy.sh 不适用' )"
  exit 0
fi

[ -n "$SERVICE" ] || die "识别不到指向 $APP_DIR 的 systemd 单元，请用 SERVICE=<名> 显式指定（静态站点没有 systemd 单元，应改用站点自己的发布方式）。"

# ---------------- 正式部署 ----------------
NEW_TAG="${1:?用法: deploy.sh <tag|ref> 或 deploy.sh --detect}"
PREV_TAG="${ROLLBACK_TO:-}"
if [ -z "$PREV_TAG" ]; then
  PREV_TAG="$(git -C "$APP_DIR" describe --tags --abbrev=0 "${NEW_TAG}^" 2>/dev/null || true)"
fi

healthy(){
  local i
  for i in $(seq 1 20); do
    if [ -n "${HEALTH_PATH:-}" ]; then
      curl -fsS --max-time 5 "http://127.0.0.1:${PORT}${HEALTH_PATH}" >/dev/null && return 0
    else
      curl -fsS --max-time 5 -o /dev/null "http://127.0.0.1:${PORT}/" && return 0
    fi
    sleep 3
  done
  return 1
}

switch_to(){
  local ref="$1" want have
  log "切换到 $ref"
  # 注意：本函数会在 `if ! switch_to ...` 里被调用，那个上下文下 bash 会
  # 关掉调用栈内的 errexit —— 所以每一步都必须显式判错，不能靠 set -e。
  # （演练时踩过：ref 写错时 checkout 报错但脚本继续跑，重启后健康检查通过，
  #   最后打印「完成：<不存在的 ref> 已在 staging 生效」并返回 0。）
  git -C "$APP_DIR" fetch --tags --prune origin \
    || { warn "git fetch 失败，放弃本次切换"; return 1; }
  git -C "$APP_DIR" checkout --force "$ref" \
    || { warn "git checkout 到 $ref 失败（ref 不存在或工作区冲突），放弃本次切换"; return 1; }
  want="$(git -C "$APP_DIR" rev-parse --verify "${ref}^{commit}" 2>/dev/null || true)"
  have="$(git -C "$APP_DIR" rev-parse HEAD 2>/dev/null || true)"
  if [ -z "$have" ]; then
    warn "读不到 HEAD，放弃本次切换"; return 1
  fi
  if [ -n "$want" ] && [ "$want" != "$have" ]; then
    warn "切换后 HEAD=${have:0:12} 与目标 ${want:0:12} 不一致，放弃本次切换"; return 1
  fi
  # 前端 dist 由 CI 构建后一起取；不在服务器上跑 Node 构建（2C4G 会与 OpenClaw 抢内存）
  systemctl restart "$SERVICE"
  if healthy; then
    log "健康检查通过：$ref  （HEAD=$(git -C "$APP_DIR" rev-parse --short HEAD)）"
    return 0
  fi
  warn "健康检查未通过：$ref"
  return 1
}

post_deploy_check(){
  [ -n "${POST_DEPLOY_CMD:-}" ] || return 0
  log "后置校验：$POST_DEPLOY_CMD"
  if sh -c "$POST_DEPLOY_CMD"; then log "后置校验通过"; return 0; fi
  warn "后置校验未通过"
  return 1
}

assert_isochrone(){
  [ -n "${ISOCHRONE_PROBE:-}" ] || { warn "未配置 ISOCHRONE_PROBE，跳过业务断言"; return 0; }
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

[ -n "${HEALTH_PATH:-}" ] || warn "没有可用健康端点，退化为端口连通性检查（正式发布前建议补一个）"

if ! switch_to "$NEW_TAG"; then
  if [ -n "${PREV_TAG:-}" ]; then
    log "部署失败，回退到 ${PREV_TAG}"
    if switch_to "$PREV_TAG"; then
      warn "已回退到 $PREV_TAG；本次发布失败，但线上是可用版本。"
    else
      warn "回退后健康检查仍不通过——需要人工介入。"
    fi
  else
    warn "目标 ref 之前没有更早的 tag，无法自动回退（只有一次发布过就会有）。"
    warn "手动回退：ROLLBACK_TO=<上一个可用的 tag|commit> bash scripts/deploy.sh <同一个 ref>"
  fi
  exit 1
fi

post_deploy_check || { log "后置校验失败，回退到 ${PREV_TAG:-无}"; [ -n "${PREV_TAG:-}" ] && switch_to "$PREV_TAG"; exit 1; }
assert_isochrone || exit 1
log "完成：$NEW_TAG 已在 $TARGET_ENV 生效（HEAD=$(git -C "$APP_DIR" rev-parse --short HEAD)）"
