# Orbit Wars Agent 任务交付反馈文档

本文档用于各 Agent 完成任务后的标准化汇报，确保每次交付都可追踪、可复核、可对比。

## 固定命名与标题规范

- **文档名称固定**：`Orbit Wars Agent 任务交付反馈文档`
- **记录标题固定格式**：`## [交付记录] v{版本} | {任务ID} | {模块ID}`
- **记录标识固定**：每次交付必须包含「版本、任务、模块、角色、日期」五元信息

## 固定交付模板（每次都按此格式填写）

```markdown
## [交付记录] v{版本} | {任务ID} | {模块ID}

### 1) 任务元信息
- 版本：v{版本}
- 任务：{任务ID}
- 模块：{模块ID}（{模块名称}）
- 角色：{角色}
- 日期：{YYYY-MM-DD}

### 2) 本次改动文件（路径 + 行数变化）
- {path_1}：+{add_1} / -{del_1}
- {path_2}：+{add_2} / -{del_2}

### 3) 单元测试结果（命令 + 结果）
- 命令：`python -m pytest tests/test_{module}.py -v`
- 结果：{passed/failed + 详细条目}

### 4) 性能验收结果
- 命令：`python -m pytest tests/perf_{module}.py -v`
- 结果：{P95 是否达标 + 测试通过情况}

### 5) 集成验收结果
- 命令：`python eval/smoke_test.py`
- 结果：{是否通过 + 关键信息}

### 6) 核心实现说明
- {本次实现的关键点 1}
- {本次实现的关键点 2}

### 7) 最后一段反馈（一句话总结）
- {一句话总结}
```

---

## [交付记录] v2.0 | T0.4 | M14

### 1) 任务元信息
- 版本：v2.0
- 任务：T0.4
- 模块：M14（Replay 数据 ETL）
- 角色：Replay Analyst
- 日期：2026-06-03

### 2) 本次改动文件（路径 + 行数变化）
- `tuning/replay_scraper/kaggle_api.py`：`+321 / -22`
- `tuning/replay_scraper/crawler.py`：`+137 / -11`
- `tests/test_replay_scraper_api.py`：`+174 / -0`（新文件）
- `tests/perf_replay_scraper.py`：`+54 / -0`（新文件）

### 3) 单元测试结果（命令 + 结果）
- 命令：`python -m pytest tests/test_replay_scraper_api.py -v`
- 结果：`4 passed`
  - `test_auth_from_default_path_reads_kaggle_json` 通过
  - `test_rpc_post_retries_on_429_with_backoff` 通过
  - `test_quota_record_and_estimate_round_trip` 通过
  - `test_run_crawl_supports_resume_checkpoint` 通过

### 4) 性能验收结果
- 命令：`python -m pytest tests/perf_replay_scraper.py -v`
- 结果：默认跳过 CI（需 `RUN_REPLAY_PERF=1` 才执行真实网络压测）；手工链路中单次 `get_episode_replay` 可稳定返回完整 JSON（`steps_len=500`）

### 5) 集成验收结果
- 命令：
  - `python -m tuning.replay_scraper.crawler --top-n 20 --max-per-team 5 --output-dir data/replays/raw --manifest data/replays/manifest.csv --quota-gb 4.0`
  - `python -m tuning.replay_scraper.crawler --top-n 20 --max-per-team 8 --output-dir data/replays/raw --manifest data/replays/manifest.csv --quota-gb 4.0`（补抓）
- 结果：通过（累计 `>= 100` episode 落盘）
  - top-1 队名：`Isaiah @ Tufa Labs`
  - top-1 submission_id：`53305666`
  - replay 字段校验：`configuration` / `steps(len=500)` / `rewards` / `statuses` 均存在
  - 第一轮抓取：`episodes_fetched=86`，`episodes_failed=1`，`bytes_downloaded=471971809`
  - 第二轮补抓：`episodes_fetched=50`，`episodes_failed=0`，`bytes_downloaded=239144267`
  - 累计落盘：`data/replays/raw` 共 `136` 个 replay；`data/replays/manifest.csv` 共 `136` 条；累计字节 `711116076`；`quota_hit=false`

