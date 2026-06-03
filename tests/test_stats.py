"""M12 评测统计工具的单元测试。

Wilson CI 与 SPRT 的实现已完成，应当全部 pass。
"""

from __future__ import annotations

import pytest

from eval.stats import wilson_ci, is_significantly_better, sprt_decision


# ---------------------------------------------------------------------------
# Wilson CI
# ---------------------------------------------------------------------------


def test_wilson_ci_empty():
    """0 局时应返回最大区间。"""
    low, high = wilson_ci(0, 0)
    assert low == 0.0
    assert high == 1.0


def test_wilson_ci_50_percent():
    """50% 胜率 + 100 局 → CI 应当对称于 0.5。"""
    low, high = wilson_ci(50, 100)
    mid = (low + high) / 2
    assert abs(mid - 0.5) < 0.01


def test_wilson_ci_extreme():
    """边界胜率不应给出 [0, 0] 或 [1, 1] 这种 degenerate 区间。"""
    low, high = wilson_ci(0, 64)
    assert low == 0.0
    assert high > 0.0   # 上沿应有非零宽度

    low, high = wilson_ci(64, 64)
    assert low < 1.0    # 下沿应有非零差距
    assert high == 1.0


def test_wilson_ci_more_games_shrinks():
    """更多样本 → CI 收紧。"""
    low_small, high_small = wilson_ci(30, 50)
    low_large, high_large = wilson_ci(300, 500)
    assert (high_large - low_large) < (high_small - low_small)


# ---------------------------------------------------------------------------
# 显著性判断
# ---------------------------------------------------------------------------


def test_is_significantly_better_obvious():
    """80% vs 50%，各 200 局，应显著优于。"""
    assert is_significantly_better(160, 200, 100, 200) is True


def test_is_significantly_better_tiny_diff():
    """52% vs 50% 各 30 局，差距太小不显著。"""
    assert is_significantly_better(16, 30, 15, 30) is False


def test_is_significantly_better_worse():
    """新版本反而更差，不应显著。"""
    assert is_significantly_better(40, 100, 60, 100) is False


# ---------------------------------------------------------------------------
# SPRT
# ---------------------------------------------------------------------------


def test_sprt_continue_at_start():
    """开局 0 局，应该继续测。"""
    assert sprt_decision(0, 0) == "continue"


def test_sprt_strong_evidence_accept_alt():
    """连胜很多局 0 败，应接受 alt（强）。

    默认 alpha=beta=0.05、p_null=0.5、p_alt=0.55 时，
    log_a = ln(19) ≈ 2.944；连胜需 ~31 局才超过阈值。
    """
    decision = sprt_decision(50, 0)
    assert decision == "accept_alt"


def test_sprt_strong_evidence_accept_null():
    """连败很多局 0 胜，应接受 null（弱）。"""
    decision = sprt_decision(0, 50)
    assert decision == "accept_null"
