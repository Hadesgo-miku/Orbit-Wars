"""
API 自爬 replay JSON 与 Kaggle 官方日包 JSON 的一致性抽样核查。

典型用法（推荐：固定 UTC 日，无需扫描官方文件列表）：
    python -m tuning.replay_scraper.consistency_check \
        --fixed-day 2026-06-01 \
        --sample-size 30

    逻辑：top-20 submission → API 按 create_time 过滤该日 episode_id →
    官方日包按路径直下 `orbit-wars-episodes-2026-06-01/{id}.json` → 与 API 重拉比对。

    旧模式（较慢，不推荐）：
    - 本地 manifest 跨多日查找官方文件
    - 或 list_files 抽样官方日包

输出：
    data/replays/consistency_check_report.json
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kaggle.api.kaggle_api_extended import KaggleApi

from . import kaggle_api


def _call_with_retry(func, max_retries: int = 5, base_s: float = 3.0):
    """对 Kaggle API 429 做指数退避重试。"""
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            msg = str(exc)
            if "429" not in msg and "Too Many Requests" not in msg:
                raise
            if attempt >= max_retries:
                break
            time.sleep(base_s * (2 ** attempt))
    raise RuntimeError(f"Kaggle API rate limited after retries: {last_error}")


@dataclass
class CompareResult:
    """单局比对结果。"""

    episode_id: int
    status: str  # match | mismatch | skip | error
    message: str = ""
    local_path: str | None = None
    official_path: str | None = None
    official_slug: str | None = None
    local_bytes: int = 0
    official_bytes: int = 0
    identical_bytes: bool = False
    steps_len_local: int | None = None
    steps_len_official: int | None = None
    has_configuration: bool = False
    has_rewards: bool = False
    has_statuses: bool = False


@dataclass
class ConsistencyReport:
    """完整核查报告。"""

    created_at: str
    local_sample: list[CompareResult] = field(default_factory=list)
    official_cross_check: list[CompareResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def _load_index_dates(index_manifest: Path) -> list[str]:
    """读取官方日包索引 manifest，返回可用日期列表（升序）。"""
    if not index_manifest.exists():
        return []
    with index_manifest.open("r", encoding="utf-8", newline="") as fp:
        rows = list(csv.DictReader(fp))
    return sorted(row["date"] for row in rows if row.get("date"))


def _load_local_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def _sample_rows(rows: list[dict[str, str]], n: int, seed: int) -> list[dict[str, str]]:
    if len(rows) <= n:
        return list(rows)
    rng = random.Random(seed)
    return rng.sample(rows, n)


def _official_slug_for_date(day: str) -> str:
    return f"kaggle/orbit-wars-episodes-{day}"


def _replay_fingerprint(replay: dict[str, Any]) -> dict[str, Any]:
    """提取用于结构比对的轻量指纹（避免逐步深度 diff 过慢）。"""
    steps = replay.get("steps")
    rewards = replay.get("rewards")
    statuses = replay.get("statuses")
    return {
        "steps_len": len(steps) if isinstance(steps, list) else -1,
        "rewards_len": len(rewards) if isinstance(rewards, list) else -1,
        "statuses_len": len(statuses) if isinstance(statuses, list) else -1,
        "has_configuration": "configuration" in replay,
        "has_rewards": rewards is not None,
        "has_statuses": statuses is not None,
        "replay_id": replay.get("id"),
        "name": replay.get("name"),
    }


def compare_replay_dicts(local: dict[str, Any], official: dict[str, Any]) -> tuple[bool, str]:
    """比较两份 replay JSON 的结构指纹是否一致。"""
    fp_local = _replay_fingerprint(local)
    fp_official = _replay_fingerprint(official)
    if fp_local == fp_official:
        return True, "fingerprint_match"

    diffs = [k for k in fp_local if fp_local[k] != fp_official.get(k)]
    return False, f"fingerprint_diff:{','.join(diffs)}"


def compare_files(local_path: Path, official_path: Path) -> CompareResult:
    """比较本地文件与官方下载文件（先比字节哈希，再比结构指纹）。"""
    episode_id = int(local_path.stem)
    result = CompareResult(
        episode_id=episode_id,
        status="error",
        local_path=str(local_path),
        official_path=str(official_path),
        local_bytes=local_path.stat().st_size if local_path.exists() else 0,
        official_bytes=official_path.stat().st_size if official_path.exists() else 0,
    )

    if not local_path.exists():
        result.message = "local_missing"
        return result
    if not official_path.exists():
        result.message = "official_missing"
        return result

    local_bytes = local_path.read_bytes()
    official_bytes = official_path.read_bytes()
    result.identical_bytes = local_bytes == official_bytes
    if result.identical_bytes:
        result.status = "match"
        result.message = "byte_identical"
        return result

    local_replay = json.loads(local_bytes.decode("utf-8"))
    official_replay = json.loads(official_bytes.decode("utf-8"))
    fp = _replay_fingerprint(local_replay)
    result.steps_len_local = fp["steps_len"]
    result.steps_len_official = _replay_fingerprint(official_replay)["steps_len"]
    result.has_configuration = fp["has_configuration"]
    result.has_rewards = fp["has_rewards"]
    result.has_statuses = fp["has_statuses"]

    ok, msg = compare_replay_dicts(local_replay, official_replay)
    result.status = "match" if ok else "mismatch"
    result.message = msg
    return result


def _build_kaggle_api() -> KaggleApi:
    api = KaggleApi()
    api.authenticate()
    return api


def download_official_episode(
    api: KaggleApi,
    episode_id: int,
    official_slug: str,
    output_path: Path,
    max_retries: int = 3,
) -> None:
    """从官方日包按单文件下载 replay JSON（带重试）。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_name = f"{episode_id}.json"
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            # KaggleApi.dataset_download_file 每次都会 print("Dataset URL: ...")，刷屏且拖慢观感。
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                ok = api.dataset_download_file(official_slug, file_name, str(output_path.parent))
            if ok is False and not output_path.exists():
                # 部分版本返回 bool，实际文件可能落在 parent 目录
                candidate = output_path.parent / file_name
                if candidate.exists():
                    candidate.replace(output_path)
            if output_path.exists():
                return
            candidate = output_path.parent / file_name
            if candidate.exists():
                candidate.replace(output_path)
                return
            raise FileNotFoundError(f"download finished but file missing: {output_path}")
        except Exception as exc:
            last_error = exc
            time.sleep(kaggle_api.BACKOFF_BASE_S * (2 ** attempt))
    raise RuntimeError(f"official download failed for {episode_id}: {last_error}")