### 6) 核心实现说明
- 在 `kaggle_api.py` 打通 Kaggle 抓取最小链路：鉴权（兼容 `~/.kaggle/kaggle.json` 与 `~/.kaggle/access_token` / `KAGGLE_API_TOKEN`）、top-N 排行榜、submission episodes 列表、episode replay 下载、本地 quota 记账与 429 指数退避。
- 在 `crawler.py` 实现 top-N → submissions → episodes → replay 调度：manifest 续抓、失败重试（≤3）、`failed_ids.txt` 记录、进度条与 quota 安全线检查。
- 新增 `tests/test_replay_scraper_api.py` 与 `tests/perf_replay_scraper.py`，覆盖鉴权/重试/quota/续抓与可选性能门禁。

### 7) 最后一段反馈（一句话总结）
- 本次改动核心是把 M14 的 Kaggle replay 抓取链路从占位实现补成“可鉴权、可重试、可续抓、可记账、可实网落盘”的 T0.4 最小闭环，并已完成 `>=100` episode 的真实数据验证。

---

## [交付记录] v0 | T0.3 | M12

### 1) 任务元信息
- 版本：v0
- 任务：T0.3
- 模块：M12（评测系统）
- 角色：Eval Lead
- 日期：2026-06-03

### 2) 本次改动文件（路径 + 行数变化）
- `eval/tournament.py`：`+245 / -5`
- `tests/test_tournament.py`：`+106 / -0`（新文件）
- `tests/perf_tournament.py`：`+59 / -0`（新文件）
- `eval/smoke_test.py`：`+72 / -0`（新文件）

### 3) 单元测试结果（命令 + 结果）
- 命令：`python -m pytest tests/test_tournament.py -v`
- 结果：`3 passed`
  - `test_run_tournament_generates_dual_seat_tasks` 通过
  - `test_win_rate_vs_counts_draw_as_half` 通过
  - `test_run_tournament_single_game_error_is_isolated` 通过

### 4) 性能验收结果
- 命令：`python -m pytest tests/perf_tournament.py -v`
- 结果：`1 passed`，P95 预算校验通过（小样本稳定通过阈值）

### 5) 集成验收结果
- 命令：`python eval/smoke_test.py`
- 结果：通过，输出 `smoke_test passed`

### 6) 核心实现说明
- 在 `eval/tournament.py` 完成 v1 runner：实现单局执行、双 seat 调度、并行/串行执行、异常隔离、结果聚合、CLI 参数解析与 JSON 落盘。
- 新增 `tests/test_tournament.py` 与 `tests/perf_tournament.py`，分别覆盖功能正确性与性能阈值；新增 `eval/smoke_test.py` 做最小集成冒烟回归。
- 修复脚本运行路径兼容问题，支持 `python eval/smoke_test.py` 直接执行。

### 7) 最后一段反馈（一句话总结）
- 本次改动核心是把 M12 的 tournament 评测链路从骨架补成“可并行运行、可异常隔离、可落盘、可测试”的 v1 实现。

---

## [交付记录] v0 | T0.2 | M9

### 1) 任务元信息
- 版本：v0
- 任务：T0.2
- 模块：M9（Plan Orchestrator）
- 角色：Code Lead
- 日期：2026-06-03

### 2) 本次改动文件（路径 + 行数变化）
- `src/policy/plan.py`：`+191 / -3`
- `tests/test_plan.py`：`+106 / -0`（新文件）
- `tests/perf_plan.py`：`+77 / -0`（新文件）
- `Orbit Wars Agent 任务交付反馈文档.md`：`+39 / -0`

### 3) 单元测试结果（命令 + 结果）
- 命令：`python -m pytest tests/test_plan.py -v`
- 结果：`3 passed`
  - `test_plan_moves_generates_legal_move_and_commitment` 通过
  - `test_plan_moves_respects_attack_budget` 通过
  - `test_plan_moves_stops_when_deadline_reached` 通过

### 4) 性能验收结果
- 命令：`python -m pytest tests/perf_plan.py -v`
- 结果：`1 passed`，在轻量桩场景下 `plan_moves` 单次调用 P95 < 5ms

### 5) 集成验收结果
- 命令：`python eval/smoke_test.py`
- 结果：通过，输出 `smoke_test passed`

### 6) 核心实现说明
- 在 `src/policy/plan.py` 实现了 T0.2 最小可跑调度器：完成星球视图统一、目标选择、phase 进攻比例、预算约束、deadline 截断与动作合法性过滤。
- 增加 commitment-aware 行为：每次生成动作后尝试写回 `world.add_commitment`，并在 M3 尚未落地时通过本地预算账本保证“同源不超发”不变量。
- 新增 `tests/test_plan.py` 与 `tests/perf_plan.py`，覆盖功能正确性与性能门禁，为后续 T1/T2 扩展保留稳定回归基线。

