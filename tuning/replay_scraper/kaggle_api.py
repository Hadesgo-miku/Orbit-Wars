"""
Kaggle Episodes API 最小化封装（M14 子模块）

参考：
    - Kaggle Episodes 内部 API 是 grpc-web 风格的 JSON RPC
    - 鉴权依赖 ~/.kaggle/kaggle.json（username + api_key）
    - 限速：5 GB / 天

主要 endpoint：
    - 取 leaderboard：competitions.LeaderboardService/GetCompetitionLeaderboard
    - 列 submissions 的 episodes：competitions.EpisodeService/ListEpisodes
    - 拉 episode replay JSON：competitions.EpisodeService/GetEpisodeReplay

注意：
    - 所有 API 调用必须经过 _rpc_post 统一封装（统一 header / 错误 / 重试）
    - 任何函数遇到 HTTP 429 (Rate Limit) 必须 backoff 指数退避
    - 默认 timeout 30s，超过即视为失败
"""
from __future__ import annotations

import base64
import datetime as dt
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import requests

KAGGLE_API_BASE: str = "https://www.kaggle.com/api/i"
DEFAULT_TIMEOUT_S: float = 30.0
# 单局 replay 体积大，kaggle-sdk 默认无硬超时；超时后由上层记 failed 并继续。
REPLAY_DOWNLOAD_TIMEOUT_S: float = 120.0
MAX_RETRIES: int = 3
BACKOFF_BASE_S: float = 1.5

COMPETITION_ID_ORBIT_WARS: int = 102140  # TODO: 占位，T0.4 必须验证真实 ID
COMPETITION_SLUG_ORBIT_WARS: str = "orbit-wars"


@dataclass(frozen=True)
class KaggleAuth:
    """从 ~/.kaggle/kaggle.json 加载的鉴权信息"""
    username: str
    api_key: str
    access_token: str | None = None

    @classmethod
    def from_default_path(cls) -> "KaggleAuth":
        """
        从 ~/.kaggle/kaggle.json 加载鉴权信息。
        如果文件不存在或字段缺失，抛 FileNotFoundError / KeyError。
        """
        # 优先兼容 legacy 凭证（kaggle.json），因为它在多数 CI/脚本场景下最稳定。
        credentials_path = Path.home() / ".kaggle" / "kaggle.json"
        if credentials_path.exists():
            with credentials_path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
            username = data["username"]
            # Kaggle 凭证文件里通常字段名是 "key"，这里兼容少数脚本自定义的 "api_key"。
            api_key = data.get("key", data.get("api_key"))
            if not api_key:
                raise KeyError("Missing 'key' in ~/.kaggle/kaggle.json")
            return cls(username=username, api_key=api_key)

        # 若没有 kaggle.json，则兼容新版 access_token 认证。
        env_token = os.environ.get("KAGGLE_API_TOKEN")
        if env_token:
            return cls(username="", api_key="", access_token=env_token.strip())

        token_path = Path.home() / ".kaggle" / "access_token"
        if token_path.exists():
            token = token_path.read_text(encoding="utf-8").strip()
            if token:
                return cls(username="", api_key="", access_token=token)

        raise FileNotFoundError(
            "Kaggle credentials not found. Expected ~/.kaggle/kaggle.json or ~/.kaggle/access_token."
        )


@dataclass(frozen=True)
class LeaderboardEntry:
    """排行榜单条目（精简版）"""
    rank: int
    team_id: int
    team_name: str
    submission_id: int
    score: float


@dataclass(frozen=True)
class EpisodeRecord:
    """单个 episode 的元信息（来自 ListEpisodes 返回）"""
    episode_id: int
    submission_id: int
    create_time: str
    end_time: str
    players_count: int
    is_winner: bool
    updated_score: float


