#!/usr/bin/env bash
# 零配置发布前门禁：自动识别这个仓库里有哪些检查项，跑得动就跑，识别不到就跳过并说明缺什么。
# 用法：bash scripts/preflight.sh        （在仓库里任意目录都能跑）
# 退出码：0 = 没有任何 FAIL（SKIP 不算失败）；1 = 至少有一项 FAIL。
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

C_RESET=$'\033[0m'; C_OK=$'\033[1;32m'; C_BAD=$'\033[1;31m'; C_WARN=$'\033[1;33m'; C_DIM=$'\033[2m'
PASS=0; FAIL=0; SKIP=0
FAILED_ITEMS=(); SKIPPED_ITEMS=()

ok(){  PASS=$((PASS+1)); printf '%s[PASS]%s %s\n' "$C_OK" "$C_RESET" "$1"; }
bad(){ FAIL=$((FAIL+1)); FAILED_ITEMS+=("$1"); printf '%s[FAIL]%s %s\n' "$C_BAD" "$C_RESET" "$1"; }
skp(){ SKIP=$((SKIP+1)); SKIPPED_ITEMS+=("$1"); printf '%s[SKIP]%s %s\n' "$C_WARN" "$C_RESET" "$1"; }
sec(){ printf '\n%s---- %s ----%s\n' "$C_DIM" "$1" "$C_RESET"; }

find_first(){ local p; for p in "$@"; do [ -e "$p" ] && { printf '%s' "$p"; return 0; }; done; return 1; }

printf '仓库：%s\n' "$REPO_ROOT"

# ======================= 环境自动识别 =======================
PY=""
for c in .venv/bin/python venv/bin/python env/bin/python; do
  [ -x "$c" ] && PY="$REPO_ROOT/$c" && break
done
[ -z "$PY" ] && PY="$(command -v python3 || command -v python || true)"

FRONTEND_DIR=""
tsc_cfg="$(find . -maxdepth 4 -name tsconfig.json -not -path '*/node_modules/*' 2>/dev/null | head -1)"
pkg="$(find . -maxdepth 3 -name package.json -not -path '*/node_modules/*' 2>/dev/null | head -1)"
[ -n "$tsc_cfg" ] && FRONTEND_DIR="$(dirname "$tsc_cfg")"
if [ -z "$FRONTEND_DIR" ] && [ -n "$pkg" ]; then FRONTEND_DIR="$(dirname "$pkg")"; fi

printf 'python：%s\n' "${PY:-未找到}"
printf '前端目录：%s\n' "${FRONTEND_DIR:-未找到 package.json}"

# ======================= 1/5 pytest =======================
sec "1/5 pytest"
if [ -z "$PY" ]; then
  skp "找不到 python 解释器"
elif ! "$PY" -c "import pytest" >/dev/null 2>&1; then
  skp "环境里没有 pytest（先装依赖：$PY -m pip install -r requirements.txt）"
elif [ ! -d tests ] && [ ! -d test ] && [ ! -e pytest.ini ] && [ ! -e tox.ini ] && [ ! -e setup.cfg ] && [ ! -e pyproject.toml ]; then
  skp "没找到测试目录或 pytest 配置"
else
  if "$PY" -m pytest -q; then ok "pytest 全绿"; else bad "pytest 未通过"; fi
fi

# ======================= 2/5 前端类型检查 =======================
sec "2/5 前端类型检查 tsc --noEmit"
if [ -z "$FRONTEND_DIR" ]; then
  skp "没有前端（未找到 package.json）"