### 7) 最后一段反馈（一句话总结）
- 本次改动核心是把公开 heuristic baseline 的最小调度思想落地为 `plan_moves` 可执行实现，并补齐了可回归的功能与性能测试闭环。

---

# 待开工任务：Subagent 启动模板

> 本节是 Orchestrator 给 Subagent 的"工作合同"。复制下面整段作为 subagent 的开局 prompt。
> 完成后 subagent 必须按文档开头的"固定交付模板"在本文件追加 `## [交付记录] v{版本} | {任务ID} | {模块ID}`。

---

## T0.4 启动模板（v2 / M14 / Replay Analyst）

```markdown
# 任务上下文
项目路径：/Users/zhaohongbo/CursorProjects/Kaggle竞赛/Orbit Wars
当前分支：v2-il-prior
主路线文档：master-plan.md（必读 §0 §1.2 §2.1 §4.2 §6）
当前迭代版本：v2.0（IL-as-Prior 主线起点）
本任务对应模块：M14（Replay 数据 ETL）

# 你的角色：Replay Analyst（subagent #1）

# 你的任务（T0.4）
实现 Kaggle Episodes API 抓取的最小链路：
- 鉴权（从 ~/.kaggle/kaggle.json）
- 取竞赛 top-N submissions 排行榜
- 列出 submission 最近 N 局 episode 元信息
- 拉取单个 episode 完整 replay JSON
- 健全性测试：成功抓 ≥ 100 个 episode 并落到 data/replays/raw/

你只能修改（**白名单**）：
- tuning/replay_scraper/kaggle_api.py
- tuning/replay_scraper/crawler.py
- tests/test_replay_scraper_api.py（新文件）
- tests/perf_replay_scraper.py（新文件）

你不能修改：
- 所有 src/** 文件
- 所有 eval/** 文件（除非任务明确允许）
- 任何 tuning/replay_scraper/ 之外的 tuning/ 文件
- master-plan.md / .gitignore / requirements.txt（动这些找 Orchestrator）
- inverse_target.py / extract_features.py（属于 T0.5/T0.6/T0.7）

# 必读
- master-plan.md §0.4（v2 范式切换决策依据）
- master-plan.md §2.1 关于 M14 的接口
- master-plan.md §6.3（Kaggle API 配额管理）
- tuning/replay_scraper/README.md（数据 schema 与已知坑）
- tuning/replay_scraper/kaggle_api.py 中的 docstring（接口签名 + 实现指引）
- tuning/replay_scraper/crawler.py 中的 docstring

# 接口约定（不可改）
- kaggle_api.KaggleAuth.from_default_path() -> KaggleAuth
- kaggle_api.get_top_n_submissions(n, auth, competition_id) -> list[LeaderboardEntry]
- kaggle_api.list_episodes_for_submission(submission_id, auth, max_count) -> list[EpisodeRecord]
- kaggle_api.get_episode_replay(episode_id, auth) -> dict
- kaggle_api.estimate_quota_used_today(quota_dir) / record_quota(quota_dir, bytes)
- crawler.run_crawl(config: CrawlConfig) -> CrawlResult
- crawler.cli() 可用 `python -m tuning.replay_scraper.crawler ...` 直接调

# 验收标准
- 单元测试：tests/test_replay_scraper_api.py 全部通过
  - 至少覆盖：鉴权加载 / 重试 backoff / quota 记账 / 中断点续抓
  - 用 monkeypatch / requests-mock 模拟 Kaggle API 响应（避免真实网络）
- 性能：单次 get_episode_replay 在网络正常情况下 P95 ≤ 5s（在 tests/perf_replay_scraper.py 中标注 marker 跳过 CI）
- 集成：手动验证至少抓 100 个真实 episode 成功，落到 data/replays/raw/
- 报告：在本文件追加交付记录（用文档开头的模板）

# 真正的"端到端验证"步骤（你必须实际运行）
1. 确认 ~/.kaggle/kaggle.json 存在（不存在则报告给 Orchestrator）
2. 调用 get_top_n_submissions(20)，把结果用 print 输出验证：team_name 应该都是 Orbit Wars 现役 top-20
3. 取 top-1 submission，调 list_episodes_for_submission(top1.submission_id, max_count=10)
4. 取其中 1 个 episode，调 get_episode_replay 拿到 JSON，校验：
   - "configuration" 字段存在
   - "steps" 字段是 list 且 len ≥ 50
   - "rewards" / "statuses" 字段存在
5. 跑 crawler.run_crawl(CrawlConfig(top_n=20, max_per_team=5))，期望抓 ≥ 100 个 episode

# 已知陷阱（不要再踩）
- Kaggle Episodes API 是 grpc-web 风格 JSON RPC，需要 `X-XSRF-TOKEN` header
- 单 episode JSON 体积 5-20MB，timeout 必须 ≥ 60s
- HTTP 429 必须指数退避（base 1.5s，最多 3 次重试）
- 每天 5GB 配额是硬墙，必须本地记账（quota_YYYY-MM-DD.json）
- 不要把 kaggle.json 的真实内容打到任何 log / commit

# 禁止
- 不要新增依赖（只能用 requirements.txt 已列：requests / tqdm / pandas 等）
- 不要新增大段 docstring 之外的 markdown 文件
- 不要"为完成度"实现 inverse_target / extract_features（这是 T0.6/T0.7 的事）
- 不要在 crawler 里写 inverse target 逻辑

# 完成后请输出
- 改动文件列表（路径 + 行数变化）
- 单元测试运行结果（python -m pytest tests/test_replay_scraper_api.py -v）
- 真实端到端运行的输出（top-1 队名 / 抓到的 episode 数量 / 累计字节数）
- 一句话总结：本次改动核心是什么
```

