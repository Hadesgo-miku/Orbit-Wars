"""M5 — Mission 生成器集合。

每个 mission 文件实现一种"战术意图"，统一接口::

    def build_X_missions(world: World, policy: Policy) -> list[Mission]

返回的 Mission 对象会送入 ``policy/scoring.py`` 评分，然后由 ``policy/plan.py``
按分数依次调度。

当前实现的 mission 类型（来自 lb-1200 的 mission family）：

- ``reinforce``      增援自家受威胁的星球
- ``rescue``         紧急自救（被打到濒临易主）
- ``recapture``      抢回刚丢失的星球
- ``capture``        占中立或敌方星球
- ``snipe``          低守敌方的快速狙击
- ``crash_exploit``  利用太阳/星球碰撞做杀伤

每个 mission 文件应当：

1. 只读 World 与 Policy，**不修改它们**（commitment 由 M9 调度时写入）
2. 跑完 M4 的三层安全过滤
3. 返回的 Mission 列表可以为空
4. 单文件 ≤ 300 行，超过请拆子模块
"""

from .reinforce import build_reinforce_missions
from .rescue import build_rescue_missions
from .recapture import build_recapture_missions
from .capture import build_capture_missions
from .snipe import build_snipe_missions
from .crash_exploit import build_crash_exploit_missions

__all__ = [
    "build_reinforce_missions",
    "build_rescue_missions",
    "build_recapture_missions",
    "build_capture_missions",
    "build_snipe_missions",
    "build_crash_exploit_missions",
]
