# Orbit Wars 主路线与多 Agent 协作总纲（master-plan v2）

> 本文件是 Orbit Wars 项目的**唯一权威文档**。所有 sub-agent 在开工前必须先读本文件。
> 凡是与本文件冲突的"个人习惯"或"AI 建议"以本文件为准。
>
> **最后更新**：2026-06-03（v2：范式切换到 IL-as-Prior 主线）
> **历史**：v0 仓库骨架（main@e9132ba）→ v1 启发式 baseline（main@6ad0f6a，T0.2/T0.3 完成）→ **v2 IL-as-Prior**（本分支 v2-il-prior 起点）

---

## 0. 项目目标与硬约束

### 0.1 三层目标（v2 按新证据重新校准）

| 结果 | 阈值 | 概率估计 | 备注 |
|------|------|------|------|
| 进入铜牌（≥1060） | 必须达成 | **85%** | v1 启发式 baseline 即可保底 |
| 进入银牌（≥1100） | 力争达成 | **65%** | IL prior 的主目标区间 |
| 触及金牌（≥1500） | 窗口达成 | **8%** | 极小：依赖 top RL replay 干净 + 模型表达力足够 |
| 预期最终 ELO（中位） | — | **1130–1280** | 中位约 1200 |

### 0.2 硬约束

- **截止日期**：6/23 23:59 UTC final submission；6/24–7/8 评测期；6/22 必须完成最终两版提交
- **提交配额**：5/day，final eval 仅看最新 2 个
- **每回合时间**：1s 硬墙（`actTimeout=1`）；推理 ≤ 0.85s，IL 推理 ≤ 5ms/mission
- **硬件**：CPU 8 核 + Kaggle 免费 T4×2
- **方法路线**：**v2 已锁定为 IL-as-Prior 主线**，启发式作为 fallback；RL 暂不做（可能未来 JAX 引擎 + 服务器租赁后加入）

### 0.3 ELO 时间衰减与启发式天花板（v2 关键判断）

**数据点**：
- **pilkwang structured baseline**（公开 lb-1200 时期 ELO ~1200）→ 当前 LB **830 / ~1700 名**
- **vkhydras peak heuristic v13.3_R8**（提交时 LB 1166）→ 当前估计 **~1000-1080**
- **vkhydras 当前**：~1500+（pivot 到 RL 后）→ 前 10 名
- 启发式公开后被 fork 与新 RL 提交不断挤压，**启发式天花板线在持续下移**

**对工程的两条直接影响**：
- 决策信号必须以"本地固定对手池"为锚，不以 Kaggle 实时 ELO 为决策依据
- 单纯启发式（即使做到 vkhydras peak 水平）现在已经**不能保证银牌**。v2 必须靠 IL 信号才能稳定进入银牌区

### 0.4 v2 范式切换的决策依据

| 维度 | v1（启发式主线） | v2（IL-as-Prior 主线） | 决策依据 |
|------|------|------|------|
| 主信号源 | 手写 mission scoring | top-20 玩家 replay 学到的 prior | vkhydras 报告：启发式 ceiling = 提交时 1166，今 ≈ 1000-1080 |
| 数据来源 | 公开 baseline 代码 | Kaggle Episodes API **自爬 top-20** | Bridelance Parquet 滞后，需要最新 RL replay |
| 模型 | 纯规则 | LightGBM 起步 → 视收益升级 MLP | Bridelance 已实证 "LightGBM BC 作 prior 有用" |
| Fallback | — | v1 完整保留作为 IL 加载失败时的兜底 | 不破坏现有交付 |
| 风险 | 已知天花板低 | 数据爬取工程不确定性高 | 风险类型已转移，可承受 |

### 0.5 v2 不做的事（明确放弃）

- ❌ **personality mode arbitration**（vkhydras 实测 n=384 净零）
- ❌ **CMA-ES 在 L4/L5/L6 对手集上调参**（vkhydras v14.0 案例：本地 +22pp，LB −52）
- ❌ **纯 BC policy（IL-as-Policy）**：covariate shift 风险高，期望 900-1100 不如 v1
- ❌ **RL 训练**：JAX 引擎/算力门槛高，剩余 20 天不足
- ❌ **追加扩展 starter kit 的物理模拟**：相信现有 kaggle_environments 1.29.1+

---

## 1. 系统架构

### 1.1 在线推理流水线（每回合 ≤1s）

```
obs ─→ [L1 World Model] ─→ [L2 战术原语] ─→ [L3 Mission 生成]
                                                  │
                                                  ▼
                                        [L4 Mission 启发式打分]
                                                  │
                                                  ▼
                                        [L4.5 IL Prior 加权]  ← v2 新增（M13）
                                                  │
                                                  ▼
                                        [L4.6 GBC tie-break]（可选, M7）
                                                  │
                                                  ▼
                                        [L5 模式/阶段门控]
                                                  │
                                                  ▼
                                        [L6 Plan Orchestrator]
                                                  │
                                                  ▼
                                        moves: [[src_id, angle, ships], ...]
```

