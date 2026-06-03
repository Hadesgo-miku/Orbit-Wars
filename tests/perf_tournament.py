"""M12 Tournament Runner 性能测试（轻量版）。

说明：
- 这里不跑真实 kaggle 环境，避免把环境初始化时间混入模块自身开销；
- 通过 monkeypatch run_single_game，专门测 run_tournament 的任务展开与聚合路径。
"""

from __future__ import annotations

import time

from eval.tournament import GameResult, TournamentConfig, run_tournament


def _fake_run_single_game(seed, agent_path, opponent_path, my_seat=0, timeout_s=60.0):
    """性能测试桩函数：返回固定结果，避免外部环境噪音。"""
    return GameResult(
        seed=seed,
        my_seat=my_seat,
        opponent_name="random_agent",
        my_reward=1.0,
        opp_reward=0.0,
        win=True,
        draw=False,
        elapsed_s=0.0,
        error=None,
    )


def _p95(values: list[float]) -> float:
    """计算 p95，样本量较小时使用最近秩近似。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[idx]


def test_run_tournament_p95_under_budget(monkeypatch):
    """单次调用 p95 应低于预算（默认 50ms）。"""
    monkeypatch.setattr("eval.tournament.run_single_game", _fake_run_single_game)

    samples = []
    for _ in range(40):
        config = TournamentConfig(
            agent_path="src/agent.py",
            opponent_paths=["eval/opponents/random_agent.py"],
            seeds=[1, 2, 3, 4],
            play_both_seats=True,
            num_workers=1,  # 串行路径更稳定，便于 CI 性能阈值控制。
        )
        started = time.perf_counter()
        result = run_tournament(config)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        samples.append(elapsed_ms)
        # 基本正确性兜底：防止“太快但没真正执行”。
        assert len(result.games) == 8

    assert _p95(samples) < 50.0
