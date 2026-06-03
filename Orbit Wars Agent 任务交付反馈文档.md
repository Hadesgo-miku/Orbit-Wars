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

## T0.5–T0.9 启动模板（占位，待 T0.4 完成后填充）

- **T0.5**（D5 / M14 / Replay Analyst）：跑全量 top-20 抓取，达到 ≥ 1500 episodes
- **T0.6**（D6 / M14 / Replay Analyst）：实现 `inverse_target.resolve_target` 并跑 50 个 episode 的解析率验证
- **T0.7**（D7 / M14 / Replay Analyst）：实现 `extract_features.run_extract`，输出 `data/replays/processed/v1.parquet`
- **T0.8**（D7 / M16 / Eval Lead）：实现 `eval/data_quality.run_quality_check`，输出 `eval/results/data_quality_v1.md`
- **T0.9**（D8 / Orchestrator）：审查数据集 v1，决定是否进入 Phase B

