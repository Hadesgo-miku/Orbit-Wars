"""统计工具：Wilson Score Interval 与 Sequential Probability Ratio Test。

为什么不用正态近似：n=64 时正态近似的 95% CI 在边界（>90% 或 <10%）会偏差 ≥ 5%。
Wilson 在所有 n 与 p 下都是 well-behaved 的。

参考：Brown, Cai, and DasGupta. "Interval Estimation for a Binomial Proportion."
"""

from __future__ import annotations

import math


def wilson_ci(wins: float, total: int, *, z: float = 1.96) -> tuple[float, float]:
    """计算二项胜率的 Wilson Score Interval。

    参数
    ----
    wins : float
        胜场数（含半场——平局算 0.5）
    total : int
        总场数
    z : float
        分位数。默认 1.96 对应 95% 置信度。

    返回
    ----
    (low, high) : tuple[float, float]
        胜率的 [low, high] 95% CI。
    """
    if total == 0:
        return 0.0, 1.0
    p_hat = wins / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p_hat + z2 / (2 * total)) / denom
    spread = z * math.sqrt(p_hat * (1 - p_hat) / total + z2 / (4 * total * total)) / denom
    return max(0.0, center - spread), min(1.0, center + spread)


def is_significantly_better(
    wins_new: float, total_new: int,
    wins_old: float, total_old: int,
    *,
    z: float = 1.96,
) -> bool:
    """新版本胜率显著高于旧版本（Δ > 0 且 Δ 的 95% CI 下沿 ≥ 0）。

    使用 Wald-style 双比例 Z 检验，对应 master-plan §5.4 的"统计显著提升"规则。
    """
    if total_new == 0 or total_old == 0:
        return False
    p_new = wins_new / total_new
    p_old = wins_old / total_old
    se = math.sqrt(
        p_new * (1 - p_new) / total_new + p_old * (1 - p_old) / total_old
    )
    if se < 1e-12:
        return p_new > p_old
    delta = p_new - p_old
    return (delta - z * se) > 0


def sprt_decision(
    wins: int, losses: int,
    *,
    p_null: float = 0.50,
    p_alt: float = 0.55,
    alpha: float = 0.05,
    beta: float = 0.05,
) -> str:
    """Sequential Probability Ratio Test — 决定是否可以早停。

    给定一段对战的 wins/losses 累积，决定：

    - "accept_alt"：我们显著强（胜率 ≥ p_alt）
    - "accept_null"：我们没有显著优势（胜率 ≤ p_null）
    - "continue"：信息不足，继续打

    参数默认值：检测 50% vs 55% 的差距（即"中等改进"），α=β=0.05。
    """
    if wins + losses == 0:
        return "continue"

    # 对数似然比
    log_lr = (
        wins * math.log(p_alt / p_null)
        + losses * math.log((1 - p_alt) / (1 - p_null))
    )

    log_a = math.log((1 - beta) / alpha)        # 接受 H1 阈值
    log_b = math.log(beta / (1 - alpha))        # 接受 H0 阈值

    if log_lr >= log_a:
        return "accept_alt"
    if log_lr <= log_b:
        return "accept_null"
    return "continue"