**L4.5 节点核心逻辑**：
```python
# 对每个 candidate mission 取 IL prior 学到的概率
prior = il_prior.predict(state_feats, source_id, target_id)   # ∈ (0, 1)
mission.score *= math.exp(IL_ALPHA * (logit(prior) - logit(0.5)))
# IL_ALPHA 通过 CMA-ES 在 L1-L3 对手集上调（不在 L4-L6 上调）
# 模型未加载/异常时 IL_ALPHA = 0，等同于 v1 行为（fallback）
```

### 1.2 离线训练 / 评测流水线（v2 大改）

```
Kaggle Episodes API ──→ raw replay JSON ──→ inverse_target ──→ parquet 数据池
       (M14 crawler)         (data/replays/raw)   (M14 ETL)    (data/replays/processed)
                                                                       │
                  ┌────────────────────────────────────────────────────┼─────────────────┐
                  ▼                                                    ▼                 ▼
       [M15 IL Prior 训练 (LightGBM)]                  [M11 GBC 价值训练]      [M10 CMA-ES 调参]
              │                                              │                       │
              ▼                                              ▼                       ▼
        models/il_prior_lgbm_v{N}                  models/value_gbc_v{N}      best_params_v{N}
              │                                              │                       │
              └──────────────────────────────────────────────┴───────────────────────┘
                                                  │
                                                  ▼
                                       M9 plan_moves 集成
                                                  │
                                                  ▼
                                       [M12 评测系统] → eval/results/v{N}.{md,json}
                                                  ▲
                                                  │
                                       [M16 数据质量监控] → 验证 M14 输出
```

### 1.3 单回合数据流（叙事版）

1. **obs 接收** → 解包 namedtuples
2. **L1 World** → 时间线 + arrival ledger
3. **L2 战术原语** → 为每对 (源, 目标) 预解 intercept + 算 reserve / needed_to_capture
4. **L5 模式检测** → mode (2P/4P) + phase (opening/pressure/finishing/very-late)
5. **L3 Mission** → reinforce / rescue / recapture / capture / snipe / crash_exploit 并行生成
6. **L4 打分** → `base_pv × danger × safety × mtype − cost_penalty`
7. **L4.5 IL Prior 加权** → `score *= exp(α × (logit_prior − logit(0.5)))` ← **v2 新增**
8. **L4.6 GBC tie-break** → top-2 差距 < 阈值时启用 GBC 价值评分
9. **L6 调度** → 按分数依次提交 + commitment-aware finalize

### 1.4 系统不变量（写测试的依据）

| 不变量 | 检查点 |
|------|------|
| `sum(send_ships from src) ≤ src.ships` | L6 finalize 前必查 |
| `len(moves) ≥ 0`（永远合法返回，包括空 list） | agent.py 出口 |
| `decision_time ≤ 850ms` P99 | agent.py wrapper |
| **IL prior 推理 ≤ 5ms/mission**（含 feature 抽取） | L4.5 入口 |
| **IL prior 模型加载失败 → IL_ALPHA = 0，等同 v1 行为** | M9 init |
| 每个 move 的 angle 都过 sun-safety + swept-collision | L4 选择前 |
| 同回合内 source 已用 ships ≤ source 当前持有 | L6 commitment 表 |

---

## 2. 模块拆解（M1–M16）

### 2.1 模块表（v2 完整版）

| ID | 模块 | 文件 | 主接口 | Owner | 状态 |
|----|------|------|------|------|------|
| M1 | 物理常量 + 数学 | `src/env/physics.py` | `fleet_speed(n)`, `BOARD`, `SUN_R` | Code Lead | v1 已实现 |
| M2 | 几何 / 拦截求解 | `src/env/geometry.py` | `solve_intercept(...)` | Code Lead | v1 部分 |
| M3 | 世界状态预测 | `src/env/world.py` | `World(obs) -> World` | Code Lead | v1 部分 |
| M4 | 安全过滤器 | `src/env/safety.py` | `is_sun_doomed`, `is_planet_doomed`, `swept_by_other` | Task agent | placeholder |
| M5 | Mission 生成器 | `src/policy/missions/*.py` | `build_X_missions(...) -> List[Mission]` | Task agents | placeholder |
| M6 | Mission 启发式打分 | `src/policy/scoring.py` | `score(mission, world, policy) -> float` | Code Lead | placeholder |
| M7 | GBC 价值 tie-break | `src/policy/value_gbc.py` | `value_score(features) -> float` | Task agent | placeholder |
| M8 | 模式 / 阶段检测 | `src/policy/modes.py` | `build_policy(world) -> Policy` | Task agent | placeholder |
| M9 | Plan Orchestrator | `src/policy/plan.py` | `plan_moves(world, policy, deadline) -> moves` | Code Lead | **v1 完成** |
| M10 | CMA-ES 调参 | `tuning/cma_es.py` | `optimize(params, evaluator) -> best_params` | Task agent | placeholder |
| M11 | GBC 训练 | `tuning/train_gbc.py` | `train_from_replays(replays) -> trees` | Task agent | placeholder |
| M12 | 评测系统 | `eval/*` | `run_tournament(agent_a, opponents, seeds) -> Result` | Eval Lead | **v1 完成** |
| **M13** | **IL Prior 接入点（v2 新）** | `src/policy/il_prior.py` | `predict_prior(state, missions) -> dict[mission_id, prob]` | Code Lead | **placeholder** |
| **M14** | **Replay 数据 ETL（v2 新）** | `tuning/replay_scraper/*` | `crawl_top_n(n=20)`, `parse_replay`, `extract_pairs` | Replay Analyst | **placeholder** |
| **M15** | **IL Prior 训练（v2 新）** | `tuning/train_il_prior.py` | `train_il_prior(parquet_path) -> lgbm models` | IL Trainer | **placeholder** |
| **M16** | **数据质量监控（v2 新）** | `eval/data_quality.py` | `check_dataset(parquet_path) -> report` | Eval Lead | **placeholder** |

