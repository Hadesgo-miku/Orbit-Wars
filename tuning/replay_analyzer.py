"""Replay Analyst 工具集。

三类功能：

1. **下载**：从 Kaggle Episodes API 拉 replay JSON 到 ``data/replays/``
2. **解析**：JSON → flat 表（episodes/actions/planet_state 等），或直接走社区
   Parquet 数据集（``replay-dataset-parquet-3000-games-ready-to-analyze``）
3. **诊断**：对单次提交的败局做"为什么输"归因，按 master-plan §5.5 模板输出
"""

from __future__ import annotations

import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# 下载
# ---------------------------------------------------------------------------


def download_episodes(
    submission_id: int,
    output_dir: Path,
    *,
    losses_only: bool = False,
    limit: int | None = None,
) -> int:
    """从 Kaggle 拉某 submission 的 replay JSON。

    使用 ``kaggle competitions episodes`` + ``kaggle competitions replay``。

    返回成功下载的 episode 数。
    """
    raise NotImplementedError("Replay Analyst 实现。")


# ---------------------------------------------------------------------------
# 解析（JSON → 结构化）
# ---------------------------------------------------------------------------


def parse_replay(replay_json_path: Path) -> dict:
    """把单局 replay JSON 解析为结构化 dict。

    Schema 参考 ``community-discussions/replay-dataset-parquet-3000-games-ready-to-analyze.md``
    中暴露的 6 张表的 column 设计。
    """
    raise NotImplementedError("Replay Analyst 实现。")


# ---------------------------------------------------------------------------
# Mission 分类
# ---------------------------------------------------------------------------


def classify_action(
    state_before: dict, action: list, state_after: dict
) -> str:
    """给单个 action 打 mission 标签。

    类别（来自 ``replay-dataset-parquet-3000-games-ready-to-analyze`` 评论区）：

    - ``EXPAND``：占中立
    - ``SNIPE``：占敌方（低守）
    - ``RESCUE``：增援被攻击的我方
    - ``REINFORCE``：例行增援未受威胁的我方
    - ``WASTE``：明显失败的发射（被截胡/撞太阳/到达时已变天）
    """
    raise NotImplementedError("Replay Analyst 实现。")


# ---------------------------------------------------------------------------
# 诊断（败局事后归因）
# ---------------------------------------------------------------------------


def diagnose_submission(
    submission_id: int,
    *,
    replay_dir: Path,
    output_path: Path,
) -> None:
    """对一次 submission 的所有败局做归因，输出 markdown 报告。

    必含（master-plan §5.5）：

    - Top 5 输给的对手 ID
    - 每个对手的 mission classification 分布
    - 输局 archetype 分布
    - 输局 phase 分布
    - 1 条具体可执行的下版本改进建议
    """
    raise NotImplementedError("Replay Analyst 实现。")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay 分析工具集")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dl = sub.add_parser("download", help="拉 replay")
    p_dl.add_argument("--submission_id", type=int, required=True)
    p_dl.add_argument("--output_dir", default="data/replays/")
    p_dl.add_argument("--losses-only", action="store_true")

    p_diag = sub.add_parser("diagnose", help="诊断")
    p_diag.add_argument("--submission_id", type=int, required=True)
    p_diag.add_argument("--replays", default="data/replays/")
    p_diag.add_argument("--output", required=True)

    return parser.parse_args()


def main() -> None:
    raise NotImplementedError("Replay Analyst 实现。")


if __name__ == "__main__":
    main()
