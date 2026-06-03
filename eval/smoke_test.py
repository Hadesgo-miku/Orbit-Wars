"""M12 评测系统集成冒烟测试。

目标：
- 不依赖 kaggle_environments；
- 验证 run_tournament 的核心流程（任务展开、聚合、统计接口）能完整跑通。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 兼容两种启动方式：
# 1) `python -m eval.smoke_test`（包方式）
# 2) `python eval/smoke_test.py`（脚本方式）
# 对于第 2 种，手动把仓库根目录注入 sys.path，确保 `import eval...` 可解析。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from eval.tournament import GameResult, TournamentConfig, run_tournament


def _fake_run_single_game(seed, agent_path, opponent_path, my_seat=0, timeout_s=60.0):
    """最小可控桩：seat=0 视为胜，seat=1 视为负，便于形成非平凡统计结果。"""
    if my_seat == 0:
        my_reward, opp_reward = 1.0, 0.0
    else:
        my_reward, opp_reward = 0.0, 1.0
    return GameResult(
        seed=seed,
        my_seat=my_seat,
        opponent_name="random_agent",
        my_reward=my_reward,
        opp_reward=opp_reward,
        win=my_reward > opp_reward,
        draw=my_reward == opp_reward,
        elapsed_s=0.001,
        error=None,
    )


def main() -> None:
    # 通过临时替换 run_single_game，把集成测试聚焦在 tournament 编排逻辑。
    import eval.tournament as tournament_mod

    original = tournament_mod.run_single_game
    tournament_mod.run_single_game = _fake_run_single_game
    try:
        config = TournamentConfig(
            agent_path="src/agent.py",
            opponent_paths=["eval/opponents/random_agent.py"],
            seeds=[5199],  # 取任意一个合法 seed 做最小回归。
            play_both_seats=True,
            num_workers=1,
        )
        result = run_tournament(config)

        # 1) 任务数量：1 对手 × 1 seed × 2 seats = 2 局
        assert len(result.games) == 2
        # 2) 胜率接口可用：一胜一负应为 50%
        wr, n = result.win_rate_vs("random_agent")
        assert n == 2
        assert wr == 0.5
    finally:
        tournament_mod.run_single_game = original

    print("smoke_test passed")


if __name__ == "__main__":
    main()
