"""M14 Replay Scraper 性能测试。

说明：
- 该测试用于手动验证真实网络条件下 get_episode_replay 的 P95；
- 默认跳过 CI，需显式设置 RUN_REPLAY_PERF=1 才会执行；
- 执行前请确保 ~/.kaggle/kaggle.json 可用。
"""

from __future__ import annotations

import os
import time

import pytest

from tuning.replay_scraper import kaggle_api


def _p95(samples: list[float]) -> float:
    """使用最近秩法估算 P95，避免依赖额外统计库。"""
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[idx]


@pytest.mark.skipif(
    os.environ.get("RUN_REPLAY_PERF") != "1",
    reason="仅手动压测时执行，CI 默认跳过。",
)
def test_get_episode_replay_p95_under_5s_real_network():
    """真实网络下，get_episode_replay 调用延迟 P95 应 <= 5 秒。"""
    auth = kaggle_api.KaggleAuth.from_default_path()
    top_entries = kaggle_api.get_top_n_submissions(n=1, auth=auth)
    assert top_entries, "leaderboard 为空，无法执行性能测试"

    episodes = kaggle_api.list_episodes_for_submission(
        submission_id=top_entries[0].submission_id,
        auth=auth,
        max_count=8,
    )
    assert episodes, "目标 submission 无可用 episode，无法执行性能测试"

    elapsed_s: list[float] = []
    for episode in episodes[:8]:
        started = time.perf_counter()
        replay = kaggle_api.get_episode_replay(episode_id=episode.episode_id, auth=auth)
        elapsed_s.append(time.perf_counter() - started)
        # 用结构校验防止“请求失败太快导致性能虚高”。
        assert "configuration" in replay
        assert isinstance(replay.get("steps"), list)

    assert _p95(elapsed_s) <= 5.0
