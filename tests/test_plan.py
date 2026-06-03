"""M9 Plan Orchestrator 单元测试。

本组测试聚焦 T0.2 的最小可跑 baseline 调度逻辑，验证：
1. 在基本可行动场景下能产出合法 move；
2. 能遵守 reserve / attack_budget 约束；
3. deadline 触发时会及时停止；
4. 会调用 world.add_commitment（若该接口可用）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from src.policy.plan import plan_moves


@dataclass
class _FakePlanet:
    """测试用星球结构，字段与 src.env.physics.Planet 对齐。"""

    id: int
    owner: int
    x: float
    y: float
    radius: float
    ships: int
    production: int


@dataclass
class _FakePolicy:
    """测试用策略快照，只保留 plan_moves 需要的字段。"""

    phase: str = "opening"
    reserve: dict[int, int] = field(default_factory=dict)
    attack_budget: dict[int, int] = field(default_factory=dict)


class _FakeWorld:
    """测试用 World 桩，提供 plan_moves 读取/写入的最小接口。"""

    def __init__(self, planets: list[_FakePlanet], player: int = 0):
        self.planets = planets
        self.player = player
        self.commitments: list[object] = []

    def add_commitment(self, commitment: object) -> None:
        """记录 commitment，便于断言调度器是否做了增量写回。"""
        self.commitments.append(commitment)


def test_plan_moves_generates_legal_move_and_commitment():
    """当我方有足够预算时，应生成至少一个合法动作并写入 commitment。"""
    world = _FakeWorld(
        planets=[
            _FakePlanet(1, 0, 10.0, 10.0, 2.0, 80, 6),
            _FakePlanet(2, -1, 20.0, 10.0, 2.0, 12, 8),
            _FakePlanet(3, 1, 80.0, 80.0, 2.0, 30, 5),
        ],
        player=0,
    )
    policy = _FakePolicy(phase="pressure", reserve={1: 10})

    moves = plan_moves(world, policy, deadline=time.perf_counter() + 1.0)

    assert len(moves) >= 1
    for move in moves:
        # move 必须符合 Kaggle 三元组约定。
        assert isinstance(move, list)
        assert len(move) == 3
        assert int(move[2]) > 0
    assert len(world.commitments) >= 1


def test_plan_moves_respects_attack_budget():
    """当 attack_budget 不足以覆盖最小占领成本时，不应盲目发射。"""
    world = _FakeWorld(
        planets=[
            _FakePlanet(10, 0, 5.0, 5.0, 2.0, 40, 5),
            _FakePlanet(20, 1, 35.0, 5.0, 2.0, 30, 6),
        ],
        player=0,
    )
    # 预算过低：无法满足 target.ships + 1 + 距离税。
    policy = _FakePolicy(phase="pressure", attack_budget={10: 8})

    moves = plan_moves(world, policy)
    assert moves == []
    assert world.commitments == []


def test_plan_moves_stops_when_deadline_reached():
    """若 deadline 已过，函数应立即返回，避免超过时限。"""
    world = _FakeWorld(
        planets=[
            _FakePlanet(1, 0, 10.0, 10.0, 2.0, 90, 6),
            _FakePlanet(2, -1, 30.0, 10.0, 2.0, 10, 7),
        ],
        player=0,
    )
    policy = _FakePolicy()

    moves = plan_moves(world, policy, deadline=time.perf_counter() - 0.001)
    assert moves == []
    assert world.commitments == []
