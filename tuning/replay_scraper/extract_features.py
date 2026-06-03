"""
Replay JSON → 训练 parquet 的特征抽取（M14 子模块）

输入：
    data/replays/raw/{episode_id}.json
输出：
    data/replays/processed/v1.parquet

每一行代表一个"决策机会"（即某玩家在某 tick 的一次出舰决策），含：
    - episode_id, tick, player_id, players_count, winner_id
    - source_id, target_id, ships, ships_frac (=ships/source.ships at launch)
    - state_features: 47-dim 全局 + per-source + per-target 数值向量
    - label_act: 1 if (出舰) else 0
    - 数据平衡：被动 turn（act=[]) 95% 丢弃（参考 IL notebook Cell 11）

特征设计（master-plan §1.3 / §M13 详述）：
    全局 (20-dim, 复用 src/policy/value_gbc.value_state_features)：
        my_ship_ratio, my_planet_ratio, my_prod_ratio,
        enemy_ship_ratio_max, enemy_planet_ratio_max, ..., tick_normalized
    per-source (~10-dim)：
        source_ships, source_prod, source_garrison_pressure,
        source_centrality, source_is_orbiting, ...
    per-target (~12-dim)：
        target_owner_code, target_ships, target_prod,
        target_dist_from_source, target_eta_with_fleet_size,
        target_is_doomed_to_sun, target_swept_by_other,
        target_reactive_snipe_risk,  ← vkhydras 关键洞察
        ...
    contextual (~5-dim)：
        tick_normalized, players_count, my_phase_encoded, ...

CLI 用法：
    python -m tuning.replay_scraper.extract_features \
        --raw-dir data/replays/raw \
        --manifest data/replays/manifest.csv \
        --output data/replays/processed/v1.parquet \
        --version v1
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tqdm import tqdm

from . import inverse_target


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
    """单次抽取的统计汇总"""
    episodes_processed: int = 0
    episodes_failed: int = 0
    pairs_emitted: int = 0
    pairs_unresolved: int = 0
    idle_turns_kept: int = 0
    idle_turns_dropped: int = 0
    per_player_count: int = 0
    failed_episode_ids: list[int] = field(default_factory=list)


def load_episode_meta(manifest_path: Path) -> dict[int, dict[str, Any]]:
    """
    读 manifest.csv，返回 {episode_id: {"submission_id":..., "team_name":..., ...}}
    供特征抽取时回填字段（如 expert team_name）。
    """
    raise NotImplementedError(
        "M14/T0.7 待实现：加载 manifest meta"
    )


def parse_replay_steps(replay_json: dict[str, Any]) -> list[dict[str, Any]]:
    """
    从 replay JSON 中提取 per-tick 的 (observation, action) per player。

    返回：
        list[ {tick, player_id, observation_dict, action_list, ...} ]

    实现要点：
        - replay_json["steps"][i][p_id]["observation"] 是 i 时刻 p_id 视角的 obs
        - replay_json["steps"][i][p_id]["action"] 是其当时做出的 action list
        - 跳过 step 0（初始局面）
        - 跳过 status != "ACTIVE" 的玩家
    """
    raise NotImplementedError(
        "M14/T0.7 待实现：解析 replay steps"
    )


def build_state_features(
    observation: dict[str, Any],
    source_id: int,
    target_id: int,
    players_count: int,
) -> dict[str, float]:
    """
    为单条 (source, target) action 构造 ~47 维特征向量。

    返回：
        {feature_name: value}，键名固定（IL prior 训练必须列对齐）

    实现要点：
        - 全局 20 维：复用 src/policy/value_gbc.value_state_features 的逻辑
        - per-source / per-target / contextual：本模块内独立实现
        - 任何 NaN/Inf 一律 clip 或 fillna 0.0
        - target_id == -1 时 per-target 字段全 0（用于"我没出舰"样本）
    """
    raise NotImplementedError(
        "M14/T0.7 待实现：feature engineering（master-plan §1.3 § extract_features 详述）"
    )


def extract_from_replay(
    replay_json: dict[str, Any],
    episode_id: int,
    config: ExtractConfig,
    rng_seed: int = 42,
) -> list[dict[str, Any]]:
    """
    单 replay → 特征行列表。

    流程：
        1. 解析 steps
        2. 对每个 (tick, player_id) 判断是否出舰
        3. 若出舰：对每个 action 用 resolve_target 反推 target
           - 仅保留 target != -1 的样本
           - 一条 action → 一行特征（source/target/ships 在内）
        4. 若未出舰：按 idle_keep_rate 概率保留一行（target_id = -1）
        5. 加上 episode_id, players_count, winner_id, tick 等元字段
    """
    raise NotImplementedError(
        "M14/T0.7 待实现：单 replay 特征抽取主流程"
    )


def run_extract(config: ExtractConfig) -> ExtractStats:
    """
    主入口：遍历 raw_dir 下所有 replay JSON，输出 parquet。

    实现要点：
        - 用 pandas/pyarrow，分批写入（每 200 episodes flush 一次）
        - 失败的 episode_id 记入 ExtractStats.failed_episode_ids
        - 解析率 < 85% 时仅警告，不退出（让 M16 数据质量监控决定丢弃哪些）
    """
    raise NotImplementedError(
        "M14/T0.7 待实现：批量抽取主循环 + parquet 落盘"
    )


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
