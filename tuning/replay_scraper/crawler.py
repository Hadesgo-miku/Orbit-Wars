"""
Top-N → Submissions → Episodes → Replay 的调度器（M14 子模块）

工作流：
    1. 调用 kaggle_api.get_top_n_submissions(20) 拿当前 LB top-20
    2. 对每个 submission，调 list_episodes_for_submission，取最近 max_per_team 局
    3. 对每个 episode_id，调 get_episode_replay 拉 JSON
    4. 写到 data/replays/raw/{episode_id}.json
    5. 同步追加 manifest.csv（episode_id, submission_id, team_name, players_count, ...）
    6. 每次调用前检查今日 quota，超过 4GB 立即停止

CLI 用法（D4 一开工就跑）：
    python -m tuning.replay_scraper.crawler --top-n 20 --max-per-team 75 \
        --output-dir data/replays/raw --manifest data/replays/manifest.csv \
        --quota-gb 4.0

注意：
    - 失败重试 ≤ 3 次，超过则写到 failed_ids.txt
    - 中断点恢复：每次启动前先读 manifest.csv，已抓的 episode_id 跳过
    - 抓取期间必须打 tqdm 进度条
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from . import kaggle_api


@dataclass
class CrawlConfig:
    """爬取任务配置"""
    top_n: int = 20
    max_per_team: int = 75
    output_dir: Path = Path("data/replays/raw")
    manifest_path: Path = Path("data/replays/manifest.csv")
    quota_gb: float = 4.0
    competition_id: int = kaggle_api.COMPETITION_ID_ORBIT_WARS


@dataclass
class CrawlResult:
    """单次爬取任务的汇总结果"""
    episodes_fetched: int
    episodes_failed: int
    bytes_downloaded: int
    duration_s: float
    quota_hit: bool


def load_already_fetched(manifest_path: Path) -> set[int]:
    """
    读取 manifest.csv，返回已经抓取过的 episode_id 集合。

    如果 manifest 不存在，返回空集合（首次启动）。
    """
    if not manifest_path.exists():
        return set()

    fetched: set[int] = set()
    with manifest_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            raw_episode_id = row.get("episode_id")
            if not raw_episode_id:
                continue
            try:
                fetched.add(int(raw_episode_id))
            except ValueError:
                # 历史脏行不应阻断主流程，直接跳过继续读取后续记录。
                continue
    return fetched


def append_manifest_row(
    manifest_path: Path,
    episode_id: int,
    submission_id: int,
    team_name: str,
    players_count: int,
    is_winner: bool,
    updated_score: float,
    create_time: str,
    bytes_size: int,
) -> None:
    """追加一行到 manifest.csv（不存在时先写 header）"""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "episode_id",
        "submission_id",
        "team_name",
        "players_count",
        "is_winner",
        "updated_score",
        "create_time",
        "bytes_size",
    ]
    should_write_header = (not manifest_path.exists()) or manifest_path.stat().st_size == 0
    with manifest_path.open("a", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        if should_write_header:
            writer.writeheader()
        writer.writerow(
            {
                "episode_id": episode_id,
                "submission_id": submission_id,
                "team_name": team_name,
                "players_count": players_count,
                "is_winner": is_winner,
                "updated_score": updated_score,
                "create_time": create_time,
                "bytes_size": bytes_size,
            }
        )


def crawl_one_episode(
    episode_id: int,
    auth: kaggle_api.KaggleAuth,
    output_dir: Path,
) -> Optional[int]:
    """
    抓取并落地单个 episode 的 replay JSON。

    返回：
        成功 → 写入文件的字节数
        失败 → None
    """
    try:
        replay = kaggle_api.get_episode_replay(episode_id=episode_id, auth=auth)
    except Exception:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{episode_id}.json"
    payload = json.dumps(replay, ensure_ascii=False)
    output_path.write_text(payload, encoding="utf-8")
    return output_path.stat().st_size


def run_crawl(config: CrawlConfig) -> CrawlResult:
    """
    主调度入口。按 top-N → submissions → episodes 顺序抓取。

    流程：
        1. 检查 ~/.kaggle/kaggle.json，加载鉴权
        2. 取 top_n submissions
        3. 读 manifest.csv 拿到 already_fetched
        4. 对每个 submission：
           a. list_episodes（max_per_team 个）
           b. 跳过 already_fetched 中的
           c. 检查今日 quota
           d. 抓 replay，写文件 + manifest
           e. 失败累计 3 次跳过
        5. 累计统计返回 CrawlResult
    """
    started_at = time.perf_counter()
    auth = kaggle_api.KaggleAuth.from_default_path()
    top_entries = kaggle_api.get_top_n_submissions(
        n=config.top_n,
        auth=auth,
        competition_id=config.competition_id,
    )

    already_fetched = load_already_fetched(config.manifest_path)
    failed_ids_path = config.manifest_path.parent / "failed_ids.txt"
    quota_dir = config.output_dir.parent / "quota"

    episodes_fetched = 0
    episodes_failed = 0
    bytes_downloaded = 0
    quota_hit = False

    for entry in tqdm(top_entries, desc="teams", unit="team"):
        episodes = kaggle_api.list_episodes_for_submission(
            submission_id=entry.submission_id,
            auth=auth,
            max_count=config.max_per_team,
        )
        for episode in tqdm(
            episodes,
            desc=f"episodes(team={entry.team_name})",
            unit="ep",
            leave=False,
        ):
            if episode.episode_id in already_fetched:
                # 中断恢复关键逻辑：manifest 里已经存在的 episode 直接跳过。
                continue

            used_gb = kaggle_api.estimate_quota_used_today(quota_dir)
            if used_gb >= config.quota_gb:
                quota_hit = True
                break

            bytes_size: Optional[int] = None
            # 单 episode 抓取失败最多重试 3 次，避免偶发网络波动拖垮全批次。
            for attempt in range(3):
                bytes_size = crawl_one_episode(
                    episode_id=episode.episode_id,
                    auth=auth,
                    output_dir=config.output_dir,
                )
                if bytes_size is not None:
                    break
                time.sleep(kaggle_api.BACKOFF_BASE_S * (2 ** attempt))

            if bytes_size is None:
                episodes_failed += 1
                failed_ids_path.parent.mkdir(parents=True, exist_ok=True)
                with failed_ids_path.open("a", encoding="utf-8") as fp:
                    fp.write(f"{episode.episode_id}\n")
                continue

            kaggle_api.record_quota(quota_dir=quota_dir, bytes_downloaded=bytes_size)
            append_manifest_row(
                manifest_path=config.manifest_path,
                episode_id=episode.episode_id,
                submission_id=episode.submission_id,
                team_name=entry.team_name,
                players_count=episode.players_count,
                is_winner=episode.is_winner,
                updated_score=episode.updated_score,
                create_time=episode.create_time,
                bytes_size=bytes_size,
            )
            already_fetched.add(episode.episode_id)
            episodes_fetched += 1
            bytes_downloaded += bytes_size

        if quota_hit:
            break

    duration_s = time.perf_counter() - started_at
    return CrawlResult(
        episodes_fetched=episodes_fetched,
        episodes_failed=episodes_failed,
        bytes_downloaded=bytes_downloaded,
        duration_s=duration_s,
        quota_hit=quota_hit,
    )


def cli() -> int:
    parser = argparse.ArgumentParser(description="Orbit Wars Top-N Replay Crawler")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--max-per-team", type=int, default=75)
    parser.add_argument("--output-dir", type=Path, default=Path("data/replays/raw"))
    parser.add_argument("--manifest", type=Path, default=Path("data/replays/manifest.csv"))
    parser.add_argument("--quota-gb", type=float, default=4.0)
    args = parser.parse_args()

    config = CrawlConfig(
        top_n=args.top_n,
        max_per_team=args.max_per_team,
        output_dir=args.output_dir,
        manifest_path=args.manifest,
        quota_gb=args.quota_gb,
    )
    result = run_crawl(config)
    print(json.dumps(result.__dict__, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
