# Replay Scraper（M14）

Kaggle Episodes API 自爬 + ETL 管线。Orbit Wars v2 IL-as-Prior 主线的**数据基础设施**。

## 子模块

| 文件 | 职责 |
|------|------|
| `kaggle_api.py` | Kaggle Episodes API 最小化封装（auth / leaderboard / list / replay） |
| `crawler.py` | Top-N → submissions → episodes → replay 的调度器 |
| `inverse_target.py` | 把"launch angle"反推为"target planet id"（来自 IL notebook Cell 7） |
| `extract_features.py` | replay JSON → 47-dim 特征 + label，落 parquet |

## 完整工作流（D4 → D8）

```bash
# Step 1: 自爬 top-20 玩家最近 75 局 replay（约 1500 episodes，~3-5 天分批跑）
python -m tuning.replay_scraper.crawler \
    --top-n 20 --max-per-team 75 \
    --output-dir data/replays/raw \
    --manifest data/replays/manifest.csv \
    --quota-gb 4.0

# Step 2: 验证 inverse_target 解析率（随机抽 100 个）
python -m tuning.replay_scraper.inverse_target --sanity-check 100

# Step 3: 批量抽取特征 → parquet
python -m tuning.replay_scraper.extract_features \
    --raw-dir data/replays/raw \
    --manifest data/replays/manifest.csv \
    --output data/replays/processed/v1.parquet \
    --version v1

# Step 4: 数据质量报告（M16）
python -m eval.data_quality \
    --parquet data/replays/processed/v1.parquet \
    --output eval/results/data_quality_v1.md
```

## 输出 schema

### `data/replays/manifest.csv`

| 列 | 类型 | 含义 |
|----|------|------|
| episode_id | int | Kaggle episode ID |
| submission_id | int | 提交 ID |
| team_name | str | 提交队伍名 |
| players_count | int | 2 / 4 |
| is_winner | bool | 该提交是否赢这局 |
| updated_score | float | 局后 ELO |
| create_time | str | ISO 时间 |
| bytes_size | int | replay JSON 字节数 |

### `data/replays/processed/v{N}.parquet`

每行 = 一个"决策机会"（某玩家在某 tick 的一次出舰决策，或一次"选择不出舰"）。

| 列 | 类型 | 含义 |
|----|------|------|
| episode_id | int | replay 来源 |
| tick | int | 决策发生的 tick |
| player_id | int | 决策者 |
| players_count | int | 2 / 4 |
| winner_id | int | 该局赢家 |
| source_id | int | 发起 planet（act=[]时为 -1） |
| target_id | int | 目标 planet（未命中 / idle 时为 -1） |
| ships | int | 派出 ship 数（idle 时为 0） |
| ships_frac | float | ships / source.ships at launch |
| label_act | int | 1 = 出舰, 0 = idle |
| f_my_ship_ratio | float | 全局特征 #1 |
| f_my_planet_ratio | float | 全局特征 #2 |
| ... | ... | 共约 47 维特征字段 |

## 约束（必须遵守）

1. **Kaggle quota**: 5 GB/day 上限，本模块默认 4 GB/day 安全线
2. **解析率**: inverse_target 解析率 < 85% 时停止入库
3. **2P/4P 比例**: 解析完成后 2P 必须 ≥ 30%（否则触发 self-play 补充）
4. **中断恢复**: 任何中断后重启都必须从 manifest.csv 续抓
5. **不要修改其他模块**: 本目录的代码不应该 import `src/**` 或 `eval/**`

## 已知坑

- bovard 历史 top-10% 数据集 2P **几乎全缺**，但 API 自爬不存在这个问题
- Kaggle Episodes API 是 grpc-web 风格的 JSON RPC，必须配 `X-XSRF-TOKEN` header
- 单 replay 体积 5-20 MB，超时阈值要拉宽到 60s
- 同一 submission 的 episode 创建时间会跨多天，要按 `create_time` 排序

## 参考

- IL notebook 的 inverse target：[`community-examples/data-generation-expert-imitation-for-rl.ipynb`](../../community-examples/data-generation-expert-imitation-for-rl.ipynb) Cell 7
- bovard 数据集（带 bug 警示）：[`community-discussions/orbit-wars-top-10-daily-episode-replay-datasets-pinned.md`](../../community-discussions/orbit-wars-top-10-daily-episode-replay-datasets-pinned.md)
- Bridelance 经验：[`community-discussions/replay-dataset-parquet-3000-games-ready-to-analyze.md`](../../community-discussions/replay-dataset-parquet-3000-games-ready-to-analyze.md)
