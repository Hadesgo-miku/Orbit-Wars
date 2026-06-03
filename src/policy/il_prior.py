"""M13 — IL Prior 接入点（v2 主路径核心）。

把离线训出的 LightGBM "IL prior" 模型在线接入 plan_moves。

工作流（master-plan §1.1 L4.5）：

1. agent 启动时（``_load_prior``）尝试从 ``models/il_prior_lgbm_v{N}.txt`` 加载模型
2. plan_moves 在 M6 评分之后、M9 调度之前，对每个 mission 调用 ``predict_prior``
3. 每个 mission 的最终 score 改为：
   ``score *= exp(IL_ALPHA * (logit(prior) - logit(0.5)))``
4. 模型未加载或推理异常 → ``IL_ALPHA_EFFECTIVE = 0`` → 完全等同于 v1 行为

不变量（master-plan §1.4）：

- IL prior 推理（含特征抽取）≤ 5ms / mission
- 模型加载失败必须**静默回退**（log 一次 warning，不能抛异常）
- 任何 NaN / Inf 输出必须被 clip 到 (0.01, 0.99) 区间

约束：
    - 不在线训练 / 微调
    - 不依赖 GPU
    - LightGBM 仅在加载时引入；预测可降级为纯 Python 树遍历（与 value_gbc 同款）
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..env.world import World
    from .scoring import Mission


# ---------------------------------------------------------------------------
# 模型容器（M15 训练完毕后填充）
# ---------------------------------------------------------------------------

#: IL prior 模型加载状态。在线推理任何路径必须先检查 IL_PRIOR_READY。
IL_PRIOR_READY: bool = False

#: 三个子模型句柄（不在线则全为 None）：
#:   target_model: p(target_id | state, source_id)  (multiclass)
#:   ships_model : p(ships_frac | state, source_id, target_id) (regression or quantile)
#:   act_model   : p(act vs idle | state, source_id) (binary)
TARGET_MODEL: Any = None
SHIPS_MODEL: Any = None
ACT_MODEL: Any = None

#: 特征列表（必须与 M15 训练时完全一致）；M15 训出来时序列化到 .json
FEATURE_NAMES: list[str] = []

#: IL_ALPHA 默认值（M6 score 乘子的强度）；通过 M10 CMA-ES 在 L1-L3 对手集上调
#: 0 = 完全等同于 v1 启发式（fallback / 模型异常时也是 0）
IL_ALPHA_DEFAULT: float = 1.0

#: 实际生效的 alpha（被 plan_moves 在 agent 启动时初始化为 IL_ALPHA_DEFAULT 或调参后的值）
IL_ALPHA_EFFECTIVE: float = 0.0

#: 模型文件的搜索路径（按顺序，找到即停）
_MODEL_SEARCH_PATHS: tuple[str, ...] = (
    "models/il_prior_lgbm_latest.txt",
    "models/il_prior_lgbm_v1.txt",
    "/kaggle_simulations/agent/il_prior_lgbm.txt",  # 提交时 submission.py 同目录
)


# ---------------------------------------------------------------------------
# 加载与初始化
# ---------------------------------------------------------------------------


def _load_prior(model_search_paths: tuple[str, ...] = _MODEL_SEARCH_PATHS) -> bool:
    """尝试加载 IL prior 模型。

    返回 True 表示加载成功，False 表示降级到纯启发式 fallback。

    实现指引：

    1. 按 ``model_search_paths`` 顺序找模型文件
    2. 尝试 ``import lightgbm`` 并 ``lgb.Booster(model_file=...)``
    3. 若 LightGBM 不可用，则尝试加载 ``models/il_prior_lgbm_v{N}_compiled.py``
       —— 这是 M15 训练后导出的"纯 Python 树遍历"格式（与 value_gbc 同款）
    4. 任一异常 → ``return False`` 且 IL_PRIOR_READY 保持 False
    5. 成功 → 设置 IL_PRIOR_READY = True，绑定 IL_ALPHA_EFFECTIVE

    在 agent 启动时调用一次（``src/agent.py`` 顶部）；不要在 plan_moves 内部反复加载。
    """
    raise NotImplementedError(
        "M13/T2.1 待实现：加载 LightGBM 或纯 Python 编译版"
    )


# ---------------------------------------------------------------------------
# 特征抽取（与 M15 训练时必须 1:1 对齐）
# ---------------------------------------------------------------------------


def state_features_for_mission(
    world: "World",
    mission: "Mission",
) -> list[float]:
    """为单个 mission 抽取 ~47 维特征向量（与训练 schema 完全一致）。

    布局（与 tuning/replay_scraper/extract_features.py 的 build_state_features 对齐）：

    - 全局 20 维：复用 ``value_gbc.value_state_features``
    - per-source 10 维：source.ships / prod / centrality / is_orbiting / ...
    - per-target 12 维：target.owner / ships / prod / eta / is_doomed / swept / reactive_snipe_risk / ...
    - contextual 5 维：tick_normalized / players_count / phase_encoded / ...

    .. warning::
        本函数必须与 ``extract_features.build_state_features`` **逐特征对齐**，
        否则在线推理 = 训练时见的不是同一份分布，效果完全失效。
    """
    raise NotImplementedError(
        "M13/T2.1 待实现：与 extract_features.build_state_features 严格对齐"
    )


# ---------------------------------------------------------------------------
# 推理入口
# ---------------------------------------------------------------------------


@dataclass
class IlPriorOutput:
    """单 mission IL prior 推理结果。"""
    #: P(target=mission.target_id | state, mission.source_id)  ∈ (0, 1)
    target_prob: float
    #: 期望发射 ships 比例（mission.ships / source.ships）
    ships_frac_pred: float
    #: P(act | state, source)  ∈ (0, 1)
    act_prob: float
    #: 推理实际耗时（ms），仅用于性能监控
    elapsed_ms: float = 0.0


def predict_one(
    world: "World",
    mission: "Mission",
) -> IlPriorOutput:
    """单 mission 推理。

    流程：

    1. 检查 IL_PRIOR_READY；False 时返回 (0.5, 0.5, 0.5) 的中性值
    2. ``feats = state_features_for_mission(world, mission)``
    3. 调三个子模型，输出三个概率 / 数值
    4. clip 到 (0.01, 0.99) 区间避免 logit 爆炸

    时间预算：单次调用 ≤ 5ms。
    """
    raise NotImplementedError(
        "M13/T2.1 待实现：单 mission 推理 + 预算监控"
    )


def predict_batch(
    world: "World",
    missions: list["Mission"],
) -> dict[int, IlPriorOutput]:
    """批量推理（推荐路径，相比逐次循环减少 Python overhead）。

    返回：
        ``{mission_id: IlPriorOutput}``，其中 mission_id 用 ``id(mission)`` 标识

    实现指引：

    - 收集所有 missions 的特征矩阵（一次 numpy 化）
    - 调 LightGBM 的 predict 一次性出多输出
    - LightGBM 不可用时退化为 predict_one 循环
    """
    raise NotImplementedError(
        "M13/T2.1 待实现：批量推理"
    )


# ---------------------------------------------------------------------------
# 与 M6 score 的融合
# ---------------------------------------------------------------------------


def apply_prior_to_missions(
    missions: list["Mission"],
    world: "World",
    *,
    alpha: float | None = None,
) -> list["Mission"]:
    """把 IL prior 乘到每个 mission.score 上。

    数学：

    .. math::
        score' = score \\cdot \\exp\\big(\\alpha (\\text{logit}(p_{prior}) - \\text{logit}(0.5))\\big)

    参数：

    - ``alpha``: None 时使用 ``IL_ALPHA_EFFECTIVE``；显式传入用于评测扫描
    - 模型未就绪或 alpha=0 → 直接 return missions（noop）

    必须在 ``rank_missions`` 之后、``plan_moves`` 调度之前调用。
    """
    if not IL_PRIOR_READY:
        return missions
    a = IL_ALPHA_EFFECTIVE if alpha is None else alpha
    if a == 0.0:
        return missions
    raise NotImplementedError(
        "M13/T2.2 待实现：apply_prior_to_missions 与 plan.py 接入"
    )


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _clip_prob(p: float, lo: float = 0.01, hi: float = 0.99) -> float:
    """概率 clip 到 (lo, hi)，避免 logit 爆炸。"""
    if math.isnan(p) or math.isinf(p):
        return 0.5
    return max(lo, min(hi, p))


def _logit(p: float) -> float:
    """logit = log(p / (1 - p))。"""
    p = _clip_prob(p)
    return math.log(p / (1.0 - p))


def get_status() -> dict[str, Any]:
    """返回当前 IL prior 状态（供 logging / smoke test 用）。"""
    return {
        "ready": IL_PRIOR_READY,
        "alpha_effective": IL_ALPHA_EFFECTIVE,
        "n_features": len(FEATURE_NAMES),
        "model_search_paths": list(_MODEL_SEARCH_PATHS),
    }
