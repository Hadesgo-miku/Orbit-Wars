# Orbit Wars 工作指引（给后续 agent）

## 当前任务定义（必须对齐）
在 Kaggle `orbit-wars` 竞赛中，目标不是“做一个能跑的 agent”，而是：
1. 稳定提升 leaderboard 对战强度（2p/4p 混合环境下的真实胜率表现）；
2. 建立可复现实验闭环（本地评测 -> 提交 -> episode/replay 回收 -> 迭代）；
3. 优先吸收社区中可直接转化为工程能力的数据/工具/方法，而非泛泛经验。

## 必读文件（最小集合）
1. `orbit-wars-overview.md`
   - 竞赛规则、评分机制、回合顺序、物理与战斗规则。
2. `orbit-wars-guide/README.md`
   - 环境机制细节与 observation/action 规范。
3. `orbit-wars-guide/agents.md`
   - 本地测试、提交、拉取 episodes/replay/logs 的标准流程。

## 社区资料策略
- 社区资料不属于每个 agent 的默认必读内容。
- 仅在需要做数据建设、评测体系、可视化或性能优化时再按需读取。
- 具体清单与用途见：`community-discussions/high-priority-assets.md`。




