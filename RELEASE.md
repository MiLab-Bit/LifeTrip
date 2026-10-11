# RELEASE · 发布流程与版本号方案

> 本文件存在的唯一目的：让「线上跑的是哪一版」有一个可复述的答案。
> 适用仓库：业务仓库（`lifetrip` / `bizatlas` / `cardio` / `redtrip`）。
> `zhice` 与两个空仓库暂不纳入自动发布：先只做「版本号 + 本文件 + tag」，成熟一个再进一个。

## 1. 版本号方案
- 格式：`vYYYY.MM.<build>`，`build` 为该月内从 1 起的发布序号。例：`v2026.10.1`。
- tag **只增不删、不可移动**（由 tag ruleset 保护，见 `tools/github-governance.sh`）。
- 线上跑的永远是某个 tag，不存在「线上是 main 的最新」。

## 2. 发布步骤（以 LifeTrip 为例）
1. 在分支上完成改动 → 提 PR 到 `main`，CI（`.github/workflows/ci.yml`）必须为绿。
2. 本地再跑一次同一条门禁：`bash scripts/preflight.sh`（离线可跑，不依赖 CI）。
3. 合并 PR。
4. 打 tag 并推送：
   ```bash
   git tag -a v2026.10.1 -m "LifeTrip v2026.10.1"
   git push origin v2026.10.1
   ```
   → 触发 `release-cut`，产出 release notes 与 `manifest.json`（含 commit SHA、产物 hash、锁文件 hash）。
5. 部署到 **staging**：`bash scripts/deploy.sh v2026.10.1`
6. UAT 验收（清单见 `docs/DEPLOY.md` 第 4 节）。
7. 部署 **生产**：同一条命令，环境指向生产。
8. 归档：把 `manifest.json` 里的 commit SHA 贴进 release notes，作为「这一版线上就是它」的证据。

## 3. 验收命令
- 门禁：`bash scripts/preflight.sh` → 退出码 0
- 健康检查：`curl -fsS http://127.0.0.1:8800/healthz`  <!-- 待现场核实：端点是否存在 -->
- 业务断言：`/v1/isochrone/analyze` 对固定坐标返回的 `time_s` 非 `null`

## 4. 回滚
1. `git tag -l | sort -V | tail -3` 找到上一个 tag。
2. `bash scripts/deploy.sh <上一个 tag>`。
3. 前端 dist 与后端**必须同 tag 一起回退**（`deploy.sh` 按 tag 取整份产物）。
4. 回滚后同样跑第 3 节的验收命令。
5. 在 release notes 里记一句回滚原因——下一次复盘要用。

## 5. 已知降级状态（不算发布成功）
`/v1/isochrone/analyze` 在 OSRM 未就绪时（systemd 单元未配地址、兜底 `127.0.0.1:5000` 无进程）返回的射线 `time_s` 全为 `null`。
此时部署必须显式标记为「**已知降级**」，不得计入「发布通过」。修完之前，这个端点不算交付。
