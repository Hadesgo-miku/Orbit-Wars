# Orbit Wars 主路线与多 Agent 协作总纲（master-plan）

> 本文件是 Orbit Wars 项目的**唯一权威文档**。所有 sub-agent 在开工前必须先读本文件。
> 凡是与本文件冲突的"个人习惯"或"AI 建议"以本文件为准。
>
> 最后更新：2026-06-03（v0：仓库骨架完成）

---

## 0. 项目目标与硬约束

### 0.1 三层目标（按优先级）

1. **必须达成**：最终提交（6/22）的 ELO 高于"原样 fork 当前任意公开 baseline"的预期值（即 1100 以下不可接受）
2. **力争达成**：最终 ELO 进入 silver 区（≥ 1150–1300），覆盖 65% 概率
3. **窗口达成**：摸到 gold 下沿（≥ 1300–1500），覆盖 15–25% 概率

### 0.2 硬约束

- **截止日期**：6/23 23:59 UTC final submission；6/24–7/8 评测期；6/22 必须完成最终两版提交
- **提交配额**：5/day，final eval 仅看最新 2 个
- **每回合时间**：1s 硬墙（`actTimeout=1`）；推理 ≤ 0.85s，留余量给序列化
- **硬件**：CPU 8 核 + Kaggle 免费 T4×2（不投钱买更高规格 GPU）
- **方法路线**：**已锁定为 Heuristic 主线**，RL 暂不做（决策依据见仓库根目录其它讨论历史）

### 0.3 ELO 时间衰减的工程影响

由于 ELO 是相对值且每天会被新对手摊薄，**当前提交的"今天 ELO"≠"上周同分数版本的 ELO"**。
对工程的两条直接影响：
- 决策信号**必须**以"本地固定对手池"为锚，不以 Kaggle 实时 ELO 为决策依据
- 任何"原样提交公开 agent"的策略都会在 1–3 周内随大家 fork 而被挤到铜牌线以下

---

## 1. 系统架构（8 层 + 离线 2 层）

### 1.1 在线推理流水线（每回合 ≤1s）

```
obs ─→ [L1 World Model] ─→ [L2 战术原语] ─→ [L3 Mission 生成]
                                                  │
                                                  ▼
                                        [L4 Mission 打分]
                                                  │
                                                  ▼
                                        [L4.5 GBC tie-break]（可选）
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

### 1.2 离线训练/评测流水线

```
Kaggle Episodes API ─→ replay JSON ─→ parquet 数据池
                                          │
                  ┌───────────────────────┼───────────────────────┐
                  ▼                       ▼                       ▼
          [L7 CMA-ES 调参]       [L7 GBC 训练]          [L8 评测系统]
              ▲                       │                       │
              │                       ▼                       ▼
              │              tuning/value_gbc_trees.py  results/v{N}.{md,json}
              │
              └──────── 喂回 L4/L5 的参数表与价值模型
```

### 1.3 单回合数据流（叙事版）

```
1. obs 接收  → 解包 namedtuples，提取 player/angular_velocity/comets
2. L1 World    → 用 initial_planets + ω 计算未来轨道；
                   用 comets.paths 算未来彗星位置；
                   把 fleets 按 (target, arrival_tick) 编进 arrival ledger；
                   每个 planet 输出时间线 [(tick, owner, garrison), ...]
3. L2 战术原语 → 为每对 (我方源, 目标) 预解 intercept（sun-aware, swept-collision）；
                   为每个我方星球算 reserve（不可避免压力）；
                   为每个目标算 needed_to_capture / needed_to_hold
4. L5 模式检测 → 数对手 → mode (2P/4P)；
                   按 step 划 phase (opening/pressure/finishing/very-late)；
                   4P 时算 enemy_race_eta + 对手画像
5. L3 Mission  → reinforce / rescue / recapture / capture / snipe / crash_exploit 并行生成
6. L4 打分     → base_pv × danger × safety × mtype − cost_penalty
7. L4.5 tie-break → top-2 差距 < 阈值时启用 GBC 模拟评分
8. L6 调度     → 按分数依次提交；每次提交后立即更新 arrival ledger；
                   commitment 表防同源重复打同目标；
                   监控 deadline，到点立即 finalize
