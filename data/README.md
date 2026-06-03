# data/ — 数据缓存（v2 IL-as-Prior 主线）

**本目录内容默认不进 git**（见根目录 `.gitignore`），仅保留目录结构与 manifest。

## 子目录

| 目录 | 内容 | 大小预估 | 写入方 |
|------|------|------|------|
| `replays/raw/` | Kaggle Episodes API 拉的 replay JSON（按 `episode_id.json` 命名） | 每局 5–20MB，全量约 15–30GB | M14 `crawler.py` |
| `replays/processed/` | parquet 化的训练数据集（`v{N}.parquet`） | ~80–500MB | M14 `extract_features.py` |
| `replays/manifest.csv` | episode 元信息（in raw/, 但允许进 git，便于回溯） | < 5MB | M14 `crawler.py` |
| `parquet/` | 公开 Parquet 数据集副本（如 Bridelance） | 80MB | 手动或脚本 |
| `episodes/` | 自己 submission_id 对应的 episode list CSV | < 1MB | M12 反馈采集 |

## v2 工作流（D4–D8）

```bash
# 1. 自爬 top-20 → data/replays/raw/{episode_id}.json
python -m tuning.replay_scraper.crawler --top-n 20 --max-per-team 75

# 2. inverse target + 特征抽取 → data/replays/processed/v1.parquet
python -m tuning.replay_scraper.extract_features --version v1

# 3. 数据质量监控 → eval/results/data_quality_v1.md
python -m eval.data_quality \
    --parquet data/replays/processed/v1.parquet \
    --output eval/results/data_quality_v1.md
```

## 备选数据源（不再作为 v2 主路径，仅作为回退）

1. 社区 Parquet 数据集（Bridelance）：
   ```bash
   kaggle datasets download nbridelancetb/orbit-wars-replay-parquet --unzip -p data/parquet/
   ```
   注意：数据可能滞后 1-2 周，且不包含最新 top-5 RL 提交。

2. bovard top-10% daily：
   ```bash
   kaggle datasets download bovard/orbit-wars-top10-episodes-2026-05-04 --unzip -p data/replays/raw/
   ```
   注意：**2P 几乎全缺**，仅 4P 部分可用。

## 拉取自己 submission 的 replay（败局诊断）

```bash
python -m tuning.replay_analyzer download \
    --submission_id 12345678 \
    --losses-only \
    --output-dir data/replays/raw/
```