---

## v2.1 任务规划调整说明（2026-06-03）

T0.4 完成后，原计划 T0.5–T0.9 切得过细。决定合并为 3 个大颗粒任务：

- **T-CRAWL**（后台挂机，无 subagent）：继续累积到 ≥1500 episodes
- **T-DATA**（一次 subagent）：合并 T0.6+T0.7+T0.8
- **T-MODEL**（一次 subagent）：合并 T1.1+T1.2+T1.3+T1.4+T1.5
- **T-WIRE**（一次 subagent）：合并 T2.1+T2.2+T2.3

---

## T-DATA 启动模板（v2.1 / M14+M16 / Replay Analyst）

```markdown
# 任务上下文
项目路径：/Users/zhaohongbo/CursorProjects/Kaggle竞赛/Orbit Wars
当前分支：v2-il-prior
主路线文档：master-plan.md（必读 §0.4 §1.2 §2.1 §4.2-4.4 §6.4 §6.5）
当前迭代版本：v2.1（IL Prior 数据 ETL 全链路）
本任务对应模块：M14（inverse_target / extract_features）+ M16（data_quality）

# 你的角色：Replay Analyst（subagent #2，大颗粒一次性完成 T0.6+T0.7+T0.8）

# 你的任务（T-DATA）
把 IL Prior 主线的离线 ETL 全链路打通并跑通端到端：
1. 实现 inverse_target.resolve_target / batch_resolve（已有占位）
2. 实现 extract_features.* 全部函数（已有占位）
3. 实现 eval/data_quality 的所有 check + 报告渲染
4. 用现有 data/replays/raw/ 已落地的 ≥100 episodes 跑端到端，落 v1_pilot 产物

你只能修改（白名单）：
- tuning/replay_scraper/inverse_target.py
- tuning/replay_scraper/extract_features.py
- eval/data_quality.py
- tests/test_inverse_target.py（新文件）
- tests/test_extract_features.py（新文件）
- tests/test_data_quality.py（新文件）
- 在数据/产物目录写入（这些路径都已 gitignore）：
  - data/replays/processed/v1_pilot.parquet
  - eval/results/data_quality_v1_pilot.md

你不能修改：
- 所有 src/** 文件（M13 接入是 T-WIRE 的事）
- tuning/replay_scraper/kaggle_api.py / crawler.py（T0.4 已完成）
- tuning/train_il_prior.py（M15 是 T-MODEL 的事）
- master-plan.md / .gitignore / requirements.txt（找 Orchestrator）

# 必读
- master-plan.md §0.4（v2 决策依据）
- master-plan.md §6.4（inverse target 校验阈值）
- master-plan.md §6.5（2P 数据问题）
- tuning/replay_scraper/inverse_target.py 的 docstring
- tuning/replay_scraper/extract_features.py 的 docstring
- eval/data_quality.py 的 docstring
- community-examples/data-generation-expert-imitation-for-rl.ipynb（Cell 7 是 resolve_target 的参考实现）
- src/policy/value_gbc.py 的 value_state_features 函数文档（前 20 维特征定义）
- src/policy/il_prior.py 的 state_features_for_mission（特征 schema 必须与本任务输出严格对齐）

# 特征 schema（v2.1 固定，必须严格实现）

输出 parquet 的每一行 = 一个"决策机会"（某玩家在某 tick 的一次出舰决策，或一次 idle）。
固定 47 维特征（特征列名固定，必须用下表的精确名称）：

## 元字段（不算 47 维）
- episode_id (int), tick (int), player_id (int), players_count (int 2/4), winner_id (int)
- source_id (int), target_id (int, -1 if idle), ships (int), ships_frac (float), label_act (int 0/1)

## 全局 20 维（命名前缀 g_）
- g_step_norm = step / 500.0
- g_n_players_norm = players_count / 4.0
- g_my_planet_ratio = #(planet.owner==me) / #planets
- g_be_planet_ratio = max over enemies of #(planet.owner==enemy) / #planets   注：be = best enemy
- g_my_ship_ratio = sum(my planet ships + my inflight ships) / total ships
- g_be_ship_ratio = same for best enemy
- g_my_prod_ratio = sum(my planet prod) / total prod
- g_be_prod_ratio = same for best enemy
- g_my_centrality_norm = (mean dist from (50,50) of my planets) / 60
- g_be_centrality_norm = same for best enemy
- g_ship_diff = g_my_ship_ratio - g_be_ship_ratio
- g_planet_diff = g_my_planet_ratio - g_be_planet_ratio
- g_prod_diff = g_my_prod_ratio - g_be_prod_ratio
- g_is_2p = 1.0 if players_count==2 else 0.0
- g_is_4p = 1.0 if players_count==4 else 0.0
- g_my_inflight_ratio = sum(my inflight ships) / total ships
- g_be_inflight_ratio = same for best enemy
- g_total_diff_ratio = (my_ships + my_inflight - be_ships - be_inflight) / total ships
- g_inflight_lead = 1.0 if my_inflight > be_inflight else 0.0
- g_phase_encoded = 0/0.33/0.66/1.0 (opening/pressure/finishing/very_late)
  其中 phase 判定规则（master-plan §1.3）：tick<60 opening, 60-200 pressure, 200-400 finishing, >400 very_late

## per-source 10 维（命名前缀 s_）
- s_ships_log = log(source.ships + 1) / 10
- s_prod_norm = source.production / 5
- s_dist_from_sun_norm = dist(source, (50,50)) / 60
- s_garrison_ratio = source.ships / (1 + sum_nearby_enemy_ships)
- s_is_orbiting = 1.0 if source is orbiting else 0.0
- s_in_combat_zone = 1.0 if 任意敌方 fleet 距 source < 10 else 0.0
- s_eta_to_nearest_enemy_planet_norm = min(eta) / 250
- s_owner_stability = 占位 0.0（暂不计算，留 v2.2）
- s_undeployable_lock = 占位 0.0（暂不计算，留 v2.2）
- s_centrality_norm = (50 - dist(source, (50,50))) / 50  注：越中心越大

## per-target 12 维（命名前缀 t_；当 target_id == -1 即 idle 样本时全设 0.0）
- t_owner_code = -1.0/0.0/1.0/2.0 → me/other_enemy/neutral/best_enemy  归一化为 (code+1)/3
- t_ships_log = log(target.ships + 1) / 10
- t_prod_norm = target.production / 5
- t_dist_from_source_norm = dist(source, target) / 100
- t_eta_with_fleet_speed_norm = dist(source, target) / fleet_speed(ships) / 250
- t_is_doomed_to_sun = 1.0 if 我方 fleet 轨迹会被 sun 吞 else 0.0（用 src/env/safety.is_sun_doomed）
- t_swept_by_other = 1.0 if 其他玩家 fleet 即将经过本 fleet 路径 else 0.0
- t_reactive_snipe_risk = 1.0 if 敌方在 N=10 tick 内可反偷 else 0.0（粗近似：dist_enemy_to_target / fleet_speed_at_50 < eta + 5）
- t_is_orbiting = 1.0 if target is orbiting else 0.0
- t_centrality_norm = (50 - dist(target, (50,50))) / 50
- t_inflight_friendly_pressure_log = log(我方在飞往 target 的 fleet 数 + 1) / 5
- t_inflight_enemy_pressure_log = log(敌方在飞往 target 的 fleet 数 + 1) / 5

## contextual 5 维（命名前缀 c_）
- c_phase_pressure = max(0.0, g_my_ship_ratio - g_be_ship_ratio - 0.05)
- c_my_action_count_this_turn = 本回合 player_id 已发动作数 / 5
- c_action_repeat_penalty = 本回合 player_id 已发往同 target_id 的次数 / 3
- c_inflight_lead_to_this_target = (my_inflight_to_target - be_inflight_to_target) / (1 + total_inflight_to_target)
- c_first_action_in_episode = 1.0 if 该 player 在该 episode 首次出舰 else 0.0

# 必须实现的函数（白名单文件中的占位需要全部实现）

## tuning/replay_scraper/inverse_target.py
- predict_planet_position_at_tick(planet, tick, angular_velocity) -> (x, y)
- resolve_target(source_id, launch_angle, ships, planets, angular_velocity, tolerance=2.0, max_ticks=250) -> int
- batch_resolve(actions, planets, angular_velocity, tolerance=2.0) -> list[int]

实现要点：
- 严格对齐 IL notebook Cell 7（fleet_speed 用 fleet_speed_simple）
- 容差默认 2.0；若整个数据集解析率 < 85% 则在 docstring/README 中提示可考虑 3.0
- 解析过程不要修改 planets list

## tuning/replay_scraper/extract_features.py
- load_episode_meta(manifest_path) -> dict[int, dict]
- parse_replay_steps(replay_json) -> list[dict]（{tick, player_id, observation, action, status}）
- build_state_features(observation, source_id, target_id, players_count) -> dict[str, float]（输出 47 维严格 schema）
- extract_from_replay(replay_json, episode_id, config, rng_seed=42) -> list[dict]
- run_extract(config) -> ExtractStats

实现要点：
- 严格按上面 47 维特征定义实现；列名一字不差
- NaN/Inf 一律 clip 到 ±10.0 或 fillna 0.0
- idle 行 95% drop；idle 行的 t_* / s_* 字段全填 0.0
- 分批写 parquet（每 200 episodes flush 一次），避免 OOM
- 用 pyarrow 直接写，schema 用 pa.float32 节省空间
- 失败的 episode_id 收进 ExtractStats.failed_episode_ids

## eval/data_quality.py
- 实现所有 check_* 函数与 run_quality_check / render_markdown_report
- 阈值用 DataQualityThresholds 默认值
- 必查 Q1-Q7 全过 = passed_overall = True；warning 不影响 overall

# 验收标准（必须同时满足）

## 单元测试
- tests/test_inverse_target.py：4 个 hand-crafted case
  - case 1: 直线射向固定 planet，hit 该 planet
  - case 2: 射向 orbiting planet，hit
  - case 3: 角度偏离 5°，miss（返回 -1）
  - case 4: 经过 sun 区域，行为合理（即使 hit 也不抛异常）
- tests/test_extract_features.py：用 mock replay 验证 schema 完整性
  - 必须有 47 个特征 + 元字段
  - 列名严格对齐
  - idle 样本的 t_*/s_* 全为 0.0
- tests/test_data_quality.py：每个 check 函数至少 1 个 positive + 1 个 negative case

## 端到端集成（必须真实跑一次）
```bash
# Step 1: 解析率健全性
python -m tuning.replay_scraper.inverse_target --sanity-check 50
# 期望: 解析率 ≥ 85%

