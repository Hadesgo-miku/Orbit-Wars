"""多进程并行 tournament runner。

设计目标：单版本 256 局（4 对手 × 64 局）在 8 核 CPU 上 ≤ 5 分钟。

调用方式（命令行）::

    python -m eval.tournament \\
        --agent src/agent.py \\
        --opponents nearest_sniper,may18_launch_safety \\
        --seeds 32 \\
        --workers 8 \\
        --output eval/results/v1_raw.json

调用方式（脚本）::

    from eval.tournament import run_tournament, TournamentConfig
    result = run_tournament(TournamentConfig(
        agent_path="src/agent.py",
        opponent_paths=["eval/opponents/nearest_sniper.py", ...],
        seeds=SEEDS[:32],
        play_both_seats=True,
        num_workers=8,
    ))
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TournamentConfig:
    """单次 tournament 的配置。"""

    #: 主 agent 路径（待评测）
    agent_path: str

    #: 对手 agent 路径列表
    opponent_paths: list[str] = field(default_factory=list)

    #: 评测使用的 seed 列表
    seeds: list[int] = field(default_factory=list)

    #: 是否对每个 seed 两个 seat 都跑（必开，否则 float drift 会污染）
    play_both_seats: bool = True

    #: 并行进程数
    num_workers: int = 8

    #: 单局 timeout（秒）
    per_game_timeout_s: float = 60.0


@dataclass
class GameResult:
    """单局结果。"""

    seed: int
    my_seat: int               # 0 或 1
    opponent_name: str
    my_reward: float
    opp_reward: float
    win: bool                  # 我赢与否
    draw: bool
    elapsed_s: float
    error: str | None = None


@dataclass
class TournamentResult:
    """整轮评测产出。"""

    config: TournamentConfig
    games: list[GameResult] = field(default_factory=list)

    def win_rate_vs(self, opponent_name: str) -> tuple[float, int]:
        """返回 (胜率, 局数)。平局算 0.5 胜。"""
        games = [g for g in self.games if g.opponent_name == opponent_name]
        if not games:
            return 0.0, 0
        wins = sum((1.0 if g.win else 0.5 if g.draw else 0.0) for g in games)
        return wins / len(games), len(games)


# ---------------------------------------------------------------------------
# 核心接口
# ---------------------------------------------------------------------------


def run_single_game(
    seed: int,
    agent_path: str,
    opponent_path: str,
    my_seat: int = 0,
    timeout_s: float = 60.0,
) -> GameResult:
    """跑一局。

    使用 ``kaggle_environments.make("orbit_wars", configuration={"seed": seed})``。
    """
    raise NotImplementedError(
        "Eval Lead 实现；参考 orbit-wars-guide/agents.md 的 env.run 用法。"
    )


def run_tournament(config: TournamentConfig) -> TournamentResult:
    """跑完整 tournament，多进程并行。

    实现要点：

    1. ``multiprocessing.Pool(num_workers)`` 并行
    2. 每个对手 × 每个 seed × (双 seat 时 ×2) 个 task
    3. 进度条（tqdm）
    4. 任何单局异常不能中断整体，记录到 ``GameResult.error``
    """
    raise NotImplementedError("Eval Lead 实现。")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orbit Wars 评测 runner")
    parser.add_argument("--agent", required=True, help="主 agent 路径")
    parser.add_argument(
        "--opponents",
        required=True,
        help="对手列表，逗号分隔（可用对手池名或路径）",
    )
    parser.add_argument("--seeds", type=int, default=32, help="使用前 N 个 seed")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", default="eval/results/_raw.json")
    parser.add_argument("--no-both-seats", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    # ...（Eval Lead 实现：解析 opponents → 路径，构造 config，跑，写 JSON）
    raise NotImplementedError("Eval Lead 实现。")


if __name__ == "__main__":
    main()
