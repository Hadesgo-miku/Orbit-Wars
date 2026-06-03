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

import os
import time
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

import requests

KAGGLE_API_BASE: str = "https://www.kaggle.com/api/i"
DEFAULT_TIMEOUT_S: float = 30.0
MAX_RETRIES: int = 3
BACKOFF_BASE_S: float = 1.5

COMPETITION_ID_ORBIT_WARS: int = 102140  # TODO: 占位，T0.4 必须验证真实 ID


@dataclass(frozen=True)
class KaggleAuth:
    """从 ~/.kaggle/kaggle.json 加载的鉴权信息"""
    username: str
    api_key: str

    @classmethod
    def from_default_path(cls) -> "KaggleAuth":
        """
        从 ~/.kaggle/kaggle.json 加载鉴权信息。
        如果文件不存在或字段缺失，抛 FileNotFoundError / KeyError。
        """
        raise NotImplementedError(
            "M14/T0.4 待实现：从 ~/.kaggle/kaggle.json 加载 username 与 key"
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
    raise NotImplementedError(
        "M14/T0.4 待实现：通用 RPC POST + 重试 + backoff"
    )


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
    raise NotImplementedError(
        f"M14/T0.4 待实现：取 top-{n} submissions"
    )


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
    raise NotImplementedError(
        f"M14/T0.4 待实现：列 submission_id={submission_id} 的 episodes"
    )


def get_episode_replay(
    episode_id: int,
    auth: KaggleAuth,
) -> dict[str, Any]:
    """
    拉取指定 episode 的完整 replay JSON。

    参数：
        episode_id: 目标 episode ID
        auth: 鉴权信息

    返回：
        replay 完整 JSON（含 configuration / steps / rewards / statuses）

    实现要点：
        - 调用 competitions.EpisodeService/GetEpisodeReplay
        - replay 体积 5-20 MB，超时阈值要拉宽到 60s
        - 建议立即写到磁盘（不要持有大对象在内存）
    """
    raise NotImplementedError(
        f"M14/T0.4 待实现：拉 episode_id={episode_id} replay JSON"
    )


def estimate_quota_used_today(quota_dir: Path) -> float:
    """
    估算今天已经消耗的 quota（GB）。

    实现思路：
        - 在 quota_dir 下维护 quota_YYYY-MM-DD.json 记录今天累计下载字节数
        - 每次成功调用 get_episode_replay 后更新该文件

    返回：
        今天累计 GB（float）。文件不存在则返回 0.0
    """
    raise NotImplementedError(
        "M14/T0.4 待实现：本地 quota 计数器"
    )


def record_quota(quota_dir: Path, bytes_downloaded: int) -> None:
    """记录一次下载消耗到 quota 文件中。"""
    raise NotImplementedError(
        "M14/T0.4 待实现：累计 quota 计数"
    )
