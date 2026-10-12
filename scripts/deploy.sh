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
#   FRONTEND_DIR      前端产物解包目录，默认 $APP_DIR/apps/web/dist
#   FRONTEND_ASSET_PREFIX  前端 Release 资产名前缀，默认 lifetrip-web
#   ALLOW_FRONTEND_MISSING 1 = 目标 tag 的 Release 没有前端资产时只告警不失败（默认 0：硬失败）
#   GITHUB_TOKEN      可选，仅私有仓库取资产时需要（LifeTrip 是 public，通常不需要）
#
# REL-16：前端产物按 tag 从 GitHub Release 下载（<prefix>-<tag>.tar.gz），
# 并用同一 Release 的 manifest.json 里的 frontend_artifact.sha256 校验。
# 取不到 / 校验不过 / 包结构不对 —— 一律退出码非 0，绝不当没事发生。
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

FRONTEND_DIR="${FRONTEND_DIR:-$APP_DIR/apps/web/dist}"
FRONTEND_ASSET_PREFIX="${FRONTEND_ASSET_PREFIX:-lifetrip-web}"
ALLOW_FRONTEND_MISSING="${ALLOW_FRONTEND_MISSING:-0}"
FRONTEND_STAGE=""
FRONTEND_STATE="untouched"

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
  echo "前端产物  : $FRONTEND_DIR（按 tag 从 Release 取 ${FRONTEND_ASSET_PREFIX}-<tag>.tar.gz）"
  if [ -f "$APP_DIR/.deployed-frontend" ]; then
    sed 's/^/            /' "$APP_DIR/.deployed-frontend"
  else
    echo "            （尚无记录：REL-16 之前的部署没有留前端状态）"
  fi
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

# ---------------- 前端产物（REL-16） ----------------
# 契约：Release 资产 <prefix>-<tag>.tar.gz，归档根是 dist/；
#       同一 Release 的 manifest.json 里 frontend_artifact.sha256 是它的摘要。
# 找不到 / 下不动 / 摘要不符 / 包结构不对 → 一律返回 1。绝不静默跳过。

repo_slug(){
  local url
  url="$(git -C "$APP_DIR" remote get-url origin 2>/dev/null || true)"
  case "$url" in
    https://github.com/*) printf '%s' "${url#https://github.com/}" | sed 's/\.git$//' ;;
    git@github.com:*)     printf '%s' "${url#git@github.com:}"   | sed 's/\.git$//' ;;
    *) return 1 ;;
  esac
}

frontend_asset_url(){
  printf 'https://github.com/%s/releases/download/%s/%s' "$1" "$2" "$3"
}

_fetch_with_auth(){
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    curl -fsSL --retry 3 --retry-delay 2 -H "Authorization: Bearer ${GITHUB_TOKEN}" -o "$2" "$1"
  else
    curl -fsSL --retry 3 --retry-delay 2 -o "$2" "$1"
  fi
}

