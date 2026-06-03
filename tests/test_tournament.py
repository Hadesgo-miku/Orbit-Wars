"""M12 Tournament Runner 单元测试。

覆盖点：
1. 任务网格生成是否符合「对手 × seeds × 双 seat」约定；
2. win_rate_vs 是否按「平局=0.5」统计；
3. 单局异常是否被隔离，不影响整体 tournament 完成。
"""

from __future__ import annotations

from eval.tournament import (
    GameResult,
    TournamentConfig,
    TournamentResult,
    run_tournament,
)


def test_run_tournament_generates_dual_seat_tasks(monkeypatch):
    """双 seat 模式下应生成 2 倍任务，并且 seat 0/1 都出现。"""
    called = []

    def fake_run_single_game(seed, agent_path, opponent_path, my_seat=0, timeout_s=60.0):
        # 记录调用参数，后续用于断言任务网格是否正确展开。
        called.append((seed, agent_path, opponent_path, my_seat, timeout_s))
        return GameResult(
            seed=seed,
            my_seat=my_seat,
            opponent_name=opponent_path.split("/")[-1].replace(".py", ""),
            my_reward=1.0,
            opp_reward=0.0,
            win=True,
            draw=False,
            elapsed_s=0.001,
            error=None,
        )

    monkeypatch.setattr("eval.tournament.run_single_game", fake_run_single_game)

    config = TournamentConfig(
        agent_path="src/agent.py",
        opponent_paths=["eval/opponents/random_agent.py", "eval/opponents/nearest_sniper.py"],
        seeds=[1, 2, 3],
        play_both_seats=True,
        num_workers=1,  # 使用串行分支，保证 monkeypatch 生效且测试稳定。
    )
    result = run_tournament(config)

    # 对手 2 × seed 3 × seat 2 = 12 局
    assert len(result.games) == 12
    assert len(called) == 12

    seats = {seat for (_, _, _, seat, _) in called}
    assert seats == {0, 1}


def test_win_rate_vs_counts_draw_as_half():
    """平局应按 0.5 胜计入胜率。"""
    cfg = TournamentConfig(agent_path="src/agent.py")
    result = TournamentResult(
        config=cfg,
        games=[
            GameResult(1, 0, "opp", 1.0, 0.0, True, False, 0.01),
            GameResult(2, 0, "opp", 0.0, 0.0, False, True, 0.01),
            GameResult(3, 0, "opp", 0.0, 1.0, False, False, 0.01),
        ],
    )
    wr, n = result.win_rate_vs("opp")
    assert n == 3
    assert wr == (1.0 + 0.5 + 0.0) / 3


def test_run_tournament_single_game_error_is_isolated(monkeypatch):
    """某一局抛异常时，runner 应继续并把错误写入 GameResult.error。"""

    def fake_run_single_game(seed, agent_path, opponent_path, my_seat=0, timeout_s=60.0):
        # 故意让一个特定任务抛错，验证 run_tournament 的异常隔离能力。
        if seed == 2 and my_seat == 1:
            raise RuntimeError("boom")
        return GameResult(
            seed=seed,
            my_seat=my_seat,
            opponent_name="random_agent",
            my_reward=0.0,
            opp_reward=0.0,
            win=False,
            draw=True,
            elapsed_s=0.002,
            error=None,
        )

    monkeypatch.setattr("eval.tournament.run_single_game", fake_run_single_game)

    config = TournamentConfig(
        agent_path="src/agent.py",
        opponent_paths=["eval/opponents/random_agent.py"],
        seeds=[1, 2],
        play_both_seats=True,
        num_workers=1,
    )
    result = run_tournament(config)

    assert len(result.games) == 4
    errors = [g for g in result.games if g.error]
    assert len(errors) == 1
    assert "boom" in errors[0].error
