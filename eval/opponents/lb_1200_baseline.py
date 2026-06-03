"""L4 对手：lb-1200 公开最强（pilkwang 派 Mission Family baseline）。

待 Task agent 移植：``community-examples/lb-1200-orbit-wars-ppo-strategy.ipynb`` 中
cell 2 的 3231 行 submission.py（注意尽管文件名带 PPO，**实际是 heuristic**，
基于 pilkwang/orbit-wars-structured-baseline v11）。

这是公开方法的天花板，目标是与之打成 50% 胜（持平就是 silver 上沿）。
"""

from __future__ import annotations


def agent(obs, config=None):
    raise NotImplementedError(
        "Task agent 实现：把 community-examples/lb-1200-orbit-wars-ppo-strategy.ipynb "
        "中的 submission.py 内容原样合并到本文件。"
    )