def episode_exists_in_official(
    api: KaggleApi,
    episode_id: int,
    official_slug: str,
    page_size: int = 1000,
) -> bool:
    """检查官方日包文件列表中是否存在该 episode 文件。"""
    token: str | None = ""
    target = f"{episode_id}.json"
    while True:
        resp = api.dataset_list_files(official_slug, page_token=token or "", page_size=page_size)
        for item in resp.files or []:
            if item.name == target:
                return True
        token = getattr(resp, "next_page_token", None) or ""
        if not token:
            break
    return False


def find_official_slug_for_episode(
    api: KaggleApi,
    episode_id: int,
    index_dates: list[str],
    preferred_day: str | None = None,
) -> str | None:
    """
    在索引日期中查找包含该 episode 的官方日包。
    优先查 preferred_day，再查索引最后 3 天；避免全量扫描 40+ 日包。
    """
    if not index_dates:
        return None

    latest_day = index_dates[-1]
    # 若局创建日晚于官方索引最新日，说明日包尚未发布，直接跳过。
    if preferred_day and preferred_day > latest_day:
        return None

    ordered_days: list[str] = []
    if preferred_day and preferred_day in index_dates:
        ordered_days.append(preferred_day)
        idx = index_dates.index(preferred_day)
        for offset in (-1, 1, -2, 2):
            pos = idx + offset
            if 0 <= pos < len(index_dates):
                day = index_dates[pos]
                if day not in ordered_days:
                    ordered_days.append(day)
    for day in index_dates[-3:]:
        if day not in ordered_days:
            ordered_days.append(day)

    for day in ordered_days:
        slug = _official_slug_for_date(day)
        try:
            if episode_exists_in_official(api, episode_id, slug):
                return slug
        except Exception:
            continue
    return None


def _list_files_page_with_retry(
    api: KaggleApi,
    official_slug: str,
    page_token: str,
    page_size: int,
) -> Any:
    """带 429 退避的 list_files 封装。"""
    last_error: Exception | None = None
    for attempt in range(kaggle_api.MAX_RETRIES + 1):
        try:
            return api.dataset_list_files(official_slug, page_token=page_token, page_size=page_size)
        except Exception as exc:
            last_error = exc
            if "429" not in str(exc) and "Too Many Requests" not in str(exc):
                raise
            if attempt >= kaggle_api.MAX_RETRIES:
                break
            time.sleep(kaggle_api.BACKOFF_BASE_S * (2 ** attempt))
    raise RuntimeError(f"list_dataset_files failed: {last_error}")


