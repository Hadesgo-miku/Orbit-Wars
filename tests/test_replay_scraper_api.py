"""M14 Replay Scraper API 单元测试。

覆盖范围：
1. 从默认路径加载 Kaggle 鉴权；
2. RPC 在 429 场景下的指数退避重试；
3. 配额 quota 的本地累计与读取；
4. crawler 的中断点续抓（跳过 manifest 里已有 episode）。
"""

from __future__ import annotations

import json
from pathlib import Path

from tuning.replay_scraper import crawler, kaggle_api


def test_auth_from_default_path_reads_kaggle_json(monkeypatch, tmp_path: Path):
    """应从 ~/.kaggle/kaggle.json 成功加载 username 与 key。"""
    fake_home = tmp_path / "home"
    kaggle_dir = fake_home / ".kaggle"
    kaggle_dir.mkdir(parents=True)
    (kaggle_dir / "kaggle.json").write_text(
        json.dumps({"username": "tester", "key": "secret"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(fake_home))

    auth = kaggle_api.KaggleAuth.from_default_path()
    assert auth.username == "tester"
    assert auth.api_key == "secret"


def test_rpc_post_retries_on_429_with_backoff(monkeypatch):
    """当 API 先返回 429 后恢复时，应按 backoff 重试并最终成功。"""

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            if self.status_code >= 400 and self.status_code not in (429, 503):
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    responses = [
        _FakeResponse(429, {"error": "too many requests"}),
        _FakeResponse(200, {"ok": True}),
    ]
    post_calls = {"count": 0}
    sleeps: list[float] = []

    def _fake_post(*args, **kwargs):
        idx = post_calls["count"]
        post_calls["count"] += 1
        return responses[idx]

    def _fake_sleep(seconds: float):
        sleeps.append(seconds)

    monkeypatch.setattr(kaggle_api.requests, "post", _fake_post)
    monkeypatch.setattr(kaggle_api.time, "sleep", _fake_sleep)

    payload = kaggle_api._rpc_post(  # noqa: SLF001 - 测试私有重试逻辑
        endpoint="competitions.EpisodeService/GetEpisodeReplay",
        payload={"episodeId": 1},
        auth=kaggle_api.KaggleAuth(username="u", api_key="k"),
    )
    assert payload == {"ok": True}
    assert post_calls["count"] == 2
    assert sleeps == [kaggle_api.BACKOFF_BASE_S]


def test_quota_record_and_estimate_round_trip(tmp_path: Path):
    """record_quota 写入后，estimate_quota_used_today 应返回正确 GB。"""
    quota_dir = tmp_path / "quota"
    kaggle_api.record_quota(quota_dir=quota_dir, bytes_downloaded=1024)
    kaggle_api.record_quota(quota_dir=quota_dir, bytes_downloaded=2048)

    used_gb = kaggle_api.estimate_quota_used_today(quota_dir=quota_dir)
    expected_gb = (1024 + 2048) / (1024 ** 3)
    assert used_gb == expected_gb


def test_run_crawl_supports_resume_checkpoint(monkeypatch, tmp_path: Path):
    """manifest 中已有的 episode 应跳过，只抓新增 episode。"""
    manifest_path = tmp_path / "manifest.csv"
    crawler.append_manifest_row(
        manifest_path=manifest_path,
        episode_id=101,
        submission_id=9001,
        team_name="existing-team",
        players_count=4,
        is_winner=True,
        updated_score=1234.5,
        create_time="2026-01-01T00:00:00Z",
        bytes_size=100,
    )

    config = crawler.CrawlConfig(
        top_n=1,
        max_per_team=2,
        output_dir=tmp_path / "raw",
        manifest_path=manifest_path,
        quota_gb=4.0,
    )

    monkeypatch.setattr(
        kaggle_api.KaggleAuth,
        "from_default_path",
        classmethod(lambda cls: kaggle_api.KaggleAuth(username="u", api_key="k")),
    )
    monkeypatch.setattr(
        kaggle_api,
        "get_top_n_submissions",
        lambda n, auth, competition_id: [
            kaggle_api.LeaderboardEntry(
                rank=1,
                team_id=1,
                team_name="team-a",
                submission_id=9001,
                score=999.0,
            )
        ],
    )
    monkeypatch.setattr(
        kaggle_api,
        "list_episodes_for_submission",
        lambda submission_id, auth, max_count: [
            kaggle_api.EpisodeRecord(
                episode_id=101,
                submission_id=submission_id,
                create_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:30:00Z",
                players_count=4,
                is_winner=True,
                updated_score=1.0,
            ),
            kaggle_api.EpisodeRecord(
                episode_id=102,
                submission_id=submission_id,
                create_time="2026-01-01T01:00:00Z",
                end_time="2026-01-01T01:30:00Z",
                players_count=4,
                is_winner=False,
                updated_score=2.0,
            ),
        ],
    )
    monkeypatch.setattr(kaggle_api, "estimate_quota_used_today", lambda quota_dir: 0.0)

    recorded_bytes: list[int] = []
    monkeypatch.setattr(
        kaggle_api,
        "record_quota",
        lambda quota_dir, bytes_downloaded: recorded_bytes.append(bytes_downloaded),
    )

    crawled_ids: list[int] = []

    def _fake_crawl_one_episode(episode_id, auth, output_dir):
        crawled_ids.append(episode_id)
        return 2048

    monkeypatch.setattr(crawler, "crawl_one_episode", _fake_crawl_one_episode)

    result = crawler.run_crawl(config)
    assert result.episodes_fetched == 1
    assert result.episodes_failed == 0
    assert crawled_ids == [102]
    assert recorded_bytes == [2048]
