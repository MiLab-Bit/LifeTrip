# DEPLOY · 部署、验收与回滚（LifeTrip）

## 1. 运行面（2026-10-12 实测）
```
公网 → Cloudflare Tunnel（cloudflared）→ Nginx → 本地端口
  lifetrip-api     127.0.0.1:8800   代码 /opt/lifetrip            健康端点 /v1/health
  lifetrip-worker  Temporal worker  /opt/lifetrip
  lifetrip-staging 127.0.0.1:8801   代码 /opt/lifetrip-staging（内存上限 512M）
  osrm-routed      docker 127.0.0.1:5000   上海 MLD 抽片，等时圈用
  前端             Nginx root=/opt/lifetrip/apps/web/dist（构建产物，不在 git 里）
```
主机：阿里云 ECS `cn-heyuan` · `ecs.u1-c1m2.large`（2C4G）。
**注意**：本仓库是 public，上面这些细节不要出现在任何对外材料里。

## 2. 发布前（只读自检）
```bash
APP_DIR=/opt/lifetrip bash scripts/deploy.sh --detect
```
会打印：认到的 systemd 单元（并校验它确实指向该目录）、端口、健康端点、当前版本、环境变量键名（值隐藏）。

## 3. 部署
```bash
APP_DIR=/opt/lifetrip-staging TARGET_ENV=staging bash scripts/deploy.sh <tag>   # 先 staging
APP_DIR=/opt/lifetrip         TARGET_ENV=production bash scripts/deploy.sh <tag>   # 再生产
```
脚本行为：`git fetch --tags` → `checkout --force <ref>` → **校验 HEAD 与目标 commit 一致** →
重启 systemd 单元 → 轮询 `/v1/health`（最多约 60 秒）→ 失败则自动回退到上一个 tag。

**坑（实测）**：`APP_DIR` 默认是 `/opt/lifetrip`。想部署 staging 却只写 `bash scripts/deploy.sh <tag>`，
会去重启**生产**的 `lifetrip-api`。脚本已加护栏（`SERVICE` 与 `APP_DIR` 不一致直接拒绝），
但命令请一律写全 `APP_DIR=`。

可选：`ISOCHRONE_PROBE`、`REQUIRE_ISOCHRONE=1`（等时圈仍降级就算失败）、`POST_DEPLOY_CMD`、`ROLLBACK_TO`。

## 4. UAT 验收清单
- [ ] `bash scripts/preflight.sh` 返回 0
- [ ] `curl -fsS http://127.0.0.1:8800/v1/health` = 200
- [ ] 首页能打开，前端版本标识与预期一致
- [ ] `/v1/isochrone/analyze`（上海市域内坐标）`degraded=false` 且 `time_s` 非 null
- [ ] `manifest.json` 的 commit SHA 与 `git -C /opt/lifetrip rev-parse HEAD` 一致
- [ ] 飞书通道仍可用（发布不应影响 openclaw / glm-relay）

## 5. 回滚
```bash
git tag -l | sort -V | tail -3
APP_DIR=/opt/lifetrip TARGET_ENV=production bash scripts/deploy.sh <上一个 tag>
```
- 实测 staging 单次回滚 8 秒（演练记录见 `milab-release`）。
- **前端 dist 不在 tag 里**：回滚只还原后端代码；`apps/web/dist` 是构建产物，
  需要同版本时请另外处理（当前没有自动化路径，见 RELEASE.md 第 6 节）。
- 回滚后重跑第 4 节。

## 6. 已知风险
- 内存：3.6G，swap 常用 1.2G 上下，OpenClaw RSS 1.2~1.4G。发布时不要同时做别的维护动作。
- `/opt/lifetrip` 与 `/opt/lifetrip-staging` 目录名互为前缀，永远显式指定 `APP_DIR`。
- 等时圈只覆盖上海市域；市域外坐标必然 `degraded=true`，别当成故障。
