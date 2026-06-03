"""本地对手池。

按 master-plan.md §5.2 五个等级：

- L0 ``random_agent``：纯随机；应当 100% 胜
- L1 ``nearest_sniper``：``orbit-wars-guide/main.py`` 自带；应当 90%+ 胜
- L2 ``may18_launch_safety``：公开 1039 → 现已沉到 800 左右；应当 70%+ 胜
- L3 ``public_heuristic_1110``：4868 行公开版（vickimar 派）；争取 55%+ 胜
- L4 ``lb_1200_baseline``：公开最强（pilkwang 派）；争取 50%+ 胜

每个对手都是独立的 ``agent(obs, config=None)`` 入口，可作为 Kaggle env.run 的参数。
"""
