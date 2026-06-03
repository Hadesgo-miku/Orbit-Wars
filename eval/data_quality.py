"""M16 — 数据质量监控。

对 M14 产出的 ``data/replays/processed/v{N}.parquet`` 做完整性检查，输出
markdown 报告到 ``eval/results/data_quality_v{N}.md``。

不通过的数据集**禁止**进入 M15 训练（master-plan §2.3 禁忌）。

检查项（必查 → 警告 → 信息）：

必查（任一失败即拒绝该数据集）：
    Q1. 行数 ≥ 5000（保证起码的样本量）
    Q2. 唯一 episode_id 数 ≥ 1500
    Q3. 2P 行数比例 ≥ 30% 或 4P 比例 ≥ 60%（任一满足）
    Q4. inverse target 解析率 ≥ 85%（target_id != -1 占有 action 样本比例）
    Q5. feature schema 与 src/policy/il_prior.FEATURE_NAMES 严格对齐
    Q6. 无 NaN / Inf
    Q7. label 分布合理：act/idle ≈ 5:95 → 10:90（idle drop 后）

警告（仅 warning，但记入报告）：
    W1. expert 多样性：top-1 expert 占比 > 40% 视为单 expert 过拟合风险
    W2. tick 分布：opening (tick < 30) / mid / late 比例失衡
    W3. winner_id 偏倚：winner ≈ player_id 的比例 > 60% 视为采样偏倚

信息（仅记录）：
    I1. 总 episodes / per-expert / per-day 分布
    I2. ships_frac 分布
    I3. 每个 player_id 的样本数
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# 必查 / 警告项的阈值
# ---------------------------------------------------------------------------


@dataclass
class DataQualityThresholds:
    min_rows: int = 5000
    min_episodes: int = 1500
    min_2p_ratio: float = 0.30
    min_4p_ratio: float = 0.60
    min_resolve_rate: float = 0.85
    expert_dominance_threshold: float = 0.40
    winner_bias_threshold: float = 0.60


# ---------------------------------------------------------------------------
# 检查项结果
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """单个检查项的结果"""
    id: str
    description: str
    passed: bool
    value: float | int | str
    threshold: str
    severity: str  # "fatal" / "warning" / "info"


@dataclass
class QualityReport:
    parquet_path: Path
    n_rows: int = 0
    n_episodes: int = 0
    n_players_2p: int = 0
    n_players_4p: int = 0
    checks: list[CheckResult] = field(default_factory=list)
    fatal_failed: int = 0
    warnings: int = 0
    passed_overall: bool = False


# ---------------------------------------------------------------------------
# 检查函数
# ---------------------------------------------------------------------------


def check_basic_counts(df: Any, thresholds: DataQualityThresholds) -> list[CheckResult]:
    """Q1, Q2, Q3 三项基础计数。"""
    raise NotImplementedError(
        "M16/T0.8 待实现：基础行数 / episode 数 / 2P-4P 比例"
    )


def check_resolve_rate(df: Any, thresholds: DataQualityThresholds) -> CheckResult:
    """Q4 inverse target 解析率检查。"""
    raise NotImplementedError(
        "M16/T0.8 待实现：解析率（target_id != -1 占有 action 样本比例）"
    )


def check_feature_schema(df: Any, expected_features: list[str]) -> CheckResult:
    """Q5 schema 对齐检查。"""
    raise NotImplementedError(
        "M16/T0.8 待实现：检查 df 列与 src/policy/il_prior.FEATURE_NAMES 对齐"
    )


def check_no_nan_inf(df: Any) -> CheckResult:
    """Q6 NaN / Inf 检查。"""
    raise NotImplementedError(
        "M16/T0.8 待实现：扫 NaN / Inf"
    )


def check_label_balance(df: Any, thresholds: DataQualityThresholds) -> CheckResult:
    """Q7 act / idle 比例检查。"""
    raise NotImplementedError(
        "M16/T0.8 待实现：act vs idle 比例"
    )


def check_expert_diversity(df: Any, thresholds: DataQualityThresholds) -> CheckResult:
    """W1 expert 多样性。"""
    raise NotImplementedError(
        "M16/T0.8 待实现：top-1 expert 占比"
    )


def check_tick_distribution(df: Any) -> CheckResult:
    """W2 tick 分布。"""
    raise NotImplementedError(
        "M16/T0.8 待实现：opening / mid / late 比例"
    )


def check_winner_bias(df: Any, thresholds: DataQualityThresholds) -> CheckResult:
    """W3 winner ≈ player_id 比例。"""
    raise NotImplementedError(
        "M16/T0.8 待实现：winner_id 偏倚"
    )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def run_quality_check(
    parquet_path: Path,
    thresholds: DataQualityThresholds | None = None,
    expected_features: list[str] | None = None,
) -> QualityReport:
    """对单个 parquet 跑完整质量检查，返回汇总报告。

    用法：

    .. code-block:: python

        report = run_quality_check(Path("data/replays/processed/v1.parquet"))
        assert report.passed_overall, "Data quality check failed"

    实现要点：
        - 用 pandas 读 parquet（注意大文件用 ``columns=...`` 限制）
        - 依次跑所有 check 函数
        - 任何 fatal failed → passed_overall = False
        - 即使 fatal failed 也跑完所有 check 项（用户需要完整 picture）
    """
    raise NotImplementedError(
        "M16/T0.8 待实现：检查项汇总"
    )


def render_markdown_report(report: QualityReport, output_path: Path) -> None:
    """把 QualityReport 渲染为 markdown 报告写到 output_path。

    报告结构：
        # Data Quality Report data_v{N}
        - 时间 / parquet 路径 / 总行数 / 总 episode 数
        ## ✅/❌ 必查项
        ## ⚠️ 警告项
        ## ℹ️ 信息项
        ## 结论
    """
    raise NotImplementedError(
        "M16/T0.8 待实现：markdown 报告生成"
    )


def cli() -> int:
    parser = argparse.ArgumentParser(description="Data Quality Checker for IL Prior dataset")
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("eval/results/data_quality_v1.md"))
    parser.add_argument("--fail-on-warning", action="store_true",
                        help="启用后 warning 也视为失败（默认仅 fatal 失败）")
    args = parser.parse_args()

    report = run_quality_check(args.parquet)
    render_markdown_report(report, args.output)
    summary = {
        "passed_overall": report.passed_overall,
        "n_rows": report.n_rows,
        "n_episodes": report.n_episodes,
        "fatal_failed": report.fatal_failed,
        "warnings": report.warnings,
    }
    print(json.dumps(summary, indent=2))
    return 0 if (report.passed_overall and (not args.fail_on_warning or report.warnings == 0)) else 1


if __name__ == "__main__":
    raise SystemExit(cli())
