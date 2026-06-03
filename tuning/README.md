# tuning/ — 离线调优与训练

| 文件 | 模块 | Owner |
|------|------|------|
| `cma_es.py` | M10 CMA-ES 调参 | Task agent |
| `train_gbc.py` | M11 GBC 价值函数训练 | Task agent |
| `replay_analyzer.py` | Replay 分析工具集 | Replay Analyst |

## 典型工作流

```bash
# 1. 拉最近一次提交的所有败局 replay
python -m tuning.replay_analyzer download \
    --submission_id 12345678 --losses-only

# 2. 跑 CMA-ES 调参（CPU 即可，~1.5 小时）
python -m tuning.cma_es \
    --params tuning/configs/v1_params.json \
    --budget 1500 \
    --output tuning/best_params_v1.json

# 3. 训 GBC 价值函数（CPU 即可，~10 分钟）
python -m tuning.train_gbc \
    --replays data/replays/ \
    --output src/policy/value_gbc_trees.py

# 4. 写周报
python -m tuning.replay_analyzer diagnose \
    --submission_id 12345678 \
    --output reports/submission-v1-diagnosis.md
```

## 调参参数清单（M10 使用）

待 Task agent 在 `tuning/configs/v1_params.json` 中维护。建议初始范围：

```json
[
  {"name": "gamma", "default": 0.99, "lower": 0.97, "upper": 0.999},
  {"name": "capture_hostile_mult", "default": 2.0, "lower": 1.0, "upper": 4.0},
  {"name": "reinforce_mult", "default": 1.35, "lower": 1.0, "upper": 2.0},
  {"name": "launch_safety_floor", "default": 0.4, "lower": 0.2, "upper": 0.7},
  {"name": "launch_safety_scale", "default": 30.0, "lower": 15.0, "upper": 50.0}
]
```
