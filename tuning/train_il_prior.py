"""M15 — IL Prior 训练（LightGBM 起步）。

从 ``data/replays/processed/v{N}.parquet`` 训练三个 LightGBM 子模型：

1. **target_model**: ``p(target_id | state, source_id)``  — multiclass over planet ids
2. **ships_model** : ``ships_frac`` 回归 / 分位预测
3. **act_model**   : ``p(act vs idle | state, source_id)`` — binary

落地物：

- ``models/il_prior_lgbm_v{N}_target.txt`` （LightGBM Booster 模型）
- ``models/il_prior_lgbm_v{N}_ships.txt``
- ``models/il_prior_lgbm_v{N}_act.txt``
- ``models/il_prior_lgbm_v{N}.json`` （元数据：feature_names, params, metrics, data_version, trained_at）
- ``models/il_prior_lgbm_v{N}_compiled.py`` （纯 Python 树遍历版，submission.py 友好）

训练目标（master-plan §5.4 IL 三指标）：

- target top-1 accuracy ≥ 45%（held-out）
- target top-3 accuracy ≥ 75%
- act_model AUC ≥ 0.78

CLI：

    python -m tuning.train_il_prior \
        --parquet data/replays/processed/v1.parquet \
        --version v1 \
        --output-dir models/ \
        --test-ratio 0.15
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# 配置 & 默认 LightGBM 超参（v1 起步值）
# ---------------------------------------------------------------------------


@dataclass
class TrainConfig:
    parquet_path: Path = Path("data/replays/processed/v1.parquet")
    version: str = "v1"
    output_dir: Path = Path("models")
    test_ratio: float = 0.15
    seed: int = 42

    # 仅保留 2P/4P 至少 N 局以上的 expert（过滤 noise）
    min_episodes_per_expert: int = 5

    # 类别约束：target 模型按 "目标 planet 在 source 视角下的 rank 序号" 建模（不直接学 absolute planet_id）
    target_n_classes: int = 16  # 最多 16 个 planet（rank by distance / value）

    # LightGBM 默认超参（已是 master-plan §6.2 提到的 v1 起步值）
    lgbm_target_params: dict[str, Any] = field(default_factory=lambda: {
        "objective": "multiclass",
        "num_class": 16,
        "metric": ["multi_logloss"],
        "num_leaves": 63,
        "learning_rate": 0.05,
        "feature_fraction": 0.85,
        "bagging_fraction": 0.85,
        "bagging_freq": 5,
        "min_data_in_leaf": 30,
        "max_depth": -1,
        "verbose": -1,
    })
    lgbm_ships_params: dict[str, Any] = field(default_factory=lambda: {
        "objective": "regression",
        "metric": ["rmse", "l1"],
        "num_leaves": 63,
        "learning_rate": 0.05,
        "feature_fraction": 0.85,
        "min_data_in_leaf": 30,
        "verbose": -1,
    })
    lgbm_act_params: dict[str, Any] = field(default_factory=lambda: {
        "objective": "binary",
        "metric": ["binary_logloss", "auc"],
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.85,
        "min_data_in_leaf": 50,
        "verbose": -1,
    })

    # 早停
    num_boost_round: int = 1500
    early_stopping_rounds: int = 50


@dataclass
class TrainMetrics:
    """训练 + 验证后的指标汇总（落到 il_prior_lgbm_v{N}.json）"""
    target_top1_acc: float = 0.0
    target_top3_acc: float = 0.0
    ships_mae: float = 0.0
    ships_rmse: float = 0.0
    act_auc: float = 0.0
    act_logloss: float = 0.0
    n_train_pairs: int = 0
    n_test_pairs: int = 0
    feature_names: list[str] = field(default_factory=list)
    best_iter_target: int = 0
    best_iter_ships: int = 0
    best_iter_act: int = 0


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------


def load_dataset(config: TrainConfig) -> tuple[Any, Any, Any]:
    """读取 parquet，返回 (df_all, df_train, df_test)。

    实现要点：
        - 用 pyarrow 或 pandas 读 parquet（columns 显式列出，避免读 obs_json 大对象）
        - 按 episode_id 分割 train/test（不要按 sample 分割，避免数据泄漏）
        - 过滤 min_episodes_per_expert 不足的 expert
        - 返回 pandas DataFrame
    """
    raise NotImplementedError(
        "M15/T1.1 待实现：parquet → train/test split (按 episode 分)"
    )


def transform_target_label(df: Any, target_n_classes: int) -> Any:
    """把 absolute target_planet_id 转换为 rank-based class id。

    动机：直接学 absolute planet_id 会导致模型对 planet 数量敏感（2P/4P map 不同）。
    转换：对每个 (state, source_id)，根据某种 ranking（如距离 source 的排序）把
    target 映射到 0..target_n_classes-1。

    输入 df 必须含：source_id, target_id, planet positions/etc.
    输出 df 增加列：target_rank ∈ [0, target_n_classes)
    """
    raise NotImplementedError(
        "M15/T1.1 待实现：absolute planet_id → rank-based class"
    )


# ---------------------------------------------------------------------------
# 三模型训练
# ---------------------------------------------------------------------------


def train_target_model(
    df_train: Any,
    df_test: Any,
    config: TrainConfig,
    feature_names: list[str],
) -> tuple[Any, dict[str, float]]:
    """训练 target 模型（multiclass）。

    返回：
        (booster, {"top1_acc": ..., "top3_acc": ..., "best_iter": ...})
    """
    raise NotImplementedError(
        "M15/T1.1 待实现：LightGBM multiclass target 模型"
    )


def train_ships_model(
    df_train: Any,
    df_test: Any,
    config: TrainConfig,
    feature_names: list[str],
) -> tuple[Any, dict[str, float]]:
    """训练 ships_frac 回归模型。

    返回：
        (booster, {"rmse": ..., "mae": ..., "best_iter": ...})
    """
    raise NotImplementedError(
        "M15/T1.2 待实现：LightGBM regression ships_frac"
    )


def train_act_model(
    df_train: Any,
    df_test: Any,
    config: TrainConfig,
    feature_names: list[str],
) -> tuple[Any, dict[str, float]]:
    """训练 act vs idle 二分类。

    返回：
        (booster, {"auc": ..., "logloss": ..., "best_iter": ...})
    """
    raise NotImplementedError(
        "M15/T1.2 待实现：LightGBM binary act 模型"
    )


# ---------------------------------------------------------------------------
# 序列化（嵌入式格式：纯 Python 树遍历）
# ---------------------------------------------------------------------------


def export_compiled_python(
    booster_target: Any,
    booster_ships: Any,
    booster_act: Any,
    feature_names: list[str],
    output_path: Path,
) -> None:
    """导出三个模型为 ``il_prior_lgbm_v{N}_compiled.py``，submission.py 直接 import。

    导出格式（参考 src/policy/value_gbc.py 同款）：

    .. code-block:: python

        IL_FEATURE_NAMES = ["my_ship_ratio", ...]
        IL_TARGET_INIT = 0.0
        IL_TARGET_N_TREES = 1200
        IL_TARGET_TREES = [(feat, thr, val, left, right), ...]
        IL_SHIPS_TREES = ...
        IL_ACT_TREES = ...

    优势：submission 不依赖 lightgbm，纯 stdlib 跑 inference，5KB-15MB。
    """
    raise NotImplementedError(
        "M15/T1.3 待实现：LightGBM Booster → 纯 Python 树遍历"
    )


def save_metadata(
    config: TrainConfig,
    metrics: TrainMetrics,
    output_path: Path,
) -> None:
    """保存 il_prior_lgbm_v{N}.json 元数据。"""
    payload = {
        "version": config.version,
        "parquet_path": str(config.parquet_path),
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "lgbm_target_params": config.lgbm_target_params,
        "lgbm_ships_params": config.lgbm_ships_params,
        "lgbm_act_params": config.lgbm_act_params,
        "test_ratio": config.test_ratio,
        "metrics": {
            "target_top1_acc": metrics.target_top1_acc,
            "target_top3_acc": metrics.target_top3_acc,
            "ships_mae": metrics.ships_mae,
            "ships_rmse": metrics.ships_rmse,
            "act_auc": metrics.act_auc,
            "act_logloss": metrics.act_logloss,
        },
        "n_train_pairs": metrics.n_train_pairs,
        "n_test_pairs": metrics.n_test_pairs,
        "feature_names": metrics.feature_names,
        "best_iter_target": metrics.best_iter_target,
        "best_iter_ships": metrics.best_iter_ships,
        "best_iter_act": metrics.best_iter_act,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def train_il_prior(config: TrainConfig) -> TrainMetrics:
    """端到端训练流程。

    步骤：
        1. load_dataset
        2. transform_target_label
        3. 抽取 feature_names（与 src/policy/il_prior.FEATURE_NAMES 必须对齐）
        4. train_target_model / train_ships_model / train_act_model
        5. 验收：metrics 是否达 §5.4 三指标
        6. 序列化（.txt + .json + _compiled.py）
        7. 返回 TrainMetrics
    """
    raise NotImplementedError(
        "M15/T1.5 待实现：端到端 train_il_prior"
    )


def cli() -> int:
    parser = argparse.ArgumentParser(description="IL Prior LightGBM Trainer")
    parser.add_argument("--parquet", type=Path, default=Path("data/replays/processed/v1.parquet"))
    parser.add_argument("--version", type=str, default="v1")
    parser.add_argument("--output-dir", type=Path, default=Path("models"))
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    config = TrainConfig(
        parquet_path=args.parquet,
        version=args.version,
        output_dir=args.output_dir,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )
    metrics = train_il_prior(config)
    print(json.dumps({
        "target_top1_acc": metrics.target_top1_acc,
        "target_top3_acc": metrics.target_top3_acc,
        "act_auc": metrics.act_auc,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
