# Data Quality Report

- 时间：2026-06-03 12:09 UTC
- Parquet：`/Volumes/for mac/Data/Orbit Wars/replays/processed/v1_pilot.parquet`
- 总行数：881405
- 总 episode 数：1023
- 2P 行数：691216
- 4P 行数：190189

## 必查项

- ✅ **Q1** 行数 ≥ min_rows: `881405` (阈值 >= 5000)
- ✅ **Q2** 唯一 episode_id 数 ≥ min_episodes: `1023` (阈值 >= 800 (pilot))
- ✅ **Q3** 2P 行比例 ≥ 30% 或 4P 行比例 ≥ 60%: `2p=0.784, 4p=0.216` (阈值 2p>=0.3 OR 4p>=0.6)
- ✅ **Q4** inverse target 解析率（出舰样本 target_id≥0）: `1.0` (阈值 >= 0.85)
- ✅ **Q5** 特征 schema 与 FEATURE_NAMES 对齐: `ok` (阈值 47 feature cols)
- ✅ **Q6** 特征列无 NaN/Inf: `nan=0, inf=0` (阈值 0)
- ✅ **Q7** label_act=1 行占比合理（idle drop 后）: `act=0.9831, idle=0.0169` (阈值 act in [0.50,0.995], idle >= 0.005)

## 警告项

- ✅ **W1** expert 多样性（无 team_name 列，跳过）: `n/a` (阈值 top1 <= 0.4)
- ⚠️ **W2** tick 分布（opening/mid/late）: `open=0.03, mid=0.62, late=0.35` (阈值 opening >= 3%)
- ⚠️ **W3** 样本行 player 即胜者比例: `0.6353` (阈值 <= 0.6)

## 结论

✅ **通过**（可进入 M15 训练）