elif [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  skp "$FRONTEND_DIR 尚未安装依赖（装完再来跑这一步）"
elif grep -q '"typescript"' "$FRONTEND_DIR/package.json" 2>/dev/null; then
  if grep -q '"typecheck"' "$FRONTEND_DIR/package.json" 2>/dev/null; then
    if ( cd "$FRONTEND_DIR" && npm run -s typecheck ); then
      ok "类型检查零错误（$FRONTEND_DIR 的 typecheck）"
    else
      bad "类型检查未通过（$FRONTEND_DIR）"
    fi
  elif ( cd "$FRONTEND_DIR" && npx --no-install tsc --noEmit ); then
    ok "tsc --noEmit 零错误"
  else
    bad "tsc 有类型错误"
  fi
else
  skp "$FRONTEND_DIR 里没有 typescript 依赖"
fi

# ======================= 3/5 eval 回归题 =======================
sec "3/5 eval 回归题"
EVAL_DIR="$(find_first content/eval eval content/evaluations evals || true)"
if [ -z "$EVAL_DIR" ]; then
  skp "没找到 eval 目录（试过 content/eval、eval、content/evaluations、evals）"
else
  n="$(find "$EVAL_DIR" -type f \( -name '*.json' -o -name '*.yaml' -o -name '*.yml' \) 2>/dev/null | wc -l | tr -d ' ')"
  printf '  识别到 %s（题目文件约 %s 个）\n' "$EVAL_DIR" "$n"
  RAN=0; REALFAILCMD=""; REALFAILOUT=""
  for cmd in \
      "$PY -m content.eval.run --all" \
      "$PY -m eval.run --all" \
      "$PY -m eval --all" \
      "$PY $EVAL_DIR/run.py --all" \
      "$PY $EVAL_DIR/run_eval.py" \
      "$PY $EVAL_DIR/main.py" \
      $( ls "$EVAL_DIR"/*.py >/dev/null 2>&1 && echo "$PY -m pytest $EVAL_DIR -q" ) \
      "$PY -m pytest tests/ -q" ; do
    out="$($cmd 2>&1)"; rc=$?
    if [ $rc -eq 0 ]; then RAN=1; printf '  入口：%s\n' "$cmd"; break; fi
    if printf '%s' "$out" | grep -qiE "No module named|can't open file|No such file|not found"; then continue; fi
    RAN=1; REALFAILCMD="$cmd"; REALFAILOUT="$(printf '%s' "$out" | tail -4)"; break
  done
  if [ "$RAN" -eq 0 ]; then
    skp "识别到 $EVAL_DIR，但没有可调用的入口（题库是数据文件，断言通常在 tests/ 内）"
  elif [ -n "$REALFAILCMD" ]; then
    printf '%s\n' "$REALFAILOUT"
    bad "eval 回归题未通过（$REALFAILCMD）"
  else
    ok "eval 回归题通过"
  fi
fi

# ======================= 4/5 离线冒烟 =======================
sec "4/5 离线接口冒烟"
SMOKE="$(find_first tests/smoke.py smoke.py scripts/smoke.sh tests/test_smoke.py tests/smoke_test.py scripts/smoke.py || true)"
if [ -z "$SMOKE" ] && [ -f Makefile ] && grep -qE '^smoke:' Makefile; then SMOKE="__make__"; fi
if [ -z "$SMOKE" ]; then
  skp "没找到冒烟入口（试过 tests/smoke.py、scripts/smoke.sh、tests/test_smoke.py、make smoke）"
else
  case "$SMOKE" in
    __make__)            CMD="make smoke" ;;
    *.sh)                CMD="bash $SMOKE" ;;
    */test_*|*/test_*)   CMD="$PY -m pytest $SMOKE -q" ;;
    *)                   CMD="$PY $SMOKE" ;;
  esac
  if $CMD; then ok "离线冒烟通过"; else bad "离线冒烟未通过"; fi
  printf '  命令：%s\n' "$CMD"
fi

# ======================= 5/5 git 状态（提醒性质，不算失败）=======================
sec "5/5 git 状态"
if [ -d .git ]; then
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    skp "工作区有未提交改动（发布前建议先提交或暂存）"
  else
    ok "工作区干净"
  fi
  if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
    ahead="$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)"
    if [ "${ahead:-0}" -gt 0 ]; then skp "有 $ahead 个 commit 还没推到远端"; else ok "与远端同步"; fi
  else
    skp "当前分支没有配置上游远端"
  fi
else
  skp "不在 git 仓库里"
fi

# ======================= 汇总 =======================
printf '\n%s================ 汇总 ================%s\n' "$C_DIM" "$C_RESET"
printf 'PASS %s ｜ FAIL %s ｜ SKIP %s\n' "$PASS" "$FAIL" "$SKIP"

if [ "$SKIP" -gt 0 ]; then
  printf '\n%s被跳过的项（不是失败，只是这个仓库里还识别不到）：%s\n' "$C_WARN" "$C_RESET"
  for i in "${SKIPPED_ITEMS[@]}"; do printf '  · %s\n' "$i"; done
fi

if [ "$FAIL" -gt 0 ]; then
  printf '\n%s门禁未通过：%s\n' "$C_BAD" "$C_RESET"
  for i in "${FAILED_ITEMS[@]}"; do printf '  · %s\n' "$i"; done
  exit 1
fi

printf '\n%s门禁通过（没有失败项，可以打 tag）。%s\n' "$C_OK" "$C_RESET"
