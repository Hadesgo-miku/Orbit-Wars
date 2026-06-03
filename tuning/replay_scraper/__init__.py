"""
M14 Replay Scraper —— Kaggle Episodes API 自爬 + ETL 管线

模块职责：
    1. 通过 Kaggle Episodes API 抓取竞赛排行榜 top-N 玩家最近 N 局 episode
    2. 解析 replay JSON，反推每个 action 的 (source, target, ships) 标签
    3. 把 (state_features, source, target, ships, label) 落 parquet

子模块：
    kaggle_api       —— Kaggle Episodes API 的最小化封装
    crawler          —— top-N → submissions → episodes → replay 的调度器
    inverse_target   —— 把"launch angle"反推为"target planet id"
    extract_features —— replay JSON → 训练用 parquet

接口约定（详见 master-plan.md §2.1）：
    - 任何对外暴露的入口函数必须可被 CLI 直接调用
    - 抓取过程不允许阻塞超过 10 分钟（必须有 progress bar + 中断点）
    - 任何写入 data/ 的文件都必须有 schema 文档

依赖：requests, tqdm, pandas, pyarrow
"""

__all__ = [
    "kaggle_api",
    "crawler",
    "inverse_target",
    "extract_features",
]
