"""
Replay JSON → 训练 parquet 的特征抽取（M14 子模块）

输出 schema 与 T-DATA / master-plan v2.1 对齐：47 维特征 + 元字段。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

from . import inverse_target

# ---------------------------------------------------------------------------
# 固定 47 维特征列名（与 il_prior / data_quality 对齐）
# ---------------------------------------------------------------------------

FEATURE_NAMES: list[str] = [
    # 全局 20
    "g_step_norm",
    "g_n_players_norm",
    "g_my_planet_ratio",
    "g_be_planet_ratio",
    "g_my_ship_ratio",
    "g_be_ship_ratio",
    "g_my_prod_ratio",
    "g_be_prod_ratio",
    "g_my_centrality_norm",
    "g_be_centrality_norm",
    "g_ship_diff",
    "g_planet_diff",
    "g_prod_diff",
    "g_is_2p",
    "g_is_4p",
    "g_my_inflight_ratio",
    "g_be_inflight_ratio",
    "g_total_diff_ratio",
    "g_inflight_lead",
    "g_phase_encoded",
    # per-source 10
    "s_ships_log",
    "s_prod_norm",
    "s_dist_from_sun_norm",
    "s_garrison_ratio",
    "s_is_orbiting",
    "s_in_combat_zone",
    "s_eta_to_nearest_enemy_planet_norm",
    "s_owner_stability",
    "s_undeployable_lock",
    "s_centrality_norm",
    # per-target 12
    "t_owner_code",
    "t_ships_log",
    "t_prod_norm",
    "t_dist_from_source_norm",
    "t_eta_with_fleet_speed_norm",
    "t_is_doomed_to_sun",
    "t_swept_by_other",
    "t_reactive_snipe_risk",
    "t_is_orbiting",
    "t_centrality_norm",
    "t_inflight_friendly_pressure_log",
    "t_inflight_enemy_pressure_log",
    # contextual 5
    "c_phase_pressure",
    "c_my_action_count_this_turn",
    "c_action_repeat_penalty",
    "c_inflight_lead_to_this_target",
    "c_first_action_in_episode",
]

META_COLUMNS: list[str] = [
    "episode_id",
    "tick",
    "player_id",
    "players_count",
    "winner_id",
    "source_id",
    "target_id",
    "ships",
    "ships_frac",
    "label_act",
]

ALL_COLUMNS: list[str] = META_COLUMNS + FEATURE_NAMES

# 太阳碰撞检测常量（与 src/env/physics 一致，避免 tuning→src 依赖）
_SUN_RADIUS = 10.0
_SUN_SAFETY = 2.0
_CENTER = (50.0, 50.0)
_FLUSH_EVERY = 200


@dataclass
class ExtractConfig:
    raw_dir: Path = Path("data/replays/raw")
    manifest_path: Path = Path("data/replays/manifest.csv")
    output_path: Path = Path("data/replays/processed/v1.parquet")
    version: str = "v1"
    idle_keep_rate: float = 0.05
    min_ships_to_label: int = 1


@dataclass
class ExtractStats:
    episodes_processed: int = 0
    episodes_failed: int = 0
    pairs_emitted: int = 0
    pairs_unresolved: int = 0
    idle_turns_kept: int = 0
    idle_turns_dropped: int = 0
    per_player_count: int = 0
    failed_episode_ids: list[int] = field(default_factory=list)


def _safe_float(value: float) -> float:
    """NaN/Inf 裁剪到 ±10，否则原样返回。"""
    if value is None or math.isnan(value) or math.isinf(value):
        return 0.0
    return max(-10.0, min(10.0, float(value)))


def _dist(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _planet_by_id(planets: list[Any], pid: int) -> Any | None:
    return next((p for p in planets if int(p[0]) == pid), None)


def _segment_hits_sun(x1: float, y1: float, x2: float, y2: float) -> bool:
    """线段是否穿过太阳安全区（简化版 segment_hits_sun）。"""
    cx, cy = _CENTER
    dx, dy = x2 - x1, y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-12:
        dist = math.hypot(cx - x1, cy - y1)
    else:
        t = max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / seg_len_sq))
        px, py = x1 + t * dx, y1 + t * dy
        dist = math.hypot(cx - px, cy - py)
    return dist < (_SUN_RADIUS + _SUN_SAFETY)


def _winner_from_replay(replay: dict[str, Any]) -> int:
    """从 rewards 或最后一步 reward 推断 winner player_id。"""
    rewards = replay.get("rewards")
    if isinstance(rewards, list) and rewards:
        try:
            return int(max(range(len(rewards)), key=lambda i: rewards[i]))
        except (ValueError, TypeError):
            pass
    steps = replay.get("steps") or []
    if not steps:
        return 0
    last = steps[-1]
    if isinstance(last, list):
        for p in last:
            if isinstance(p, dict) and p.get("reward", -1) == 1:
                return int(p.get("observation", {}).get("player", 0))
    return 0


def _best_enemy_id(
    planets: list[Any],
    fleets: list[Any],
    my_player: int,
    n_players: int,
) -> int:
    """选 ship+inflight 总量最大的敌方 player_id。"""
    totals: dict[int, float] = {}
    for p in planets:
        owner = int(p[1])
        if owner < 0 or owner == my_player:
            continue
        totals[owner] = totals.get(owner, 0.0) + float(p[5])
    for f in fleets:
        owner = int(f[1])
        if owner < 0 or owner == my_player:
            continue
        totals[owner] = totals.get(owner, 0.0) + float(f[5])
    if not totals:
        return (my_player + 1) % max(n_players, 2)
    return max(totals, key=totals.get)


def _phase_encoded(tick: int) -> float:
    if tick < 60:
        return 0.0
    if tick < 200:
        return 0.33
    if tick < 400:
        return 0.66
    return 1.0


def _owner_code(owner: int, my_player: int, best_enemy: int) -> float:
    if owner == my_player:
        return -1.0
    if owner < 0:
        return 1.0
    if owner == best_enemy:
        return 2.0
    return 0.0


def _fleet_target_id(fleet: Any) -> int | None:
    """fleet: [id, owner, x, y, angle, ships, target_planet_id?]"""
    if len(fleet) >= 7:
        return int(fleet[6])
    return None


def _inflight_to_target(fleets: list[Any], owner: int, target_id: int) -> int:
    count = 0
    for f in fleets:
        if int(f[1]) != owner:
            continue
        tid = _fleet_target_id(f)
        if tid is not None and tid == target_id:
            count += int(f[5])
    return count


def _nearby_enemy_ships(planets: list[Any], fleets: list[Any], source: Any, my_player: int) -> float:
    sx, sy = float(source[2]), float(source[3])
    total = 0.0
    for p in planets:
        if int(p[1]) == my_player or int(p[1]) < 0:
            continue
        if _dist(sx, sy, float(p[2]), float(p[3])) < 25.0:
            total += float(p[5])
    for f in fleets:
        if int(f[1]) == my_player or int(f[1]) < 0:
            continue
        if _dist(sx, sy, float(f[2]), float(f[3])) < 25.0:
            total += float(f[5])
    return total


def _eta_to_nearest_enemy_planet(planets: list[Any], source: Any, my_player: int, ships: int) -> float:
    sx, sy = float(source[2]), float(source[3])
    speed = max(inverse_target.fleet_speed_simple(ships), 1e-6)
    best = float("inf")
    for p in planets:
        owner = int(p[1])
        if owner == my_player or owner < 0:
            continue
        d = _dist(sx, sy, float(p[2]), float(p[3]))
        best = min(best, d / speed)
    return best if math.isfinite(best) else 250.0


def _is_doomed_to_sun(
    source: Any,
    target: Any,
    launch_angle: float,
    ships: int,
    planets: list[Any],
    angular_velocity: float,
) -> float:
    """沿发射方向模拟至目标 ETA，路径是否穿太阳。"""
    speed = inverse_target.fleet_speed_simple(ships)
    dist_st = _dist(float(source[2]), float(source[3]), float(target[2]), float(target[3]))
    eta = max(1, int(math.ceil(dist_st / speed)))
    fx, fy = float(source[2]), float(source[3])
    dx, dy = math.cos(launch_angle), math.sin(launch_angle)
    prev_x, prev_y = fx, fy
    for t in range(1, min(eta + 1, 251)):
        fx += dx * speed
        fy += dy * speed
        if _segment_hits_sun(prev_x, prev_y, fx, fy):
            return 1.0
        prev_x, prev_y = fx, fy
    tx, ty = inverse_target.predict_planet_position_at_tick(target, eta, angular_velocity)
    if _segment_hits_sun(prev_x, prev_y, tx, ty):
        return 1.0
    return 0.0


def _swept_by_other_planet(
    source_id: int,
    target_id: int,
    launch_angle: float,
    ships: int,
    planets: list[Any],
    angular_velocity: float,
) -> float:
    hit = inverse_target.resolve_target(
        source_id, launch_angle, ships, planets, angular_velocity
    )
    if hit == -1:
        return 0.0
    return 1.0 if hit != target_id else 0.0


def _reactive_snipe_risk(
    target: Any,
    planets: list[Any],
    fleets: list[Any],
    my_player: int,
    best_enemy: int,
    eta: float,
) -> float:
    tx, ty = float(target[2]), float(target[3])
    for p in planets:
        if int(p[1]) != best_enemy:
            continue
        d = _dist(float(p[2]), float(p[3]), tx, ty)
        if d / inverse_target.fleet_speed_simple(50) < eta + 5:
            return 1.0
    for f in fleets:
        if int(f[1]) != best_enemy:
            continue
        d = _dist(float(f[2]), float(f[3]), tx, ty)
        if d / inverse_target.fleet_speed_simple(max(1, int(f[5]))) < eta + 5:
            return 1.0
    return 0.0


def load_episode_meta(manifest_path: Path) -> dict[int, dict[str, Any]]:
    """读 manifest.csv → {episode_id: meta}。"""
    meta: dict[int, dict[str, Any]] = {}
    if not manifest_path.exists():
        return meta
    with manifest_path.open("r", encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            eid = int(row["episode_id"])
            meta[eid] = dict(row)
    return meta


def parse_replay_steps(replay_json: dict[str, Any]) -> list[dict[str, Any]]:
    """
    解析 steps → 每玩家每 tick 一条记录（跳过 step 0，仅 ACTIVE）。
    """
    records: list[dict[str, Any]] = []
    for step_idx, step in enumerate(replay_json.get("steps", [])):
        if step_idx == 0:
            continue
        if not isinstance(step, list):
            continue
        for player in step:
            if not isinstance(player, dict):
                continue
            if player.get("status") != "ACTIVE":
                continue
            obs = player.get("observation") or {}
            tick = int(obs.get("step", step_idx))
            records.append(
                {
                    "tick": tick,
                    "player_id": int(obs.get("player", 0)),
                    "observation": obs,
                    "action": player.get("action") or [],
                }
            )
    return records


def build_state_features(
    observation: dict[str, Any],
    source_id: int,
    target_id: int,
    players_count: int,
    *,
    tick: int | None = None,
    launch_angle: float | None = None,
    ships: int = 0,
    my_action_count_this_turn: int = 0,
    action_repeat_penalty: float = 0.0,
    first_action_in_episode: float = 0.0,
) -> dict[str, float]:
    """构造 47 维特征字典（列名严格固定）。"""
    planets: list[Any] = observation.get("planets") or []
    fleets: list[Any] = observation.get("fleets") or []
    my_player = int(observation.get("player", 0))
    step = int(tick if tick is not None else observation.get("step", 0))
    n_players = max(players_count, 2)
    best_enemy = _best_enemy_id(planets, fleets, my_player, n_players)

    n_planets = max(len(planets), 1)
    total_ships = 0.0
    total_prod = 0.0
    my_ships = my_inflight = 0.0
    be_ships = be_inflight = 0.0
    my_planets = be_planets = 0
    my_prod = be_prod = 0.0
    my_cent_sum = be_cent_sum = 0.0
    my_cent_n = be_cent_n = 0

    for p in planets:
        owner = int(p[1])
        ships_p = float(p[5])
        prod_p = float(p[6]) if len(p) > 6 else 0.0
        total_ships += ships_p
        total_prod += prod_p
        cx, cy = float(p[2]), float(p[3])
        cent = _dist(cx, cy, *_CENTER)
        if owner == my_player:
            my_ships += ships_p
            my_planets += 1
            my_prod += prod_p
            my_cent_sum += cent
            my_cent_n += 1
        elif owner == best_enemy:
            be_ships += ships_p
            be_planets += 1
            be_prod += prod_p
            be_cent_sum += cent
            be_cent_n += 1

    for f in fleets:
        owner = int(f[1])
        sh = float(f[5])
        total_ships += sh
        if owner == my_player:
            my_inflight += sh
        elif owner == best_enemy:
            be_inflight += sh

    total_ships = max(total_ships, 1.0)
    total_prod = max(total_prod, 1.0)

    g_my_planet_ratio = my_planets / n_planets
    g_be_planet_ratio = be_planets / n_planets
    g_my_ship_ratio = (my_ships + my_inflight) / total_ships
    g_be_ship_ratio = (be_ships + be_inflight) / total_ships
    g_my_prod_ratio = my_prod / total_prod
    g_be_prod_ratio = be_prod / total_prod
    g_my_centrality_norm = (my_cent_sum / max(my_cent_n, 1)) / 60.0
    g_be_centrality_norm = (be_cent_sum / max(be_cent_n, 1)) / 60.0

    feats: dict[str, float] = {
        "g_step_norm": step / 500.0,
        "g_n_players_norm": n_players / 4.0,
        "g_my_planet_ratio": g_my_planet_ratio,
        "g_be_planet_ratio": g_be_planet_ratio,
        "g_my_ship_ratio": g_my_ship_ratio,
        "g_be_ship_ratio": g_be_ship_ratio,
        "g_my_prod_ratio": g_my_prod_ratio,
        "g_be_prod_ratio": g_be_prod_ratio,
        "g_my_centrality_norm": g_my_centrality_norm,
        "g_be_centrality_norm": g_be_centrality_norm,
        "g_ship_diff": g_my_ship_ratio - g_be_ship_ratio,
        "g_planet_diff": g_my_planet_ratio - g_be_planet_ratio,
        "g_prod_diff": g_my_prod_ratio - g_be_prod_ratio,
        "g_is_2p": 1.0 if n_players == 2 else 0.0,
        "g_is_4p": 1.0 if n_players == 4 else 0.0,
        "g_my_inflight_ratio": my_inflight / total_ships,
        "g_be_inflight_ratio": be_inflight / total_ships,
        "g_total_diff_ratio": (my_ships + my_inflight - be_ships - be_inflight) / total_ships,
        "g_inflight_lead": 1.0 if my_inflight > be_inflight else 0.0,
        "g_phase_encoded": _phase_encoded(step),
    }

    # idle 或无效 source：s_* / t_* 全 0
    source = _planet_by_id(planets, source_id) if source_id >= 0 else None
    if source is None or target_id < 0:
        for name in FEATURE_NAMES:
            if name.startswith("s_") or name.startswith("t_"):
                feats[name] = 0.0
    else:
        sx, sy = float(source[2]), float(source[3])
        nearby_enemy = _nearby_enemy_ships(planets, fleets, source, my_player)
        feats["s_ships_log"] = math.log(float(source[5]) + 1.0) / 10.0
        feats["s_prod_norm"] = float(source[6]) / 5.0 if len(source) > 6 else 0.0
        feats["s_dist_from_sun_norm"] = _dist(sx, sy, *_CENTER) / 60.0
        feats["s_garrison_ratio"] = float(source[5]) / (1.0 + nearby_enemy)
        feats["s_is_orbiting"] = 1.0 if inverse_target.is_planet_orbiting(source) else 0.0
        feats["s_in_combat_zone"] = 0.0
        for f in fleets:
            if int(f[1]) != my_player and int(f[1]) >= 0:
                if _dist(sx, sy, float(f[2]), float(f[3])) < 10.0:
                    feats["s_in_combat_zone"] = 1.0
                    break
        eta_ne = _eta_to_nearest_enemy_planet(planets, source, my_player, max(ships, 1))
        feats["s_eta_to_nearest_enemy_planet_norm"] = min(eta_ne, 250.0) / 250.0
        feats["s_owner_stability"] = 0.0
        feats["s_undeployable_lock"] = 0.0
        feats["s_centrality_norm"] = (50.0 - _dist(sx, sy, *_CENTER)) / 50.0

        target = _planet_by_id(planets, target_id) if target_id >= 0 else None
        if target is None:
            for name in FEATURE_NAMES:
                if name.startswith("t_"):
                    feats[name] = 0.0
        else:
            owner = int(target[1])
            code = _owner_code(owner, my_player, best_enemy)
            feats["t_owner_code"] = (code + 1.0) / 3.0
            feats["t_ships_log"] = math.log(float(target[5]) + 1.0) / 10.0
            feats["t_prod_norm"] = float(target[6]) / 5.0 if len(target) > 6 else 0.0
            feats["t_dist_from_source_norm"] = _dist(sx, sy, float(target[2]), float(target[3])) / 100.0
            spd = max(inverse_target.fleet_speed_simple(max(ships, 1)), 1e-6)
            eta = _dist(sx, sy, float(target[2]), float(target[3])) / spd
            feats["t_eta_with_fleet_speed_norm"] = min(eta, 250.0) / 250.0
            ang = launch_angle if launch_angle is not None else 0.0
            v_ang = float(observation.get("angular_velocity", 0.0))
            feats["t_is_doomed_to_sun"] = _is_doomed_to_sun(
                source, target, ang, max(ships, 1), planets, v_ang
            )
            feats["t_swept_by_other"] = _swept_by_other_planet(
                source_id, target_id, ang, max(ships, 1), planets, v_ang
            )
            feats["t_reactive_snipe_risk"] = _reactive_snipe_risk(
                target, planets, fleets, my_player, best_enemy, eta
            )
            feats["t_is_orbiting"] = 1.0 if inverse_target.is_planet_orbiting(target) else 0.0
            feats["t_centrality_norm"] = (50.0 - _dist(float(target[2]), float(target[3]), *_CENTER)) / 50.0
            my_inf = _inflight_to_target(fleets, my_player, target_id)
            be_inf = _inflight_to_target(fleets, best_enemy, target_id)
            feats["t_inflight_friendly_pressure_log"] = math.log(my_inf + 1.0) / 5.0
            feats["t_inflight_enemy_pressure_log"] = math.log(be_inf + 1.0) / 5.0

    total_inf_tgt = (
        _inflight_to_target(fleets, my_player, target_id)
        + _inflight_to_target(fleets, best_enemy, target_id)
        if target_id >= 0
        else 0
    )
    my_inf_t = _inflight_to_target(fleets, my_player, target_id) if target_id >= 0 else 0
    be_inf_t = _inflight_to_target(fleets, best_enemy, target_id) if target_id >= 0 else 0

    feats["c_phase_pressure"] = max(0.0, feats["g_my_ship_ratio"] - feats["g_be_ship_ratio"] - 0.05)
    feats["c_my_action_count_this_turn"] = min(my_action_count_this_turn, 5) / 5.0
    feats["c_action_repeat_penalty"] = min(action_repeat_penalty, 3.0) / 3.0
    feats["c_inflight_lead_to_this_target"] = (
        (my_inf_t - be_inf_t) / (1.0 + total_inf_tgt) if target_id >= 0 else 0.0
    )
    feats["c_first_action_in_episode"] = first_action_in_episode

    return {k: _safe_float(feats.get(k, 0.0)) for k in FEATURE_NAMES}


def extract_from_replay(
    replay_json: dict[str, Any],
    episode_id: int,
    config: ExtractConfig,
    rng_seed: int = 42,
) -> list[dict[str, Any]]:
    """单局 replay → 训练行列表。"""
    rng = random.Random(rng_seed ^ (episode_id & 0xFFFFFFFF))
    players_count = 2
    if replay_json.get("rewards") and len(replay_json["rewards"]) == 4:
        players_count = 4
    winner_id = _winner_from_replay(replay_json)

    rows: list[dict[str, Any]] = []
    first_action: set[int] = set()
    steps = parse_replay_steps(replay_json)

    # 按 tick 聚合，统计同回合动作次数与重复 target
    by_tick: dict[int, list[dict[str, Any]]] = {}
    for rec in steps:
        by_tick.setdefault(rec["tick"], []).append(rec)

    for tick in sorted(by_tick.keys()):
        tick_records = by_tick[tick]
        for rec in tick_records:
            player_id = rec["player_id"]
            obs = rec["observation"]
            actions = rec["action"]
            planets = obs.get("planets") or []
            v_ang = float(obs.get("angular_velocity", 0.0))

            if actions:
                resolved_targets: list[int] = []
                parsed_actions: list[tuple[int, float, int]] = []
                for move in actions:
                    if len(move) < 3:
                        continue
                    sid, ang, ship_n = int(move[0]), float(move[1]), int(move[2])
                    if ship_n < config.min_ships_to_label:
                        continue
                    parsed_actions.append((sid, ang, ship_n))

                if not parsed_actions:
                    continue

                targets = inverse_target.batch_resolve(parsed_actions, planets, v_ang)
                target_repeat: dict[int, int] = {}
                action_idx = 0
                for (sid, ang, ship_n), tid in zip(parsed_actions, targets):
                    if tid == -1:
                        continue
                    source = _planet_by_id(planets, sid)
                    if source is None:
                        continue
                    src_ships = max(int(source[5]), 1)
                    ships_frac = ship_n / src_ships
                    target_repeat[tid] = target_repeat.get(tid, 0)
                    feat = build_state_features(
                        obs,
                        sid,
                        tid,
                        players_count,
                        tick=tick,
                        launch_angle=ang,
                        ships=ship_n,
                        my_action_count_this_turn=action_idx,
                        action_repeat_penalty=float(target_repeat[tid]),
                        first_action_in_episode=1.0 if player_id not in first_action else 0.0,
                    )
                    first_action.add(player_id)
                    target_repeat[tid] += 1
                    action_idx += 1
                    rows.append(
                        {
                            "episode_id": episode_id,
                            "tick": tick,
                            "player_id": player_id,
                            "players_count": players_count,
                            "winner_id": winner_id,
                            "source_id": sid,
                            "target_id": tid,
                            "ships": ship_n,
                            "ships_frac": _safe_float(ships_frac),
                            "label_act": 1,
                            **feat,
                        }
                    )
            else:
                # 被动回合：95% 丢弃
                if rng.random() > config.idle_keep_rate:
                    continue
                feat = build_state_features(
                    obs,
                    -1,
                    -1,
                    players_count,
                    tick=tick,
                )
                rows.append(
                    {
                        "episode_id": episode_id,
                        "tick": tick,
                        "player_id": player_id,
                        "players_count": players_count,
                        "winner_id": winner_id,
                        "source_id": -1,
                        "target_id": -1,
                        "ships": 0,
                        "ships_frac": 0.0,
                        "label_act": 0,
                        **feat,
                    }
                )

    return rows


def _rows_to_table(rows: list[dict[str, Any]]) -> pa.Table:
    """list[dict] → pyarrow Table（float32 特征列）。"""
    if not rows:
        return pa.table({c: pa.array([], type=pa.float32()) for c in ALL_COLUMNS})
    columns: dict[str, list[Any]] = {c: [] for c in ALL_COLUMNS}
    for row in rows:
        for c in ALL_COLUMNS:
            val = row.get(c, 0)
            if c in FEATURE_NAMES or c in ("ships_frac",):
                columns[c].append(float(val))
            else:
                columns[c].append(int(val))

    arrays: dict[str, pa.Array] = {}
    for c in ALL_COLUMNS:
        if c in FEATURE_NAMES or c == "ships_frac":
            arrays[c] = pa.array(columns[c], type=pa.float32())
        else:
            arrays[c] = pa.array(columns[c], type=pa.int32())
    return pa.table(arrays)


def run_extract(config: ExtractConfig) -> ExtractStats:
    """遍历 raw_dir，分批写 parquet。"""
    stats = ExtractStats()
    raw_files = sorted(config.raw_dir.glob("*.json"))
    config.output_path.parent.mkdir(parents=True, exist_ok=True)

    buffer: list[dict[str, Any]] = []
    writer: pq.ParquetWriter | None = None
    schema = None

    def flush_buffer() -> None:
        nonlocal writer, schema, buffer
        if not buffer:
            return
        table = _rows_to_table(buffer)
        if writer is None:
            schema = table.schema
            writer = pq.ParquetWriter(config.output_path, schema)
        writer.write_table(table)
        buffer = []

    for path in tqdm(raw_files, desc="extract_features"):
        episode_id = int(path.stem)
        try:
            with path.open("r", encoding="utf-8") as fp:
                replay = json.load(fp)
            rows = extract_from_replay(replay, episode_id, config)
            stats.episodes_processed += 1
            stats.pairs_emitted += len(rows)
            buffer.extend(rows)
            if stats.episodes_processed % _FLUSH_EVERY == 0:
                flush_buffer()
        except Exception:
            stats.episodes_failed += 1
            stats.failed_episode_ids.append(episode_id)

    flush_buffer()
    if writer is not None:
        writer.close()

    return stats


def cli() -> int:
    parser = argparse.ArgumentParser(description="Replay → Parquet ETL")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/replays/raw"))
    parser.add_argument("--manifest", type=Path, default=Path("data/replays/manifest.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/replays/processed/v1.parquet"))
    parser.add_argument("--version", type=str, default="v1")
    parser.add_argument("--idle-keep-rate", type=float, default=0.05)
    args = parser.parse_args()

    config = ExtractConfig(
        raw_dir=args.raw_dir,
        manifest_path=args.manifest,
        output_path=args.output,
        version=args.version,
        idle_keep_rate=args.idle_keep_rate,
    )
    stats = run_extract(config)
    print(json.dumps(stats.__dict__, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
