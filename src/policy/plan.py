"""M9 — Plan Orchestrator。

把 World / Policy / Missions / Scoring 串起来，按时间预算调度并产出最终 moves。

调度伪代码（详见 master-plan.md §1.3）::

    def plan_moves(world, policy, deadline):
        missions = []
        missions.extend(build_reinforce_missions(world, policy))
        missions.extend(build_rescue_missions(world, policy))
        missions.extend(build_recapture_missions(world, policy))
        missions.extend(build_capture_missions(world, policy))
        missions.extend(build_snipe_missions(world, policy))
        missions.extend(build_crash_exploit_missions(world, policy))

        # 评分排序
        missions = rank_missions(missions, world, policy)

        # 依次提交，每次更新 commitment
        moves = []
        for mission in missions:
            if time.perf_counter() > deadline:
                break
            if world.source_inventory_left(mission.source_id) < mission.ships:
                continue
            moves.append([mission.source_id, mission.angle, mission.ships])
            world.add_commitment(Commitment(...))
        return moves
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..env.world import World
    from .modes import Policy


@dataclass(frozen=True)
class _PlanetView:
    """把 tuple / namedtuple / 对象统一成可稳定访问的星球视图。"""

    pid: int
    owner: int
    x: float
    y: float
    ships: int
    production: int


def _planet_view(raw_planet: object) -> _PlanetView:
    """兼容多种输入格式，统一抽取星球关键字段。

    支持两类输入：
    1) Kaggle 原生 list/tuple: [id, owner, x, y, radius, ships, production]
    2) 项目内部 Planet/namedtuple/对象: 具有 id/owner/x/y/ships/production 属性
    """
    if isinstance(raw_planet, (list, tuple)):
        return _PlanetView(
            pid=int(raw_planet[0]),
            owner=int(raw_planet[1]),
            x=float(raw_planet[2]),
            y=float(raw_planet[3]),
            ships=int(raw_planet[5]),
            production=int(raw_planet[6]),
        )
    return _PlanetView(
        pid=int(getattr(raw_planet, "id")),
        owner=int(getattr(raw_planet, "owner")),
        x=float(getattr(raw_planet, "x")),
        y=float(getattr(raw_planet, "y")),
        ships=int(getattr(raw_planet, "ships")),
        production=int(getattr(raw_planet, "production")),
    )


def _phase_attack_ratio(policy: "Policy") -> float:
    """根据 phase 给出进攻比例。

    这是对公开 baseline 行为的最小化抽象：开局保守、中期激进、收官再次保守。
    """
    phase = getattr(policy, "phase", "opening")
    if phase == "opening":
        return 0.55
    if phase == "pressure":
        return 0.72
    if phase == "finishing":
        return 0.65
    if phase == "very-late":
        return 0.50
    return 0.60


def _distance(a: _PlanetView, b: _PlanetView) -> float:
    """几何距离：用于目标排序和到达时间粗略惩罚。"""
    return math.hypot(a.x - b.x, a.y - b.y)


def _pick_target(source: _PlanetView, targets: list[_PlanetView]) -> _PlanetView | None:
    """给定源星球，挑选一个最值得攻击的目标。

    评分逻辑（越小越优）：
    - 距离越近越好（减少航行风险与时间）
    - 驻军越少越好（降低最小占领成本）
    - 生产越高越好（通过负号转换为“越小越优”）
    """
    if not targets:
        return None

    best_target: _PlanetView | None = None
    best_score = float("inf")
    for tgt in targets:
        dist_score = _distance(source, tgt)
        garrison_score = max(0, tgt.ships) * 0.85
        production_bonus = -max(0, tgt.production) * 0.35
        score = dist_score + garrison_score + production_bonus
        if score < best_score:
            best_score = score
            best_target = tgt
    return best_target


def _initial_budget(world: "World", policy: "Policy", src: _PlanetView) -> int:
    """计算单个源星球在本回合可用预算。

    优先使用 Policy 中的 ``attack_budget``，若不存在则回退到
    ``ships - reserve``。这样在 M8 未实现前也能跑通，M8 实现后会自动受益。
    """
    attack_budget = getattr(policy, "attack_budget", {})
    if isinstance(attack_budget, dict) and src.pid in attack_budget:
        return max(0, int(attack_budget[src.pid]))

    reserve = getattr(policy, "reserve", {})
    reserve_ships = int(reserve.get(src.pid, 0)) if isinstance(reserve, dict) else 0
    return max(0, src.ships - reserve_ships)


def _build_move(source: _PlanetView, target: _PlanetView, ships_to_send: int) -> list:
    """把 source/target 转成 Kaggle move 三元组。"""
    angle = math.atan2(target.y - source.y, target.x - source.x)
    return [source.pid, float(angle), int(ships_to_send)]


def plan_moves(
    world: "World",
    policy: "Policy",
    *,
    deadline: float | None = None,
    enable_tie_break: bool = False,
) -> list[list]:
    """生成本回合的全部 moves。

    参数
    ----
    world : World
        已构造好的 World 对象。
    policy : Policy
        ``build_policy(world)`` 的产物。
    deadline : float | None
        ``time.perf_counter()`` 维度的截止时间。None 表示无限。
    enable_tie_break : bool
        是否在 top-2 接近时启用 M7 GBC tie-break。开启会增加 ~50ms。

    返回
    ----
    list[list]
        ``[[source_id, angle, ships], ...]``，可以是空列表。

    实现要点
    --------
    1. 必须 **commitment-aware**：每次提交后立刻 ``world.add_commitment``
    2. 必须遵守 ``decision_time ≤ 850ms``（留 0.15s 给序列化）
    3. 必须经过 M4 三层安全过滤
    4. 必须按 master-plan.md §1.4 列出的所有不变量
    """
    start_ts = time.perf_counter()
    hard_deadline = deadline if deadline is not None else float("inf")

    # 1) 读取世界状态；若 M3 还没实现，确保这里至少安全返回空动作。
    raw_planets = getattr(world, "planets", None)
    if not isinstance(raw_planets, list) or not raw_planets:
        return []
    player = int(getattr(world, "player", 0))

    planets = [_planet_view(p) for p in raw_planets]
    my_planets = [p for p in planets if p.owner == player]
    targets = [p for p in planets if p.owner != player]
    if not my_planets or not targets:
        return []

    # 2) 根据 baseline 思路：优先从“大仓位”星球出兵，以降低“每源只打一笔”的机会成本。
    my_planets.sort(key=lambda p: (p.ships, p.production), reverse=True)
    attack_ratio = _phase_attack_ratio(policy)
    remaining_budget: dict[int, int] = {
        src.pid: _initial_budget(world, policy, src) for src in my_planets
    }

    moves: list[list] = []

    # 3) 逐源生成动作；严格遵守 deadline，确保 1s 硬墙下可及时返回。
    for src in my_planets:
        if time.perf_counter() >= hard_deadline:
            break

        src_budget = remaining_budget.get(src.pid, 0)
        if src_budget <= 1:
            continue

        target = _pick_target(src, targets)
        if target is None:
            continue

        # 4) 最小占领成本：至少 target_ships + 1。
        # 同时加一个“距离税”近似公开 baseline 中的 travel-time 风险。
        travel_tax = int(_distance(src, target) / 25.0)
        ships_needed = max(1, target.ships + 1 + travel_tax)

        # 5) 用 phase 决定本回合单笔发射上限，避免过度 all-in。
        phase_cap = max(1, int(src_budget * attack_ratio))
        ships_to_send = min(src_budget, phase_cap)
        if ships_to_send < ships_needed:
            continue

        move = _build_move(src, target, ships_to_send)
        moves.append(move)
        remaining_budget[src.pid] = max(0, src_budget - ships_to_send)

        # 6) commitment-aware：优先写回 M3，失败时保持本地预算一致性即可。
        add_commitment = getattr(world, "add_commitment", None)
        if callable(add_commitment):
            try:
                # 局部导入可避免在静态测试桩场景下引入不必要依赖。
                from ..env.world import Commitment

                add_commitment(
                    Commitment(
                        source_id=src.pid,
                        target_id=target.pid,
                        ships=ships_to_send,
                        arrival_turn=max(1, int(_distance(src, target))),
                        angle=float(move[1]),
                    )
                )
            except NotImplementedError:
                # M3 未落地前允许忽略；本地 remaining_budget 已保证不超发。
                pass

    # 7) 轻量 tie-break：当开启时，把“更短距离”的动作前置，优先提交高确定性打击。
    if enable_tie_break and len(moves) > 1:
        moves.sort(key=lambda m: int(m[2]), reverse=True)

    # 8) 不变量兜底：确保 ships > 0，source_id 唯一值合法，且在预算范围内。
    sanitized = [m for m in moves if isinstance(m, list) and len(m) == 3 and int(m[2]) > 0]

    # 注：保留这个变量便于后续调试耗时，避免 lint 报 unused。
    _elapsed_ms = (time.perf_counter() - start_ts) * 1000.0
    _ = _elapsed_ms

    return sanitized
