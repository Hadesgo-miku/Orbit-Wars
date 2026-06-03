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
import json
import multiprocessing as mp
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .seeds import SEEDS

try:
    # tqdm 仅用于更友好的进度展示；若环境未安装，下面会回退到无进度条实现。
    from tqdm import tqdm  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - 非关键路径，且依赖是否存在取决于运行环境
    tqdm = None

# ---------------------------------------------------------------------------
# 对手池别名表：
# CLI 允许用户传入“短名字”（如 nearest_sniper），这里统一映射到具体文件路径。
# ---------------------------------------------------------------------------

_OPPONENT_NAME_TO_PATH: dict[str, str] = {
    "random_agent": "eval/opponents/random_agent.py",
    "nearest_sniper": "eval/opponents/nearest_sniper.py",
    "may18_launch_safety": "eval/opponents/may18_launch_safety.py",
    "public_heuristic_1110": "eval/opponents/public_heuristic_1110.py",
    "lb_1200_baseline": "eval/opponents/lb_1200_baseline.py",
}

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

    def to_dict(self) -> dict[str, Any]:
        """把结果序列化为 JSON 友好的 dict。"""
        return {
            "config": {
                "agent_path": self.config.agent_path,
                "opponent_paths": self.config.opponent_paths,
                "seeds": self.config.seeds,
                "play_both_seats": self.config.play_both_seats,
                "num_workers": self.config.num_workers,
                "per_game_timeout_s": self.config.per_game_timeout_s,
            },
            "games": [
                {
                    "seed": g.seed,
                    "my_seat": g.my_seat,
                    "opponent_name": g.opponent_name,
                    "my_reward": g.my_reward,
                    "opp_reward": g.opp_reward,
                    "win": g.win,
                    "draw": g.draw,
                    "elapsed_s": g.elapsed_s,
                    "error": g.error,
                }
                for g in self.games
            ],
        }


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
    started = time.perf_counter()
    opponent_name = Path(opponent_path).stem

    try:
        # 延迟导入：避免在“仅做模块导入”场景下强绑定 kaggle_environments。
        from kaggle_environments import make  # type: ignore[import-not-found]
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return GameResult(
            seed=seed,
            my_seat=my_seat,
            opponent_name=opponent_name,
            my_reward=0.0,
            opp_reward=0.0,
            win=False,
            draw=False,
            elapsed_s=elapsed,
            error=f"import kaggle_environments failed: {exc}",
        )

    try:
        # 1) 使用固定 seed 创建环境，确保可复现。
        env = make("orbit_wars", configuration={"seed": seed}, debug=False)

        # 2) 根据 seat 决定 env.run 的 agent 顺序。
        if my_seat == 0:
            agents = [agent_path, opponent_path]
            my_idx, opp_idx = 0, 1
        else:
            agents = [opponent_path, agent_path]
            my_idx, opp_idx = 1, 0

        # 3) 执行整局对战，最终奖励位于最后一个 step。
        env.run(agents)
        final_step = env.steps[-1]
        my_reward_raw = final_step[my_idx].reward
        opp_reward_raw = final_step[opp_idx].reward
        my_reward = float(my_reward_raw if my_reward_raw is not None else 0.0)
        opp_reward = float(opp_reward_raw if opp_reward_raw is not None else 0.0)

        # 4) 由奖励关系推导胜负平。
        win = my_reward > opp_reward
        draw = my_reward == opp_reward
        elapsed = time.perf_counter() - started

        # 5) 超时不强杀（v1 先保证稳定性），但记录错误信号便于报告排查。
        error = None
        if elapsed > timeout_s:
            error = f"timeout_exceeded: elapsed={elapsed:.3f}s > {timeout_s:.3f}s"

        return GameResult(
            seed=seed,
            my_seat=my_seat,
            opponent_name=opponent_name,
            my_reward=my_reward,
            opp_reward=opp_reward,
            win=win,
            draw=draw,
            elapsed_s=elapsed,
            error=error,
        )
    except Exception as exc:  # 捕获单局异常，保证 tournament 能持续跑完。
        elapsed = time.perf_counter() - started
        return GameResult(
            seed=seed,
            my_seat=my_seat,
            opponent_name=opponent_name,
            my_reward=0.0,
            opp_reward=0.0,
            win=False,
            draw=False,
            elapsed_s=elapsed,
            error=str(exc),
        )