### 2.2 模块改进 ROI 优先级（v2 重排，按 IL 主线）

1. **M14 Replay 数据 ETL** — IL 主线的全部根据，没数据全完（P0，D4-D8）
2. **M16 数据质量监控** — 验证 M14 输出可信（P0，D7-D8）
3. **M15 IL Prior 训练** — 主信号产出（P1，D9-D12）
4. **M13 + M9 改造** — 把 IL 信号接入决策（P1，D13-D15）
5. **M12 评测 L5/L6 对手** — 自我对照与启发式天花板对照（P1 补丁，D15）
6. **M4 安全过滤** — 启发式 fallback 也要保证质量（P2，D16+）
7. **M10 CMA-ES 调 IL_ALPHA** — 调 IL prior 的乘子 α（P2，D16+）
8. **M7 / M11 GBC tie-break** — 锦上添花（P3，D18+）
9. **M5 / M6 Mission 增量** — 仅在 IL 收益不足时启动（P3，仅条件触发）

### 2.3 模块改进禁忌

- 不要在没有 M16 数据质量验证的情况下训 M15（垃圾进垃圾出）
- 不要在 M15 模型评估前接入 M13（必须先验 top-1 acc ≥ 45%）
- 不要在 M14 抓取期间频繁重试导致 API quota 浪费
- 不要同时改 M3 + M5 + M6 然后只跑一次评测（Lin Myat Ko 的 "7 changes in 2 days → all broken" 教训）
- 不要在 M9 里堆 hard-coded 阶段逻辑，那是 M8 的职责
- 不要在 M5 里写"判断当前是不是 opening"，那是 M8 提供 policy 参数

---

## 3. 多 Agent 协作模型

### 3.1 角色与交付物（v2 更新：新增 IL Trainer，加强 Replay Analyst）

| 角色 | 长期 / 单次 | 主要职责 | 交付物 | 交付位置 | 节奏 |
|------|------|------|------|------|------|
| **Orchestrator**（你 / 主对话） | 长期 | 进度、决策、版本号、提交节奏 | 提交决策、phase 切换检查点 | `submissions/log.md`（追加） | 每次提交 / 每 phase 末 |
| **Eval Lead** | 长期 | M12/M16 维护 + 每版评测报告 | 评测结果（CI / archetype 分层）+ 数据质量报告 | `eval/results/v{N}.md` + `eval/data_quality_v{N}.md` | 每版本 / 每数据批次 |
| **Code Lead** | 长期 | `src/**` owner + M9/M13 改造 + 合并 PR | 代码 diff + PR-style 说明 | `src/**` | 每次合并 |
| **Replay Analyst** | 长期（v2 职责重大加强） | **M14 数据爬取 / 解析 / 增量维护** + 周报 | `tuning/replay_scraper/*` + `data/replays/**` + 周报 | python + parquet + markdown | 爬取持续 / 每周报 |
| **IL Trainer**（v2 新角色） | 长期 | **M15 IL prior 模型训练 + 模型版本管理** | `tuning/train_il_prior.py` + `models/il_prior_lgbm_v{N}.*` | python + 模型文件 + 元数据 JSON | 每个数据版本 |
| **Task agent #X** | 单次 | 单项工作（如 M4 实现） | 单文件实现 + 测试 | 任务文档约定路径 | python + pytest | 单次 |

### 3.2 Task agent "工作合同"模板

每次启动 sub-agent 都用这个模板复制粘贴：

