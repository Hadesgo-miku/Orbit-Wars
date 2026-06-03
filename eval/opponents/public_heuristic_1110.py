"""L3 对手：公开 heuristic 1110（vickimar 派 4868 行版本）。

待 Task agent 移植：``community-examples/recent-high-scores/orbit-wars-heuristic-lb-1110.ipynb``
（或同源的 oribt-war-12 / orbit-wars-exp30）的完整代码。

这是当前"copy-paste 群体"的最大公开 baseline，**也是我们最大的威胁**。
本地评测时打它的胜率是单一最重要指标。
"""

from __future__ import annotations


def agent(obs, config=None):
    raise NotImplementedError(
        "Task agent 实现：把 community-examples/recent-high-scores/"
        "orbit-wars-heuristic-lb-1110.ipynb 中的 4868 行 submission.py 内容"
        "原样合并到本文件，仅保留 ``agent`` 入口与所有依赖。"
    )
