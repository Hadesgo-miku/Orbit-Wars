# Orbit Wars 社区高优先资产清单（按需阅读）

> 说明：本文件用于集中管理社区资产，不作为每个 agent 的默认必读。

## 1) 官方日更 replay 索引（原始 JSON）
- 来源：`daily-episode-datasets-pinned.md`
- 链接：`https://www.kaggle.com/datasets/kaggle/orbit-wars-episodes-index`
- 主要用途：
  - 持续拉取高质量官方 replay（按天更新）
  - 做长期训练语料池与对手行为跟踪
  - 作为“权威上游数据源”

## 2) 社区 Parquet 化 replay 方案
- 来源：`replay-dataset-parquet-3000-games-ready-to-analyze.md`
- 关键点：
  - 提供现成 Parquet 数据集（更快查询）
  - 提供从 JSON 构建 Parquet 的可复现 notebook（可自建管线）
- 主要用途：
  - 快速 EDA、策略诊断、行为统计
  - 大规模离线特征工程
  - 训练数据组织（state/action 表结构化）

## 3) 分层 seed 评测面板（128 seeds / 32 archetypes）
- 来源：`seed-panel-preview-128-seeds-32-game-shape-archetypes.md`
- 链接：`https://www.kaggle.com/datasets/chrisleitescha/orbit-wars-seed-panel-preview`
- 主要用途：
  - 本地 A/B 回归测试
  - 识别“总体胜率提升但某类地图退化”的结构性问题
  - 固定评测基准，减少随机波动

## 4) 开发工具链仓库（可视化 + 赛事批跑）
- 来源：`tooling-visualizer-cinema-mode-tournament-runner.md`
- 链接：`https://github.com/MatthewWHuang/orbit-wars`
- 主要用途：
  - 单局可视化诊断（轨迹、关键事件）
  - 多种子并行对战统计
  - submission 打包与局部性能优化

## 5) 规则/实现变更提醒（sweep 逻辑）
- 来源：`sweep-logic-visualizer-updates-pinned.md`
- 主要用途：
  - 检查本地模拟与线上环境版本一致性
  - 防止“本地有效、线上失效”的评测偏差
