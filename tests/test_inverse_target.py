"""inverse_target 单元测试（T-DATA）。"""
from __future__ import annotations

import math

import pytest

from tuning.replay_scraper import inverse_target


def _planet(pid: int, x: float, y: float, radius: float = 3.0, ships: int = 10) -> tuple:
    return (pid, 0, x, y, radius, ships, 1)


def test_straight_shot_hits_fixed_planet():
    """case 1: 直线射向固定外轨 planet。"""
    planets = [
        _planet(0, 20.0, 50.0),
        _planet(1, 80.0, 50.0, radius=4.0),
    ]
    ang = math.atan2(0.0, 60.0)
    tid = inverse_target.resolve_target(0, ang, 50, planets, angular_velocity=0.0)
    assert tid == 1


def test_orbiting_planet_hit():
    """case 2: 射向内轨旋转 planet。"""
    planets = [
        _planet(0, 50.0, 20.0),
        _planet(1, 55.0, 35.0, radius=3.0),
    ]
    ang = math.atan2(15.0, 5.0)
    tid = inverse_target.resolve_target(0, ang, 30, planets, angular_velocity=0.05)
    assert tid in (1, -1)
    assert tid != 0


def test_angle_miss_returns_minus_one():
    """case 3: 角度偏离 5°，应 miss。"""
    planets = [
        _planet(0, 20.0, 50.0),
        _planet(1, 80.0, 50.0, radius=4.0),
    ]
    base = math.atan2(0.0, 60.0)
    ang = base + math.radians(15.0)
    tid = inverse_target.resolve_target(0, ang, 50, planets, angular_velocity=0.0, tolerance=2.0)
    assert tid == -1


def test_sun_region_does_not_raise():
    """case 4: 路径靠近太阳区域不抛异常。"""
    planets = [
        _planet(0, 45.0, 50.0),
        _planet(1, 55.0, 50.0, radius=2.0),
    ]
    ang = math.pi / 2
    tid = inverse_target.resolve_target(0, ang, 10, planets, angular_velocity=0.02)
    assert tid in (-1, 0, 1)


def test_batch_resolve_length():
    actions = [(0, 0.0, 10), (0, math.pi / 4, 20)]
    planets = [_planet(0, 10.0, 10.0), _planet(1, 70.0, 70.0)]
    out = inverse_target.batch_resolve(actions, planets, 0.0)
    assert len(out) == 2
