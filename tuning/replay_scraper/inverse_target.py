"""
Inverse Targeting Resolver（M14 子模块）

把 expert 输出的"连续 launch angle"反推为"目标 planet id"。
对齐 community-examples/data-generation-expert-imitation-for-rl.ipynb Cell 7。
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any

DEFAULT_COLLISION_TOLERANCE: float = 2.0
MAX_SIMULATION_TICKS: int = 250
BOARD_CENTER_X: float = 50.0
BOARD_CENTER_Y: float = 50.0


def fleet_speed_simple(ships: int) -> float:
    """IL notebook 简化舰队速度：min(1.0 + ships // 20, 6.0)。"""
    return min(1.0 + ships // 20, 6.0)


def _planet_orbital_radius(planet: tuple[Any, ...]) -> float:
    """星球轨道半径（相对棋盘中心）。"""
    px, py, pr = planet[2] - BOARD_CENTER_X, planet[3] - BOARD_CENTER_Y, planet[4]
    return math.hypot(px, py)


def is_planet_orbiting(planet: tuple[Any, ...]) -> bool:
    """内轨星球会绕中心旋转；外轨视为静止。"""
    px, py, pr = planet[2] - BOARD_CENTER_X, planet[3] - BOARD_CENTER_Y, planet[4]
    return math.hypot(px, py) + pr < 50.0


def predict_planet_position_at_tick(
    planet: tuple[Any, ...],
    tick: int,
    angular_velocity: float,
) -> tuple[float, float]:
    """
    预测 planet 在 tick 的位置（与 IL notebook 一致）。

    外轨（r_orb + radius >= 50）固定；内轨按角速度旋转。
    """
    px, py, pr = planet[2] - BOARD_CENTER_X, planet[3] - BOARD_CENTER_Y, planet[4]
    r_orb = math.hypot(px, py)
    if r_orb + pr >= 50.0:
        return planet[2], planet[3]
    angle = math.atan2(py, px) + angular_velocity * tick
    return (
        BOARD_CENTER_X + r_orb * math.cos(angle),
        BOARD_CENTER_Y + r_orb * math.sin(angle),
    )


def resolve_target(
    source_id: int,
    launch_angle: float,
    ships: int,
    planets: list[tuple[Any, ...]],
    angular_velocity: float,
    tolerance: float = DEFAULT_COLLISION_TOLERANCE,
    max_ticks: int = MAX_SIMULATION_TICKS,
) -> int:
    """
    射线 + 逐 tick 碰撞模拟，返回首个命中的 planet_id，未命中为 -1。
    """
    source = next((p for p in planets if p[0] == source_id), None)
    if source is None:
        return -1

    fx, fy = source[2], source[3]
    dx, dy = math.cos(launch_angle), math.sin(launch_angle)
    speed = fleet_speed_simple(ships)

    for t in range(1, max_ticks + 1):
        fx += dx * speed
        fy += dy * speed
        for planet in planets:
            if planet[0] == source_id:
                continue
            tx, ty = predict_planet_position_at_tick(planet, t, angular_velocity)
            if math.hypot(fx - tx, fy - ty) < planet[4] + tolerance:
                return int(planet[0])
    return -1


def batch_resolve(
    actions: list[tuple[int, float, int]],
    planets: list[tuple[Any, ...]],
    angular_velocity: float,
    tolerance: float = DEFAULT_COLLISION_TOLERANCE,
) -> list[int]:
    """批量反推 target；共享 planets 快照，不修改输入列表。"""
    return [
        resolve_target(sid, ang, ships, planets, angular_velocity, tolerance=tolerance)
        for sid, ang, ships in actions
    ]


def resolution_stats(resolved: list[int]) -> dict[str, float]:
    """解析率统计。"""
    if not resolved:
        return {"total": 0, "resolved": 0, "unresolved": 0, "hit_rate": 0.0}
    total = len(resolved)
    hit = sum(1 for t in resolved if t != -1)
    return {
        "total": total,
        "resolved": hit,
        "unresolved": total - hit,
        "hit_rate": hit / total,
    }


def _collect_actions_from_replay(replay: dict[str, Any]) -> list[tuple[int, float, int, list, float]]:
    """从单局 replay 收集 (sid, ang, ships, planets, v_ang) 样本。"""
    samples: list[tuple[int, float, int, list, float]] = []
    for step_idx, step in enumerate(replay.get("steps", [])):
        if step_idx == 0:
            continue
        players = step if isinstance(step, list) else []
        for player in players:
            if not isinstance(player, dict):
                continue
            if player.get("status") != "ACTIVE":
                continue
            actions = player.get("action") or []
            if not actions:
                continue
            obs = player.get("observation") or {}
            planets = obs.get("planets") or []
            v_ang = float(obs.get("angular_velocity", 0.0))
            for move in actions:
                if len(move) < 3:
                    continue
                sid, ang, ships = int(move[0]), float(move[1]), int(move[2])
                samples.append((sid, ang, ships, planets, v_ang))
    return samples


def run_sanity_check(raw_dir: Path, sample_episodes: int, seed: int = 42) -> dict[str, Any]:
    """
    随机抽样若干 episode，统计 inverse target 解析率（用于 Step 1 验收）。
    """
    files = sorted(raw_dir.glob("*.json"))
    if not files:
        return {"error": f"no json in {raw_dir}", "hit_rate": 0.0}

    rng = random.Random(seed)
    pick = files if len(files) <= sample_episodes else rng.sample(files, sample_episodes)

    all_targets: list[int] = []
    for path in pick:
        with path.open("r", encoding="utf-8") as fp:
            replay = json.load(fp)
        for sid, ang, ships, planets, v_ang in _collect_actions_from_replay(replay):
            all_targets.append(
                resolve_target(sid, ang, ships, planets, v_ang)
            )

    stats = resolution_stats(all_targets)
    stats["episodes_sampled"] = len(pick)
    stats["actions_total"] = len(all_targets)
    return stats


def cli() -> int:
    parser = argparse.ArgumentParser(description="Inverse target resolver sanity check")
    parser.add_argument(
        "--sanity-check",
        type=int,
        default=0,
        help="随机抽样 N 个 episode 统计解析率",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/replays/raw"),
        help="replay JSON 目录",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.sanity_check <= 0:
        parser.print_help()
        return 1

    stats = run_sanity_check(args.raw_dir, args.sanity_check, seed=args.seed)
    print(json.dumps(stats, indent=2))
    hit_rate = float(stats.get("hit_rate", 0.0))
    return 0 if hit_rate >= 0.85 else 1


if __name__ == "__main__":
    raise SystemExit(cli())
