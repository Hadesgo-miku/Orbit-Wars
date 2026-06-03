"""
榜首队伍（LB #1）replay 专用下载：官方日包优先，API 回退。

用途：
    从 ``top1_episodes_since_2026-05-31.csv``（或同类表）读取 episode 列表，
    默认 **排除 2026-06-03**（改走 API 且占 Episodes 日配额），
    对其余日期（如 06-01、06-02）用官方日包 ``orbit-wars-episodes-{date}/{id}.json`` 直下。

目录约定（与 ``raw/`` 并列，不混放）::

    /Volumes/for mac/Data/Orbit Wars/replays/top1_isaiah/
        episodes_to_fetch.csv   # 本次待下清单（已过滤日期）
        manifest.csv            # 断点续传
        failed_ids.txt
        json/{episode_id}.json

用法::

    python -m tuning.replay_scraper.top1_fetch
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
class EpisodeRow:
    """CSV 中的一行 episode 元信息。"""

    episode_id: int
    submission_id: int
    team_name: str
    create_time: str
    utc_day: str
    players_count: int
    is_winner: bool
    updated_score: float


@dataclass
class Top1FetchConfig:
    episodes_csv: Path
    output_dir: Path = Path("/Volumes/for mac/Data/Orbit Wars/replays/top1_isaiah")
    exclude_days: frozenset[str] = frozenset({"2026-06-03"})
    prefer_official: bool = True
    quota_gb: float = 4.0  # 仅 API 回退时累计（官方日包不计入）


@dataclass
class Top1FetchResult:
    planned: int
    fetched: int
    skipped: int
    failed: int
    official_count: int
    api_count: int
    bytes_downloaded: int
    quota_hit: bool
    duration_s: float


def load_episode_rows(csv_path: Path, exclude_days: frozenset[str]) -> list[EpisodeRow]:
    """读取 episode 表，并按 UTC 日期过滤（默认去掉 6 月 3 日）。"""
    rows: list[EpisodeRow] = []
    with csv_path.open("r", encoding="utf-8", newline="") as fp:
        for raw in csv.DictReader(fp):
            utc_day = str(raw.get("utc_day") or raw.get("create_time", "")[:10])
            if utc_day in exclude_days:
                continue
            episode_id = int(raw["episode_id"])
            rows.append(
                EpisodeRow(
                    episode_id=episode_id,
                    submission_id=int(raw.get("submission_id") or 0),
                    team_name=str(raw.get("team_name") or ""),
                    create_time=str(raw.get("create_time") or ""),
                    utc_day=utc_day,
                    players_count=int(raw.get("players_count") or 0),
                    is_winner=str(raw.get("is_winner", "")).lower() in ("true", "1", "yes"),
                    updated_score=float(raw.get("updated_score") or 0.0),
                )
            )
    rows.sort(key=lambda item: item.create_time, reverse=True)
    return rows


def save_episodes_to_fetch(output_dir: Path, rows: list[EpisodeRow]) -> Path:
    """把过滤后的待下载列表写到 output_dir/episodes_to_fetch.csv。"""
    path = output_dir / "episodes_to_fetch.csv"
    output_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "episode_id",
        "submission_id",
        "team_name",
        "create_time",
        "utc_day",
        "players_count",
        "is_winner",
        "updated_score",
    ]
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "episode_id": row.episode_id,
                    "submission_id": row.submission_id,
                    "team_name": row.team_name,
                    "create_time": row.create_time,
                    "utc_day": row.utc_day,
                    "players_count": row.players_count,
                    "is_winner": row.is_winner,
                    "updated_score": row.updated_score,
                }
            )
    return path


def load_manifest_ids(manifest_path: Path) -> set[int]:
    """已写入 manifest 的 episode_id（断点续传）。"""
    if not manifest_path.exists():
        return set()
    done: set[int] = set()
    with manifest_path.open("r", encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            raw_id = row.get("episode_id")
            if raw_id:
                done.add(int(raw_id))
    return done


def append_manifest(
    manifest_path: Path,
    row: EpisodeRow,
    bytes_size: int,
    fetch_source: str,
) -> None:
    """追加一条下载记录。"""
    fieldnames = [
        "episode_id",
        "submission_id",
        "team_name",
        "create_time",
        "utc_day",
        "players_count",
        "is_winner",
        "updated_score",
        "bytes_size",
        "fetch_source",
    ]
    write_header = (not manifest_path.exists()) or manifest_path.stat().st_size == 0
    with manifest_path.open("a", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "episode_id": row.episode_id,
                "submission_id": row.submission_id,
                "team_name": row.team_name,
                "create_time": row.create_time,
                "utc_day": row.utc_day,
                "players_count": row.players_count,
                "is_winner": row.is_winner,
                "updated_score": row.updated_score,
                "bytes_size": bytes_size,
                "fetch_source": fetch_source,
            }
        )


def _fetch_via_api(episode_id: int, auth: kaggle_api.KaggleAuth, output_path: Path) -> int:
    """Episodes API 拉取单局 JSON。"""
    replay = kaggle_api.get_episode_replay(episode_id=episode_id, auth=auth)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(replay, ensure_ascii=False), encoding="utf-8")
    return output_path.stat().st_size


def run_top1_fetch(config: Top1FetchConfig) -> Top1FetchResult:
    """执行榜首队伍 replay 下载（官方日包优先）。"""
    started = time.perf_counter()
    output_dir = config.output_dir
    json_dir = output_dir / "json"
    manifest_path = output_dir / "manifest.csv"
    failed_path = output_dir / "failed_ids.txt"
    quota_dir = output_dir / "quota"

    rows = load_episode_rows(config.episodes_csv, config.exclude_days)
    save_episodes_to_fetch(output_dir, rows)

    auth = kaggle_api.KaggleAuth.from_default_path()
    kaggle_cli = _build_kaggle_api()
    already = load_manifest_ids(manifest_path)

    fetched = 0
    failed = 0
    official_count = 0
    api_count = 0
    bytes_downloaded = 0
    quota_hit = False

    pending = [r for r in rows if r.episode_id not in already]
    skipped = len(rows) - len(pending)

    for row in tqdm(pending, desc="top1_fetch", unit="ep"):
        output_path = json_dir / f"{row.episode_id}.json"
        if output_path.exists():
            already.add(row.episode_id)
            skipped += 1
            continue

        bytes_size: int | None = None
        fetch_source = ""

        # 官方日包：按 utc_day 拼 slug，单文件直下（不占 Episodes API 日配额）
        # 重试已在 download_official_episode 内完成，此处不再套外层重试（避免 3×3 次请求）
        if config.prefer_official and row.utc_day:
            official_slug = f"kaggle/orbit-wars-episodes-{row.utc_day}"
            try:
                download_official_episode(
                    kaggle_cli,
                    episode_id=row.episode_id,
                    official_slug=official_slug,
                    output_path=output_path,
                )
                bytes_size = output_path.stat().st_size
                fetch_source = "official"
                official_count += 1
            except Exception:
                bytes_size = None

        # API 回退（计入 quota_gb）
        if bytes_size is None:
            if kaggle_api.estimate_quota_used_today(quota_dir) >= config.quota_gb:
                quota_hit = True
                break
            for attempt in range(3):
                try:
                    bytes_size = _fetch_via_api(row.episode_id, auth, output_path)
                    fetch_source = "api"
                    api_count += 1
                    kaggle_api.record_quota(quota_dir=quota_dir, bytes_downloaded=bytes_size)
                    break
                except Exception:
                    time.sleep(kaggle_api.BACKOFF_BASE_S * (2**attempt))

        if bytes_size is None:
            failed += 1
            failed_path.parent.mkdir(parents=True, exist_ok=True)
            with failed_path.open("a", encoding="utf-8") as fp:
                fp.write(f"{row.episode_id}\n")
            continue

        append_manifest(manifest_path, row, bytes_size, fetch_source)
        already.add(row.episode_id)
        fetched += 1
        bytes_downloaded += bytes_size

    return Top1FetchResult(
        planned=len(rows),
        fetched=fetched,
        skipped=skipped,
        failed=failed,
        official_count=official_count,
        api_count=api_count,
        bytes_downloaded=bytes_downloaded,
        quota_hit=quota_hit,
        duration_s=time.perf_counter() - started,
    )


def cli() -> int:
    parser = argparse.ArgumentParser(
        description="LB 榜首队伍 replay 下载（默认排除 2026-06-03，官方日包优先）",
    )
    parser.add_argument(
        "--episodes-csv",
        type=Path,
        default=Path("/Volumes/for mac/Data/Orbit Wars/replays/top1_episodes_since_2026-05-31.csv"),
        help="episode 列表 CSV（含 episode_id, utc_day 等）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Volumes/for mac/Data/Orbit Wars/replays/top1_isaiah"),
        help="输出根目录（内含 json/ 与 manifest，不与 raw/ 混放）",
    )
    parser.add_argument(
        "--exclude-days",
        type=str,
        default="2026-06-03",
        help="逗号分隔，这些 UTC 日期跳过（默认仅排除 6 月 3 日）",
    )
    parser.add_argument(
        "--no-official",
        action="store_true",
        help="不使用官方日包，全部走 API",
    )
    parser.add_argument(
        "--quota-gb",
        type=float,
        default=4.0,
        help="API 回退时的本地日流量上限（GB）；官方日包不计入",
    )
    args = parser.parse_args()

    exclude = frozenset(d.strip() for d in args.exclude_days.split(",") if d.strip())
    config = Top1FetchConfig(
        episodes_csv=args.episodes_csv,
        output_dir=args.output_dir,
        exclude_days=exclude,
        prefer_official=not args.no_official,
        quota_gb=args.quota_gb,
    )
    result = run_top1_fetch(config)
    print(json.dumps(result.__dict__, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
