# src/ — 主代码

各文件与模块编号的对应见 [`../master-plan.md`](../master-plan.md) §2.1。

## 一图速查

```
src/
├── agent.py         入口（Kaggle 调用）
├── env/
│   ├── physics.py   M1 物理常量 + fleet_speed
│   ├── geometry.py  M2 几何 + 拦截求解（sun-aware/swept-collision）
│   ├── world.py     M3 World：obs → 时间线 + arrival ledger + commitment
│   └── safety.py    M4 sun-doomed / planet-doomed / swept-by-other
└── policy/
    ├── modes.py     M8 模式与阶段检测
    ├── missions/    M5 各 mission 生成器（每文件一种）
    ├── scoring.py   M6 评分公式 + ScoringParams（M10 的调参目标）
    ├── value_gbc.py M7 GBC 价值函数 tie-break
    └── plan.py      M9 Plan Orchestrator（合并 + 调度）
```

## 当前状态（v0）

所有模块为 placeholder（接口签名 + docstring + NotImplementedError）。
`agent.py` 在底层模块 raise 时 fallback 到空列表，可正常 import。

下一步（D2 起）：
- 由 Code Lead 把 `community-examples/lb-1200-orbit-wars-ppo-strategy.ipynb` 中的
  3231 行实现拆分到对应模块文件，保留 `plan_moves` 作为可跑 baseline。
- 由 Task agent 按 master-plan §4.2 的 T0–T1 任务清单逐项填充。