```markdown
# 任务上下文
项目路径：/Users/zhaohongbo/CursorProjects/Kaggle竞赛/Orbit Wars
主路线文档：master-plan.md（必读）
当前迭代版本：v{N}
本任务对应模块：M{x} ({module_name})

# 你的任务
具体工作：{task_description}
你只能修改：{allowed_files}
你不能修改：所有不在上面清单里的文件

# 必读
- master-plan.md 中 §2.1 关于 M{x} 的接口约定
- 当前实现：{current_file_path}（如已存在）
- 参考代码：{reference_files}

# 接口约定（必须严格遵守，签名见 placeholder 文件中的 docstring）
{interface_signature}

# 验收标准
- 单元测试：tests/test_{module}.py 全部通过（含你新增的）
- 性能：单次调用 P95 < {budget}ms（在 tests/perf_{module}.py 中验证）
- 集成：能通过 eval/smoke_test.py
- 评测：本地 vs 上一版本 256 局胜率 ≥ 50% + 95% CI 下沿 ≥ 48%

# 禁止
- 不要新增依赖（坚持 stdlib + numpy + sklearn + cma + pyarrow + pandas + lightgbm + requests + tqdm）
- 不要新增 markdown 文件（除非任务明确要求）
- 不要"为完成度"硬塞功能（接口外的功能一律拒绝）
- 不要触碰其他模块（如确需修改另一模块，分开提任务）

# 完成后请输出（按"Orbit Wars Agent 任务交付反馈文档"模板）
- 改动文件列表（路径 + 行数变化）
- 单元测试运行结果（python -m pytest tests/test_{module}.py -v）
- 一句话总结：本次改动核心是什么
```

### 3.3 交付物的物理映射（v2 更新）

```
/orbit-wars/                           (仓库根)
├── master-plan.md                     ← 本文件（Orchestrator 维护）
├── submissions/
│   └── log.md                         ← Orchestrator 追加
├── Orbit Wars Agent 任务交付反馈文档.md  ← 各 Task agent 完成后追加
│
├── src/                               ← Code Lead + Task agents
│   ├── agent.py                       ← 集成入口
│   ├── env/
│   │   ├── physics.py                 ← M1
│   │   ├── geometry.py                ← M2
│   │   ├── world.py                   ← M3
│   │   └── safety.py                  ← M4
│   └── policy/
│       ├── modes.py                   ← M8
│       ├── scoring.py                 ← M6
│       ├── value_gbc.py               ← M7
│       ├── il_prior.py                ← M13（v2 新增）
│       ├── plan.py                    ← M9（v2 改造接入 L4.5）
│       └── missions/*.py              ← M5.1-M5.6
│
├── eval/                              ← Eval Lead
│   ├── seeds.py
│   ├── tournament.py
│   ├── stats.py
│   ├── report.py
│   ├── data_quality.py                ← M16（v2 新增）
│   ├── smoke_test.py
│   ├── opponents/
│   │   ├── random_agent.py
│   │   ├── nearest_sniper.py
│   │   ├── may18_launch_safety.py     ← 待移植
│   │   ├── public_heuristic_1110.py   ← 待移植
│   │   ├── lb_1200_baseline.py        ← 待移植
│   │   ├── v1_baseline.py             ← L5（v2 新：自我对照）
│   │   └── peak_heuristic_v13_3_R8.py ← L6（条件移植，启发式 ceiling 参考）
│   └── results/
│       ├── v1.md / v1.json            ← 已有
│       ├── v2.md / v2.json
│       ├── data_quality_v1.md         ← M16 输出
│       └── ...
│
├── tuning/                            ← Task agents + IL Trainer + Replay Analyst
│   ├── cma_es.py                      ← M10
│   ├── train_gbc.py                   ← M11
│   ├── train_il_prior.py              ← M15（v2 新增）
│   ├── replay_analyzer.py             ← Replay Analyst 工具
│   └── replay_scraper/                ← M14（v2 新增整个目录）
│       ├── __init__.py
│       ├── kaggle_api.py              ← Episodes API 封装
│       ├── crawler.py                 ← top-20 → episodes → replay 调度
│       ├── inverse_target.py          ← angle → target_id 反推
│       ├── extract_features.py        ← replay → (state_feat, src, tgt, ships, label)
│       └── README.md
│
├── data/                              ← Replay Analyst 维护（gitignore raw/）
│   ├── replays/
│   │   ├── raw/                       ← 自爬 JSON（episode_id 分目录）
│   │   ├── processed/                 ← parquet 输出
│   │   └── manifest.csv               ← episode_id, player_id, submission_id, lb_score, date
│   └── episodes/                      ← submission_id → episode_id 列表 CSV
│
├── models/                            ← IL Trainer + Task agents（v2 新增）
│   ├── il_prior_lgbm_v1.txt           ← LightGBM 模型主体
│   ├── il_prior_lgbm_v1.json          ← 训练元数据（特征列表/超参/数据版本）
│   ├── value_gbc_v1.json              ← M11 输出
│   └── README.md
│
├── tests/                             ← 每个 Task agent 补充
│   ├── test_physics.py
│   ├── test_geometry.py
│   ├── test_world.py
│   ├── test_safety.py
│   ├── test_plan.py
│   ├── test_scoring.py
│   ├── test_tournament.py
│   ├── test_il_prior.py               ← v2 新增
│   ├── test_replay_scraper.py         ← v2 新增
│   ├── test_data_quality.py           ← v2 新增
│   ├── perf_plan.py
│   ├── perf_tournament.py
│   └── perf_il_prior.py               ← v2 新增
│
└── reports/                           ← Replay Analyst 周报
    ├── week1-replay-analysis.md
    └── ...
```

### 3.4 必须遵守的 5 条协作规则