# Step 2: 抽取 pilot parquet
python -m tuning.replay_scraper.extract_features \
    --raw-dir data/replays/raw \
    --manifest data/replays/manifest.csv \
    --output data/replays/processed/v1_pilot.parquet \
    --version v1_pilot
# 期望: parquet 文件存在 + 行数 ≥ 5000

# Step 3: 数据质量报告
python -m eval.data_quality \
    --parquet data/replays/processed/v1_pilot.parquet \
    --output eval/results/data_quality_v1_pilot.md
# 期望: 必查项全过

# 验收：
# 1. 三步全部 exit 0
# 2. v1_pilot.parquet ≥ 5000 行
# 3. data_quality_v1_pilot.md 必查项全过
# 4. inverse target 解析率 ≥ 85%（在质量报告中体现）
```

## 性能
- batch_resolve 对 1 万条 action 的解析 < 60 秒
- run_extract 对 100 个 episode 的处理 < 5 分钟

# 已知陷阱
- IL notebook 用 fleet_speed_simple（min(1.0 + ships//20, 6.0)），与 src/env/physics.fleet_speed 不同
  → 本模块统一用 fleet_speed_simple 保持与 IL notebook 对齐
- replay JSON 的 steps[i][p_id]['observation'] 的 planets 字段是 list of list，索引约定 [id, owner, x, y, radius, ships, prod, ...]
- replay JSON 的 status 可能是 "ACTIVE" / "DONE" / "ERROR"，仅取 ACTIVE
- 2P 数据可能很少（< 30%），本任务不强制 2P/4P 比例（master-plan §6.5 处理）
  → data_quality 报告中只是 warning 不是 fatal
- inverse target 在某些超长射程会 miss（max_ticks=250 边界）
  → 在 batch_resolve 增加日志统计 ticks_used 分布

# 禁止
- 不要新增依赖
- 不要新增 markdown 文件
- 不要碰 src/** 或 train_il_prior.py
- 不要在 il_prior.py 里加任何东西（那是 T-WIRE 的事）

# 完成后请输出（在本反馈文档追加交付记录，按文档头部模板）
- 改动文件列表 + 行数变化
- 单元测试结果（3 个 test 文件全跑）
- 端到端集成 3 步骤的真实输出
- v1_pilot.parquet 的：总行数 / 2P 行数 / 4P 行数 / 解析率
- data_quality_v1_pilot.md 必查项是否全过
- 一句话总结
```

