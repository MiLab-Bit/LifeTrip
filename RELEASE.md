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
| 当前 tag | **`v2026.10.1`** → commit `079fae8`，线上实测即此版本 |
| release 附件 | `manifest.json`（commit `079fae8e207bf04a3dde48481ca9bd1633fd6637`） |
| CI | `.github/workflows/ci.yml`，job `preflight`；另有 `release-cut`（tag 触发） |
| 分支保护 | 已开（必需 `preflight`，strict=true，需 PR，禁 force push，`enforce_admins=false`） |
| tag ruleset | 已开（id 24875000 `protect-release-tags`，v* 禁删禁移） |
| Environment | `production` 已建（required reviewers），但**当前没有任何 workflow 引用它**（见第 6 节） |

## 1. 版本号方案
- 格式：`vYYYY.MM.<build>`，例 `v2026.10.1`。
- tag **只增不删、不可移动**（由 tag ruleset 强制，已实测删不掉）。

## 2. 发布步骤
1. 分支上完成改动 → PR 到 `main`，CI `preflight` 必须绿。
2. 本地复跑：`bash scripts/preflight.sh`。
3. 合并 PR。
4. 打 tag 并推送（**只由人工执行**）：`git tag -a v2026.10.2 -m "LifeTrip v2026.10.2" && git push origin v2026.10.2`
   → 触发 `release-cut`，产出 release notes 与 `manifest.json`。
5. 部署 staging：`APP_DIR=/opt/lifetrip-staging TARGET_ENV=staging bash scripts/deploy.sh v2026.10.2`
6. UAT 验收（`docs/DEPLOY.md` 第 4 节）。
7. 部署生产：`APP_DIR=/opt/lifetrip TARGET_ENV=production bash scripts/deploy.sh v2026.10.2`

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
- **前端不在 tag 里（重要）**：`apps/web/dist` 被 `.gitignore` 忽略、不进仓库，
  所以 `git checkout <tag>` **只回滚后端**，前端 `dist` 原地不动。回滚前请确认前端是否需要另行处理（见第 6 节）。

## 5. 同源纪律
`scripts/deploy.sh` / `CLAUDE.md` / `docs/DEPLOY.md` 都是 `milab-release` 的副本。
2026-10-12 上游与副本出现漂移（本仓库的 deploy.sh 比上游新），已把副本回灌上游。
**先改上游，再同步到本仓库。**

## 6. 已知缺口（如实记录）
- `production` Environment 已建但**没有 workflow 使用它**：部署目前是「人在服务器上跑 deploy.sh」，
  没有走 GitHub Actions，所以审批闸门当前不生效。
- 前端 `dist` 不由 tag 携带，`manifest.json` 里的 `artifact_sha256` 也不是前端产物的摘要
  （`release-cut` 没有任何构建步骤，它算的是仓库里恰好叫 `dist*`/`*.whl`/`*.tar.gz` 的那几个文件的摘要）。
  ⇒「前后端同 tag 一起回退」**目前不成立**。要修就得先决定前端产物怎么交付（随 release 附件发，还是走独立构建流水线）。
- staging 公网入口（Cloudflare DNS）未配，只能从服务器内部验收。