1. **每次只一个 agent 改主代码仓**。Task agent 跑完必须在 chat 中输出"我改了哪些文件"，由 Code Lead / Orchestrator 确认合并。
2. **任何代码改动必须有评测号码**。版本号 + 本地胜率（vs 上版 + 95% CI）+ 评测 seed 数。没有数字的"我觉得这样更好"一律拒绝。
3. **Eval Lead 是单一信源**。所有"v3 比 v2 强"判断只能引用 `eval/results/v{N}.md`。
4. **Replay Analyst 周报必产**。每周一份位于 `reports/week{N}-replay-analysis.md`，否则改进会变成无方向的随机游走。
5. **Orchestrator 持有"提交否决权"**。任何提交前必须由 Orchestrator 确认本地胜率达到承诺标准；否则不烧 5/day quota。

### 3.5 版本号约定（v2 更新）

| 版本 | 含义 |
|------|------|
| v0 | 仓库骨架（main@e9132ba） |
| v1 | 启发式 baseline（T0.2 plan_moves + T0.3 tournament，main@6ad0f6a） |
| **v2** | **IL-as-Prior 主线起点（本分支 v2-il-prior）** |
| v2.1 | Phase A 完成：数据 ETL + ≥1500 episodes 落地 |
| v2.2 | Phase B 完成：IL prior LightGBM 训练 + 模型 v1 |
| v2.3 | Phase C 完成：L4.5 接入 plan_moves + 通过本地 A/B |
| v3 | 第一次 Kaggle 提交（校准用） |
| v3.x | 数据 / 模型增量迭代 |
| v4 | （条件）升级到 MLP |
| v5 | Final 候选 |

每个版本号必须有：
- `eval/results/v{N}.md` 评测报告（或 `eval/data_quality_v{N}.md` 如果是数据版本）
- `submissions/log.md` 一行记录
- 提交时记录 submission_id + commit + 24h ELO

---

## 4. 20 天日程表（v2 完全重写）

### 4.1 阶段分配

| Phase | 天数 | 主线 | 关键交付 | 提交决策点 |
|------|------|------|------|------|
| **A 数据基础设施** | D4–D8 | M14 自爬 + M16 数据质量 | `data/replays/processed/v1.parquet`（≥1500 ep） | — |
| **B IL Prior 训练** | D9–D12 | M15 LightGBM 三模型 | `models/il_prior_lgbm_v1.txt` + 验证报告 | — |
| **C 融合接入** | D13–D15 | M13 + M9 改造 + L4.5 上线 | `src/policy/il_prior.py` + `plan.py` 改造 + A/B 报告 | **D14 第 1 次提交（校准）** |
| **D 评测决策** | D16–D17 | 大样本 A/B + 决策 | `eval/results/v3.md` | **D17 第 2 次提交（v3）** |
| **E 升级（条件）** | D18–D20 | 若收益 ≥ +30 LB 进入 patch；否则启动 MLP | `models/il_prior_mlp_v1.npz`（条件） | **D20 第 3 次提交** |
| **F 最终决战** | D21–D22 | 数据 refresh + 模型 refresh + 最终两版 | Final submissions | **D22 final 两版** |

### 4.2 Phase A 详细任务（D4–D8）

| 天 | 任务 ID | 模块 | 负责 | 交付物 |
|---|------|------|------|------|
| D4 | T0.4 | M14 | Replay Analyst | `tuning/replay_scraper/kaggle_api.py` + 100 ep 健全性 |
| D5 | T0.5 | M14 | Replay Analyst | `tuning/replay_scraper/crawler.py` 跑全量 top-20 启动 |
| D6 | T0.6 | M14 | Replay Analyst | `tuning/replay_scraper/inverse_target.py` |
| D7 | T0.7 | M14 | Replay Analyst | `tuning/replay_scraper/extract_features.py` → parquet |
| D7 | T0.8 | M16 | Eval Lead | `eval/data_quality.py` + `eval/results/data_quality_v1.md` |
| D8 | T0.9 | M14 | Orchestrator | 确认数据集 v1 可用（≥1500 ep, 2P/4P 比例 ≥ 30/70） |

### 4.3 Phase B 详细任务（D9–D12）

| 天 | 任务 ID | 模块 | 交付物 |
|---|------|------|------|
| D9 | T1.1 | M15 | `train_il_prior.py`：target 模型 |
| D9 | T1.2 | M15 | `train_il_prior.py`：ships_frac + act 模型 |
| D10 | T1.3 | M15 | 模型序列化（嵌入式 / submission.py 友好） |
| D11 | T1.4 | M15 | 验证：top-1 / top-3 accuracy 报告 |
| D12 | T1.5 | M15 | `models/il_prior_lgbm_v1.*` 落地 + 元数据 |

### 4.4 Phase C 详细任务（D13–D15）

| 天 | 任务 ID | 模块 | 交付物 |
|---|------|------|------|
| D13 | T2.1 | M13 | `src/policy/il_prior.py` 实现 `predict_prior` + 加载 fallback |
| D13 | T2.2 | M9 | `src/policy/plan.py` 改造接入 L4.5 节点 |
| D14 | T2.3 | M9 | 性能测试：推理 P95 ≤ 800ms |
| D14 | T2.4 | — | **第 1 次提交** Kaggle（校准用） |
| D15 | T2.5 | M12 | 大样本 A/B vs v1：n=384 4P + n=256 2P |
| D15 | T2.6 | M12 | `eval/opponents/v1_baseline.py`（L5 自我对照） |

