# RELEASE · 发布流程与版本号方案（LifeTrip）

> 上游模板：`MiLab-Bit/milab-release`。**本文件是副本**——要改口径请改上游再同步。
> LifeTrip 是 REL 的**试点仓库**：唯一一个真正走完整条发布路径的仓库。

## 0. 本仓库现状（2026-10-12 实测）

| 项 | 值 |
|---|---|
| 代码目录 | `/opt/lifetrip`（生产） / `/opt/lifetrip-staging`（staging） |
| systemd 单元 | `lifetrip-api`（8800） / `lifetrip-worker` / `lifetrip-staging`（8801） |
| 健康端点 | `GET /v1/health`（**不是 `/healthz`**） |
| 线上域名 | `lifetrip.sy-realm.ltd` |
| 当前 tag | **`v2026.10.2`** → commit `1f38bbf`，线上实测即此版本（前端产物 `lifetrip-web-v2026.10.2.tar.gz`） |
| release 附件 | `manifest.json` + `lifetrip-web-<tag>.tar.gz`（前端产物，**REL-16 起**） |
| workflow | `.github/workflows/`：`ci`（job `preflight`，含「前端产物可构建」）+ `release-cut`（tag 触发）+ `deploy-production`（手动触发，走 `production` Environment 审批） |
| 分支保护 | 已开（必需 `preflight`，strict=true，需 PR，禁 force push，`enforce_admins=false`） |
| tag ruleset | 已开（id 24875000 `protect-release-tags`，v* 禁删禁移） |
| Environment | `production`：required reviewers = 仓库属主（API 读回确认）；`deploy-production` 的 `deploy` job 引用它 → **审批闸门生效**（见第 6 节） |

## 1. 版本号方案
- 格式：`vYYYY.MM.<build>`，例 `v2026.10.1`。
- tag **只增不删、不可移动**（由 tag ruleset 强制，已实测删不掉）。

## 2. 发布步骤
1. 分支上完成改动 → PR 到 `main`，CI `preflight` 必须绿。
2. 本地复跑：`bash scripts/preflight.sh`。
3. 合并 PR。
4. 打 tag 并推送（**只由人工执行**）：`git tag -a v2026.10.2 -m "LifeTrip v2026.10.2" && git push origin v2026.10.2`
   → 触发 `release-cut`：**真的构建前端**、产出 `lifetrip-web-<tag>.tar.gz` 与 `manifest.json`。
5. 部署 staging：`APP_DIR=/opt/lifetrip-staging TARGET_ENV=staging bash scripts/deploy.sh v2026.10.2`
6. UAT 验收（`docs/DEPLOY.md` 第 4 节）。
7. 部署生产（两条路，二选一）：
   - **走 GitHub（常规路径，有审批闸门）**：Actions → `deploy-production` → Run workflow → 填 tag
     → 到本次运行的 `production` Environment 上点 **Approve and run**。
   - **服务器上手跑（紧急用，绕过闸门）**：
     `APP_DIR=/opt/lifetrip TARGET_ENV=production HEALTH_PATH=/v1/health bash scripts/deploy.sh v2026.10.2`

## 3. 验收命令
```bash
curl -fsS http://127.0.0.1:8800/v1/health
curl -s -X POST http://127.0.0.1:8800/v1/isochrone/analyze -H 'Content-Type: application/json' \
  -d '{"center":{"lat":31.2304,"lng":121.4737},"minutes":15}'
```
第二条必须是**上海市域内**的坐标，并检查 `degraded=false` 且射线 `time_s` 非 null。
字段名是 `lng` 不是 `lon`；顶层是 `center` 而非 `lat`/`lon`（写错会拿到 422）。

## 4. 回滚
```bash
git tag -l | sort -V | tail -3
APP_DIR=/opt/lifetrip TARGET_ENV=production bash scripts/deploy.sh <上一个 tag>
```
- 实测：staging 上单次回滚 **8 秒**（`milab-release/docs/REL-15-staging回滚演练-2026-10-12.md`）。
- **自动回退的真实边界**：脚本取「目标 ref 之前最近的 tag」。现在只有一个 tag，
  所以第一次发布的自动回退是空的；第二个 tag 出现后才会真正生效。
- **前端现在跟着 tag 走了（REL-16）**：`deploy.sh` 在切代码之前会先按 tag 从该 Release 下载
  `lifetrip-web-<tag>.tar.gz`，用同一 Release 的 `manifest.json` 里的 `frontend_artifact.sha256` 校验，
  再原子解包到 `$FRONTEND_DIR`（默认 `$APP_DIR/apps/web/dist`）。所以「前后端同 tag 一起回滚」成立。
- **取不到前端 = 部署失败**：下载失败 / 摘要不符 / 包结构不对，一律退出码非 0，**不会静默跳过**。
- **历史 tag 例外**：`v2026.10.1` 的 Release 只有 `manifest.json`（前端资产是 REL-16 才开始产出的）。
  回滚到这类 tag 会硬失败；只有显式加 `ALLOW_FRONTEND_MISSING=1` 才会「只切后端」并大声告警。
  要补齐历史 tag，用 `release-cut` 的 `workflow_dispatch` 指定该 tag 跑一次（只加资产，不动 tag）。

## 5. 同源纪律
`scripts/deploy.sh` / `CLAUDE.md` / `docs/DEPLOY.md` 都是 `milab-release` 的副本。
2026-10-12 上游与副本出现漂移（本仓库的 deploy.sh 比上游新），已把副本回灌上游。
**先改上游，再同步到本仓库。**

## 6. 已知缺口（如实记录）
- ~~`production` Environment 没有 workflow 使用它~~ → **REL-16 已接**：`.github/workflows/deploy-production.yml`
  的 `deploy` job 引用了 `production` Environment，**下一次走 GitHub 的生产部署会先停在「等待批准」**，
  由仓库属主点 Approve and run 才开始。
- ⚠ **它还跑不完**：Environment 里还没有 3 个 secret（`LIFETRIP_DEPLOY_HOST` / `LIFETRIP_DEPLOY_USER` /
  `LIFETRIP_SSH_KEY`），**必须由本人添加**（我方不动她账号里的凭据），步骤见
  `milab-release/docs/最小权限发布凭据.md` 第 2 节。在那之前，job 会在批准之后停在「缺 secret」并明确报错。
- ~~前端 `dist` 不由 tag 携带~~ → **REL-16 已修**：`release-cut` 会构建前端并上传 `lifetrip-web-<tag>.tar.gz`，
  `manifest.json` 的 `artifact_sha256` 改为「前端 + 后端」的组合摘要（并有 `frontend_artifact` /
  `backend_artifact_sha256` 两个明细字段）。旧的 `artifact_sha256` 只覆盖到仓库里一个恰好叫
  `districts.py` 的后端源文件——按字面理解「只是后端摘要」甚至都不成立，它只是一个文件的摘要。
- staging 公网入口（Cloudflare DNS）未配，只能从服务器内部验收。
