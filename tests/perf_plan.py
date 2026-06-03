"""M9 Plan Orchestrator 性能测试（轻量版）。

目标：验证 T0.2 的最小调度器在纯 Python 桩环境下，单次调用 p95 小于 5ms。
说明：该测试不依赖 kaggle_environments，避免把环境初始化噪声混入模块耗时。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from src.policy.plan import plan_moves


@dataclass
class _FakePlanet:
    id: int
    owner: int
    x: float
    y: float
    radius: float
    ships: int
    production: int


@dataclass
class _FakePolicy:
    phase: str = "pressure"
    reserve: dict[int, int] = field(default_factory=dict)
    attack_budget: dict[int, int] = field(default_factory=dict)


class _FakeWorld:
    def __init__(self, planets: list[_FakePlanet], player: int = 0):
        self.planets = planets
        self.player = player
        self.commitments: list[object] = []

    def add_commitment(self, commitment: object) -> None:
        self.commitments.append(commitment)


def _p95(samples: list[float]) -> float:
    """最近秩法估算 p95，适合中小样本的 CI 性能门禁。"""
    ordered = sorted(samples)
    idx = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[idx]


def test_plan_moves_p95_under_5ms():
    """在固定规模输入下，plan_moves 单次调用 p95 应小于 5ms。"""
    # 构造 6 个我方星球 + 12 个目标，覆盖多源筛选、预算计算和 commitment 写回路径。
    planets = []
    for i in range(6):
        planets.append(_FakePlanet(i, 0, 10.0 + i * 3, 20.0 + i * 2, 2.0, 120, 6))
    for i in range(12):
        owner = -1 if i % 2 == 0 else 1
        planets.append(
            _FakePlanet(100 + i, owner, 45.0 + i * 2, 50.0 + i, 2.0, 20 + i, 5 + (i % 3))
        )

    policy = _FakePolicy(
        phase="pressure",
        reserve={i: 20 for i in range(6)},
    )

    samples_ms: list[float] = []
    for _ in range(80):
        world = _FakeWorld(planets=planets, player=0)
        started = time.perf_counter()
        moves = plan_moves(world, policy, deadline=time.perf_counter() + 0.2)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        samples_ms.append(elapsed_ms)
        # 正确性兜底：防止“过快是因为没有执行核心逻辑”。
        assert all(len(m) == 3 and m[2] > 0 for m in moves)

    assert _p95(samples_ms) < 5.0