### 4.5 Phase D 详细任务（D16–D17）

| 天 | 任务 ID | 模块 | 交付物 |
|---|------|------|------|
| D16 | T3.1 | M10 | CMA-ES 调 `IL_ALPHA` 等参数（仅 L1-L3 对手集） |
| D16 | T3.2 | — | 24h 后回收 D14 提交 ELO，与本地预测对比 |
| D17 | T3.3 | M12 | `eval/results/v3.md` + 决策：进 Phase E 还是停 |
| D17 | T3.4 | — | **第 2 次提交（v3）** |

### 4.6 Phase E 详细任务（条件触发，D18–D20）

| 天 | 任务 ID | 模块 | 交付物 |
|---|------|------|------|
| D18 | T4.1 | M15+ | （条件）小型 MLP 设计 + 训练 |
| D18 | T4.2 | M7 | （可选）GBC value tie-break 接入 L4.6 |
| D19 | T4.3 | M14 | 数据 refresh（data_v2，补抓 D8 之后的最新 episode） |
| D19 | T4.4 | M15 | 用 data_v1 + data_v2 重训 `il_prior_lgbm_v2` |
| D20 | T4.5 | — | **第 3 次提交** + 备用版本 |

### 4.7 Phase F 详细任务（D21–D22）

| 天 | 任务 ID | 模块 | 交付物 |
|---|------|------|------|
| D21 | T5.1 | M14/M15 | 最后一次数据 + 模型 refresh（data_v3 + lgbm_v3） |
| D21 | T5.2 | M12 | A/B：lgbm_v3 vs lgbm_v2 vs lgbm_v1 vs v1_baseline |
| D22 | T5.3 | — | **最终两版**（稳健 + 激进）提交 |
| D22 | T5.4 | — | 复盘 + 文档归档 |

---

## 5. 评测协议（决定一切信号质量）

### 5.1 本地 vs Kaggle 提交的决策原则

> **结论：85%+ 决策在本地完成，Kaggle 提交只用于最终校准与 4P 验证。**

| 改进类型 | 决策方式 |
|------|------|
| **IL 模型版本切换** | 100% 本地（≥ 384 局 4P + 256 局 2P） |
| **数据集版本切换** | 100% 本地（M16 报告先过） |
| 数值调参（CMA-ES 输出） | 100% 本地 |
| Bug 修复 | 100% 本地 |
| 新增 mission 类 | 100% 本地（≥ 256 局 + 95% CI） |
| **大版本切换**（如 v2→v3） | 本地 ≥ 500 局确认 → 提交 1 次校准 |
| **4P 模式真实表现** | 必须靠 Kaggle 提交（本地凑不出 3 个不同风格对手） |

### 5.2 对手池设计（v2 更新）

`eval/opponents/` 中放 5+1 个等级的对手：

| 等级 | 对手 | 用途 | CMA-ES 调参可用？ |
|------|------|------|------|
| L0 | `random_agent` | 健全性（应 100% 胜） | ✅ |
| L1 | `nearest_sniper` | 简单合理对手（应 90%+ 胜） | ✅ |
| L2 | `may18_launch_safety` | 中等难度（应 70%+ 胜） | ✅ |
| L3 | `public_heuristic_1110` | 同档威胁（争取 55%+ 胜） | ✅ |
| L4 | `lb_1200_baseline` | 公开启发式（争取 50%+ 胜） | ❌ **held-out** |
| **L5（v2 新）** | **`v1_baseline`**（自身上版本启发式） | **自我对照，验证 IL 收益** | ❌ **held-out** |
| **L6（条件）** | **`peak_heuristic_v13_3_R8`**（vkhydras） | **真实启发式 ceiling 参考** | ❌ **held-out** |

**评测套餐**：默认对 L1–L5 各打 64 局（32 seeds × 2 seats），单版本 320 局，8 进程约 4 分钟。

### 5.3 评测报告标准格式（`eval/results/v{N}.md`）