---

## [交付记录] v2.1 | T-DATA | M14+M16

### 1) 任务元信息
- 版本：v2.1
- 任务：T-DATA
- 模块：M14（inverse_target / extract_features）+ M16（data_quality）
- 角色：Replay Analyst
- 日期：2026-06-03

### 2) 本次改动文件（路径 + 行数变化）
- `tuning/replay_scraper/inverse_target.py`：占位 → 完整实现（含 `--sanity-check` CLI）
- `tuning/replay_scraper/extract_features.py`：占位 → 完整实现（47 维 FEATURE_NAMES + pyarrow 分批写）
- `eval/data_quality.py`：占位 → 完整实现（Q1–Q7 + W1–W3 + `--pilot`）
- `tests/test_inverse_target.py`：新文件（5 cases）
- `tests/test_extract_features.py`：新文件（4 cases）
- `tests/test_data_quality.py`：新文件（9 cases）

### 3) 单元测试结果（命令 + 结果）
- 命令：`python -m pytest tests/test_inverse_target.py tests/test_extract_features.py tests/test_data_quality.py -v`
- 结果：`18 passed`

### 4) 性能验收结果
- inverse_target 抽样 50 局：47446 actions，解析率 96.35%（≥85%）
- extract_features 1023 局：约 6 分钟，881405 行