def _run_task(task: tuple[int, str, str, int, float]) -> GameResult:
    """Pool worker 入口（顶层函数，便于被 multiprocessing pickling）。"""
    seed, agent_path, opponent_path, seat, timeout_s = task
    return run_single_game(
        seed=seed,
        agent_path=agent_path,
        opponent_path=opponent_path,
        my_seat=seat,
        timeout_s=timeout_s,
    )


def _run_task_safely(task: tuple[int, str, str, int, float]) -> GameResult:
    """兜底包装：即使 worker 层抛异常，也转成带 error 的 GameResult。"""
    seed, _agent_path, opponent_path, seat, _timeout_s = task
    opponent_name = Path(opponent_path).stem
    started = time.perf_counter()
    try:
        return _run_task(task)
    except Exception as exc:  # pragma: no cover - 这里属于“防御性保险丝”
        return GameResult(
            seed=seed,
            my_seat=seat,
            opponent_name=opponent_name,
            my_reward=0.0,
            opp_reward=0.0,
            win=False,
            draw=False,
            elapsed_s=time.perf_counter() - started,
            error=f"worker_exception: {exc}",
        )


def run_tournament(config: TournamentConfig) -> TournamentResult:
    """跑完整 tournament，多进程并行。

    实现要点：

    1. ``multiprocessing.Pool(num_workers)`` 并行
    2. 每个对手 × 每个 seed × (双 seat 时 ×2) 个 task
    3. 进度条（tqdm）
    4. 任何单局异常不能中断整体，记录到 ``GameResult.error``
    """
    if not config.opponent_paths:
        raise ValueError("opponent_paths 不能为空。")
    if not config.seeds:
        raise ValueError("seeds 不能为空。")

    # 1) 构建完整任务网格：对手 × seed × seat。
    seats = (0, 1) if config.play_both_seats else (0,)
    tasks: list[tuple[int, str, str, int, float]] = []
    for opponent_path in config.opponent_paths:
        for seed in config.seeds:
            for seat in seats:
                tasks.append(
                    (
                        seed,
                        config.agent_path,
                        opponent_path,
                        seat,
                        config.per_game_timeout_s,
                    )
                )

    # 2) 跑任务：
    #    - num_workers <= 1：串行模式（更利于单元测试 monkeypatch）。
    #    - num_workers >= 2：Pool 并行模式。
    games: list[GameResult] = []
    total = len(tasks)
    use_progress = tqdm is not None

    if config.num_workers <= 1:
        if use_progress:
            for task in tqdm(tasks, desc="tournament", total=total):
                games.append(_run_task_safely(task))
        else:
            for task in tasks:
                games.append(_run_task_safely(task))
    else:
        with mp.Pool(processes=config.num_workers) as pool:
            iterator = pool.imap_unordered(_run_task_safely, tasks)
            if use_progress:
                for game in tqdm(iterator, desc="tournament", total=total):
                    games.append(game)
            else:
                for game in iterator:
                    games.append(game)

    return TournamentResult(config=config, games=games)


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
    # 1) 解析对手：支持“逗号分隔的别名”与“文件路径”混用。
    opponent_tokens = [token.strip() for token in args.opponents.split(",") if token.strip()]
    if not opponent_tokens:
        raise ValueError("至少需要一个 opponent。")

    opponent_paths: list[str] = []
    for token in opponent_tokens:
        if token in _OPPONENT_NAME_TO_PATH:
            opponent_paths.append(_OPPONENT_NAME_TO_PATH[token])
        else:
            opponent_paths.append(token)

    # 2) 取 seeds 前 N 个。
    if args.seeds <= 0:
        raise ValueError("--seeds 必须 > 0。")
    if args.seeds > len(SEEDS):
        raise ValueError(f"--seeds 超过上限：{args.seeds} > {len(SEEDS)}")
    seeds = SEEDS[: args.seeds]

    config = TournamentConfig(
        agent_path=args.agent,
        opponent_paths=opponent_paths,
        seeds=seeds,
        play_both_seats=not args.no_both_seats,
        num_workers=args.workers,
    )
    result = run_tournament(config)

    # 3) 输出原始 JSON，供后续 report/stats 使用。
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    # 4) 命令行给出简洁摘要，方便快速确认跑没跑对。
    total_games = len(result.games)
    total_wins = sum(1.0 if g.win else 0.5 if g.draw else 0.0 for g in result.games)
    win_rate = (total_wins / total_games) if total_games else 0.0
    print(
        f"Done: games={total_games}, wins={total_wins:.1f}, "
        f"win_rate={win_rate:.2%}, output={output_path}"
    )


if __name__ == "__main__":
    main()
