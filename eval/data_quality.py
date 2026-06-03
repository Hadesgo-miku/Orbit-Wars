"""M16 — 数据质量监控（IL Prior parquet）。"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from tuning.replay_scraper.extract_features import FEATURE_NAMES

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
    # pilot 模式：规模未达标时放宽 episode 数门槛
    pilot: bool = False
    pilot_min_episodes: int = 800

    def effective_min_episodes(self) -> int:
        if self.pilot:
            return self.pilot_min_episodes
        return self.min_episodes


@dataclass
class CheckResult:
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


def _load_df(parquet_path: Path) -> pd.DataFrame:
    return pd.read_parquet(parquet_path)


def check_basic_counts(df: pd.DataFrame, thresholds: DataQualityThresholds) -> list[CheckResult]:
    """Q1 行数、Q2 episode 数、Q3 2P/4P 比例。"""
    n_rows = len(df)
    n_episodes = int(df["episode_id"].nunique()) if "episode_id" in df.columns else 0
    n_2p = int((df["players_count"] == 2).sum()) if "players_count" in df.columns else 0
    n_4p = int((df["players_count"] == 4).sum()) if "players_count" in df.columns else 0
    ratio_2p = n_2p / max(n_rows, 1)
    ratio_4p = n_4p / max(n_rows, 1)

    q1 = CheckResult(
        id="Q1",
        description="行数 ≥ min_rows",
        passed=n_rows >= thresholds.min_rows,
        value=n_rows,
        threshold=f">= {thresholds.min_rows}",
        severity="fatal",
    )
    min_eps = thresholds.effective_min_episodes()
    q2 = CheckResult(
        id="Q2",
        description="唯一 episode_id 数 ≥ min_episodes",
        passed=n_episodes >= min_eps,
        value=n_episodes,
        threshold=f">= {min_eps}" + (" (pilot)" if thresholds.pilot else ""),
        severity="fatal",
    )
    q3 = CheckResult(
        id="Q3",
        description="2P 行比例 ≥ 30% 或 4P 行比例 ≥ 60%",
        passed=(ratio_2p >= thresholds.min_2p_ratio) or (ratio_4p >= thresholds.min_4p_ratio),
        value=f"2p={ratio_2p:.3f}, 4p={ratio_4p:.3f}",
        threshold=f"2p>={thresholds.min_2p_ratio} OR 4p>={thresholds.min_4p_ratio}",
        severity="fatal",
    )
    return [q1, q2, q3]


def check_resolve_rate(df: pd.DataFrame, thresholds: DataQualityThresholds) -> CheckResult:
    """Q4：有出舰样本中 target_id != -1 占比。"""
    if "label_act" in df.columns:
        act_df = df[df["label_act"] == 1]
    else:
        act_df = df[df["source_id"] >= 0]
    if len(act_df) == 0:
        rate = 0.0
    else:
        rate = float((act_df["target_id"] >= 0).mean())
    return CheckResult(
        id="Q4",
        description="inverse target 解析率（出舰样本 target_id≥0）",
        passed=rate >= thresholds.min_resolve_rate,
        value=round(rate, 4),
        threshold=f">= {thresholds.min_resolve_rate}",
        severity="fatal",
    )


def check_feature_schema(df: pd.DataFrame, expected_features: list[str]) -> CheckResult:
    """Q5：列名与 FEATURE_NAMES 严格一致。"""
    missing = [c for c in expected_features if c not in df.columns]
    passed = len(missing) == 0
    return CheckResult(
        id="Q5",
        description="特征 schema 与 FEATURE_NAMES 对齐",
        passed=passed,
        value=f"missing={missing}" if missing else "ok",
        threshold=f"{len(expected_features)} feature cols",
        severity="fatal",
    )


def check_no_nan_inf(df: pd.DataFrame) -> CheckResult:
    """Q6：特征列无 NaN/Inf。"""
    import numpy as np

    cols = [c for c in FEATURE_NAMES if c in df.columns]
    arr = df[cols].to_numpy(dtype=float)
    nan_count = int(np.isnan(arr).sum())
    inf_count = int(np.isinf(arr).sum())
    passed = nan_count == 0 and inf_count == 0
    return CheckResult(
        id="Q6",
        description="特征列无 NaN/Inf",
        passed=passed,
        value=f"nan={nan_count}, inf={inf_count}",
        threshold="0",
        severity="fatal",
    )


def check_label_balance(df: pd.DataFrame, thresholds: DataQualityThresholds) -> CheckResult:
    """
    Q7：idle drop 后应以出舰样本为主，同时保留少量 idle 负样本。

    95% 丢弃被动回合后，act 行占比通常 > 50%；若几乎无 idle 保留则失败。
    """
    if "label_act" not in df.columns:
        return CheckResult(
            id="Q7",
            description="label_act 分布",
            passed=False,
            value="missing label_act",
            threshold="act_ratio in [0.50, 0.995] and idle_ratio >= 0.005",
            severity="fatal",
        )
    act_ratio = float((df["label_act"] == 1).mean())
    idle_ratio = 1.0 - act_ratio
    passed = 0.50 <= act_ratio <= 0.995 and idle_ratio >= 0.005
    return CheckResult(
        id="Q7",
        description="label_act=1 行占比合理（idle drop 后）",
        passed=passed,
        value=f"act={act_ratio:.4f}, idle={idle_ratio:.4f}",
        threshold="act in [0.50,0.995], idle >= 0.005",
        severity="fatal",
    )


def check_expert_diversity(df: pd.DataFrame, thresholds: DataQualityThresholds) -> CheckResult:
    """W1：单 expert 占比（需 team_name 列，无则跳过为 info）。"""
    if "team_name" not in df.columns:
        return CheckResult(
            id="W1",
            description="expert 多样性（无 team_name 列，跳过）",
            passed=True,
            value="n/a",
            threshold=f"top1 <= {thresholds.expert_dominance_threshold}",
            severity="warning",
        )
    top_share = float(df["team_name"].value_counts(normalize=True).iloc[0])
    return CheckResult(
        id="W1",
        description="top-1 expert 行占比",
        passed=top_share <= thresholds.expert_dominance_threshold,
        value=round(top_share, 4),
        threshold=f"<= {thresholds.expert_dominance_threshold}",
        severity="warning",
    )


def check_tick_distribution(df: pd.DataFrame) -> CheckResult:
    """W2：opening/mid/late tick 分布记录。"""
    if "tick" not in df.columns:
        return CheckResult(
            id="W2",
            description="tick 分布",
            passed=True,
            value="n/a",
            threshold="info only",
            severity="warning",
        )
    opening = float((df["tick"] < 30).mean())
    mid = float(((df["tick"] >= 30) & (df["tick"] < 200)).mean())
    late = float((df["tick"] >= 200).mean())
    # 仅 warning：opening 过少
    passed = opening >= 0.03
    return CheckResult(
        id="W2",
        description="tick 分布（opening/mid/late）",
        passed=passed,
        value=f"open={opening:.2f}, mid={mid:.2f}, late={late:.2f}",
        threshold="opening >= 3%",
        severity="warning",
    )


def check_winner_bias(df: pd.DataFrame, thresholds: DataQualityThresholds) -> CheckResult:
    """W3：winner_id == player_id 比例。"""
    if "winner_id" not in df.columns or "player_id" not in df.columns:
        return CheckResult(
            id="W3",
            description="winner 偏倚",
            passed=True,
            value="n/a",
            threshold=f"<= {thresholds.winner_bias_threshold}",
            severity="warning",
        )
    rate = float((df["winner_id"] == df["player_id"]).mean())
    return CheckResult(
        id="W3",
        description="样本行 player 即胜者比例",
        passed=rate <= thresholds.winner_bias_threshold,
        value=round(rate, 4),
        threshold=f"<= {thresholds.winner_bias_threshold}",
        severity="warning",
    )


def run_quality_check(
    parquet_path: Path,
    thresholds: DataQualityThresholds | None = None,
    expected_features: list[str] | None = None,
) -> QualityReport:
    """对 parquet 跑完整质量检查。"""
    thresholds = thresholds or DataQualityThresholds()
    expected_features = expected_features or FEATURE_NAMES

    df = _load_df(parquet_path)
    report = QualityReport(
        parquet_path=parquet_path,
        n_rows=len(df),
        n_episodes=int(df["episode_id"].nunique()) if "episode_id" in df.columns else 0,
        n_players_2p=int((df["players_count"] == 2).sum()) if "players_count" in df.columns else 0,
        n_players_4p=int((df["players_count"] == 4).sum()) if "players_count" in df.columns else 0,
    )

    checks: list[CheckResult] = []
    checks.extend(check_basic_counts(df, thresholds))
    checks.append(check_resolve_rate(df, thresholds))
    checks.append(check_feature_schema(df, expected_features))
    checks.append(check_no_nan_inf(df))
    checks.append(check_label_balance(df, thresholds))
    checks.append(check_expert_diversity(df, thresholds))
    checks.append(check_tick_distribution(df))
    checks.append(check_winner_bias(df, thresholds))

    report.checks = checks
    report.fatal_failed = sum(1 for c in checks if c.severity == "fatal" and not c.passed)
    report.warnings = sum(1 for c in checks if c.severity == "warning" and not c.passed)
    report.passed_overall = report.fatal_failed == 0
    return report


def render_markdown_report(report: QualityReport, output_path: Path) -> None:
    """渲染 markdown 报告。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Data Quality Report",
        "",
        f"- 时间：{now}",
        f"- Parquet：`{report.parquet_path}`",
        f"- 总行数：{report.n_rows}",
        f"- 总 episode 数：{report.n_episodes}",
        f"- 2P 行数：{report.n_players_2p}",
        f"- 4P 行数：{report.n_players_4p}",
        "",
        "## 必查项",
        "",
    ]
    for c in report.checks:
        if c.severity != "fatal":
            continue
        mark = "✅" if c.passed else "❌"
        lines.append(f"- {mark} **{c.id}** {c.description}: `{c.value}` (阈值 {c.threshold})")
    lines.extend(["", "## 警告项", ""])
    for c in report.checks:
        if c.severity != "warning":
            continue
        mark = "✅" if c.passed else "⚠️"
        lines.append(f"- {mark} **{c.id}** {c.description}: `{c.value}` (阈值 {c.threshold})")
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "✅ **通过**（可进入 M15 训练）"
            if report.passed_overall
            else f"❌ **未通过**（fatal 失败 {report.fatal_failed} 项）",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def cli() -> int:
    parser = argparse.ArgumentParser(description="Data Quality Checker for IL Prior dataset")
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("eval/results/data_quality_v1.md"))
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="pilot 数据集：放宽 Q2 episode 数门槛（≥800）",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="warning 也视为失败",
    )
    args = parser.parse_args()

    thresholds = DataQualityThresholds(pilot=args.pilot or "pilot" in args.parquet.stem)
    report = run_quality_check(args.parquet, thresholds=thresholds)
    render_markdown_report(report, args.output)
    summary = {
        "passed_overall": report.passed_overall,
        "n_rows": report.n_rows,
        "n_episodes": report.n_episodes,
        "fatal_failed": report.fatal_failed,
        "warnings": report.warnings,
    }
    print(json.dumps(summary, indent=2))
    ok = report.passed_overall and (not args.fail_on_warning or report.warnings == 0)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(cli())