def _rpc_post(
    endpoint: str,
    payload: dict[str, Any],
    auth: KaggleAuth,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """
    统一的 JSON RPC POST 封装。

    职责：
        - 拼接 KAGGLE_API_BASE + endpoint
        - 设置 Authorization basic auth (username:api_key)
        - 设置 Content-Type / X-XSRF-TOKEN
        - 处理 HTTP 429 / 503 → 指数退避 + 重试 MAX_RETRIES 次
        - 返回反序列化后的 JSON dict

    异常：
        - 鉴权失败 → RuntimeError
        - 超过 MAX_RETRIES → RuntimeError
        - 非 2xx 状态 → requests.HTTPError
    """
    url = f"{KAGGLE_API_BASE}/{endpoint}"
    # access_token 优先，其次回退到 legacy username:key Basic Auth。
    if auth.access_token:
        authorization = f"Bearer {auth.access_token}"
    else:
        basic_token = base64.b64encode(f"{auth.username}:{auth.api_key}".encode("utf-8")).decode("utf-8")
        authorization = f"Basic {basic_token}"
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Kaggle grpc-web 风格 API 需要带 XSRF 头才能通过网关校验。
        "X-XSRF-TOKEN": "1",
    }

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= MAX_RETRIES:
                break
            # 网络类异常也做指数退避，尽量避免临时抖动导致整批失败。
            backoff_s = BACKOFF_BASE_S * (2 ** attempt)
            time.sleep(backoff_s)
            continue

        if response.status_code in (401, 403):
            raise RuntimeError("Kaggle API authentication failed.")

        if response.status_code in (429, 503):
            if attempt >= MAX_RETRIES:
                raise RuntimeError(
                    f"Endpoint {endpoint} exceeded retry limit on HTTP {response.status_code}."
                )
            backoff_s = BACKOFF_BASE_S * (2 ** attempt)
            time.sleep(backoff_s)
            continue

        response.raise_for_status()
        return response.json()

    raise RuntimeError(f"Endpoint {endpoint} failed after retries: {last_error}")