```

### 1.4 系统不变量（写测试的依据）

| 不变量 | 检查点 |
|------|------|
| `sum(send_ships from src) ≤ src.ships` | L6 finalize 前必查 |
| `len(moves) ≥ 0`（永远合法返回，包括空 list） | agent.py 出口 |
| `decision_time ≤ 850ms` P99 | agent.py wrapper |
| 每个 move 的 angle 都过 sun-safety + swept-collision | L4 选择前 |
| 同回合内 source 已用 ships ≤ source 当前持有 | L6 commitment 表 |

---

## 2. 模块拆解（M1–M12）

### 2.1 模块表（含 owner / 文件位置 / 接口）

| ID | 模块 | 文件 | 主接口 | Owner |
|----|------|------|------|------|
| **M1** | 物理常量 + 数学 | `src/env/physics.py` | `fleet_speed(n)`, `BOARD`, `SUN_R` 等 | Code Lead |
| **M2** | 几何 / 拦截求解 | `src/env/geometry.py` | `solve_intercept(src, tgt, vel, ships) -> InterceptSolution` | Code Lead |
| **M3** | 世界状态预测 | `src/env/world.py` | `World(obs) -> World`（时间线 + arrival ledger） | Code Lead |
| **M4** | 安全过滤器 | `src/env/safety.py` | `is_sun_doomed`, `is_planet_doomed`, `swept_by_other` | Task agent |
| **M5** | Mission 生成器 | `src/policy/missions/*.py` | `build_X_missions(world, policy) -> List[Mission]` | Task agents（每类一人） |
| **M6** | Mission 打分 | `src/policy/scoring.py` | `score(mission, world, policy) -> float` | Code Lead |
| **M7** | GBC 价值 tie-break | `src/policy/value_gbc.py` | `value_score(features) -> float` | Task agent |
| **M8** | 模式/阶段检测 | `src/policy/modes.py` | `build_policy(world) -> Policy` | Task agent |
| **M9** | Plan Orchestrator | `src/policy/plan.py` | `plan_moves(world, policy, deadline) -> moves` | Code Lead（核心调度） |
| **M10** | CMA-ES 调参 | `tuning/cma_es.py` | `optimize(params, evaluator) -> best_params` | Task agent |
| **M11** | GBC 训练 | `tuning/train_gbc.py` | `train_from_replays(replays) -> trees` | Task agent |
| **M12** | 评测系统 | `eval/*` | `run_tournament(agent_a, opponents, seeds) -> Result` | Eval Lead |

### 2.2 模块改进 ROI 优先级（"边际增益 / 工时"）

1. **M12 评测系统** — 不做这个所有改进都是赌博（基建）
2. **M4 安全过滤** — 工时小、增益稳（+20 ~ +40 ELO）
3. **M10 CMA-ES 调参** — 一次性扫遍 M5/M6/M8 数值常量（+30 ~ +80 ELO）
4. **M3 commitment-aware 时间线** — Mission Family 的基石（+30 ~ +80 ELO）
5. **M7 GBC tie-break** — 边际增益清晰（+50 ~ +100 ELO）
6. **M5 mission 增量** — 每次只加 1 类，平稳爬升（每类 +10 ~ +40 ELO）

### 2.3 模块改进禁忌

- 不要同时改 M3 + M5 + M6 然后只跑一次评测（Lin Myat Ko 的 "7 changes in 2 days → all broken" 教训）
- 不要在 M9 里堆 hard-coded 阶段逻辑，那是 M8 的职责
- 不要在 M5 里写"判断当前是不是 opening"，那是 M8 提供 policy 参数

---

## 3. 多 Agent 协作模型

### 3.1 角色与交付物（**核心：交付形式与交付位置**）

| 角色 | 长期/单次 | 主要职责 | 交付物 | 交付位置 | 交付格式 | 节奏 |
|------|------|------|------|------|------|------|
| **Orchestrator**（你 / 主对话） | 长期 | 进度跟踪、决策、提交节奏、版本号管理 | 提交决策、phase 切换检查点 | `submissions/log.md`（追加） | markdown 单行/段 | 每个提交、每个 phase 末尾 |
| **Eval Lead** | 长期 | M12 评测系统的维护 + 每个版本评测报告 | 评测结果（CI / archetype 分层） | `eval/results/v{N}.md` 与 `eval/results/v{N}.json` | markdown 表 + JSON | 每个版本（main 合并后） |
| **Code Lead** | 长期 | 主代码仓 owner、合并 M1–M9 的 PR、保持代码风格 | 代码 diff + 合并说明 | `src/**`（直接修改） + 在 chat 中给出 PR-style 说明 | 文件改动 + 单元测试 | 每次合并 |
| **Replay Analyst** | 长期 | 对手画像 / 败局事后归因 / 数据集维护 | 周报 + 数据集脚本 | `reports/week{N}-replay-analysis.md` | markdown 报告 | 每周一份 |
| **Task agent #X** | 单次 | 具体单项工作（如 M4 实现、某 mission 实现） | 单文件实现 + 测试 | 任务文档约定的具体路径 | Python 代码 + pytest 测试 | 单次 |

### 3.2 Task agent "工作合同"模板

每次启动 sub-agent 都用这个模板复制粘贴，避免重复解释项目背景：

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
- 不要新增依赖（坚持 stdlib + numpy + sklearn + cma + pyarrow + pandas）
- 不要新增 markdown 文件（除非任务明确要求）
- 不要"为完成度"硬塞功能（接口外的功能一律拒绝）
- 不要触碰其他模块（如确需修改另一模块，分开提任务）

# 完成后请输出
- 改动文件列表（路径 + 行数变化）
- 单元测试运行结果（python -m pytest tests/test_{module}.py -v）
- 一句话总结：本次改动核心是什么
```

### 3.3 交付物的物理映射（这是 §3.1 表格的"展开版"）

```
/orbit-wars/                           (仓库根)
├── master-plan.md                     ← 本文件（Orchestrator 维护）
├── submissions/
│   └── log.md                         ← Orchestrator 追加提交决策
│
├── src/                               ← Code Lead + Task agents 写代码
│   ├── agent.py                       ← M9 + M3-7 集成入口
│   ├── env/
│   │   ├── physics.py                 ← M1
│   │   ├── geometry.py                ← M2
│   │   ├── world.py                   ← M3
│   │   └── safety.py                  ← M4
│   └── policy/
│       ├── modes.py                   ← M8
│       ├── scoring.py                 ← M6
│       ├── value_gbc.py               ← M7（含离线训出的 trees 数组）
│       ├── plan.py                    ← M9
│       └── missions/
│           ├── reinforce.py           ← M5.1
│           ├── rescue.py              ← M5.2
│           ├── recapture.py           ← M5.3
│           ├── capture.py             ← M5.4
│           ├── snipe.py               ← M5.5
│           └── crash_exploit.py       ← M5.6
│
├── eval/                              ← Eval Lead 维护
│   ├── seeds.py                       ← 128 seeds + by_archetype
│   ├── tournament.py                  ← 多进程 runner
│   ├── stats.py                       ← Wilson CI / SPRT
│   ├── report.py                      ← markdown 报告生成
│   ├── opponents/                     ← 本地对手池
│   │   ├── random_agent.py
│   │   ├── nearest_sniper.py
│   │   ├── may18_launch_safety.py     ← 待 Task agent 移植
│   │   ├── public_heuristic_1110.py   ← 待 Task agent 移植
│   │   └── lb_1200_baseline.py        ← 待 Task agent 移植
│   └── results/                       ← 评测产出
│       ├── v0.md / v0.json
│       ├── v1.md / v1.json
│       └── ...
│
├── tuning/                            ← Task agents 维护
│   ├── cma_es.py                      ← M10
│   ├── train_gbc.py                   ← M11
│   └── replay_analyzer.py             ← Replay Analyst 工具
│
├── tests/                             ← 每个 Task agent 补充
│   ├── test_physics.py
│   ├── test_geometry.py
│   ├── test_world.py
│   ├── test_safety.py
│   ├── test_missions_*.py
│   ├── test_scoring.py
│   └── test_plan.py
│
├── data/                              ← Replay Analyst + .gitignore
│   ├── replays/                       ← Kaggle replay JSON
│   ├── parquet/                       ← parquet 化的数据
│   └── episodes/                      ← episode 列表 CSV
│
└── reports/                           ← Replay Analyst 周报
    ├── week1-replay-analysis.md
    ├── week2-replay-analysis.md
    └── ...
```

### 3.4 必须遵守的 5 条协作规则

1. **每次只一个 agent 改主代码仓**。Task agent 跑完必须在 chat 中输出"我改了哪些文件"，由 Code Lead/Orchestrator 确认合并。
2. **任何代码改动必须有评测号码**。版本号 + 本地胜率（vs 上版 + 95% CI）+ 评测 seed 数。没有数字的"我觉得这样更好"一律拒绝。
3. **Eval Lead 是单一信源**。所有"v3 比 v2 强"判断只能引用 `eval/results/v{N}.md`。
4. **Replay Analyst 周报必产**。每周一份位于 `reports/week{N}-replay-analysis.md`，否则改进会变成无方向的随机游走。
5. **Orchestrator 持有"提交否决权"**。任何提交前必须由 Orchestrator 确认本地胜率达到承诺标准；否则不烧 5/day quota。

### 3.5 版本号约定

- `v0`：仓库骨架完成（本文件创建时）
- `v1` ~ `vN`：每次"重大版本"递增；小修小补不递增
- 每个版本号必须有：
  - `eval/results/v{N}.md` 评测报告
  - `submissions/log.md` 记录一行（即使没提交也要记本地版本）
  - 如果提交，记录 submission_id + commit message + 24h 后 ELO

---

## 4. 20 天日程表

### 4.1 阶段分配

| Phase | 天数 | 主线 | 关键交付 | 提交决策点 |
|------|------|------|------|------|
| **P0 基建** | D1–3 | 仓库骨架 + 评测系统 + Replay 数据下载 | `eval/` 跑通；`v0` baseline 评测出炉 | — |
| **P1 抓低垂果实** | D4–7 | M4 安全过滤 + M3 commitment + M10 一轮调参 | `v1` 评测报告 | **D7：第 1 次提交** |
| **P2 Mission Family** | D8–14 | M5 全套 mission 重构 + M6 评分升级 + M8 模式细化 + M9 重写 + M10 二轮调参 | `v2` 评测报告 | **D14：第 2 次提交** |
| **P3 精修与决战** | D15–22 | M7 GBC tie-break + 4P 优化 + 性能优化 + A/B 双版本 | `v3`、`v4` 评测报告 | **D19：第 3 次；D22：最终两版** |

### 4.2 P0 详细任务（立即开始）

| 天 | 任务 ID | 模块 | 负责 | 交付物 |
|---|------|------|------|------|
| D1 | T0.1 | 仓库骨架 | Code Lead | `src/**/*.py` placeholder（**本任务**） |
| D1 | T0.2 | 移植公开 baseline 到模块 | Code Lead | `src/policy/plan.py` 含从 `orbit-wars-heuristic-lb-1110` 拆解的最小可跑版本 |
| D2 | T0.3 | 评测系统 v1 | Eval Lead | `eval/tournament.py` 跑通 32 seeds × 2 seats |
| D2 | T0.4 | 移植 may18 + 1110 + 1200 到 opponents/ | Task agent | `eval/opponents/*.py` |
| D3 | T0.5 | 评测系统 v2（128 seeds + Wilson CI + 分层报告） | Eval Lead | `eval/stats.py`, `eval/report.py` |
| D3 | T0.6 | Replay 数据管线 | Replay Analyst | `tuning/replay_analyzer.py` + 已下载 ≥ 500 局 replay |
| D3 | T0.7 | `v0` 评测报告 | Eval Lead | `eval/results/v0.md` |

### 4.3 P1 详细任务（D4–7）

| 天 | 任务 ID | 模块 | 交付物 |
|---|------|------|------|
| D4 | T1.1 | M4 安全过滤 | `src/env/safety.py` + `tests/test_safety.py` |
| D4 | T1.2 | M4 合并到 plan | 修改 `src/policy/plan.py` 加入 safety gate |
| D5 | T1.3 | M3 commitment-aware 时间线 | `src/env/world.py` 升级 |
| D5 | T1.4 | M11 GBC 训练管线雏形（不接入） | `tuning/train_gbc.py` |
| D6 | T1.5 | M10 CMA-ES 调 50 个数值常量 | `tuning/cma_es.py` + `tuning/best_params_v1.json` |
| D6 | T1.6 | 应用 best_params_v1 到代码 | 更新 `src/policy/scoring.py` 等 |
| D7 | T1.7 | `v1` 评测报告 + 提交决策 | `eval/results/v1.md` + `submissions/log.md` 追加 |
| D7 | T1.8 | Week 1 复盘 | `reports/week1-replay-analysis.md` |

### 4.4 P2 详细任务（D8–14）

| 天 | 任务 ID | 模块 |
|---|------|------|
| D8 | T2.1 | M5 重写：将公开 baseline 中的 mission 类型拆到独立文件 |
| D9 | T2.2 | M5 完善：补全 snipe / crash_exploit / live-doomed salvage |
| D10 | T2.3 | M6 评分升级：引入 PV(γ) + danger map + launch-safety penalty |
| D11 | T2.4 | M8 模式细化：opening / pressure / finishing / very-late 边界 + 4P 对手画像 |
| D12 | T2.5 | M9 plan_moves orchestrator 重写：commitment-aware + 阶段化 |
| D13 | T2.6 | M10 二轮调参（覆盖新增参数） |
| D14 | T2.7 | `v2` 评测报告 + 第 2 次提交 |

### 4.5 P3 详细任务（D15–22）

| 天 | 任务 ID | 模块 |
|---|------|------|
| D15 | T3.1 | M7 GBC tie-break 接入：top-2 差距 < 阈值时启用 |
| D16 | T3.2 | 4P 模式专门优化（kingmaker 规避、second-place 保位） |
| D16 | T3.3 | Week 2 复盘 |
| D17 | T3.4 | 性能优化（热路径缓存、numpy 化、避免不必要的 dict） |
| D18 | T3.5 | A/B 大样本测试（≥ 500 局）确认 v3 真实优于 v2 |
| D19 | T3.6 | `v3` 提交 + 备用版本同时提交 |
| D20-21 | T3.7 | 观察 D19 提交 ELO 表现，做 last-mile 调整 |
| D22 | T3.8 | **最终两版**：稳健版 + 激进版 6/22 提交（这两个进 final eval） |

---

## 5. 评测协议（决定一切信号质量）

### 5.1 本地 vs Kaggle 提交的决策原则

> **结论：85%+ 决策在本地完成，Kaggle 提交只用于最终校准与 4P 验证。**

| 改进类型 | 决策方式 |
|------|------|
| 数值调参（CMA-ES 输出） | 100% 本地 |
| Bug 修复 | 100% 本地 |
| 新增 mission 类 | 100% 本地（≥ 256 局 + 95% CI） |
| 评分公式调整 | 100% 本地 |
| 性能优化（不改逻辑） | 100% 本地 |
| **大版本切换**（如 P1→P2） | 本地 ≥ 500 局确认 → 提交 1 次校准 |
| **4P 模式真实表现** | 必须靠 Kaggle 提交（本地凑不出 3 个不同风格对手） |
| **周度对手分布探针** | 每周 1 次"探针"提交 |

### 5.2 对手池设计

`eval/opponents/` 中放 5 个等级的对手：

| 等级 | 对手 | 用途 |
|------|------|------|
| L0 | `random_agent` | 检验"是不是连基础都没掉"（应 100% 胜） |
| L1 | `nearest_sniper`（来自 `orbit-wars-guide/main.py`） | 简单合理对手（应 90%+ 胜） |
| L2 | `may18_launch_safety`（公开 1039 → 现已沉到 800 左右） | 中等难度（应 70%+ 胜） |
| L3 | `public_heuristic_1110`（即"vickimar 派"4868 行公开版） | 等同于"你最大威胁"（争取 55%+ 胜） |
| L4 | `lb_1200_baseline`（即 pilkwang 派公开版） | 公开最强（争取 50%+ 胜） |

**评测套餐**：默认对 L1–L4 各打 64 局（32 seeds × 2 seats），单版本 256 局，8 进程约 3 分钟。

### 5.3 评测报告标准格式（`eval/results/v{N}.md`）

```markdown
# Eval Report v{N}

- 版本：v{N}
- 评测时间：YYYY-MM-DD HH:MM
- 评测对手池：L1, L2, L3, L4
- 评测 seeds：32 (from BY_ARCHETYPE)
- 每对手局数：64 (32 seeds × 2 seats)
- 总局数：256

## 整体战绩

| Opponent | Games | Wins | Win% | 95% CI | vs v{N-1} Δ |
|----------|-------|------|------|--------|------|
| nearest_sniper | 64 | 63 | 98.4% | [91.6%, 99.7%] | +0.0% |
| may18_launch_safety | 64 | 49 | 76.6% | [64.6%, 85.4%] | +3.1% |
| public_heuristic_1110 | 64 | 37 | 58.6% | [46.0%, 70.2%] | +6.3% ✓ |
| lb_1200_baseline | 64 | 30 | 47.7% | [35.6%, 60.0%] | +8.1% ✓ |
| **Aggregate** | **256** | **179** | **70.3%** | **[64.6%, 75.5%]** | **+4.4%** |

## 按 archetype 分层（vs public_heuristic_1110）

| Archetype | Games | Win% | vs Prev |
|-----------|-------|------|---------|
| high_prod__mostly_static__big_static | 16 | 81% | +5% |
| low_prod__mostly_rotating__big_rotating | 16 | 53% | -2% ⚠ |
| ... | ... | ... | ... |

## 结论

- [x] vs v{N-1} 整体胜率提升显著（Δ ≥ +2% 且 95% CI 下沿 ≥ 0）
- [ ] 部分 archetype 退化（low_prod 系列 -2%）
- 建议：进入下一版本前先排查 low_prod 子集
```

### 5.4 评测统计原则（**必须遵守**）

- **Wilson Score Interval**，不要用正态近似（小样本偏差大）
- 视 `vs Prev Δ > 0 且 Δ - 1.96 × SE_Δ > 0` 为"统计显著提升"
- 用 **SPRT**（顺序概率比检验）可早停：明显 > 50% 或 < 50% 时无需打满 64 局
- **双 seat 必跑**：float drift 会让单 seat 估值偏差 ~3–5%（[seed-panel-preview 评论](community-discussions/seed-panel-preview-128-seeds-32-game-shape-archetypes.md)）

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
- 每个对手的 mission classification 分布（被 EXPAND / SNIPE / RESCUE / WASTE 战胜？）
- 输局 archetype 分布
- 输局 phase 分布（开局 / 中盘 / 收官）
- 1 条**具体可执行**的下版本改进建议

### 5.6 提交配额分配

5/day × 20 day = 100 上限，实际预算：

| 周 | 用 1 个 | 用 2 个 | 用 ≥3 个 |
|----|------|------|------|
| Week 1 | 大部分天闲置 | D7（v1 提交） | — |
| Week 2 | 大部分天闲置 | D14（v2 提交） | — |
| Week 3 | D15–17 闲置 | D18（A/B） | D19（v3 + 备用 + 探针） |
| Week 4 | — | — | **D22（最终 4 选 2，候选 ≥ 4 个）** |

**全周期总提交 ≈ 25–35 次**，远低于上限。**剩余 quota 留给"修 bug 紧急提交"。**

---

## 6. 快速参考

### 6.1 Day 1 第一件事

读完本文件后，Orchestrator 应立即：
1. 创建 `submissions/log.md` 记录 `v0 — repo skeleton complete`
2. 启动 **T0.2**（移植公开 baseline 到模块结构）
3. 同时启动 **T0.3**（评测系统 v1）

### 6.2 关键依赖

```
kaggle-environments>=1.29.1  # 注意：1.0.9 是旧版，必须升级
numpy>=1.24
scikit-learn>=1.3            # 用于 GBC 训练
cma>=3.3                     # CMA-ES
pyarrow>=12.0                # parquet
pandas>=2.0                  # replay 分析
pytest>=7.0                  # 测试
kaggle>=1.5                  # CLI
```

### 6.3 必读文件清单（按优先级）

1. **本文件**（master-plan.md）
2. `orbit-wars-overview.md` — 竞赛规则
3. `orbit-wars-guide/README.md` — 环境机制
4. `orbit-wars-guide/agents.md` — 提交/拉数据流程
5. 按需阅读 `community-discussions/high-priority-assets.md` 列出的社区资料

### 6.4 关键引用代码（不要重复实现）

- 物理公式：`fleet_speed = 1.0 + 5.0 * (log(n)/log(1000))^1.5`
- 对手 baseline 移植源：
  - `eval/opponents/nearest_sniper.py` ← `orbit-wars-guide/main.py`
  - `eval/opponents/may18_launch_safety.py` ← `community-examples/orbit-wars-1039-2-lb-launch-safety-heuristic.ipynb`
  - `eval/opponents/public_heuristic_1110.py` ← `community-examples/recent-high-scores/orbit-wars-heuristic-lb-1110.ipynb`
  - `eval/opponents/lb_1200_baseline.py` ← `community-examples/lb-1200-orbit-wars-ppo-strategy.ipynb`
- 主开发分支起点：`src/policy/plan.py` 从 `community-examples/lb-1200-orbit-wars-ppo-strategy.ipynb` 拆解

### 6.5 当前进度（v0：仓库骨架）

- [x] 目录结构创建
- [x] master-plan.md 落地
- [ ] 顶层 README / requirements.txt / .gitignore
- [ ] src/ placeholder 与接口签名
- [ ] eval/ placeholder
- [ ] tuning/ placeholder
- [ ] 2 个最简对手实现
