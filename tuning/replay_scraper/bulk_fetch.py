"""
Top-20 历史对局批量下载（官方日包优先，API 回退）。

工作流：
    1. 一次拉排行榜 top-N（按公开 ELO 分的 submission，不是按人名）
    2. 每个 submission 调 list_submission_episodes（约 20 次 API，带 create_time）
    3. 按 create_time 的 UTC 日期定位官方日包，直下 {episode_id}.json（不扫描全日包文件列表）
    4. 官方失败则回退 Episodes API
    5. manifest 断点续传 + 总进度条

用法示例：
    python -m tuning.replay_scraper.bulk_fetch \
        --output-dir "/Volumes/for mac/Data/Orbit Wars/replays/raw" \
        --manifest "/Volumes/for mac/Data/Orbit Wars/replays/manifest.csv" \
        --top-n 20 --max-per-team 75 --max-total 1000
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from . import kaggle_api
from .consistency_check import _build_kaggle_api, download_official_episode


@dataclass(frozen=True)
class PlannedEpisode:
    """待下载的一局元信息（规划阶段生成，含官方日包日期）。"""

    episode_id: int
    submission_id: int
    team_name: str
    create_time: str
    utc_day: str
    players_count: int
    is_winner: bool
    updated_score: float


@dataclass
class BulkFetchConfig:
    top_n: int = 20
    max_per_team: int = 75
    max_total: int = 1000
    output_dir: Path = Path("data/replays/raw")
    manifest_path: Path = Path("data/replays/manifest.csv")
    queue_path: Path = Path("data/replays/fetch_queue.csv")
    quota_gb: float = 4.0
    prefer_official: bool = True
    # 这些 UTC 日期不走官方日包（例如 2026-06-03 尚未发布官方索引时直接 API）
    api_only_days: frozenset[str] = frozenset({"2026-06-03"})


@dataclass
class BulkFetchResult:
    planned: int
    episodes_fetched: int
    episodes_skipped: int
    episodes_failed: int
    bytes_downloaded: int
    official_count: int
    api_count: int
    duration_s: float
    quota_hit: bool


def load_already_fetched(manifest_path: Path) -> set[int]:
    """从 manifest 读取已完成的 episode_id（断点续传）。"""
    if not manifest_path.exists():
        return set()
    fetched: set[int] = set()
    with manifest_path.open("r", encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            raw_id = row.get("episode_id")
            if raw_id:
                try:
                    fetched.add(int(raw_id))
                except ValueError:
                    continue
    return fetched


def append_manifest_row(
    manifest_path: Path,
    episode: PlannedEpisode,
    bytes_size: int,
    fetch_source: str,
) -> None:
    """追加 manifest 行（含 fetch_source：official / api）。"""
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
        "fetch_source",
        "utc_day",
    ]
    write_header = (not manifest_path.exists()) or manifest_path.stat().st_size == 0
    with manifest_path.open("a", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "episode_id": episode.episode_id,
                "submission_id": episode.submission_id,
                "team_name": episode.team_name,
                "players_count": episode.players_count,
                "is_winner": episode.is_winner,
                "updated_score": episode.updated_score,
                "create_time": episode.create_time,
                "bytes_size": bytes_size,
                "fetch_source": fetch_source,
                "utc_day": episode.utc_day,
            }
        )


def load_fetch_queue(queue_path: Path) -> list[PlannedEpisode]:
    """从 fetch_queue.csv 读取规划（续传时跳过 API 重扫）。"""
    if not queue_path.exists():
        return []
    plans: list[PlannedEpisode] = []
    with queue_path.open("r", encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            raw_id = row.get("episode_id")
            if not raw_id:
                continue
            plans.append(
                PlannedEpisode(
                    episode_id=int(raw_id),
                    submission_id=int(row.get("submission_id") or 0),
                    team_name=str(row.get("team_name") or ""),
                    create_time=str(row.get("create_time") or ""),
                    utc_day=str(row.get("utc_day") or ""),
                    players_count=int(row.get("players_count") or 0),
                    is_winner=str(row.get("is_winner", "")).lower() in ("true", "1", "yes"),
                    updated_score=float(row.get("updated_score") or 0.0),
                )
            )
    plans.sort(key=lambda item: item.create_time, reverse=True)
    return plans


def save_fetch_queue(queue_path: Path, plans: list[PlannedEpisode]) -> None:
    """把规划结果落盘，便于核对日期分布（非断点必需）。"""
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "episode_id",
                "submission_id",
                "team_name",
                "create_time",
                "utc_day",
                "players_count",
                "is_winner",
                "updated_score",
            ],
        )
        writer.writeheader()
        for item in plans:
            writer.writerow(
                {
                    "episode_id": item.episode_id,
                    "submission_id": item.submission_id,
                    "team_name": item.team_name,
                    "create_time": item.create_time,
                    "utc_day": item.utc_day,
                    "players_count": item.players_count,
                    "is_winner": item.is_winner,
                    "updated_score": item.updated_score,
                }
            )


def build_download_plan(config: BulkFetchConfig) -> list[PlannedEpisode]:
    """
    规划待下载列表（API 扫描仅发生在这里）：
    - 排行榜 1 次
    - 每个 top submission 列 episodes 1 次
    - 按 episode_id 去重
    """
    auth = kaggle_api.KaggleAuth.from_default_path()
    leaders = kaggle_api.get_top_n_submissions(n=config.top_n, auth=auth)

    seen: set[int] = set()
    plans: list[PlannedEpisode] = []

    for entry in leaders:
        episodes = kaggle_api.list_episodes_for_submission(
            submission_id=entry.submission_id,
            auth=auth,
            max_count=config.max_per_team,
        )
        for ep in episodes:
            if ep.episode_id in seen:
                continue
            seen.add(ep.episode_id)
            utc_day = ep.create_time[:10] if ep.create_time else ""
            plans.append(
                PlannedEpisode(
                    episode_id=ep.episode_id,
                    submission_id=ep.submission_id,
                    team_name=entry.team_name,
                    create_time=ep.create_time,
                    utc_day=utc_day,
                    players_count=ep.players_count,
                    is_winner=ep.is_winner,
                    updated_score=ep.updated_score,
                )
            )

    # 新的在前，便于优先抓近期对局。
    plans.sort(key=lambda item: item.create_time, reverse=True)
    return plans[: config.max_total]


def _fetch_via_api(episode_id: int, auth: kaggle_api.KaggleAuth, output_path: Path) -> int:
    """通过 Episodes API 拉取并写入 output_path。"""
    replay = kaggle_api.get_episode_replay(episode_id=episode_id, auth=auth)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(replay, ensure_ascii=False), encoding="utf-8")
    return output_path.stat().st_size


def _fetch_via_official(
    api,
    episode: PlannedEpisode,
    output_path: Path,
) -> int:
    """从官方日包按 episode_id 直下（无需 list 全日包）。"""
    if not episode.utc_day:
        raise ValueError("missing utc_day")
    official_slug = f"kaggle/orbit-wars-episodes-{episode.utc_day}"
    download_official_episode(
        api=api,
        episode_id=episode.episode_id,
        official_slug=official_slug,
        output_path=output_path,
    )
    return output_path.stat().st_size


def run_bulk_fetch(
    config: BulkFetchConfig,
    *,
    plan_from: Path | None = None,
    plan_only: bool = False,
) -> BulkFetchResult:
    """执行批量下载主流程。"""
    started = time.perf_counter()
    auth = kaggle_api.KaggleAuth.from_default_path()
    kaggle_cli = _build_kaggle_api()

    if plan_from is not None and plan_from.exists():
        plans = load_fetch_queue(plan_from)
    else:
        plans = build_download_plan(config)
        save_fetch_queue(config.queue_path, plans)

    if plan_only:
        return BulkFetchResult(
            planned=len(plans),
            episodes_fetched=0,
            episodes_skipped=0,
            episodes_failed=0,
            bytes_downloaded=0,
            official_count=0,
            api_count=0,
            duration_s=time.perf_counter() - started,
            quota_hit=False,
        )

    already = load_already_fetched(config.manifest_path)
    quota_dir = config.manifest_path.parent / "quota"
    failed_path = config.manifest_path.parent / "failed_ids.txt"

    episodes_fetched = 0
    episodes_skipped = 0
    episodes_failed = 0
    bytes_downloaded = 0
    official_count = 0
    api_count = 0
    quota_hit = False

    pending = [p for p in plans if p.episode_id not in already]
    episodes_skipped += len(plans) - len(pending)

    progress = tqdm(pending, desc="download", unit="ep")
    for episode in progress:
        used_gb = kaggle_api.estimate_quota_used_today(quota_dir)
        if used_gb >= config.quota_gb:
            progress.write(
                f"[bulk_fetch] 已达本地 API 流量上限 {config.quota_gb:.2f} GB "
                f"(已记 {used_gb:.2f} GB)，正常停止；请次日或改用官方日包续传。"
            )
            quota_hit = True
            break

        output_path = config.output_dir / f"{episode.episode_id}.json"
        if output_path.exists():
            already.add(episode.episode_id)
            episodes_skipped += 1
            continue

        bytes_size: int | None = None
        fetch_source = ""
        last_error: Exception | None = None

        # 指定日期（默认含 2026-06-03）跳过官方日包，避免无效 list/404 重试，直接 API。
        use_official = (
            config.prefer_official
            and episode.utc_day
            and episode.utc_day not in config.api_only_days
        )
        if use_official:
            for attempt in range(3):
                try:
                    bytes_size = _fetch_via_official(kaggle_cli, episode, output_path)
                    fetch_source = "official"
                    official_count += 1
                    break
                except Exception:
                    time.sleep(kaggle_api.BACKOFF_BASE_S * (2**attempt))

        if bytes_size is None:
            for attempt in range(3):
                try:
                    bytes_size = _fetch_via_api(episode.episode_id, auth, output_path)
                    fetch_source = "api"
                    api_count += 1
                    break
                except Exception as exc:
                    last_error = exc
                    time.sleep(kaggle_api.BACKOFF_BASE_S * (2**attempt))

        if bytes_size is None:
            episodes_failed += 1
            if last_error is not None:
                progress.write(
                    f"[bulk_fetch] failed episode {episode.episode_id}: "
                    f"{type(last_error).__name__}: {last_error}"
                )
            failed_path.parent.mkdir(parents=True, exist_ok=True)
            with failed_path.open("a", encoding="utf-8") as fp:
                fp.write(f"{episode.episode_id}\n")
            continue

        kaggle_api.record_quota(quota_dir=quota_dir, bytes_downloaded=bytes_size)
        append_manifest_row(config.manifest_path, episode, bytes_size, fetch_source)
        already.add(episode.episode_id)
        episodes_fetched += 1
        bytes_downloaded += bytes_size

    return BulkFetchResult(
        planned=len(plans),
        episodes_fetched=episodes_fetched,
        episodes_skipped=episodes_skipped,
        episodes_failed=episodes_failed,
        bytes_downloaded=bytes_downloaded,
        official_count=official_count,
        api_count=api_count,
        duration_s=time.perf_counter() - started,
        quota_hit=quota_hit,
    )


def cli() -> int:
    parser = argparse.ArgumentParser(description="Orbit Wars 批量 replay 下载（官方优先）")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--max-per-team", type=int, default=75)
    parser.add_argument("--max-total", type=int, default=1000)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Volumes/for mac/Data/Orbit Wars/replays/raw"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("/Volumes/for mac/Data/Orbit Wars/replays/manifest.csv"),
    )
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path("/Volumes/for mac/Data/Orbit Wars/replays/fetch_queue.csv"),
    )
    parser.add_argument("--quota-gb", type=float, default=4.0)
    parser.add_argument("--no-official", action="store_true", help="全部局仅用 API，不走官方日包")
    parser.add_argument(
        "--api-only-days",
        type=str,
        default="2026-06-03",
        help="逗号分隔 UTC 日期：这些日期的局跳过官方日包，直接 API（默认 2026-06-03）",
    )
    parser.add_argument(
        "--plan-from",
        type=Path,
        default=None,
        help="从已有 fetch_queue.csv 加载规划，不调用排行榜/list API",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="仅生成/保存 fetch_queue，不下载",
    )
    args = parser.parse_args()

    api_only = frozenset(
        day.strip() for day in args.api_only_days.split(",") if day.strip()
    )

    config = BulkFetchConfig(
        top_n=args.top_n,
        max_per_team=args.max_per_team,
        max_total=args.max_total,
        output_dir=args.output_dir,
        manifest_path=args.manifest,
        queue_path=args.queue,
        quota_gb=args.quota_gb,
        prefer_official=not args.no_official,
        api_only_days=api_only,
    )
    result = run_bulk_fetch(
        config,
        plan_from=args.plan_from,
        plan_only=args.plan_only,
    )
    print(json.dumps(result.__dict__, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