```markdown
# Eval Report v{N}

- 版本：v{N}
- 评测时间：YYYY-MM-DD HH:MM
- IL Prior 模型：models/il_prior_lgbm_v{X}.txt（数据版本 data_v{Y}）
- 评测对手池：L1, L2, L3, L4, L5
- 评测 seeds：32 (from BY_ARCHETYPE)
- 每对手局数：64 (32 seeds × 2 seats)
- 总局数：320

## 整体战绩

| Opponent | Games | Wins | Win% | 95% CI | vs v{N-1} Δ |
|----------|-------|------|------|--------|------|
| nearest_sniper | 64 | 63 | 98.4% | [91.6%, 99.7%] | +0.0% |
| may18_launch_safety | 64 | 49 | 76.6% | [64.6%, 85.4%] | +3.1% |
| public_heuristic_1110 | 64 | 37 | 58.6% | [46.0%, 70.2%] | +6.3% ✓ |
| lb_1200_baseline | 64 | 30 | 47.7% | [35.6%, 60.0%] | +8.1% ✓ |
| **v1_baseline（自身上版）** | 64 | 38 | **59.4%** | [46.7%, 71.0%] | **+9.4% ✓** |
| **Aggregate** | **320** | **217** | **67.8%** | **[62.4%, 72.8%]** | **+5.6%** |

## IL Prior 子项指标

- target top-1 accuracy（held-out replay）：47.3%
- target top-3 accuracy（held-out replay）：78.5%
- ships_frac MAE：0.14
- act 二分类 AUC：0.81

## 按 archetype 分层（vs v1_baseline）
...

## 结论
- [x] vs v1_baseline 整体胜率提升显著（+9.4%，下沿 +1.4%）
- [ ] 2P 子集胜率仅 +3.2%（数据缺失影响，需 self-play 补）
- 建议：进入 Phase D 提交 v3
```

### 5.4 评测统计原则（v2 强化版，必须遵守）

- **Wilson Score Interval**，不要用正态近似（小样本偏差大）
- **vs Prev Δ > 0 且 95% CI 下沿 > 0** 才算"统计显著提升"
- **SPRT**（顺序概率比检验）可早停：明显 > 50% 或 < 50% 时无需打满 64 局
- **双 seat 必跑**：float drift 会让单 seat 估值偏差 ~3–5%
- **vkhydras 三条铁律**（v2 新增，从社区证据补入）：
  1. **本地 A/B → LB 换算比 ~3–5 LB/pp**（n=192 时 4P 噪声 ±6–8pp）
  2. **必须 gate-and-retest at n=384**（单次 A/B 不足以决策）
  3. **CMA-ES 调参的 evaluation 对手只用 L1/L2/L3**（L4/L5/L6 留作 held-out）
- **IL 模型评估三指标**（v2 新增）：
  1. **top-1 accuracy**（预测 target 命中率）目标 ≥ 45%
  2. **top-3 accuracy**（top-3 包含真 target 的概率）目标 ≥ 75%
  3. **game win rate**（接入 plan_moves 后实际胜率）目标 vs v1_baseline ≥ 55%

### 5.5 提交后反馈采集流程

每次提交后 24–48h 内执行：

```bash
# 1. 查 episode 列表
kaggle competitions episodes <SUBMISSION_ID> -v > data/episodes/v{N}.csv

# 2. 找到所有败局，下 replay + logs
python tuning/replay_analyzer.py download --submission_id <SUBMISSION_ID> --losses-only

# 3. 跑分析报告
python tuning/replay_analyzer.py diagnose --submission_id <SUBMISSION_ID> \
    > reports/submission-v{N}-diagnosis.md
```

**败局诊断报告必含**：
- Top 5 输给的对手 ID
- 每个对手的 mission classification 分布
- 输局 archetype 分布 + phase 分布
- **IL prior 在败局中的 top-1 命中率**（若显著低于 train acc，说明 covariate shift）
- 1 条具体可执行的下版本改进建议

### 5.6 提交配额分配（v2 重排）

5/day × 20 day = 100 上限，实际预算：

| 周 | 用法 |
|----|------|
| Week 1（D1–D7） | **0 提交**（数据爬取期，不能浪费配额） |
| Week 2（D8–D14） | D14 第 1 次提交（校准 IL prior） |
| Week 3（D15–D21） | D17 / D20 各 1 次 + Day-of A/B 探针 |
| Week 4（D22） | 最终两版（候选 ≥ 3 个） |

**全周期总提交 ~10–15 次**，远低于上限。剩余 quota 留给"修 bug 紧急提交"。

---

## 6. v2 IL 数据生命周期（新章节）

### 6.1 数据版本号

| 数据版本 | 内容 | 抓取日期 | 用途 |
|------|------|------|------|
| `data_v1` | top-20 玩家最近 ~75 ep/人，≥1500 总 ep | D4–D8 | 训练 `il_prior_lgbm_v1` |
| `data_v2` | data_v1 + 新增 D8 之后的 ep | D19 | 训练 `il_prior_lgbm_v2` |
| `data_v3` | data_v2 + 最后一次 refresh | D21 | 训练 `il_prior_lgbm_v3`（最终） |

### 6.2 数据 ↔ 模型版本映射（必须记录）

| Model | Trained on | Train Date | Train Acc (top-1) | Test Acc (top-1) |
|-------|-----------|------|------|------|
| il_prior_lgbm_v1 | data_v1 | D12 | TBD | TBD |
| il_prior_lgbm_v2 | data_v1+v2 | D19 | TBD | TBD |
| il_prior_lgbm_v3 | data_v1+v2+v3 | D21 | TBD | TBD |

每个模型必须落 `models/il_prior_lgbm_v{N}.json` 元数据：
```json
{
  "version": "v1",
  "data_versions": ["data_v1"],
  "trained_at": "2026-06-12T18:30:00Z",
  "n_train_pairs": 412350,
  "n_test_pairs": 51420,
  "features": ["my_ship_ratio", "..."],
  "lgbm_params": {"num_leaves": 63, "learning_rate": 0.05, "..."},
  "metrics": {"top1_acc": 0.473, "top3_acc": 0.785, "ships_frac_mae": 0.14}
}
```

