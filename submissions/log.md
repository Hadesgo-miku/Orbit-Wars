# 提交记录

> 由 Orchestrator 维护。每个版本一行；提交记录 submission_id 与 24h 后 ELO。

## v0 — 仓库骨架完成（2026-06-03）

- 类型：本地版本 / 未提交
- 内容：master-plan.md + 模块骨架 + 评测脚手架 + 最简对手（random / nearest_sniper）
- commit：`e9132ba v0-仓库骨架完成`
- 下一步：T0.2（移植公开 baseline 到模块）+ T0.3（评测系统 v1）

## v1 — 启发式 baseline 完成（2026-06-03）

- 类型：本地版本 / 未提交
- 内容：T0.2 `plan_moves` 最小可跑实现 + T0.3 评测系统 v1（tournament runner + smoke test）
- commit：`6ad0f6a v1-T0.2与T0.3完成 基础框架固定`
- 测试：3 个 plan 单测 + 3 个 tournament 单测 + perf 测试通过
- 当前状态：**保留作为 v2 IL-as-Prior 主线的启发式 fallback**
- 下一步：原计划 T0.4 移植 may18/1110/1200 对手 → **已调整为 v2 范式切换**

---

## v2 — 范式切换到 IL-as-Prior 主线（2026-06-03）

- 类型：**分支策略决策**（创建新分支 `v2-il-prior`）
- 决策背景：
  - 启发式天花板已被 vkhydras 抵达（peak heuristic v13.3_R8 LB 1166，按 ELO 衰减估算今 ~1000-1080）
  - pilkwang structured baseline 当前 LB 830 / 1700 名（早期高分已被竞争稀释）
  - vkhydras 当前 LB 1500+ / 前 10（pivot 到 RL）
  - 单纯启发式已无法稳定进入银牌区
- 三大架构决策：
  - **部署形态**：IL-as-Prior（IL 输出 (source,target) 先验，乘到启发式 mission.score 上）
  - **数据来源**：Kaggle Episodes API 自爬 top-20 玩家最近 ~75 局 episode（约 1500 局）
  - **模型**：LightGBM 三模型起步（target / ships / act），D16+ 视收益升级到小型 MLP
- 期望分布更新：
  - 铜牌（≥1060）概率：80% → **85%**
  - 银牌（≥1100）概率：50% → **65%**
  - 金牌（≥1500）概率：5% → **8%**
  - 预期最终 ELO（中位）：1100-1200 → **1130-1280**
- 本次落地：
  - master-plan.md 大幅重写为 v2 IL-as-Prior 主线
  - 新增 M13 (`src/policy/il_prior.py`)
  - 新增 M14 (`tuning/replay_scraper/` 整目录)
  - 新增 M15 (`tuning/train_il_prior.py`)
  - 新增 M16 (`eval/data_quality.py`)
  - requirements.txt 增补 lightgbm / requests / tqdm
  - .gitignore 调整：data/replays/{raw,processed} 忽略，models/ 保留元数据
  - 创建 data/ 与 models/ 目录结构
- 下一步：
  - **D4 启动 T0.4**（Replay Analyst subagent，实现 Kaggle Episodes API 抓取链路）
  - **D7 启动 T0.8**（Eval Lead subagent，实现数据质量监控）

---

<!-- 提交模板（每次提交后追加）：

## v{N} — {一句话描述}（YYYY-MM-DD）

- 类型：Kaggle 提交 / 本地版本
- submission_id：{ID}
- commit message：{提交时的描述}
- 本地胜率（vs v{N-1}）：{x}% (95% CI [{low}, {high}])
- 关键变更：
  - ...
  - ...
- IL Prior 模型版本：il_prior_lgbm_v{X}（数据版本 data_v{Y}）
- 24h 后 ELO：{score}
- 48h 后 ELO：{score}
- 备注：{异常 / 观察}

-->