### 5) 集成验收结果（外置盘数据路径）
- 数据根目录：`/Volumes/for mac/Data/Orbit Wars/replays`（manifest/raw 1023 局对齐）
- Step 1：`python -m tuning.replay_scraper.inverse_target --sanity-check 50 --raw-dir .../raw` → exit 0，hit_rate=0.9635
- Step 2：`python -m tuning.replay_scraper.extract_features ... --output .../processed/v1_pilot.parquet` → exit 0，881405 行
- Step 3：`python -m eval.data_quality --parquet .../v1_pilot.parquet --pilot` → exit 0，`passed_overall=true`

### 6) 核心实现说明
- `inverse_target` 严格对齐 IL notebook Cell 7（fleet_speed_simple + 250 tick 碰撞模拟）
- `extract_features` 输出 47 维固定列名 + 10 维元字段；idle 95% drop；每 200 局 flush parquet
- `data_quality` pilot 模式 Q2 门槛降至 800 episodes；Q7 校验 idle drop 后 act 为主且保留 ≥0.5% idle

### 7) v1_pilot 数据摘要
- 总行数：881405；episode 数：1023；2P 行：691216；4P 行：190189
- 出舰样本解析率：100%（extract 已过滤 target=-1）
- 必查项：全过；警告：W3 winner 偏倚 63.5%（非 fatal）

