# models/ — 训出来的模型 & 元数据

由 M15（IL prior）与 M11（GBC value）写入。

## 文件命名规范

| 文件 | 内容 | 是否进 git |
|------|------|------|
| `il_prior_lgbm_v{N}_target.txt` | LightGBM Booster (target 模型) | ❌ |
| `il_prior_lgbm_v{N}_ships.txt` | LightGBM Booster (ships_frac 模型) | ❌ |
| `il_prior_lgbm_v{N}_act.txt` | LightGBM Booster (act 模型) | ❌ |
| `il_prior_lgbm_v{N}.json` | 元数据（features / params / metrics / data_version / trained_at） | ✅ |
| `il_prior_lgbm_v{N}_compiled.py` | 纯 Python 树遍历版（提交时一起打包） | ✅ |
| `il_prior_lgbm_latest.txt` | 指向当前激活模型的 symlink（在线 agent 默认加载这个） | ❌（重生成） |
| `value_gbc_v{N}.json` | M11 GBC value function 元数据 + tree 数组 | ✅ |

## 元数据 JSON schema（必填字段）

```json
{
  "version": "v1",
  "data_versions": ["data_v1"],
  "trained_at": "2026-06-12T18:30:00Z",
  "lgbm_target_params": { "num_leaves": 63, "learning_rate": 0.05, "..." },
  "lgbm_ships_params": { "..." },
  "lgbm_act_params": { "..." },
  "test_ratio": 0.15,
  "metrics": {
    "target_top1_acc": 0.473,
    "target_top3_acc": 0.785,
    "ships_mae": 0.14,
    "act_auc": 0.81
  },
  "n_train_pairs": 412350,
  "n_test_pairs": 51420,
  "feature_names": ["my_ship_ratio", "..."]
}
```

## 数据 ↔ 模型版本映射（master-plan §6.2）

| Model | Trained on | Train Date | Target Top-1 | Status |
|-------|-----------|------|------|------|
| il_prior_lgbm_v1 | data_v1 | D12 | TBD | Phase B 交付 |
| il_prior_lgbm_v2 | data_v1 + data_v2 | D19 | TBD | Phase E 交付（条件） |
| il_prior_lgbm_v3 | data_v1 + data_v2 + data_v3 | D21 | TBD | Phase F 最终 |

## 加载顺序（in-agent）

`src/policy/il_prior._load_prior` 按以下优先级搜索：

1. `models/il_prior_lgbm_latest.txt`（symlink）
2. `models/il_prior_lgbm_v{latest}.txt`（按版本号倒序）
3. `/kaggle_simulations/agent/il_prior_lgbm.txt`（提交时 submission.py 同目录）

任何搜索失败 → 静默回退到 v1 启发式行为（IL_ALPHA_EFFECTIVE = 0）。