def sample_official_episode_ids(
    api: KaggleApi,
    official_slug: str,
    sample_size: int,
    seed: int,
    pool_size: int = 300,
) -> list[int]:
    """
    从官方日包文件列表中抽样 episode_id（无需拉全量 4000+ 文件名）。
    默认从前若干页凑够 pool_size 个候选后随机抽取。
    """
    pool: list[int] = []
    token: str = ""
    while len(pool) < pool_size:
        resp = _list_files_page_with_retry(api, official_slug, page_token=token, page_size=100)
        for item in resp.files or []:
            if item.name.endswith(".json"):
                pool.append(int(item.name.replace(".json", "")))
        token = getattr(resp, "next_page_token", None) or ""
        if not token:
            break
    if not pool:
        return []
    return _sample_rows([{"episode_id": str(eid)} for eid in pool], min(sample_size, len(pool)), seed)


def run_local_manifest_check(
    api: KaggleApi,
    local_manifest: Path,
    raw_dir: Path,
    cache_dir: Path,
    index_dates: list[str],
    sample_size: int,
    seed: int,
) -> list[CompareResult]:
    """从本地 manifest 抽样，尝试下载官方同名 JSON 并与本地 raw 比对。"""
    rows = _sample_rows(_load_local_manifest(local_manifest), sample_size, seed)
    results: list[CompareResult] = []

    for row in rows:
        episode_id = int(row["episode_id"])
        create_day = (row.get("create_time") or "")[:10]
        local_path = raw_dir / f"{episode_id}.json"
        slug = find_official_slug_for_episode(api, episode_id, index_dates, preferred_day=create_day)
        if slug is None:
            results.append(
                CompareResult(
                    episode_id=episode_id,
                    status="skip",
                    message=f"not_in_official_index_yet (create_day={create_day})",
                    local_path=str(local_path),
                )
            )
            continue

        official_path = cache_dir / slug.split("/")[-1] / f"{episode_id}.json"
        try:
            if not official_path.exists():
                download_official_episode(api, episode_id, slug, official_path)
            cmp_result = compare_files(local_path, official_path)
            cmp_result.official_slug = slug
            results.append(cmp_result)
        except Exception as exc:
            results.append(
                CompareResult(
                    episode_id=episode_id,
                    status="error",
                    message=str(exc),
                    local_path=str(local_path),
                    official_slug=slug,
                )
            )
    return results


def collect_episode_ids_from_api_for_day(
    auth: kaggle_api.KaggleAuth,
    utc_day: str,
    top_n: int = 20,
) -> list[int]:
    """
    从 top-N submission 的 episode 元信息中，按 create_time 的 UTC 日期过滤。
    不需要扫描官方日包文件列表。
    """
    episode_ids: set[int] = set()
    leaders = _call_with_retry(lambda: kaggle_api.get_top_n_submissions(n=top_n, auth=auth))
    for entry in leaders:
        episodes = _call_with_retry(
            lambda sid=entry.submission_id: kaggle_api.list_episodes_for_submission(
                submission_id=sid,
                auth=auth,
                max_count=500,
            )
        )
        for episode in episodes:
            if episode.create_time[:10] == utc_day:
                episode_ids.add(episode.episode_id)
    return sorted(episode_ids)


def sample_episode_ids_from_official_pages(
    api: KaggleApi,
    utc_day: str,
    sample_size: int,
    seed: int,
    list_pages: int = 1,
    page_size: int = 100,
) -> list[int]:
    """仅从官方日包前 N 页文件列表抽样（不调用 leaderboard，适合 429 限流时）。"""
    official_slug = _official_slug_for_date(utc_day)
    pool: list[int] = []
    token = ""
    for _ in range(list_pages):
        resp = _list_files_page_with_retry(api, official_slug, page_token=token, page_size=page_size)
        for item in resp.files or []:
            if item.name.endswith(".json"):
                pool.append(int(item.name.replace(".json", "")))
        token = getattr(resp, "next_page_token", None) or ""
        if not token:
            break
    if not pool:
        return []
    picked = _sample_rows([{"episode_id": str(eid)} for eid in pool], min(sample_size, len(pool)), seed)
    return [int(row["episode_id"]) for row in picked]


