"""M1 物理常量与公式的单元测试。

这个文件应当 v0 阶段就能跑通（M1 是唯一已实现的模块）。
"""

from __future__ import annotations

import math

import pytest

from src.env.physics import (
    BOARD,
    SUN_RADIUS,
    MAX_SPEED,
    MIN_SPEED,
    fleet_speed,
    is_orbiting,
    planet_radius_from_production,
    dist,
)


# ---------------------------------------------------------------------------
# 常量基本不变量
# ---------------------------------------------------------------------------


def test_board_constants():
    """棋盘 / 太阳 / 速度常量与竞赛规则一致。"""
    assert BOARD == 100.0
    assert SUN_RADIUS == 10.0
    assert MAX_SPEED == 6.0
    assert MIN_SPEED == 1.0


# ---------------------------------------------------------------------------
# fleet_speed 公式（关键路径，每回合调用上千次）
# ---------------------------------------------------------------------------


def test_fleet_speed_one_ship_is_min():
    """1 艘船速度 = 1.0/turn（竞赛规则原文）。"""
    assert fleet_speed(1) == pytest.approx(1.0)


def test_fleet_speed_1000_ships_is_max():
    """1000 艘船达到 max 6.0/turn（公式的右边界）。"""
    assert fleet_speed(1000) == pytest.approx(MAX_SPEED, abs=1e-9)


def test_fleet_speed_more_than_1000_capped():
    """超过 1000 不再加速（取上限）。"""
    assert fleet_speed(10_000) == pytest.approx(MAX_SPEED, abs=1e-9)


def test_fleet_speed_500_ships_around_5():
    """500 艘船约 5.0/turn（竞赛说明"~500 ships moves at about 5"）。

    精确公式给出 5.27，"about 5" 应理解为 around 5 而非严格 ≤ 5。
    """
    v = fleet_speed(500)
    assert 5.0 < v < 5.4


def test_fleet_speed_monotonic():
    """速度对 ships 单调递增（直到 1000 触顶）。"""
    prev = fleet_speed(1)
    for n in [2, 5, 10, 50, 100, 200, 500, 999]:
        curr = fleet_speed(n)
        assert curr >= prev
        prev = curr


# ---------------------------------------------------------------------------
# is_orbiting / 反推 radius
# ---------------------------------------------------------------------------


def test_is_orbiting_threshold():
    """边界：r_orbit + r_planet < 50 为 orbiting。"""
    assert is_orbiting(orbital_radius=10.0, planet_radius=2.0) is True
    assert is_orbiting(orbital_radius=49.0, planet_radius=1.0) is False
    assert is_orbiting(orbital_radius=48.0, planet_radius=1.0) is True


def test_planet_radius_from_production():
    """``radius = 1 + ln(production)``。"""
    assert planet_radius_from_production(1) == pytest.approx(1.0)
    assert planet_radius_from_production(2) == pytest.approx(1.0 + math.log(2))
    assert planet_radius_from_production(5) == pytest.approx(1.0 + math.log(5))


def test_dist_basic():
    """欧氏距离的基本 case。"""
    assert dist(0, 0, 3, 4) == pytest.approx(5.0)
    assert dist(50, 50, 50, 50) == pytest.approx(0.0)