def _unwrap_result(data: dict[str, Any]) -> dict[str, Any]:
    """统一解包 Kaggle RPC 常见外层字段，便于下游做兼容解析。"""
    for key in ("result", "data", "payload"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return data


def _coerce_float(value: Any, default: float = 0.0) -> float:
    """把数值字段安全转为 float，遇到空值或异常时回退默认值。"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int = 0) -> int:
    """把数值字段安全转为 int，兼容字符串数字。"""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _competition_slug_from_id(competition_id: int) -> str:
    """把旧版 competition_id 映射为 kaggle-sdk 需要的 competition slug。"""
    if competition_id == COMPETITION_ID_ORBIT_WARS:
        return COMPETITION_SLUG_ORBIT_WARS
    # 当前项目只服务 Orbit Wars，未知 ID 时回退到主赛事 slug，避免任务中断。
    return COMPETITION_SLUG_ORBIT_WARS


@contextmanager
def _open_competition_client(auth: KaggleAuth) -> Iterator[Any]:
    """
    打开 kaggle-sdk competition client，并在上下文中临时注入鉴权环境变量。
    """
    from kaggle.api.kaggle_api_extended import KaggleApi

    # 临时覆盖环境变量，确保 access_token / legacy key 都能被 kaggle-sdk 识别。
    old_user = os.environ.get("KAGGLE_USERNAME")
    old_key = os.environ.get("KAGGLE_KEY")
    old_token = os.environ.get("KAGGLE_API_TOKEN")
    try:
        if auth.access_token:
            os.environ["KAGGLE_API_TOKEN"] = auth.access_token
        elif auth.username and auth.api_key:
            os.environ["KAGGLE_USERNAME"] = auth.username
            os.environ["KAGGLE_KEY"] = auth.api_key

        api = KaggleApi()
        api.authenticate()
        with api.build_kaggle_client() as kaggle:
            yield kaggle.competitions.competition_api_client
    finally:
        # 用完即恢复，避免污染其他命令会话。
        if old_user is None:
            os.environ.pop("KAGGLE_USERNAME", None)
        else:
            os.environ["KAGGLE_USERNAME"] = old_user
        if old_key is None:
            os.environ.pop("KAGGLE_KEY", None)
        else:
            os.environ["KAGGLE_KEY"] = old_key
        if old_token is None:
            os.environ.pop("KAGGLE_API_TOKEN", None)
        else:
            os.environ["KAGGLE_API_TOKEN"] = old_token


def _pick_submission_id_for_team(client: Any, team_id: int) -> int:
    """
    从 team 的公开提交里选一个“当前活跃”submission。
    规则：优先最近提交时间；若无时间字段则回退第一条。
    """
    from kagglesdk.competitions.types import competition_api_service as cas

    request = cas.ApiListTeamPublicSubmissionsRequest()
    request.team_id = team_id

    response = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.list_team_public_submissions(request)
            break
        except requests.RequestException:
            if attempt >= MAX_RETRIES:
                raise
            # 对短时网络抖动进行指数退避，减少整批 top-N 抓取中断概率。
            time.sleep(BACKOFF_BASE_S * (2 ** attempt))

    if response is None:
        return 0
    submissions = list(response.submissions or [])
    if not submissions:
        return 0

    def _submission_sort_key(item: Any) -> str:
        data = item.to_dict() if hasattr(item, "to_dict") else {}
        return str(data.get("dateSubmitted") or "")

    submissions.sort(key=_submission_sort_key, reverse=True)
    newest = submissions[0]
    data = newest.to_dict() if hasattr(newest, "to_dict") else {}
    return _coerce_int(data.get("id"))


def get_top_n_submissions(
    n: int,
    auth: KaggleAuth,
    competition_id: int = COMPETITION_ID_ORBIT_WARS,
) -> list[LeaderboardEntry]:
    """
    取竞赛 top-N 排行榜对应的 submission_id 列表。

    参数：
        n: 取前 N 名（按当前 LB score 降序）
        auth: 鉴权信息
        competition_id: 竞赛 ID

    返回：
        list[LeaderboardEntry]，长度 = n，按 score 降序

    实现要点：
        - 调用 competitions.LeaderboardService/GetCompetitionLeaderboard
        - 处理 pagination（如果 n > 单页上限）
        - 注意：leaderboard 上的 submission_id 是该 team 的"当前活跃"提交
    """
    if n <= 0:
        return []

    from kagglesdk.competitions.types import competition_api_service as cas

    competition_slug = _competition_slug_from_id(competition_id)
    entries: list[LeaderboardEntry] = []
    page_token: str | None = None

    with _open_competition_client(auth) as client:
        while len(entries) < n:
            request = cas.ApiGetLeaderboardRequest()
            request.competition_name = competition_slug
            request.page_size = min(max(n, 20), 100)
            if page_token:
                request.page_token = page_token

            response = client.get_leaderboard(request)
            rows = list(response.submissions or [])
            if not rows:
                break

            for index, row in enumerate(rows, start=len(entries) + 1):
                row_data = row.to_dict() if hasattr(row, "to_dict") else {}
                team_id = _coerce_int(row_data.get("teamId"))
                if team_id <= 0:
                    continue
                submission_id = _pick_submission_id_for_team(client=client, team_id=team_id)
                if submission_id <= 0:
                    continue

                entries.append(
                    LeaderboardEntry(
                        rank=index,
                        team_id=team_id,
                        team_name=str(row_data.get("teamName") or "unknown"),
                        submission_id=submission_id,
                        score=_coerce_float(row_data.get("score")),
                    )
                )
                if len(entries) >= n:
                    break

            next_page = str(getattr(response, "next_page_token", "") or "")
            if not next_page or next_page == page_token:
                break
            page_token = next_page

    return entries[:n]


def list_episodes_for_submission(
    submission_id: int,
    auth: KaggleAuth,
    max_count: int = 100,
) -> list[EpisodeRecord]:
    """
    列出指定 submission 最近 max_count 局 episode。

    参数：
        submission_id: 目标 submission ID
        auth: 鉴权信息
        max_count: 最多取多少个 episode（默认 100）

    返回：
        list[EpisodeRecord]，按 create_time 降序（最新的在前）

    实现要点：
        - 调用 competitions.EpisodeService/ListEpisodes
        - 处理 pagination
        - 过滤掉 in-progress 局（只取已结束）
    """
    if max_count <= 0:
        return []

    from kagglesdk.competitions.types import competition_api_service as cas

    with _open_competition_client(auth) as client:
        request = cas.ApiListSubmissionEpisodesRequest()
        request.submission_id = submission_id
        response = client.list_submission_episodes(request)
        episodes = list(response.episodes or [])

    records: list[EpisodeRecord] = []
    for item in episodes:
        item_data = item.to_dict() if hasattr(item, "to_dict") else {}
        episode_id = _coerce_int(item_data.get("id") or item_data.get("episodeId"))
        if episode_id <= 0:
            continue

        end_time = str(item_data.get("endTime") or "")
        if not end_time:
            continue

        agents = list(item_data.get("agents", []))
        my_agent = next(
            (agent for agent in agents if _coerce_int(agent.get("submissionId")) == submission_id),
            {},
        )
        records.append(
            EpisodeRecord(
                episode_id=episode_id,
                submission_id=submission_id,
                create_time=str(item_data.get("createTime") or ""),
                end_time=end_time,
                players_count=len(agents),
                # Kaggle episodes 的 reward > 0 代表该 agent 胜出。
                is_winner=_coerce_float(my_agent.get("reward"), default=0.0) > 0.0,
                updated_score=_coerce_float(my_agent.get("updatedScore"), default=0.0),
            )
        )

    records.sort(key=lambda item: item.create_time, reverse=True)
    return records[:max_count]


def get_episode_replay(
    episode_id: int,
    auth: KaggleAuth,
    *,
    timeout_s: float = REPLAY_DOWNLOAD_TIMEOUT_S,
) -> dict[str, Any]:
    """
    拉取指定 episode 的完整 replay JSON。

    参数：
        episode_id: 目标 episode ID
        auth: 鉴权信息
        timeout_s: 单局下载最长等待秒数（避免配额触顶后 API 挂死导致 tqdm 假停）

    返回：
        replay 完整 JSON（含 configuration / steps / rewards / statuses）

    实现要点：
        - 调用 competitions.EpisodeService/GetEpisodeReplay
        - replay 体积 5-20 MB，用线程 + timeout 包住 sdk 调用
        - 建议立即写到磁盘（不要持有大对象在内存）
    """
    from kagglesdk.competitions.types import competition_api_service as cas

    def _download() -> dict[str, Any]:
        with _open_competition_client(auth) as client:
            request = cas.ApiGetEpisodeReplayRequest()
            request.episode_id = episode_id
            response = client.get_episode_replay(request)
            response.raise_for_status()
            replay = response.json()
        if "configuration" not in replay or "steps" not in replay:
            raise RuntimeError(
                f"Replay schema missing required fields for episode_id={episode_id}"
            )
        return replay

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_download)
        try:
            return future.result(timeout=timeout_s)
        except FuturesTimeoutError as exc:
            raise TimeoutError(
                f"get_episode_replay timed out after {timeout_s}s (episode_id={episode_id})"
            ) from exc


def estimate_quota_used_today(quota_dir: Path) -> float:
    """
    估算今天已经消耗的 quota（GB）。

    实现思路：
        - 在 quota_dir 下维护 quota_YYYY-MM-DD.json 记录今天累计下载字节数
        - 每次成功调用 get_episode_replay 后更新该文件

    返回：
        今天累计 GB（float）。文件不存在则返回 0.0
    """
    today = dt.date.today().isoformat()
    quota_path = quota_dir / f"quota_{today}.json"
    if not quota_path.exists():
        return 0.0

    with quota_path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    bytes_used = _coerce_int(payload.get("bytes_used"), default=0)
    return bytes_used / (1024 ** 3)


def record_quota(quota_dir: Path, bytes_downloaded: int) -> None:
    """记录一次下载消耗到 quota 文件中。"""
    quota_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    quota_path = quota_dir / f"quota_{today}.json"

    current_bytes = 0
    if quota_path.exists():
        with quota_path.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)
        current_bytes = _coerce_int(payload.get("bytes_used"), default=0)

    updated_bytes = current_bytes + max(0, int(bytes_downloaded))
    with quota_path.open("w", encoding="utf-8") as fp:
        json.dump(
            {
                "date": today,
                "bytes_used": updated_bytes,
            },
            fp,
            ensure_ascii=False,
            indent=2,
        )