def run_fixed_day_check(
    auth: kaggle_api.KaggleAuth,
    api: KaggleApi,
    utc_day: str,
    cache_dir: Path,
    sample_size: int,
    seed: int,
    top_n: int = 20,
    ids_source: str = "api",
) -> list[CompareResult]:
    """
    固定官方日包日期的一致性核查（推荐路径）：
    1. API 列出该日 episode_id（按 create_time 过滤）
    2. 官方按 `{slug}/{episode_id}.json` 直接下载（不 list 全量文件）
    3. API 重拉同局 replay，与官方文件比对
    """
    official_slug = _official_slug_for_date(utc_day)
    if ids_source == "official-list":
        all_ids = sample_episode_ids_from_official_pages(
            api=api, utc_day=utc_day, sample_size=sample_size, seed=seed, list_pages=1
        )
    else:
        try:
            all_ids = collect_episode_ids_from_api_for_day(auth=auth, utc_day=utc_day, top_n=top_n)
        except Exception as exc:
            if "429" not in str(exc) and "rate limit" not in str(exc).lower():
                raise
            all_ids = sample_episode_ids_from_official_pages(
                api=api, utc_day=utc_day, sample_size=sample_size, seed=seed, list_pages=1
            )
    if not all_ids:
        return [
            CompareResult(
                episode_id=-1,
                status="error",
                message=f"no API episodes on {utc_day} for top-{top_n}",
                official_slug=official_slug,
            )
        ]

    if ids_source == "official-list" and len(all_ids) <= sample_size:
        picked_ids = all_ids
    else:
        picked_ids = [
            int(row["episode_id"])
            for row in _sample_rows(
                [{"episode_id": str(eid)} for eid in all_ids],
                min(sample_size, len(all_ids)),
                seed,
            )
        ]
    results: list[CompareResult] = []
    for episode_id in picked_ids:
        official_path = cache_dir / utc_day / f"{episode_id}.json"
        api_cache_path = cache_dir / "api_refetch" / f"{episode_id}.json"
        try:
            if not official_path.exists():
                download_official_episode(api, episode_id, official_slug, official_path)

            replay = _call_with_retry(
                lambda eid=episode_id: kaggle_api.get_episode_replay(episode_id=eid, auth=auth)
            )
            api_cache_path.parent.mkdir(parents=True, exist_ok=True)
            api_cache_path.write_text(json.dumps(replay, ensure_ascii=False), encoding="utf-8")

            cmp_result = compare_files(api_cache_path, official_path)
            cmp_result.official_slug = official_slug
            results.append(cmp_result)
        except Exception as exc:
            results.append(
                CompareResult(
                    episode_id=episode_id,
                    status="error",
                    message=str(exc),
                    official_slug=official_slug,
                )
            )
    return results


def run_official_cross_check(
    auth: kaggle_api.KaggleAuth,
    api: KaggleApi,
    official_date: str,
    cache_dir: Path,
    sample_size: int,
    seed: int,
) -> list[CompareResult]:
    """
    从指定官方日包随机抽 episode_id：
    - 下载官方 JSON
    - 用 Episodes API 再拉同一局
    - 比对两者是否一致
    """
    official_slug = _official_slug_for_date(official_date)
    picked = sample_official_episode_ids(api, official_slug, sample_size, seed)
    if not picked:
        return [
            CompareResult(
                episode_id=-1,
                status="error",
                message=f"no episodes listed in {official_slug}",
                official_slug=official_slug,
            )
        ]
    results: list[CompareResult] = []

    for row in picked:
        episode_id = int(row["episode_id"])
        official_path = cache_dir / official_slug.split("/")[-1] / f"{episode_id}.json"
        api_cache_path = cache_dir / "api_refetch" / f"{episode_id}.json"
        try:
            if not official_path.exists():
                download_official_episode(api, episode_id, official_slug, official_path)

            replay = _call_with_retry(
                lambda eid=episode_id: kaggle_api.get_episode_replay(episode_id=eid, auth=auth)
            )
            api_cache_path.parent.mkdir(parents=True, exist_ok=True)
            api_cache_path.write_text(json.dumps(replay, ensure_ascii=False), encoding="utf-8")

            cmp_result = compare_files(api_cache_path, official_path)
            cmp_result.official_slug = official_slug
            results.append(cmp_result)
        except Exception as exc:
            results.append(
                CompareResult(
                    episode_id=episode_id,
                    status="error",
                    message=str(exc),
                    official_slug=official_slug,
                )
            )
    return results