# 只下载 + 校验，不改动线上任何文件；成功时把待落位的内容留在 $FRONTEND_STAGE。
fetch_frontend(){
  local ref="$1" slug asset work tarball mfe have
  FRONTEND_STAGE=""

  if ! git -C "$APP_DIR" rev-parse --verify "refs/tags/$ref" >/dev/null 2>&1; then
    if [ "$ALLOW_FRONTEND_MISSING" = "1" ]; then
      warn "ref=$ref 不是 tag：前端产物只按 tag 交付，本次跳过前端、只切后端——已在摘要里标注"
      FRONTEND_STATE="skipped-not-a-tag:$ref"
      return 0
    fi
    warn "ref=$ref 不是 tag：无法确定该取哪一份前端产物。确实要「只切后端」请显式加 ALLOW_FRONTEND_MISSING=1。"
    return 1
  fi

  case "$FRONTEND_DIR" in
    "$APP_DIR"/*) ;;
    *) warn "FRONTEND_DIR=$FRONTEND_DIR 不在 APP_DIR=$APP_DIR 之内，拒绝对它做任何移动"; return 1 ;;
  esac

  slug="$(repo_slug || true)"
  [ -n "$slug" ] || { warn "读不到 origin 的 GitHub 仓库地址，无法按 tag 下载前端产物"; return 1; }

  asset="${FRONTEND_ASSET_PREFIX}-${ref}.tar.gz"
  work="$(mktemp -d)" || { warn "建临时目录失败"; return 1; }
  tarball="$work/$asset"

  log "取前端产物：$(frontend_asset_url "$slug" "$ref" "$asset")"
  if ! _fetch_with_auth "$(frontend_asset_url "$slug" "$ref" "$asset")" "$tarball"; then
    warn "下载前端产物失败：$asset（release 不存在 / 该 tag 没有前端资产 / 网络不通）"
    rm -rf "$work"
    if [ "$ALLOW_FRONTEND_MISSING" = "1" ]; then
      warn "ALLOW_FRONTEND_MISSING=1：本次前端保持现状、只切后端——已在摘要里标注"
      FRONTEND_STATE="skipped-missing-asset:$ref"
      return 0
    fi
    return 1
  fi
  have="$(sha256sum "$tarball" | cut -d' ' -f1)"

  mfe=""
  if _fetch_with_auth "$(frontend_asset_url "$slug" "$ref" manifest.json)" "$work/manifest.json"; then
    mfe="$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print((d.get("frontend_artifact") or {}).get("sha256","") or "")' "$work/manifest.json" 2>/dev/null || true)"
  fi
  if [ -n "$mfe" ]; then
    if [ "$mfe" != "$have" ]; then
      warn "前端产物摘要不符：manifest 里 $mfe，实际 $have。拒绝落位。"
      rm -rf "$work"; return 1
    fi
    log "前端产物摘要与 manifest 一致：${have:0:16}…"
  elif [ "$ALLOW_FRONTEND_MISSING" = "1" ]; then
    warn "该 Release 的 manifest.json 没有 frontend_artifact.sha256（历史标签），跳过摘要校验：${have:0:16}…"
  else
    warn "该 Release 的 manifest.json 缺少 frontend_artifact.sha256，无法校验前端产物；拒绝落位。"
    rm -rf "$work"; return 1
  fi

  mkdir -p "$work/unpack"
  if ! tar -xzf "$tarball" -C "$work/unpack"; then
    warn "前端产物解包失败：$asset"; rm -rf "$work"; return 1
  fi
  if [ ! -f "$work/unpack/dist/index.html" ]; then
    warn "前端产物里没有 dist/index.html（包结构不符合契约）"; rm -rf "$work"; return 1
  fi

  FRONTEND_STAGE="$work"
  FRONTEND_REF="$ref"
  FRONTEND_SHA="$have"
  FRONTEND_ASSET="$asset"
  FRONTEND_STATE="staged:$ref"
  return 0
}

# 把 $FRONTEND_STAGE 里的 dist 原子落到 $FRONTEND_DIR（先在同目录改名，再 mv）。
apply_frontend(){
  [ -n "${FRONTEND_STAGE:-}" ] || return 0
  local parent new old
  parent="$(dirname "$FRONTEND_DIR")"
  mkdir -p "$parent" || { warn "建 $parent 失败"; return 1; }
  new="$parent/.dist.new.$$"
  old="$parent/.dist.old.$$"
  rm -rf "$new" "$old"
  if ! mv "$FRONTEND_STAGE/unpack/dist" "$new"; then
    warn "前端产物准备落位失败：$new"; rm -rf "$FRONTEND_STAGE"; FRONTEND_STAGE=""; return 1
  fi
  if [ -e "$FRONTEND_DIR" ]; then
    if ! mv "$FRONTEND_DIR" "$old"; then
      warn "移开旧前端产物失败：$FRONTEND_DIR"; rm -rf "$new" "$FRONTEND_STAGE"; FRONTEND_STAGE=""; return 1
    fi
  fi
  if ! mv "$new" "$FRONTEND_DIR"; then
    warn "前端产物落位失败，尝试把旧产物放回去"
    [ -e "$old" ] && mv "$old" "$FRONTEND_DIR"
    rm -rf "$new" "$FRONTEND_STAGE"; FRONTEND_STAGE=""; return 1
  fi
  rm -rf "$old" "$FRONTEND_STAGE"; FRONTEND_STAGE=""
  printf 'tag=%s\nsha256=%s\nasset=%s\napplied_at=%s\n' \
    "$FRONTEND_REF" "$FRONTEND_SHA" "$FRONTEND_ASSET" "$(date -u +%FT%TZ)" \
    > "$APP_DIR/.deployed-frontend" 2>/dev/null || true
  log "前端产物已就位：$FRONTEND_DIR（${FRONTEND_ASSET}）"
  FRONTEND_STATE="installed:$FRONTEND_REF:${FRONTEND_SHA:0:12}"
  return 0
}

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
  # 先把前端产物下载+校验好：这一步失败时代码还没切、服务没重启，等于零改动。
  if ! fetch_frontend "$ref"; then
    warn "前端产物取不到，放弃本次切换（代码未切、服务未重启）"
    return 1
  fi
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
  # REL-16：前端产物落位（不在服务器上跑 Node 构建——2C4G 会与 OpenClaw 抢内存）
  if ! apply_frontend; then
    warn "前端产物落位失败，放弃本次切换（服务未重启）"
    return 1
  fi
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
log "完成：$NEW_TAG 已在 $TARGET_ENV 生效（HEAD=$(git -C "$APP_DIR" rev-parse --short HEAD)；前端 $FRONTEND_STATE）"