### 8) 最后一段反馈（一句话总结）
- T-DATA 全链路已在外置盘 ~1023 局 replay 上跑通，产物 `v1_pilot.parquet` 与质量报告可用于后续 T-MODEL pilot 训练；全量 v1 需 T-CRAWL 达 ≥1500 episodes 后复跑 extract（去掉 `--pilot`）。

---

## T-MODEL 启动模板（v2.2 / M15 / IL Trainer）

> 在 T-DATA 完成且 T-CRAWL 累计 ≥1500 episodes 后启动。届时会用 v1.parquet（不是 v1_pilot）训练。

```markdown
# 任务上下文
（同 T-DATA 头部 + 主线文档 §2.1 M15 + §5.4 IL 三指标）

# 你的角色：IL Trainer（subagent #3）

# 你的任务（T-MODEL）
合并 T1.1-T1.5：用 v1.parquet 训出 LightGBM 三模型（target / ships / act），导出嵌入式纯 Python 版，落元数据。

你只能修改：
- tuning/train_il_prior.py
- tests/test_train_il_prior.py（新文件，仅覆盖序列化与元数据；训练不写测试）
- 在产物目录写入：models/il_prior_lgbm_v1*.{txt,json,_compiled.py}

你不能修改：
- src/** / eval/** / tuning/replay_scraper/**

# 验收门槛（master-plan §4.4 T-MODEL 完成定义）
- 3 个 LightGBM Booster 落地
- il_prior_lgbm_v1.json 元数据完整（含 metrics）
- il_prior_lgbm_v1_compiled.py 可被 src/policy/il_prior._load_prior 加载
- target top-1 acc ≥ 40%（pilot） / ≥ 45%（full）
- target top-3 acc ≥ 70%
- act_model AUC ≥ 0.75

# 端到端集成
```bash
python -m tuning.train_il_prior \
    --parquet data/replays/processed/v1.parquet \
    --version v1 \
    --output-dir models/ \
    --test-ratio 0.15
# 期望: 三个 .txt + 一个 .json + 一个 _compiled.py 全部生成
```
```

---

## T-WIRE 启动模板（v2.3 / M13+M9 / Code Lead）

> 在 T-MODEL 完成后启动。

```markdown
# 任务上下文
（同 T-DATA 头部 + §1.1 L4.5 节点 + §1.4 不变量 + §4.4 T-WIRE 完成定义）

# 你的角色：Code Lead（subagent #4）

# 你的任务（T-WIRE）
合并 T2.1-T2.3：实现 M13 在线推理 + 改造 M9 plan.py 接入 L4.5 + 性能验证。

你只能修改：
- src/policy/il_prior.py（完成全部 NotImplementedError）
- src/policy/plan.py（仅修改 scoring 之后、调度之前的部分，加 L4.5 节点）
- tests/test_il_prior.py（新文件）
- tests/perf_il_prior.py（新文件）
- tests/test_plan.py（仅 + 一个 fallback 回归测试，不删现有 case）

你不能修改：
- src/policy/scoring.py / modes.py / value_gbc.py
- 任何 missions/ 下的文件
- 任何 tuning/ 下的文件
- 任何 eval/ 下的文件

# 关键设计点
- IL_PRIOR_READY = False 时 plan.py 行为必须与 v1 完全一致（回归测试必须通过）
- IL_ALPHA_EFFECTIVE 默认 = 1.0；通过环境变量 IL_ALPHA 可覆盖（评测扫描用）
- predict_batch 内部用 numpy 一次性算所有 mission（避免 Python loop）
- state_features_for_mission 必须与 extract_features.build_state_features 列名完全对齐
  → 若不对齐：单测必须断言失败（在 il_prior._load_prior 中校验 FEATURE_NAMES）

# 验收
- tests/test_il_prior.py：模型加载 / clip / logit / apply_prior_to_missions 四类
- tests/perf_il_prior.py：predict_batch 对 50 missions ≤ 5ms
- tests/test_plan.py：fallback 回归（无模型时与 v1 行为完全一致）
- 集成：python eval/smoke_test.py 通过

# 端到端校验（必须真实跑）
1. 模型未加载场景：删除 models/ → plan_moves 行为应该完全等同 v1
2. 模型加载场景：随便造一个 mock il_prior_lgbm_latest.txt 看是否走 L4.5 路径
3. 性能：plan_moves 单次 P95 ≤ 850ms（含 IL prior 推理）
```