### 6.3 Kaggle Episodes API 配额管理

- 每天检查 quota usage，**超过 4GB 立即停爬**
- 优先级：top-5 → top-10 → top-20（按 LB 排序）
- 缺失日期补抓策略：D14 / D19 重爬时**只抓 last_seen_date 以后**的 episode
- 单 episode 失败重试上限 3 次，超过则记录到 `data/replays/manifest.csv` 的 `failed_ids.txt` 中

### 6.4 Inverse Targeting 校验

- 每批解析后**随机抽 50 个 episode 人工验证**（或 visualizer 对照）
- 解析失败率 **> 15% 时停止入库**，回查 `resolve_target` 容差
- 解析输出必须含：`(state_features, source_id, target_id, ships, players, winner, episode_id, tick)`

### 6.5 2P 数据问题（v2 必须重视）

bovard 2P replay 几乎全缺。我们的策略：
- **首选**：通过 API 自爬 top-20 玩家的全部 episode（既会包含 2P 也会包含 4P）
- **回退**：若自爬 2P 比例 < 20%，启动 self-play 数据增广（用 v1_baseline 作为 expert）
- **如失败**：2P 场景退化为纯启发式 `plan_moves`，IL_ALPHA = 0

---

## 7. 快速参考

### 7.1 v2 Day 1（=D4）第一件事

启动 **T0.4**：实现 Kaggle Episodes API 抓取，验证链路。
模板见"Orbit Wars Agent 任务交付反馈文档.md" 末尾的 T0.4 task 启动模板。

### 7.2 关键依赖（v2 新增）

```
kaggle-environments>=1.29.1  # 必须升级（1.0.9 是旧版有 sweep bug）
numpy>=1.24
scikit-learn>=1.3            # 用于 GBC 训练（M11）
cma>=3.3                     # CMA-ES（M10）
pyarrow>=12.0                # parquet
pandas>=2.0                  # replay 分析
pytest>=7.0                  # 测试
kaggle>=1.5                  # CLI
lightgbm>=4.0                # IL prior 主模型（v2 新增）
requests>=2.31               # Kaggle Episodes API 自爬（v2 新增）
tqdm>=4.66                   # 进度条（v2 新增）
```

### 7.3 v2 必读文件清单

1. **本文件**（master-plan.md）
2. `orbit-wars-overview.md` — 竞赛规则
3. `orbit-wars-guide/README.md` — 环境机制
4. **`community-discussions/replay-dataset-parquet-3000-games-ready-to-analyze.md`** — Bridelance BC 经验（v2 关键）
5. **`community-discussions/orbit-wars-top-10-daily-episode-replay-datasets-pinned.md`** — 数据集 + 已知缺陷
6. **`community-examples/data-generation-expert-imitation-for-rl.ipynb`** — inverse target 工程范例
7. **`community-examples/orbit-wars-heuristic-bots-master/README.md`** — vkhydras 启发式 ceiling 数据
8. `community-discussions/sharing-our-rl-lessons-so-far.md` — Lin Myat Ko 的 RL 工程教训（即使不做 RL 也要读）

### 7.4 关键引用代码

- 物理公式：`fleet_speed = 1.0 + 5.0 * (log(n)/log(1000))^1.5`
- Inverse Targeting 核心：`community-examples/data-generation-expert-imitation-for-rl.ipynb` Cell 7 的 `resolve_target`
- 对手 baseline 移植源：
  - `eval/opponents/nearest_sniper.py` ← `orbit-wars-guide/main.py`
  - `eval/opponents/may18_launch_safety.py` ← `community-examples/orbit-wars-1039-2-lb-launch-safety-heuristic.ipynb`
  - `eval/opponents/public_heuristic_1110.py` ← `community-examples/recent-high-scores/orbit-wars-heuristic-lb-1110.ipynb`
  - `eval/opponents/lb_1200_baseline.py` ← `community-examples/lb-1200-orbit-wars-ppo-strategy.ipynb`
  - `eval/opponents/peak_heuristic_v13_3_R8.py` ← `community-examples/orbit-wars-heuristic-bots-master/08_v13_3_R8_full_stack_lb1166_PEAK_HEURISTIC.py`

### 7.5 v2 当前进度（v2.0：本分支起点）

- [x] 决策：从启发式主线切换到 IL-as-Prior
- [x] 分支创建建议：`v2-il-prior`
- [x] master-plan.md 重写完成（本次）
- [ ] M14 骨架（`tuning/replay_scraper/`）← 即将创建
- [ ] M13 骨架（`src/policy/il_prior.py`）← 即将创建
- [ ] M15 骨架（`tuning/train_il_prior.py`）← 即将创建
- [ ] M16 骨架（`eval/data_quality.py`）← 即将创建
- [ ] requirements.txt 增补 lightgbm/requests/tqdm
- [ ] 启动 T0.4
