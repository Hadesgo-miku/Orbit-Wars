"""决策层（M5–M9）。

按 master-plan.md §1 的流水线顺序：

- modes        模式与阶段检测（2P/4P × opening/pressure/finishing/very-late）
- missions/*   各类 mission 生成器（reinforce / rescue / recapture / capture / snipe / crash_exploit）
- scoring      Mission 评分（PV(γ) + danger map + launch-safety + mission-mult）
- value_gbc    GBC 价值函数 tie-break（离线训出的 trees）
- plan         Plan Orchestrator（合并所有 mission，按 deadline 调度）
"""
