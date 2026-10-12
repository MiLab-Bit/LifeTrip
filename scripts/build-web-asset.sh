#!/usr/bin/env bash
# REL-16 · 构建前端产物并打包成「跟 tag 绑定」的 Release 资产
#
# 为什么有它：apps/web/dist 被 .gitignore 排除、不进仓库，前端因此不在 tag 里，
# 「前后端同 tag 一起回滚」不成立。本脚本把构建产物做成可下载、可校验的资产，
# 让 release-cut 在打 tag 时产出它，让 deploy.sh 能按 tag 取回来。
#
# 用法：
#   bash scripts/build-web-asset.sh <ref>        # ref 通常就是 tag 名，用来命名产物
#
# 环境变量（全部可选）：
#   WEB_PACKAGE  = @lifetrip/web   要构建的工作区包名
#   WEB_DIR      = apps/web/dist   构建产物目录（相对工作区根）
#   ASSET_PREFIX = lifetrip-web    资产名前缀
#   OUT_DIR      = $PWD            资产与 web-asset.env 的输出目录
#   SKIP_INSTALL = 1               跳过依赖安装（CI 前一步已装好依赖时用）
#   SKIP_BUILD   = 1               跳过构建、直接打包已有产物（仅调试用）
#
# 产出：
#   <OUT_DIR>/<ASSET_PREFIX>-<ref>.tar.gz   （归档内是 dist/ 一层目录）
#   <OUT_DIR>/web-asset.env                 （ASSET_NAME / ASSET_PATH / ASSET_SHA256 / ASSET_SIZE）
# 退出码：0 = 产物已生成并校验通过；非 0 = 任一步失败。绝不「安静地跳过」。
set -euo pipefail

REF="${1:?用法: bash scripts/build-web-asset.sh <ref>（用 tag 名命名产物）}"
WEB_PACKAGE="${WEB_PACKAGE:-@lifetrip/web}"
WEB_DIR="${WEB_DIR:-apps/web/dist}"
ASSET_PREFIX="${ASSET_PREFIX:-lifetrip-web}"
OUT_DIR="${OUT_DIR:-$PWD}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

log(){ printf '==> %s\n' "$*"; }
die(){ printf '错误：%s\n' "$*" >&2; exit 1; }

# 1) 工作区根：pnpm/yarn/npm 工作区的锁文件在【根目录】，
#    成员包目录里找不到锁文件，所以从锁文件反推根，不靠猜。
LOCK="$(find . -maxdepth 4 \( -name pnpm-lock.yaml -o -name yarn.lock -o -name package-lock.json \) \
        -not -path '*/node_modules/*' | head -1)"
[ -n "$LOCK" ] || die "找不到锁文件（pnpm-lock.yaml / yarn.lock / package-lock.json），无法确定工作区根"
WS="$(dirname "$LOCK")"
log "工作区根：$WS（锁文件 $LOCK）"

# 2) 包管理器：pnpm 版本取仓库 package.json 的 packageManager，不猜版本
case "$LOCK" in
  *pnpm-lock.yaml)
    if [ "${SKIP_INSTALL:-0}" != "1" ] || ! command -v pnpm >/dev/null 2>&1; then
      PM="$(sed -nE 's/.*"packageManager"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' "$WS/package.json" | head -1)"
      [ -n "$PM" ] || PM="pnpm@9.15.0"
      log "启用包管理器：$PM"
      corepack enable 2>/dev/null || true
      corepack prepare "$PM" --activate
    fi
    ;;
  *yarn.lock)         command -v yarn >/dev/null 2>&1 || die "仓库用 yarn，但环境里没有 yarn" ;;
  *package-lock.json) : ;;
  *) die "不支持的锁文件：$LOCK" ;;
esac

install_deps(){
  case "$LOCK" in
    *pnpm-lock.yaml)    ( cd "$WS" && pnpm install --frozen-lockfile ) ;;
    *yarn.lock)         ( cd "$WS" && yarn install --frozen-lockfile ) ;;
    *package-lock.json) ( cd "$WS" && npm ci ) ;;
  esac
}

build_web(){
  case "$LOCK" in
    *pnpm-lock.yaml)    ( cd "$WS" && pnpm --filter "$WEB_PACKAGE" build ) ;;
    *yarn.lock)         ( cd "$WS" && yarn workspace "$WEB_PACKAGE" build ) ;;
    *package-lock.json) ( cd "$WS" && npm run build ) ;;
  esac
}

if [ "${SKIP_INSTALL:-0}" = "1" ]; then
  log "SKIP_INSTALL=1：复用已装好的依赖"
else
  log "安装依赖（--frozen-lockfile）"
  install_deps
fi

if [ "${SKIP_BUILD:-0}" = "1" ]; then
  log "SKIP_BUILD=1：复用已有构建产物"
else
  log "构建 $WEB_PACKAGE（apps/web 的 build 脚本：tsc -b && vite build）"
  build_web
fi

# 3) 校验产物：没有 index.html 就是构建没产出可用前端
SRC="$WS/$WEB_DIR"
[ -f "$SRC/index.html" ] || die "构建产物里没有 $WEB_DIR/index.html（构建未产出可用前端）"

# 4) 打包：归档内保留 dist/ 一层，部署端解包后直接得到 dist
ASSET="${ASSET_PREFIX}-${REF}.tar.gz"
mkdir -p "$OUT_DIR"
tar -czf "$OUT_DIR/$ASSET" -C "$(dirname "$SRC")" "$(basename "$WEB_DIR")"

ASSET_SHA256="$(sha256sum "$OUT_DIR/$ASSET" | cut -d' ' -f1)"
ASSET_SIZE="$(wc -c < "$OUT_DIR/$ASSET" | tr -d ' ')"
cat > "$OUT_DIR/web-asset.env" <<ENV
ASSET_NAME=$ASSET
ASSET_PATH=$OUT_DIR/$ASSET
ASSET_SHA256=$ASSET_SHA256
ASSET_SIZE=$ASSET_SIZE
ENV

log "前端产物就绪：$ASSET（${ASSET_SIZE} 字节，sha256=$ASSET_SHA256）"
cat "$OUT_DIR/web-asset.env"