def _summarize(results: list[CompareResult]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in results:
        summary[item.status] = summary.get(item.status, 0) + 1
    return summary


def run_check(
    local_manifest: Path,
    raw_dir: Path,
    index_manifest: Path,
    cache_dir: Path,
    sample_size: int,
    seed: int,
    official_cross_check: int,
    official_date: str | None,
    fixed_day: str | None,
    top_n: int,
    ids_source: str,
) -> ConsistencyReport:
    """执行完整核查流程并生成报告对象。"""
    api = _build_kaggle_api()
    auth = kaggle_api.KaggleAuth.from_default_path()
    index_dates = _load_index_dates(index_manifest)
    if official_date is None and index_dates:
        official_date = index_dates[-1]

    report = ConsistencyReport(created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    if fixed_day:
        # 推荐：固定一日，API 过滤 + 官方直下，不做跨日/全量 list_files 扫描。
        report.official_cross_check = run_fixed_day_check(
            auth=auth,
            api=api,
            utc_day=fixed_day,
            cache_dir=cache_dir,
            sample_size=sample_size,
            seed=seed,
            top_n=top_n,
            ids_source=ids_source,
        )
        report.local_sample = []
    else:
        report.local_sample = run_local_manifest_check(
            api=api,
            local_manifest=local_manifest,
            raw_dir=raw_dir,
            cache_dir=cache_dir,
            index_dates=index_dates,
            sample_size=sample_size,
            seed=seed,
        )
        if official_cross_check > 0 and official_date:
            report.official_cross_check = run_official_cross_check(
                auth=auth,
                api=api,
                official_date=official_date,
                cache_dir=cache_dir,
                sample_size=official_cross_check,
                seed=seed,
            )

    report.summary = {
        "mode": "fixed_day" if fixed_day else "legacy",
        "fixed_day": fixed_day,
        "ids_source": ids_source,
        "local_sample": _summarize(report.local_sample),
        "official_cross_check": _summarize(report.official_cross_check),
        "index_latest_date": index_dates[-1] if index_dates else None,
        "official_cross_check_date": official_date if not fixed_day else fixed_day,
    }
    return report


def cli() -> int:
    parser = argparse.ArgumentParser(description="API vs 官方日包 replay JSON 一致性核查")
    parser.add_argument("--local-manifest", type=Path, default=Path("data/replays/manifest.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/replays/raw"))
    parser.add_argument("--index-manifest", type=Path, default=Path("data/manifest.csv"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/replays/consistency_cache"))
    parser.add_argument("--output", type=Path, default=Path("data/replays/consistency_check_report.json"))
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--official-cross-check",
        type=int,
        default=30,
        help="从官方日包抽样并与 API 重拉结果比对；设为 0 可关闭",
    )
    parser.add_argument(
        "--official-date",
        type=str,
        default=None,
        help="官方交叉比对使用的 UTC 日期（默认取 index manifest 最后一天）",
    )
    parser.add_argument(
        "--fixed-day",
        type=str,
        default=None,
        help="推荐：固定 UTC 日（如 2026-06-01），API 按 create_time 过滤 + 官方直下，无需扫描",
    )
    parser.add_argument("--top-n", type=int, default=20, help="fixed-day 模式下取排行榜前 N 队")
    parser.add_argument(
        "--ids-source",
        choices=("api", "official-list"),
        default="api",
        help="episode_id 来源：api=top20+create_time 过滤；official-list=仅官方日包首页抽样（省 API）",
    )
    args = parser.parse_args()

    report = run_check(
        local_manifest=args.local_manifest,
        raw_dir=args.raw_dir,
        index_manifest=args.index_manifest,
        cache_dir=args.cache_dir,
        sample_size=args.sample_size,
        seed=args.seed,
        official_cross_check=args.official_cross_check,
        official_date=args.official_date,
        fixed_day=args.fixed_day,
        top_n=args.top_n,
        ids_source=args.ids_source,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "created_at": report.created_at,
                "summary": report.summary,
                "local_sample": [asdict(x) for x in report.local_sample],
                "official_cross_check": [asdict(x) for x in report.official_cross_check],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps(report.summary, ensure_ascii=False, indent=2))
    print(f"report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
