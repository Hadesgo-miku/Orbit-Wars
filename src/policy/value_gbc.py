"""M7 — GBC 价值函数 tie-break。

参考 ``community-examples/orbit-wars-sim-value-search-agent.ipynb`` 的实现：

- 离线用 sklearn ``GradientBoostingClassifier`` 在 replay 上训练（label = 终态胜负）
- 序列化为 5 个 list：``feat_list / thr_list / val_list / left_list / right_list``
- 在线时 30 行 Python 走树，无需 sklearn 依赖

仅在 M6 输出的 top-2 mission 分数差距小于阈值时启用，避免每回合都消耗时间。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..env.world import World
    from .scoring import Mission


# ---------------------------------------------------------------------------
# 模型容器（M11 训练完毕后填充）
# ---------------------------------------------------------------------------

#: 树结构占位；M11 的 train_gbc 会把训练结果写到 ``src/policy/value_gbc_trees.py``
#: 该文件由 ``train_gbc.py`` 生成，内容形如：
#:
#:     GBC_INIT = 0.0
#:     GBC_N_TREES = 100
#:     GBC_TREES = [(feat, thr, val, left, right), ...]
#:
#: 然后被本模块的 ``_load_trees`` 加载。
GBC_INIT: float = 0.0
GBC_N_TREES: int = 0
GBC_TREES: list[tuple] = []


def _load_trees() -> None:
    """尝试加载训出的树（v0 时不存在则保持空，调用方会 fallback）。"""
    global GBC_INIT, GBC_N_TREES, GBC_TREES
    try:
        from . import value_gbc_trees  # type: ignore
    except ImportError:
        return
    GBC_INIT = getattr(value_gbc_trees, "GBC_INIT", 0.0)
    GBC_N_TREES = getattr(value_gbc_trees, "GBC_N_TREES", 0)
    GBC_TREES = getattr(value_gbc_trees, "GBC_TREES", [])


_load_trees()


# ---------------------------------------------------------------------------
# 特征 + 打分
# ---------------------------------------------------------------------------


def value_state_features(
    planet_states: list[dict],
    fleet_states: list[dict],
    my_player: int,
    n_players: int,
    step: int,
) -> list[float]:
    """从状态生成 20 维特征向量。

    特征参考 sim-value-search 的 ``_value_state_features``：

    1. step / 500
    2. n_players / 4
    3. my_planets / total_planets
    4. best_enemy_planets / total_planets
    5. my_ships / total_ships
    6. best_enemy_ships / total_ships
    7. my_prod / total_prod
    8. best_enemy_prod / total_prod
    9. my_centrality / 60
    10. best_enemy_centrality / 60
    11. reserved (0)
    12. (my_ships − be_ships) / total_ships
    13. (my_planets − be_planets) / total_planets
    14. (my_prod − be_prod) / total_prod
    15. is_2p
    16. is_4p
    17. my_inflight / total_ships
    18. be_inflight / total_ships
    19. (my_ships + my_inflight − be_ships − be_inflight) / total_ships
    20. my_inflight > be_inflight
    """
    raise NotImplementedError(
        "M7.value_state_features 由 Task agent 实现；参考 sim-value-search。"
    )


def value_score(features: list[float]) -> float:
    """走 GBC 树，返回 logit（越大越对我方有利）。"""
    if GBC_N_TREES == 0:
        # 未加载模型，调用方应跳过 tie-break
        return 0.0
    z = GBC_INIT
    for feat_list, thr_list, val_list, left_list, right_list in GBC_TREES:
        node = 0
        while feat_list[node] >= 0:
            if features[feat_list[node]] <= thr_list[node]:
                node = left_list[node]
            else:
                node = right_list[node]
        z += val_list[node]
    return z


def tie_break(
    candidates: list["Mission"],
    world: "World",
    *,
    lookahead: int = 20,
) -> "Mission":
    """在 top-K 候选中通过短前向模拟 + GBC 打分挑出最优。

    实现指引：

    1. 对每个 candidate，调用 ``world.simulate_outcome(candidate, lookahead)``
    2. 终态生成 20 维特征
    3. ``value_score(features)`` 取最大者
    4. GBC 未加载（``GBC_N_TREES == 0``）时直接返回 ``candidates[0]``
    """
    if GBC_N_TREES == 0 or not candidates:
        return candidates[0] if candidates else None  # type: ignore[return-value]
    raise NotImplementedError("M7.tie_break 由 Task agent 实现（模型已加载分支）。")
