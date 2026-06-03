"""Markdown 评测报告生成器。

输入：``TournamentResult`` + 上一版的 ``TournamentResult``（用于 Δ 对比）。
输出：``eval/results/v{N}.md`` 与 ``eval/results/v{N}.json``。

格式严格遵循 master-plan.md §5.3，便于后续 sub-agent 解析。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tournament import TournamentResult


def render_markdown(
    result: "TournamentResult",
    prev_result: "TournamentResult | None" = None,
    *,
    version: str,
    timestamp: str,
) -> str:
    """生成 master-plan §5.3 标准格式的 markdown 报告。

    分三部分：

    1. 整体战绩表（对每个对手胜率 + 95% CI + vs 上版 Δ）
    2. 按 archetype 分层（默认 vs 最强对手 public_heuristic_1110）
    3. 结论 checklist + 下一步建议
    """
    raise NotImplementedError("Eval Lead 实现；参考 master-plan §5.3 模板。")


def dump_json(result: "TournamentResult", output: Path) -> None:
    """把结果落 JSON（用于后续工具解析）。"""
    raise NotImplementedError("Eval Lead 实现。")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 markdown 评测报告")
    parser.add_argument("--raw", required=True, help="run_tournament 输出的 raw json")
    parser.add_argument("--version", required=True, help="版本号，如 v1")
    parser.add_argument("--prev", help="上一版 raw json，用于 Δ 对比")
    parser.add_argument("--output", help="输出 .md 路径，默认 eval/results/{version}.md")
    return parser.parse_args()


def main() -> None:
    raise NotImplementedError("Eval Lead 实现。")


if __name__ == "__main__":
    main()
