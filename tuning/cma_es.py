"""M10 — CMA-ES 调参器。

调谁：``src/policy/scoring.py`` 中 ``ScoringParams`` 暴露的 ~25 个常量，加上
lb-1200 baseline 中的 ``F14_4A_2P_FOCUS_*`` 一族（如果合并进 src/）。

调多久：~1500 个评测（200 generations × 30 trials），8 核 CPU 单局 ~3s，
总时间约 1.5 小时。CPU-bound，**不需要 GPU**。

输出：``tuning/best_params_v{N}.json``，由 Task agent 合并回代码常量。

参考实现：``import cma; es = cma.CMAEvolutionStrategy(theta_flat, sigma0=0.1)``
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class ParamSpec:
    """单个待调参数的定义。"""

    name: str          # 参数名（同 ScoringParams 中的字段名）
    default: float
    lower: float       # CMA-ES 软边界
    upper: float
    log_scale: bool = False  # 是否对数尺度采样


def load_param_specs(path: Path) -> list[ParamSpec]:
    """从 JSON 加载参数定义。

    JSON 格式::

        [
          {"name": "gamma", "default": 0.99, "lower": 0.95, "upper": 0.999},
          {"name": "capture_hostile_mult", "default": 2.0, "lower": 1.0, "upper": 4.0},
          ...
        ]
    """
    raise NotImplementedError("Task agent 实现；参考 master-plan §2.1 M10。")


def optimize(
    specs: list[ParamSpec],
    evaluator: Callable[[dict[str, float]], float],
    *,
    budget: int = 1500,
    sigma0: float = 0.3,
    output_path: Path,
) -> dict[str, float]:
    """跑 CMA-ES。

    参数
    ----
    specs : list[ParamSpec]
        参数清单。
    evaluator : Callable[[dict[str, float]], float]
        给一组参数返回评估分数（越大越好）。例如：胜率 × 100。
        典型实现：把参数写入 ``scoring.ScoringParams``，跑 tournament 256 局，
        返回总胜率。
    budget : int
        总评估次数预算。
    sigma0 : float
        CMA-ES 初始步长。0.3 适合归一化到 [0, 1] 的参数。
    output_path : Path
        中间最优参数落盘路径（避免崩溃丢失结果）。

    返回
    ----
    dict[str, float]
        最优参数组（与 ``ScoringParams`` 字段名同名）。
    """
    raise NotImplementedError("Task agent 实现；pip install cma 后直接调用。")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CMA-ES 调参")
    parser.add_argument("--params", required=True, help="参数定义 JSON")
    parser.add_argument("--budget", type=int, default=1500)
    parser.add_argument("--output", required=True, help="最优参数输出 JSON")
    parser.add_argument("--eval-seeds", type=int, default=32,
                        help="每次评估的 seed 数（默认 32，~64 局/对手）")
    parser.add_argument("--eval-opponents", default="public_heuristic_1110",
                        help="评估对手（建议只用 L3，时间最省）")
    return parser.parse_args()


def main() -> None:
    raise NotImplementedError("Task agent 实现。")


if __name__ == "__main__":
    main()
