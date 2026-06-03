"""M11 — GBC 价值函数训练。

数据源：本地 ``data/replays/`` 中的 replay JSON（来自 Kaggle Episodes API
或社区 Parquet 数据集）。

特征：``src/policy/value_gbc.py::value_state_features`` 的 20 维（必须保持一致）。

标签：episode 终态胜负（per player）。

模型：``sklearn.ensemble.GradientBoostingClassifier``，~100 trees，max_depth=4。

序列化：把训完的树拆成 5 个 list（feat/thr/val/left/right），写到
``src/policy/value_gbc_trees.py``，被 ``value_gbc.py::_load_trees`` 加载。
这样运行时不需要 sklearn 依赖（Kaggle 提交体积小）。

参考实现：``community-examples/orbit-wars-sim-value-search-agent.ipynb`` 的
``_load_value_model`` + ``_value_score``。
"""

from __future__ import annotations

import argparse
from pathlib import Path


def train_from_replays(
    replay_dir: Path,
    *,
    n_estimators: int = 100,
    max_depth: int = 4,
    learning_rate: float = 0.1,
    output_path: Path,
) -> None:
    """从 replay JSON 训练 GBC 并序列化为 ``value_gbc_trees.py``。

    实现步骤：

    1. 遍历 replay_dir 下所有 ``*.json``
    2. 每局抽取若干"中间状态"（建议每 25 步采一次）
    3. 用 ``value_state_features`` 算特征
    4. 标签 = 该局最终胜负（"my_player 是否赢"，单标量 0/1）
    5. ``sklearn.ensemble.GradientBoostingClassifier`` 训练
    6. 提取每棵树的 (feat, thr, val, left, right) 5 个 list
    7. 写到 ``src/policy/value_gbc_trees.py`` 形如::

           GBC_INIT = -0.123
           GBC_N_TREES = 100
           GBC_TREES = [
               ([feat_list], [thr_list], [val_list], [left_list], [right_list]),
               ...
           ]
    """
    raise NotImplementedError("Task agent 实现；参考 sim-value-search 的同源逻辑。")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="训练 GBC 价值函数")
    parser.add_argument("--replays", default="data/replays/",
                        help="本地 replay 目录")
    parser.add_argument("--output", default="src/policy/value_gbc_trees.py",
                        help="输出 Python 模块路径")
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--max-depth", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    raise NotImplementedError("Task agent 实现。")


if __name__ == "__main__":
    main()
