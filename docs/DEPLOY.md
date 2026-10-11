# DEPLOY · 部署、验收与回滚

## 1. 拓扑（现状）
```
公网 → Cloudflare Tunnel（cloudflared）→ Nginx → 各本地端口
  lifetrip-api   uvicorn 127.0.0.1:8800   代码 /opt/lifetrip，前端 dist 静态
  redtrip        8799
  bizatlas       8000
  cardio         8010
  temporal       7233 / 8233
  openclaw       docker 容器（飞书 WebSocket 长连接 + Telegram bot One_MiBot）
  glm-relay      systemd（GLM-5.2 → 上游中转）
  备份            每天 03:00
```
主机：阿里云 ECS `cn-heyuan` · `ecs.u1-c1m2.large`（2C4G）。
**注意**：如果本仓库是 public，上面这些细节（IP、端口、目录）不要写进来；本文件只适用于私有仓库。

## 2. 环境
| 环境 | 入口 | 用途 |
|---|---|---|
| staging / UAT | 同一台机器、独立目录与端口（待现场核实具体端口），Cloudflare Tunnel 的第二个 hostname | 发布前验收与回滚演练 |
| production | `lifetrip.sy-realm.ltd` | 对外 |

staging 与生产**共用这台 2C4G**，所以：
- staging 只跑必需服务，不要复制 14 项飞书 bot 任务；
- 不要在服务器上跑 Node 构建（会吃满内存并与 OpenClaw 抢内存），构建一律在 CI 里做。

## 3. 发布
先看一眼脚本会认成什么（只读，不做任何改动）：
```bash
bash scripts/deploy.sh --detect
```
再发布：
```bash
bash scripts/deploy.sh v2026.10.1
```
脚本行为：`git fetch --tags` → `checkout <tag>` → 重启 systemd 单元 → 轮询健康端点（最多约 60 秒）→ 失败则自动回退到上一个 tag。
发布前先在 staging 跑一次；生产发布同样用它。

## 4. UAT 验收清单
- [ ] `scripts/preflight.sh` 在目标 tag 上返回 0
- [ ] 健康端点返回 200
- [ ] 首页与主要页面能打开，前端版本标识与预期一致
- [ ] `/v1/isochrone/analyze` 对固定坐标返回的 `time_s` **非 null**（若为 null，记为「已知降级」，不算通过）
- [ ] `manifest.json` 里的 commit SHA 与线上运行的版本一致
- [ ] 飞书侧原有通道仍可用（发布不应影响 openclaw / glm-relay）

## 4.5 基线采集（发布前先留一份）
```bash
bash scripts/collect-baseline.sh --brief     # 先看关键几段
bash scripts/collect-baseline.sh > infra/baseline-$(date +%F).txt 2>&1   # 留档
```
它是只读的：不重启、不改配置、不写文件；环境变量只打印键名，token/secret/key 类字段值打成 `****`。

## 5. 回滚
```bash
git tag -l | sort -V | tail -3        # 找上一个 tag
bash scripts/deploy.sh <上一个 tag>
```
- 前后端必须同 tag 一起回退（脚本按 tag 取整份产物）。
- 回滚后重跑第 4 节清单。
- 目标：从决定回滚到旧版本恢复服务 ≤ 30 分钟。
- 在 release notes 里记一句回滚原因。

## 6. 已知风险
- 内存：3.6G + swap 已用近 1G，OpenClaw RSS 1.4G+。发布动作与内存事故容易互相掩盖 —— 发布时不要同时做其他维护动作。
- 入口：Cloudflare Tunnel 断掉时，所有服务一起不可达；发布前后各确认一次隧道状态。
